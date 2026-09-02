"""The assistant's grounding corpus.

Derived, never authored: rebuilt from the loaded rule pack every time the pack
changes, so the assistant can only ever explain policy that is actually in
force, and every statutory claim it makes carries a citation id.

The whole corpus is a few dozen short statements, which is why it goes into the
prompt wholesale behind a cache breakpoint. Full-text search exists for the day
that stops being true (and to let the tools answer narrow lookups cheaply).
"""

from __future__ import annotations

import logging
from typing import Any

from ..engine import RulePack
from ..engine.pack import _text
from ..persistence import db

log = logging.getLogger(__name__)


def build_chunks(pack: RulePack) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []

    for citation_id, record in pack.citations.items():
        extract = record.get("verbatim_extract")
        if not extract:
            continue
        chunks.append(
            {
                "source_kind": "CITATION",
                "source_ref": citation_id,
                "locale": "en",
                "title": record.get("title") or citation_id,
                "content": f"{record.get('issuer', '')}: {extract}".strip(": "),
                "citation_id": citation_id,
            }
        )

    for doc in pack.documents.values():
        for locale in ("en", "sw"):
            label = _text(doc.label, locale)
            how = _text(doc.how_to_obtain, locale)
            if not label:
                continue
            chunks.append(
                {
                    "source_kind": "DOCUMENT_HOWTO",
                    "source_ref": doc.code,
                    "locale": locale,
                    "title": label,
                    "content": how or label,
                    "citation_id": None,
                }
            )

    for rule in pack.rules:
        for locale in ("en", "sw"):
            message = _text(rule.message, locale)
            if not message:
                continue
            remedy = _text(rule.remedy, locale)
            chunks.append(
                {
                    "source_kind": "RULE_MESSAGE",
                    "source_ref": rule.code,
                    "locale": locale,
                    "title": rule.code,
                    "content": f"{message} {remedy or ''}".strip(),
                    "citation_id": rule.citation,
                }
            )

    return chunks


def rebuild(pack: RulePack) -> int:
    chunks = build_chunks(pack)
    try:
        with db.admin_connection() as conn, conn.cursor() as cur:
            for chunk in chunks:
                cur.execute(
                    """
                    insert into ai.knowledge_chunk
                        (source_kind, source_ref, locale, title, content, citation_id)
                    values (%(source_kind)s, %(source_ref)s, %(locale)s, %(title)s,
                            %(content)s, %(citation_id)s)
                    on conflict (source_kind, source_ref, locale) do update set
                        title = excluded.title,
                        content = excluded.content,
                        citation_id = excluded.citation_id,
                        updated_at = now()
                    """,
                    chunk,
                )
    except Exception as exc:
        log.warning("could not rebuild the assistant corpus: %s", exc)
        return 0
    log.info("assistant corpus rebuilt: %d chunks", len(chunks))
    return len(chunks)


def search(query: str, locale: str = "en", limit: int = 6) -> list[dict[str, Any]]:
    """Keyword search over the corpus.

    The text-search config is a literal per locale so it matches the partial
    expression indexes exactly (Postgres has no Swahili dictionary, so Swahili
    rows index unstemmed under 'simple').
    """
    config = "english" if locale == "en" else "simple"
    try:
        with db.admin_connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select source_kind, source_ref, title, content, citation_id,
                       ts_rank_cd(to_tsvector('{config}', title || ' ' || content),
                               websearch_to_tsquery('{config}', %s)) as rank
                  from ai.knowledge_chunk
                 where locale = %s
                   and to_tsvector('{config}', title || ' ' || content)
                       @@ websearch_to_tsquery('{config}', %s)
                 order by rank desc
                 limit %s
                """,
                (query, locale, query, limit),
            )
            return cur.fetchall()
    except Exception as exc:
        log.warning("corpus search failed: %s", exc)
        return []


def as_prompt_document(pack: RulePack, locale: str) -> str:
    """The whole corpus as one cacheable block, each entry tagged with its id.

    Tagging is what makes citation extraction deterministic: the model is told to
    write [SOURCE:<id>] inline, and the backend maps those markers back to
    citation records rather than trusting prose.
    """
    lines: list[str] = ["# Official sources and rules currently in force", ""]
    lines.append(
        f"Scheme: {pack.scheme_name} ({pack.scheme_code}). "
        f"Season {pack.season.code}, effective {pack.season.effective_from} to {pack.season.effective_to}."
    )
    lines.append("")

    lines.append("## Cited sources")
    for citation_id, record in sorted(pack.citations.items()):
        extract = record.get("verbatim_extract")
        status = "UNVERIFIED" if pack.citation_is_unverified(citation_id) else "verified"
        lines.append(
            f"- [SOURCE:{citation_id}] ({status}, {record.get('issuer', 'unknown issuer')}) "
            f"{record.get('title', '')}"
            + (f' — quote: "{extract}"' if extract else " — no verbatim quote on file")
        )

    lines.append("")
    lines.append("## Gate rules")
    for rule in pack.rules:
        message = _text(rule.message, locale) or ""
        remedy = _text(rule.remedy, locale) or ""
        applies = "always" if rule.applies_when is None else f"when {rule.applies_when}"
        lines.append(
            f"- {rule.code} ({rule.severity}, applies {applies}) [SOURCE:{rule.citation}]: "
            f"{message} {remedy}".rstrip()
        )

    lines.append("")
    lines.append("## Required artifacts")
    for doc in pack.documents.values():
        label = _text(doc.label, locale) or doc.code
        how = _text(doc.how_to_obtain, locale) or ""
        lines.append(f"- {doc.code}: {label}. How to get it: {how}")

    lines.append("")
    lines.append("## Allocation and official prices")
    alloc = pack.allocation
    lines.append(
        f"- Allocation [SOURCE:{alloc.citation}]: {alloc.planting_bags_per_acre} bags planting and "
        f"{alloc.topdress_bags_per_acre} bags top dressing per acre, "
        f"capped at {alloc.max_total_bags} bags per season, "
        f"{alloc.bag_weight_kg}kg per bag, fractional acreage rounded {alloc.rounding_mode}."
    )
    for price in pack.prices:
        flag = " (UNVERIFIED SOURCE)" if pack.citation_is_unverified(price.citation) else ""
        lines.append(
            f"- Official price [SOURCE:{price.citation}]: {price.fertilizer_code} "
            f"({price.purpose}) KES {price.price_kes_per_bag} per bag{flag}"
        )

    lines.append("")
    lines.append("## Depots")
    for depot in sorted(pack.depots.values(), key=lambda d: d.name):
        days = ", ".join(str(d) for d in sorted(depot.hours))
        county = pack.counties.get(depot.county_code, depot.county_code)
        lines.append(f"- {depot.code}: {depot.name}, {county} county. Open ISO weekdays {days}.")

    return "\n".join(lines)
