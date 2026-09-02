-- Kilimo Hakika / DepotReady - pack compilation, publish guards, audit log, RLS.

-- ---------------------------------------------------------------------------
-- Compile: normalized authoring tables -> one self-contained pack payload
--
-- The output of this function is the ONLY thing the engine ever sees. It is
-- also what database/scheme_rules.json holds, so the engine can boot and be
-- unit-tested with no database at all.
-- ---------------------------------------------------------------------------

create or replace function kh.compile_pack(p_scheme_code text, p_season_code text)
returns jsonb
language sql
stable
as $$
with season as (
  select s.*
  from kh.scheme_season s
  where s.scheme_code = p_scheme_code
    and s.code = p_season_code
),
used_citations as (
  select distinct c.*
  from kh.citation c
  where c.id in (
    select citation_id from season
    union select citation_id from kh.allocation_rule where season_id = (select id from season)
    union select citation_id from kh.price          where season_id = (select id from season)
    union select citation_id from kh.rule           where season_id = (select id from season)
    union select citation_id from kh.depot          where is_active
    union select citation_id from kh.depot_hours
    union select citation_id from kh.depot_closure  where closed_on >= current_date - 30
  )
)
select jsonb_build_object(
  'engine_contract', '1.0',
  'scheme', (
    select jsonb_build_object('code', sc.code, 'name', sc.name, 'administering_body', sc.administering_body)
    from kh.scheme sc where sc.code = p_scheme_code
  ),
  'season', (
    select jsonb_build_object(
      'code', se.code,
      'label', jsonb_build_object('en', se.label_en, 'sw', se.label_sw),
      'effective_from', se.effective_from,
      'effective_to', se.effective_to,
      'citation', se.citation_id
    ) from season se
  ),
  'counties', coalesce((
    select jsonb_agg(jsonb_build_object('code', c.code, 'name', c.name) order by c.name)
    from kh.county c
  ), '[]'::jsonb),
  'depots', coalesce((
    select jsonb_agg(
      jsonb_build_object(
        'code', d.code,
        'name', d.name,
        'county', d.county_code,
        'operator', d.operator,
        'kind', d.kind,
        'citation', d.citation_id,
        'hours', coalesce((
          select jsonb_object_agg(h.weekday::text,
                   jsonb_build_object('opens', to_char(h.opens_at,'HH24:MI'),
                                      'closes', to_char(h.closes_at,'HH24:MI')))
          from kh.depot_hours h where h.depot_code = d.code
        ), '{}'::jsonb),
        'closures', coalesce((
          select jsonb_agg(jsonb_build_object(
                   'date', cl.closed_on,
                   'reason', jsonb_build_object('en', cl.reason_en, 'sw', cl.reason_sw),
                   'citation', cl.citation_id) order by cl.closed_on)
          from kh.depot_closure cl
          where cl.depot_code = d.code and cl.closed_on >= current_date - 30
        ), '[]'::jsonb)
      ) order by d.name)
    from kh.depot d where d.is_active
  ), '[]'::jsonb),
  'documents', coalesce((
    select jsonb_agg(
      jsonb_build_object(
        'code', dc.code,
        'label', jsonb_build_object('en', dc.label_en, 'sw', dc.label_sw),
        'issuer', dc.issuer,
        'how_to_obtain', jsonb_build_object('en', dc.how_to_obtain_en, 'sw', dc.how_to_obtain_sw),
        'is_physical', dc.is_physical
      ) order by dc.sort_order, dc.code)
    from kh.document dc
  ), '[]'::jsonb),
  'fertilizers', coalesce((
    select jsonb_agg(
      jsonb_build_object('code', f.code,
                         'name', jsonb_build_object('en', f.name_en, 'sw', f.name_sw))
      order by f.sort_order, f.code)
    from kh.fertilizer_type f
  ), '[]'::jsonb),
  'allocation', (
    select jsonb_build_object(
      'planting_bags_per_acre', a.planting_bags_per_acre,
      'topdress_bags_per_acre', a.topdress_bags_per_acre,
      'max_total_bags', a.max_total_bags,
      'bag_weight_kg', a.bag_weight_kg,
      'rounding_mode', a.rounding_mode,
      'cap_split', a.cap_split,
      'min_acres', a.min_acres,
      'citation', a.citation_id
    ) from kh.allocation_rule a where a.season_id = (select id from season)
  ),
  'prices', coalesce((
    select jsonb_agg(jsonb_build_object(
             'fertilizer', p.fertilizer_code,
             'purpose', p.purpose,
             'price_kes_per_bag', p.price_kes_per_bag,
             'citation', p.citation_id) order by p.fertilizer_code, p.purpose)
    from kh.price p where p.season_id = (select id from season)
  ), '[]'::jsonb),
  'rules', coalesce((
    select jsonb_agg(jsonb_build_object(
             'code', r.code,
             'kind', r.kind,
             'document', r.document_code,
             'applies_when', r.applies_when,
             'severity', r.severity,
             'message', jsonb_build_object('en', r.message_en, 'sw', r.message_sw),
             'remedy', jsonb_build_object('en', r.remedy_en, 'sw', r.remedy_sw),
             'citation', r.citation_id) order by r.eval_order, r.code)
    from kh.rule r
    where r.season_id = (select id from season) and r.is_enabled
  ), '[]'::jsonb),
  'citations', coalesce((
    select jsonb_object_agg(uc.id, jsonb_build_object(
             'title', uc.title,
             'issuer', uc.issuer,
             'source_type', uc.source_type,
             'reference', uc.reference,
             'url', uc.url,
             'issued_on', uc.issued_on,
             'retrieved_on', uc.retrieved_on,
             'verbatim_extract', uc.verbatim_extract))
    from used_citations uc
  ), '{}'::jsonb)
);
$$;

comment on function kh.compile_pack is 'Builds the immutable pack payload. Pure and stable for a given authoring state.';

-- ---------------------------------------------------------------------------
-- Build and publish
-- ---------------------------------------------------------------------------

create or replace function kh.build_rule_pack(
  p_scheme_code text,
  p_season_code text,
  p_version     text,
  p_built_by    text default null
) returns kh.rule_pack
language plpgsql
as $$
declare
  v_payload jsonb;
  v_row     kh.rule_pack;
begin
  v_payload := kh.compile_pack(p_scheme_code, p_season_code);

  if v_payload -> 'season' is null or v_payload -> 'season' = 'null'::jsonb then
    raise exception 'no season % for scheme %', p_season_code, p_scheme_code;
  end if;
  if v_payload -> 'allocation' is null or v_payload -> 'allocation' = 'null'::jsonb then
    raise exception 'season %/% has no allocation_rule; question 3 would be unanswerable',
      p_scheme_code, p_season_code;
  end if;
  if jsonb_array_length(v_payload -> 'rules') = 0 then
    raise exception 'season %/% has no rules; every input would return PROCEED',
      p_scheme_code, p_season_code;
  end if;

  -- The pack carries its own version, so a payload lifted out of the database
  -- (or read from the bundled fixture) still identifies itself.
  v_payload := jsonb_set(v_payload, '{pack_version}', to_jsonb(p_version), true);

  insert into kh.rule_pack (version, scheme_code, season_code, payload, checksum, built_by)
  values (
    p_version, p_scheme_code, p_season_code, v_payload,
    encode(digest(v_payload::text, 'sha256'), 'hex'),
    coalesce(p_built_by, current_user)
  )
  returning * into v_row;

  return v_row;
end;
$$;

-- Publishing is the gate where citation discipline is mechanically enforced.
create or replace function kh.publish_rule_pack(p_version text)
returns kh.rule_pack
language plpgsql
as $$
declare
  v_row      kh.rule_pack;
  v_unverified text[];
begin
  select * into v_row from kh.rule_pack where version = p_version for update;
  if not found then
    raise exception 'no rule pack %', p_version;
  end if;

  -- A BLOCKER decides whether a farmer spends bus fare. It may not rest on an
  -- unverified source. Advisories may, and are surfaced as such.
  select array_agg(distinct r.value ->> 'code')
    into v_unverified
  from jsonb_array_elements(v_row.payload -> 'rules') r
  where r.value ->> 'severity' = 'BLOCKER'
    and (v_row.payload -> 'citations' -> (r.value ->> 'citation') ->> 'source_type') = 'UNVERIFIED';

  if v_unverified is not null then
    raise exception 'refusing to publish %: BLOCKER rules cite UNVERIFIED sources: %',
      p_version, array_to_string(v_unverified, ', ');
  end if;

  -- Same standard for the statutory numbers. A wrong price defeats the entire
  -- anti-exploitation purpose of showing one.
  select array_agg(distinct p.value ->> 'fertilizer')
    into v_unverified
  from jsonb_array_elements(v_row.payload -> 'prices') p
  where (v_row.payload -> 'citations' -> (p.value ->> 'citation') ->> 'source_type') = 'UNVERIFIED';

  if v_unverified is not null then
    raise exception 'refusing to publish %: prices cite UNVERIFIED sources: %',
      p_version, array_to_string(v_unverified, ', ');
  end if;

  if (v_row.payload -> 'citations'
        -> (v_row.payload -> 'allocation' ->> 'citation') ->> 'source_type') = 'UNVERIFIED' then
    raise exception 'refusing to publish %: allocation rule cites an UNVERIFIED source', p_version;
  end if;

  if (v_row.payload -> 'citations'
        -> (v_row.payload -> 'season' ->> 'citation') ->> 'source_type') = 'UNVERIFIED' then
    raise exception 'refusing to publish %: season window cites an UNVERIFIED source', p_version;
  end if;

  if v_row.checksum <> encode(digest(v_row.payload::text, 'sha256'), 'hex') then
    raise exception 'checksum mismatch on %; payload was tampered with', p_version;
  end if;

  update kh.rule_pack set is_active = false
   where scheme_code = v_row.scheme_code and is_active and version <> p_version;

  update kh.rule_pack
     set published_at = coalesce(published_at, now()), is_active = true
   where version = p_version
  returning * into v_row;

  return v_row;
end;
$$;

-- Immutability: once published, payload/checksum/version are frozen. Only the
-- active flag and notes may move (so a bad pack can be rolled back, never edited).
create or replace function kh.rule_pack_freeze() returns trigger
language plpgsql as $$
begin
  if old.published_at is not null then
    if new.payload::text <> old.payload::text
       or new.checksum <> old.checksum
       or new.version <> old.version
       or new.scheme_code <> old.scheme_code
       or new.season_code <> old.season_code then
      raise exception 'rule pack % is published and immutable; build a new version instead', old.version;
    end if;
  end if;
  return new;
end;
$$;

create trigger rule_pack_freeze_update
  before update on kh.rule_pack
  for each row execute function kh.rule_pack_freeze();

create or replace function kh.rule_pack_no_delete() returns trigger
language plpgsql as $$
begin
  if old.published_at is not null then
    raise exception 'published rule pack % cannot be deleted; verdicts reference it', old.version;
  end if;
  return old;
end;
$$;

create trigger rule_pack_freeze_delete
  before delete on kh.rule_pack
  for each row execute function kh.rule_pack_no_delete();

-- ---------------------------------------------------------------------------
-- Audit log
--
-- Purpose: when a farmer says "the app told me PROCEED and the gate turned me
-- away", we must be able to replay the exact verdict. That needs the inputs and
-- the pack version - and nothing that identifies the farmer.
-- ---------------------------------------------------------------------------

create table kh.triage_log (
  id                uuid primary key default gen_random_uuid(),
  requested_at      timestamptz not null default now(),
  rule_pack_version text        not null references kh.rule_pack(version),
  engine_version    text        not null,
  input             jsonb       not null,   -- acreage, depot, tenure, doc codes, travel date
  input_hash        text        not null,   -- sha256 of canonical input, for dedupe/replay
  verdict           text        not null check (verdict in ('PROCEED','DO_NOT_TRAVEL')),
  reason_kind       text        not null,
  blocker_codes     text[]      not null default '{}',
  total_bags        integer,
  min_total_cost_kes numeric(12,2),
  latency_ms        integer,
  client_kind       text
);

create index triage_log_requested_at_idx on kh.triage_log using brin (requested_at);
create index triage_log_verdict_idx      on kh.triage_log (verdict, requested_at desc);
create index triage_log_blockers_idx     on kh.triage_log using gin (blocker_codes);

comment on table kh.triage_log is 'Insert-only. No national ID, no name, no phone number, no IP. Data minimisation under the Kenya Data Protection Act 2019; retention 90 days (see kh.prune_triage_log).';

create or replace function kh.prune_triage_log(p_keep_days integer default 90)
returns integer language sql as $$
  with gone as (
    delete from kh.triage_log
     where requested_at < now() - make_interval(days => p_keep_days)
    returning 1
  ) select count(*)::integer from gone;
$$;

-- ---------------------------------------------------------------------------
-- RLS and grants (defence in depth on top of an unexposed schema)
-- ---------------------------------------------------------------------------

do $$
declare t text;
begin
  foreach t in array array[
    'citation','county','depot','depot_hours','depot_closure','document',
    'scheme','scheme_season','allocation_rule','fertilizer_type','price',
    'rule','rule_pack','triage_log'
  ] loop
    execute format('alter table kh.%I enable row level security', t);
    execute format('alter table kh.%I force row level security', t);
  end loop;
end;
$$;

-- No policies are created: with RLS on and no policy, every non-owner role is
-- denied. The backend connects as a role that bypasses RLS (service_role /
-- table owner); browsers reach none of this.
revoke all on schema kh from anon, authenticated;
revoke all on all tables in schema kh from anon, authenticated;
revoke all on all functions in schema kh from anon, authenticated;
alter default privileges in schema kh revoke all on tables from anon, authenticated;
