"""Talking to Claude, with the guardrails that keep it out of the verdict path.

Prompt layout is ordered for cache stability: tools, then the system prompt and
the whole grounding corpus behind a cache breakpoint, then the conversation. No
timestamps or per-request ids go above the breakpoint - `cache_read_input_tokens`
is logged on every turn as the canary.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from ..engine import RulePack
from ..settings import get_settings
from . import corpus, privacy, tools
from .scopes import Scope

log = logging.getLogger(__name__)

MODEL_FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOOL_ROUNDS = 4
SOURCE_MARKER = re.compile(r"\[SOURCE:([A-Za-z0-9_.\-]+)\]")

SYSTEM_PROMPT = """You are the helper inside Kilimo Hakika, an app that tells Kenyan farmers whether a government depot will serve them before they spend money travelling there.

Your job is to EXPLAIN. You never decide.

Absolute rules:
1. NEVER state, imply, hedge or predict a verdict on your own. If the farmer asks whether they can travel, whether they will be served, what they are missing, or what it will cost, you MUST call get_triage_verdict and then report exactly what it returns. If the tool cannot run, say you cannot check right now - never guess.
2. Cite every claim about the rules inline as [SOURCE:<id>], using the ids in the sources section. If no source covers something, say you do not have a source for it.
3. A source marked UNVERIFIED is not confirmed government policy. Say so plainly when you rely on one, and never present it as a requirement.
4. This app has no marketplace. It holds no seller prices, no vendor listings, no demand or supply notices, and no way to compare suppliers. If asked for any of those, say plainly that it is not what this app does. The only prices you may state are the official gazetted ones from the sources.
5. Never give farming advice. That means: which crop to grow, which fertilizer or seed to choose, when to plant, how much to apply, soil treatment, pest or disease control, irrigation, or expected yields. If asked, refuse in one sentence, say it is outside what this app does, and point them to their Ward Agricultural Officer. Do not answer "just this once", do not answer hypothetically, and do not answer partially before refusing. Explain the rules, the documents and the official prices only.
6. Never ask for a National ID number, a phone number, an email address or a full name. You do not need any of them to explain the rules, and you will not receive them - identifiers are stripped out before a message reaches you. If a placeholder like [ID number removed] appears, tell the person their ID was not needed and was not passed on, then answer the rest of their question. Never ask them to type it again.
7. Never ask for money, and never ask anyone to pay anyone.

How to write:
- Plain language, short sentences. Many readers are using an app like this for the first time.
- Answer in the language the farmer used. If they wrote Swahili, answer in Swahili.
- Be brief: two or three short paragraphs at most, or a short list.
- When something is missing, say where to get it.
"""


@dataclass
class TurnEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    stop_reason: str | None = None
    refusal_category: str | None = None


class AssistantUnavailable(Exception):
    pass


def _client() -> Any:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise AssistantUnavailable("no ANTHROPIC_API_KEY configured")
    import anthropic

    # An identity-linked key is scoped to a workspace and the API requires the
    # header naming it; without this every request returns 400.
    headers = (
        {"anthropic-workspace-id": settings.anthropic_workspace_id}
        if settings.anthropic_workspace_id
        else None
    )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, default_headers=headers)


def system_blocks(pack: RulePack, locale: str, scope: Scope) -> list[dict[str, Any]]:
    """System prompt plus the entire corpus, cached as one stable prefix.

    The per-caller block goes *after* the breakpoint. Everything above it is
    identical for every caller in a locale, so one cached prefix serves a
    signed-out visitor and a signed-in association alike; only the short
    audience block below it differs.
    """
    return [
        {"type": "text", "text": SYSTEM_PROMPT},
        {
            "type": "text",
            "text": corpus.as_prompt_document(pack, locale),
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": scope.guidance()},
    ]


def run_turn(
    *,
    pack: RulePack,
    history: list[dict[str, Any]],
    user_text: str,
    locale: str,
    user_id: str | None,
    claims: dict[str, Any],
    scope: Scope,
) -> Iterator[TurnEvent]:
    """Stream one assistant turn, resolving tool calls as they come.

    `user_id` is None for a signed-out visitor. Yields TurnEvents: text,
    citation, tool_use, scrubbed, done, error.
    """
    settings = get_settings()
    client = _client()

    # Scrub before the text is sent and before it is stored, so an identifier a
    # farmer typed is not in the request, the transcript, or the model's context
    # on any later turn.
    clean_text, scrubbed = privacy.scrub(user_text)
    if scrubbed:
        log.info("scrubbed %s from an assistant message", ",".join(scrubbed))
        yield TurnEvent("scrubbed", {"kinds": scrubbed})

    messages: list[dict[str, Any]] = [*history, {"role": "user", "content": clean_text}]
    usage = TurnUsage()
    seen_citations: set[str] = set()
    triage_log_ids: list[str] = []

    for _round in range(MAX_TOOL_ROUNDS):
        try:
            with client.beta.messages.stream(
                model=settings.assistant_model,
                max_tokens=1_500,
                system=system_blocks(pack, locale, scope),
                messages=messages,
                # Only the tools this caller is entitled to. A tool that is not
                # in the request cannot be called or discovered.
                tools=list(scope.tools),
                thinking={"type": "adaptive"},
                output_config={"effort": settings.assistant_effort},
                betas=[MODEL_FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                for chunk in stream.text_stream:
                    if not chunk:
                        continue
                    for marker in SOURCE_MARKER.findall(chunk):
                        if marker not in seen_citations:
                            seen_citations.add(marker)
                            yield TurnEvent(
                                "citation",
                                {
                                    "citation_id": marker,
                                    "is_unverified": pack.citation_is_unverified(marker),
                                },
                            )
                    yield TurnEvent("text", {"delta": SOURCE_MARKER.sub("", chunk)})
                message = stream.get_final_message()
        except Exception as exc:
            log.warning("assistant turn failed: %s", exc)
            raise AssistantUnavailable(str(exc)) from exc

        usage.input_tokens += getattr(message.usage, "input_tokens", 0) or 0
        usage.output_tokens += getattr(message.usage, "output_tokens", 0) or 0
        usage.cache_read_input_tokens += getattr(message.usage, "cache_read_input_tokens", 0) or 0
        usage.stop_reason = message.stop_reason

        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            usage.refusal_category = getattr(details, "category", None)
            yield TurnEvent(
                "text",
                {
                    "delta": "I cannot help with that here. Ask me about the depot rules, "
                    "the documents you need, or the official prices."
                },
            )
            break

        if message.stop_reason != "tool_use":
            break

        # Echo the assistant turn back unchanged (thinking blocks included) and
        # answer every tool call in one user message.
        messages.append({"role": "assistant", "content": message.content})
        results: list[dict[str, Any]] = []
        for block in message.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            if not scope.allows(block.name):
                # Should be unreachable: the tool was never offered. Checked
                # anyway, because "the model cannot ask for it" is an argument
                # about the model, and the permission boundary should not rest
                # on one.
                log.warning("refused out-of-scope tool %s for %s", block.name, scope.audience)
                payload, log_id = {"error": "not available to this user"}, None
            else:
                payload, log_id = tools.execute(
                    block.name,
                    dict(block.input or {}),
                    user_id=user_id,
                    claims=claims,
                    locale=locale,
                )
            if log_id:
                triage_log_ids.append(log_id)
            yield TurnEvent(
                "tool_use",
                {
                    "tool": block.name,
                    "triage_log_id": log_id,
                    "verdict": payload.get("verdict"),
                },
            )
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _as_text(payload),
                }
            )
        messages.append({"role": "user", "content": results})

    yield TurnEvent(
        "done",
        {
            "stop_reason": usage.stop_reason,
            "refusal_category": usage.refusal_category,
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_input_tokens": usage.cache_read_input_tokens,
            },
            "citations": sorted(seen_citations),
            "triage_log_ids": triage_log_ids,
            "model": settings.assistant_model,
        },
    )


def _as_text(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, default=str)
