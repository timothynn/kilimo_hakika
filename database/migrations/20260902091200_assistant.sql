-- Kilimo Hakika - assistant module: chatbot, recommendations, grounding corpus.
--
-- INVARIANT 1, enforced structurally: nothing here can produce a verdict. When
-- the assistant needs one it calls the deterministic triage API as a tool and
-- records the resulting kh.triage_log id in ai.tool_invocation, so any answer
-- that mentions a verdict is traceable to the engine that computed it.
--
-- Grounding is Postgres full-text search over a corpus of a few dozen cited
-- statements - small enough to sit inside a cached prompt prefix. No vector
-- store: pgvector earns its place only once the corpus outgrows the cache, and
-- it does not yet.

create schema if not exists ai;
comment on schema ai is 'Assistant conversations, recommendations, and the grounding corpus. Never in the verdict path.';

-- ---------------------------------------------------------------------------
-- Prompts as versioned data
-- ---------------------------------------------------------------------------

create table ai.prompt_version (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,               -- 'assistant.chat', 'recommend.gap_plan'
  version        integer not null,
  model          text not null,               -- 'claude-opus-5'
  effort         text check (effort in ('low','medium','high','xhigh','max')),
  system_prompt  text not null,
  notes          text,
  created_by     uuid references identity.app_user(id),
  created_at     timestamptz not null default now(),
  is_active      boolean not null default false,
  unique (name, version)
);

create unique index prompt_version_one_active on ai.prompt_version (name) where is_active;

comment on table ai.prompt_version is
  'A prompt is configuration, not a string literal in a handler. Every stored answer and recommendation names the prompt version and model that produced it, so a bad answer can be traced to a specific prompt and that prompt rolled back.';

-- ---------------------------------------------------------------------------
-- Grounding corpus
-- ---------------------------------------------------------------------------

create table ai.knowledge_chunk (
  id            uuid primary key default gen_random_uuid(),
  source_kind   text not null
                  check (source_kind in ('CITATION','DOCUMENT_HOWTO','RULE_MESSAGE','PLATFORM_FAQ')),
  source_ref    text not null,                -- citation id, document code, rule code, signal id
  locale        text not null check (locale in ('en','sw')),
  title         text not null,
  content       text not null,
  citation_id   text references kh.citation(id),
  updated_at    timestamptz not null default now(),
  unique (source_kind, source_ref, locale)
);

-- Postgres ships no Swahili dictionary, so Swahili rows index under 'simple'
-- (no stemming, no stop words). Adequate for a keyword hit over a small corpus;
-- revisit if recall disappoints.
--
-- Two partial expression indexes rather than one generated tsvector column:
-- picking the text-search config from the row's `locale` needs a text-to-regconfig
-- cast, which is only STABLE, and a generated column requires an IMMUTABLE
-- expression. With the config as a literal per index, the expression is
-- immutable and the planner still gets an index. Queries must use the matching
-- literal config so the expression matches.
create index knowledge_chunk_fts_en on ai.knowledge_chunk
  using gin (to_tsvector('english', title || ' ' || content))
  where locale = 'en';

create index knowledge_chunk_fts_sw on ai.knowledge_chunk
  using gin (to_tsvector('simple', title || ' ' || content))
  where locale = 'sw';

comment on table ai.knowledge_chunk is
  'Derived, not authored: rebuilt from kh.citation, kh.document and kh.rule whenever a rule pack is published. A chunk whose source is a statutory rule keeps its citation_id so the assistant can always answer "who says so".';

-- ---------------------------------------------------------------------------
-- Conversations
-- ---------------------------------------------------------------------------

create table ai.conversation (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references identity.app_user(id) on delete cascade,
  locale      text not null default 'en' check (locale in ('en','sw')),
  channel     text not null default 'WEB' check (channel in ('WEB','USSD','SMS')),
  status      text not null default 'OPEN' check (status in ('OPEN','CLOSED')),
  started_at  timestamptz not null default now(),
  closed_at   timestamptz
);

create index conversation_user_idx on ai.conversation (user_id, started_at desc);

create table ai.message (
  id                uuid primary key default gen_random_uuid(),
  conversation_id   uuid not null references ai.conversation(id) on delete cascade,
  seq               integer not null,
  role              text not null check (role in ('user','assistant','tool')),
  content           text not null,
  model             text,
  prompt_version_id uuid references ai.prompt_version(id),
  input_tokens      integer,
  output_tokens     integer,
  cache_read_tokens integer,
  stop_reason       text,
  refusal_category  text,
  latency_ms        integer,
  created_at        timestamptz not null default now(),
  unique (conversation_id, seq),
  -- An assistant turn must name the model and prompt that produced it.
  check ((role <> 'assistant') or (model is not null and prompt_version_id is not null))
);

create table ai.tool_invocation (
  id             uuid primary key default gen_random_uuid(),
  message_id     uuid not null references ai.message(id) on delete cascade,
  tool_name      text not null,
  input          jsonb not null,
  output         jsonb,
  ok             boolean not null default true,
  triage_log_id  uuid references kh.triage_log(id),
  latency_ms     integer,
  created_at     timestamptz not null default now(),
  -- If the assistant consulted the engine, the verdict it saw is on the record.
  check ((tool_name <> 'get_triage_verdict') or (triage_log_id is not null or ok = false))
);

comment on table ai.tool_invocation is
  'The seam between the assistant and the deterministic core. The assistant may read a verdict through get_triage_verdict and quote it; it may never compute, adjust or predict one. This table is how that claim stays auditable.';

-- ---------------------------------------------------------------------------
-- Recommendations
-- ---------------------------------------------------------------------------

create table ai.recommendation (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references identity.app_user(id) on delete cascade,
  kind               text not null
                       check (kind in ('GAP_PLAN','TIMING','LEARNING')),
  subject            jsonb not null,           -- the inputs it was based on
  body_en            text not null,
  body_sw            text,
  grounding_refs     text[] not null default '{}',
  model              text not null,
  prompt_version_id  uuid not null references ai.prompt_version(id),
  triage_log_id      uuid references kh.triage_log(id),
  created_at         timestamptz not null default now(),
  accepted           boolean,
  feedback           text
);

create index recommendation_user_idx on ai.recommendation (user_id, created_at desc);

comment on table ai.recommendation is
  'Advice, recorded as advice. Rendered outside the verdict panel and labelled as generated. `grounding_refs` lists the corpus rows it drew on; an empty array on a shipped recommendation is a bug, not a shrug.';

comment on column ai.recommendation.kind is
  'GAP_PLAN: how to close the missing-document list. TIMING: when to travel given depot hours and season dates. LEARNING: explaining a rule or a document. None of these may restate or alter a verdict.';

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table ai.prompt_version   enable row level security;
alter table ai.knowledge_chunk  enable row level security;
alter table ai.conversation     enable row level security;
alter table ai.message          enable row level security;
alter table ai.tool_invocation  enable row level security;
alter table ai.recommendation   enable row level security;

-- Consent gate: no conversation may exist without a live ASSISTANT_AI consent.
-- Withdraw consent and the next insert fails at the database, not at whichever
-- code path remembered to check.
create policy conversation_self on ai.conversation
  for all using (user_id = identity.uid())
  with check (
    user_id = identity.uid()
    and identity.has_permission('assistant.chat')
    and exists (
      select 1 from identity.consent c
      where c.user_id = identity.uid()
        and c.purpose = 'ASSISTANT_AI'
        and c.withdrawn_at is null
    )
  );

create policy message_own_conversation on ai.message
  for all using (
    conversation_id in (select id from ai.conversation where user_id = identity.uid())
  )
  with check (
    conversation_id in (select id from ai.conversation where user_id = identity.uid())
  );

create policy tool_invocation_own on ai.tool_invocation
  for select using (
    message_id in (
      select m.id from ai.message m
      join ai.conversation c on c.id = m.conversation_id
      where c.user_id = identity.uid()
    )
  );

create policy recommendation_self on ai.recommendation
  for select using (user_id = identity.uid());
create policy recommendation_feedback on ai.recommendation
  for update using (user_id = identity.uid())
  with check (user_id = identity.uid());

-- The corpus is public policy text; the prompts that consume it are not.
create policy knowledge_chunk_read on ai.knowledge_chunk for select using (true);
create policy prompt_version_read on ai.prompt_version
  for select using (identity.has_permission('audit.read'));

grant usage on schema ai to authenticated;
grant select on ai.knowledge_chunk to authenticated;
grant select, insert, update on ai.conversation, ai.message to authenticated;
grant select on ai.tool_invocation to authenticated;
grant select, update on ai.recommendation to authenticated;
grant select on ai.prompt_version to authenticated;
