"""The chatbot and recommendations.

Consent is checked before a single token leaves the machine, and the RLS policy
on `ai.conversation` refuses to create one without a live ASSISTANT_AI consent -
so withdrawing consent stops model calls at the database, not just in the UI.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...assistant import client as assistant_client
from ...assistant import privacy, scopes
from ...assistant import tools as assistant_tools
from ...assistant.client import AssistantUnavailable
from ...packs.repository import repository
from ...persistence import db
from ...settings import get_settings
from ..deps import Caller, OptionalCallerDep, require, require_consent
from ..schemas import AssistantMessageRequest

log = logging.getLogger(__name__)
router = APIRouter()

HISTORY_TURNS = 12


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _load_history(claims: dict[str, Any], conversation_id: str) -> list[dict[str, Any]]:
    with db.user_connection(claims) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select role, content from ai.message
             where conversation_id = %s and role in ('user','assistant')
             order by seq desc limit %s
            """,
            (conversation_id, HISTORY_TURNS),
        )
        rows = list(reversed(cur.fetchall()))
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def _ensure_conversation(caller: Caller, conversation_id: str | None, locale: str) -> str:
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        if conversation_id:
            cur.execute(
                "select id::text as id from ai.conversation where id = %s and user_id = %s",
                (conversation_id, caller.user_id),
            )
            row = cur.fetchone()
            if row:
                return row["id"]
        cur.execute(
            """
            insert into ai.conversation (user_id, locale) values (%s, %s)
            returning id::text as id
            """,
            (caller.user_id, locale),
        )
        return cur.fetchone()["id"]


def _next_seq(claims: dict[str, Any], conversation_id: str) -> int:
    with db.user_connection(claims) as conn, conn.cursor() as cur:
        cur.execute(
            "select coalesce(max(seq), 0) + 1 as seq from ai.message where conversation_id = %s",
            (conversation_id,),
        )
        return int(cur.fetchone()["seq"])


def _active_prompt_id(name: str) -> str | None:
    with db.admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id::text as id from ai.prompt_version where name = %s and is_active limit 1",
            (name,),
        )
        row = cur.fetchone()
        return row["id"] if row else None


@router.post("/assistant/messages")
def send_message(
    body: AssistantMessageRequest,
    caller: OptionalCallerDep = None,
) -> StreamingResponse:
    """One assistant turn.

    Open to signed-out visitors, who get the public-policy tier: the two tools
    that read published government policy, and nothing that touches a person.
    See `assistant/scopes.py` for what each tier may reach.

    A signed-in caller needs `assistant.chat` and a live ASSISTANT_AI consent,
    both checked here. A visitor has no account to consent on behalf of and
    nothing personal is read or written for them, so there is nothing to
    consent to - and no transcript is kept.
    """
    if caller is not None:
        if not caller.has("assistant.chat"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "this action needs the assistant.chat permission",
                        "permission": "assistant.chat",
                    }
                },
            )
        require_consent(caller, "ASSISTANT_AI")

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "ASSISTANT_UNAVAILABLE",
                    "message": "the helper is not configured right now",
                }
            },
        )

    loaded = repository.current
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NO_ACTIVE_PACK", "message": "no rules loaded"}},
        )

    scope = scopes.resolve(
        user_id=None if caller is None else caller.user_id,
        roles=None if caller is None else caller.roles,
        permissions=None if caller is None else caller.permissions,
        all_tools=assistant_tools.DEFINITIONS,
    )

    # A visitor has no conversation row, so nothing they type is stored and no
    # history is carried between turns. That is the privacy trade for not making
    # them sign in, and it is why the tier cannot do anything personal anyway.
    conversation_id = (
        None if caller is None else _ensure_conversation(caller, body.conversation_id, body.locale)
    )
    history = (
        [] if caller is None or conversation_id is None else _load_history(caller.claims, conversation_id)
    )
    prompt_id = _active_prompt_id("assistant.chat")

    def stream() -> Any:
        seq = 0 if caller is None or conversation_id is None else _next_seq(caller.claims, conversation_id)
        message_id: str | None = None
        answer: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        scrubbed_kinds: list[str] = []

        if caller is not None and conversation_id is not None:
            # Store the scrubbed text, not what was typed: the transcript must
            # not become the place an identifier ends up at rest either.
            stored_text, scrubbed_kinds = privacy.scrub(body.text)
            try:
                with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into ai.message (conversation_id, seq, role, content)
                        values (%s, %s, 'user', %s) returning id::text as id
                        """,
                        (conversation_id, seq, stored_text),
                    )
                    cur.fetchone()
            except Exception as exc:
                log.warning("could not store the farmer's message: %s", exc)

        yield _sse(
            "message_start",
            {
                "conversation_id": conversation_id,
                "audience": str(scope.audience),
                "signed_in": scope.is_signed_in,
                "capabilities": sorted(tool["name"] for tool in scope.tools),
            },
        )

        try:
            for event in assistant_client.run_turn(
                pack=loaded.pack,
                history=history,
                user_text=body.text,
                locale=body.locale,
                user_id=None if caller is None else caller.user_id,
                claims={} if caller is None else caller.claims,
                scope=scope,
            ):
                if event.type == "text":
                    answer.append(event.data["delta"])
                elif event.type == "tool_use":
                    tool_calls.append(event.data)
                yield _sse(event.type, event.data)
                if event.type == "done" and caller is not None and conversation_id is not None:
                    message_id = _persist_answer(
                        caller,
                        conversation_id,
                        seq + 1,
                        "".join(answer),
                        event.data | {"scrubbed": scrubbed_kinds},
                        prompt_id,
                    )
                    if message_id:
                        _persist_tools(caller, message_id, tool_calls)
        except AssistantUnavailable as exc:
            log.warning("assistant unavailable mid-stream: %s", exc)
            yield _sse(
                "error",
                {
                    "code": "ASSISTANT_UNAVAILABLE",
                    "message": "The helper is unavailable. The depot check still works.",
                },
            )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _persist_answer(
    caller: Caller,
    conversation_id: str,
    seq: int,
    text: str,
    done: dict[str, Any],
    prompt_id: str | None,
) -> str | None:
    if not text.strip():
        return None
    usage = done.get("usage") or {}
    try:
        with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into ai.message (
                    conversation_id, seq, role, content, model, prompt_version_id,
                    input_tokens, output_tokens, cache_read_tokens, stop_reason, refusal_category
                ) values (%s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s, %s)
                returning id::text as id
                """,
                (
                    conversation_id,
                    seq,
                    text,
                    done.get("model"),
                    prompt_id,
                    usage.get("input_tokens"),
                    usage.get("output_tokens"),
                    usage.get("cache_read_input_tokens"),
                    done.get("stop_reason"),
                    done.get("refusal_category"),
                ),
            )
            return cur.fetchone()["id"]
    except Exception as exc:
        log.warning("could not store the assistant's answer: %s", exc)
        return None


def _persist_tools(caller: Caller, message_id: str, calls: list[dict[str, Any]]) -> None:
    if not calls:
        return
    try:
        with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
            for call in calls:
                cur.execute(
                    """
                    insert into ai.tool_invocation (message_id, tool_name, input, output, triage_log_id)
                    values (%s, %s, %s::jsonb, %s::jsonb, %s)
                    """,
                    (
                        message_id,
                        call["tool"],
                        json.dumps({}),
                        json.dumps({"verdict": call.get("verdict")}),
                        call.get("triage_log_id"),
                    ),
                )
    except Exception as exc:
        log.warning("could not store tool invocations: %s", exc)


@router.get("/assistant/conversations/{conversation_id}")
def conversation(
    conversation_id: str, caller: Annotated[Caller, Depends(require("assistant.chat"))]
) -> dict[str, Any]:
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select seq, role, content, created_at
              from ai.message where conversation_id = %s
             order by seq asc
            """,
            (conversation_id,),
        )
        rows = cur.fetchall()
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "seq": row["seq"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ],
    }


@router.get("/assistant/recommendations")
def recommendations(caller: Annotated[Caller, Depends(require("assistant.chat"))]) -> dict[str, Any]:
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id::text as id, kind, body_en, body_sw, grounding_refs, model,
                   created_at, accepted
              from ai.recommendation where user_id = %s
             order by created_at desc limit 20
            """,
            (caller.user_id,),
        )
        rows = cur.fetchall()
    return {
        "items": [
            {
                "id": row["id"],
                "kind": row["kind"],
                "body": row["body_en"],
                "body_sw": row["body_sw"],
                "grounding_refs": row["grounding_refs"],
                "model": row["model"],
                "generated": True,
                "created_at": row["created_at"].isoformat(),
                "accepted": row["accepted"],
            }
            for row in rows
        ]
    }
