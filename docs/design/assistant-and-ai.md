# The assistant: chatbot, recommendations, tracking

Status: proposed, 2 September 2026. Schema:
[`20260902091200_assistant.sql`](../../database/migrations/20260902091200_assistant.sql).

---

## 1. What this is, and the one thing it must never do

The assistant explains. It answers "what is a chief's letter and who says I need
one?", "why can't I collect at Nakuru if I registered in Bungoma?", "what does
the association say about supply next month?", and "I was told to bring an
e-voucher code — how do I get one?"

It does **not** produce a verdict. Ever. When a verdict is relevant it calls the
deterministic triage API as a tool and quotes the result. This is not a prompt
preference; it is the architecture:

- The engine has no model call in it and no network access. There is nowhere for
  a model to interpose.
- The assistant reaches a verdict only through the `get_triage_verdict` tool,
  and every such call writes a `kh.triage_log` id into `ai.tool_invocation`. A
  check constraint requires that id, so an answer that discusses a verdict is
  traceable to the engine run that produced it.
- The system prompt forbids restating, softening, hedging or predicting a
  verdict, and the eval suite tests exactly that (§6).

A farmer betting bus fare gets rules and citations. The model is there to make
those rules legible, not to have an opinion about them.

---

## 2. Grounding: a cached corpus, not a vector store

`ai.knowledge_chunk` is derived — rebuilt from `kh.citation`, `kh.document`,
`kh.rule` and published `market.signal` rows every time a rule pack is
published. Each chunk from a statutory rule keeps its `citation_id`, so "who
says so" is always answerable.

The whole corpus today is on the order of a few dozen statements — roughly 8–10K
tokens. That is small enough to put **all of it** in the prompt, behind a cache
breakpoint, and skip retrieval entirely. A vector store for a corpus this size
would add a dependency, an embedding provider, and a class of silent recall bugs
in exchange for nothing.

**Prompt layout**, ordered for cache stability (render order is `tools` →
`system` → `messages`, and any byte change invalidates everything after it):

1. `tools` — a fixed, deterministically ordered tool list.
2. `system` — the versioned prompt from `ai.prompt_version`, then the full
   grounding corpus as `document` blocks with `citations: {enabled: true}`, then
   a `cache_control` breakpoint.
3. `messages` — conversation history, then the farmer's question.

Nothing volatile goes above the breakpoint: no timestamp, no request id, no
user's name, no "today is …". Those belong in the last user message. If
`usage.cache_read_input_tokens` comes back zero on repeated turns, something has
leaked upward — that metric is the canary and it goes in the logs on every turn.

Citations are enabled on the corpus documents so the model's answer carries
`cited_text` spans pointing back into the source we gave it. That is what lets
the UI show a farmer the exact sentence from the NCPB FAQ underneath the
explanation, rather than a claim.

Postgres full-text search over `ai.knowledge_chunk` stays in the schema for the
case the corpus outgrows the cache — thousands of market signals, or a full
110-depot roster with per-depot notes. `pgvector` is deferred until FTS itself
proves insufficient, which for keyword-shaped policy questions is unlikely.

---

## 3. Model, parameters, cost

| Setting | Value |
|---|---|
| Model | `claude-opus-5` |
| Thinking | `{type: "adaptive"}` — on by default for this model |
| Effort | `output_config: {effort: "low"}` for chat turns, `"medium"` for recommendations |
| Streaming | Yes, for every chat turn |
| Refusal fallbacks | `betas: ["server-side-fallback-2026-07-01"]` with `fallbacks: "default"` |
| Structured output | `output_config.format` for recommendations |

Opus 5 is $5 / $25 per million input / output tokens. With effort `low` and a
cached prefix, a chat turn is roughly 300–800 output tokens plus a cache read of
the corpus — on the order of a couple of US cents per turn, single-digit
Kenyan shillings. Cache reads are billed at a steep discount to fresh input;
confirm the current rate against the pricing page before you build a budget on
it, and log `usage` per turn from day one so the real number replaces this
estimate quickly.

`stop_reason` must be checked before reading content: safety classifiers can
decline a request and return HTTP 200 with `stop_reason: "refusal"`. Server-side
fallbacks are enabled so a refusal routes to another model rather than showing a
farmer an error.

**A cost decision that is yours, not mine.** Haiku 4.5 ($1 / $5) and Sonnet 5
($2 / $10) would cut per-turn cost several-fold on what is mostly extractive
Q&A over a small, well-structured corpus. I have defaulted to Opus 5 and have
not downgraded it for cost, because quality-for-cost on farmer-facing
explanations is a product call. Say the word and it is a one-line change in
`ai.prompt_version`, which is exactly why the model lives in that table.

---

## 4. Tools

Four, all read-only. The assistant has no write tool, so there is no path from a
conversation to a state change.

| Tool | Purpose |
|---|---|
| `get_triage_verdict` | Calls the internal triage engine with the farmer's saved profile plus anything they have told the assistant. Returns the verdict payload verbatim. |
| `search_policy` | FTS over `ai.knowledge_chunk`, returning chunks with citation ids. |
| `get_document_guidance` | One document's label, issuer and how-to-obtain text, in the farmer's language. |
| `get_market_signals` | Published `market.signal` rows for a product and county, each labelled with the publishing organisation. |

Tools are declared with `strict: true` so arguments validate exactly, and the
tool list is ordered deterministically to keep the cache prefix stable.

`get_market_signals` returns supplier-declared data. The system prompt requires
that every such figure is attributed to its organisation by name and never
described as official, gazetted, or a cap — the same invariant the schema
enforces with `price_authority`, restated where the prose is generated.

---

## 5. Recommendations and tracking

**Recommendations** land in `ai.recommendation` as typed rows via structured
outputs, with the model, prompt version and `grounding_refs` recorded. Four kinds:

- `GAP_PLAN` — the order to close the missing-document list in, given what the
  farmer is missing and where each artifact comes from. This is the useful one:
  a farmer holding a red verdict wants a sequence, not a list.
- `TIMING` — when to travel, from depot hours, dated closures and the season
  window.
- `MARKET_CONTEXT` — what verified organisations have published, attributed.
- `LEARNING` — plain-language explanation of a rule or document.

Every recommendation renders **outside** the verdict panel, labelled as
generated. An empty `grounding_refs` array on a shipped recommendation is a bug.

**Tracking** is `identity.triage_history.gap_state`: after a `DO_NOT_TRAVEL` the
farmer gets their missing artifacts as a checklist they tick off, and the next
triage pre-fills from what they have already resolved. The assistant can read
that state to answer "what's left?" and the analytics side aggregates it into the
one genuinely valuable by-product of this system — which missing artifact turns
the most farmers away, by county. That is a number the Ministry does not
currently have.

---

## 6. Evaluation and guardrails

The assistant is the one part of the platform that can be confidently wrong, so
it gets an eval suite before it gets a UI:

1. **Never-a-verdict test.** A corpus of questions phrased to bait a verdict
   ("so can I go tomorrow or not?"). Pass condition: either the answer contains
   no verdict, or a `get_triage_verdict` invocation exists for that turn and the
   answer's verdict matches it exactly.
2. **Grounding test.** Every factual claim about policy must carry a citation
   from the corpus we supplied. Answers with uncited policy claims fail.
3. **Attribution test.** Any market figure in an answer must name its
   organisation and must not appear alongside "official", "gazetted" or "cap".
4. **Refusal-path test.** A refusal must surface as a helpful message plus a
   working fallback, never as a stack trace or a blank screen.
5. **Language test.** A Swahili question gets a Swahili answer, with the same
   citations.
6. **Cache-health check.** `cache_read_input_tokens` above zero on the second
   and later turns of every eval conversation. A regression here is a silent
   cost bug, so it fails the build.

**Degradation.** If the Anthropic API is unreachable, the assistant returns a
plain "the helper is unavailable" and the rest of the platform is untouched —
triage, prices and signals all work without it. The assistant is a convenience
layer over a product that must function when it is absent.

---

## 7. Open questions

1. **SMS and USSD channels** are in the `ai.conversation.channel` enum because a
   feature-phone farmer is the archetypal user, but nothing is designed for them
   yet. USSD would need a session state machine and a 182-character discipline
   that shapes every prompt — a separate design, not a flag.
2. **Who reviews the prompts?** `ai.prompt_version` makes prompts reviewable
   configuration; the review workflow for them is not defined. Policy gets
   author/reviewer/publisher separation. Prompts that explain policy to farmers
   arguably deserve the same, and currently only `audit.read` holders can even
   see them.
3. **Does agronomic advice come next?** The rewritten scope permits it. It is
   also the highest-liability output on the table — a fertilizer-choice
   recommendation that costs a farmer a harvest is a different order of mistake
   than a wrong opening time. If it is wanted, it should be its own
   `ai.recommendation` kind with its own eval set and a named expert reviewing
   the prompt, not an incidental capability of a general chatbot.
