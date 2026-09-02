-- Kilimo Hakika / DepotReady - policy data layer, core schema.
--
-- Design contract (see docs/design/backend-database.md):
--   * These tables are the AUTHORING system of record for policy.
--   * The triage engine NEVER reads these tables at request time. It reads a
--     compiled, immutable snapshot from kh.rule_pack. Determinism depends on it.
--   * Every rule carries a NOT NULL citation. A rule without a citation is not
--     a rule - that is enforced here by foreign keys, not by convention.
--
-- Target: Postgres 15+ (Supabase). Everything lives in schema `kh`, which is
-- deliberately NOT in Supabase's exposed-schema list, so PostgREST will not
-- serve policy data straight to browsers.

create extension if not exists "btree_gist";
create extension if not exists "pgcrypto";

create schema if not exists kh;
comment on schema kh is 'Kilimo Hakika policy data. Not exposed via PostgREST.';

-- ---------------------------------------------------------------------------
-- Provenance
-- ---------------------------------------------------------------------------

create table kh.citation (
  id                text primary key,
  title             text        not null,
  issuer            text        not null,
  source_type       text        not null
    check (source_type in ('GAZETTE','CIRCULAR','AGENCY_FAQ','AGENCY_PUBLICATION','PRESS','UNVERIFIED')),
  reference         text,                 -- e.g. 'Gazette Notice No. 1234 of 2025'
  url               text,
  issued_on         date,
  retrieved_on      date        not null default current_date,
  verbatim_extract  text,                 -- the wording the rule is derived from
  notes             text,
  created_at        timestamptz not null default now()
);

comment on table  kh.citation is 'Official sources. UNVERIFIED marks a rule we believe is real but have not traced to a published source; publishing a pack containing one is blocked (see kh.publish_rule_pack).';
comment on column kh.citation.verbatim_extract is 'Quote the source wording. If you cannot quote it, you cannot cite it.';

-- ---------------------------------------------------------------------------
-- Reference geography and depots
-- ---------------------------------------------------------------------------

create table kh.county (
  code  text primary key,
  name  text not null unique
);

create table kh.depot (
  code         text primary key,          -- e.g. 'NCPB-NAKURU'
  name         text not null,
  county_code  text not null references kh.county(code),
  operator     text not null default 'NCPB',
  kind         text not null default 'DEPOT' check (kind in ('DEPOT','SILO_COMPLEX','PARTNER_OUTLET')),
  is_active    boolean not null default true,
  citation_id  text not null references kh.citation(id),
  notes        text
);

create index depot_county_idx on kh.depot(county_code) where is_active;

-- Opening hours are policy, not code: "will I be served?" is false on a Sunday.
create table kh.depot_hours (
  depot_code  text not null references kh.depot(code) on delete cascade,
  weekday     smallint not null check (weekday between 1 and 7),  -- ISO: 1 = Monday
  opens_at    time not null,
  closes_at   time not null,
  citation_id text not null references kh.citation(id),
  primary key (depot_code, weekday),
  check (closes_at > opens_at)
);

-- Public holidays, stock-outs, maintenance. A dated override beats weekly hours.
create table kh.depot_closure (
  depot_code  text not null references kh.depot(code) on delete cascade,
  closed_on   date not null,
  reason_en   text not null,
  reason_sw   text,
  citation_id text not null references kh.citation(id),
  primary key (depot_code, closed_on)
);

-- ---------------------------------------------------------------------------
-- Documents: the physical artifacts a farmer must be holding
-- ---------------------------------------------------------------------------

create table kh.document (
  code              text primary key,     -- 'NATIONAL_ID_ORIGINAL', 'EVOUCHER_CODE', ...
  label_en          text not null,
  label_sw          text not null,
  issuer            text,
  how_to_obtain_en  text,
  how_to_obtain_sw  text,
  is_physical       boolean not null default true,
  sort_order        smallint not null default 100
);

comment on column kh.document.is_physical is 'True for artifacts carried to the gate. False for states (e.g. being on the register), which are still gate conditions but cannot be brought.';

-- ---------------------------------------------------------------------------
-- Schemes and seasons - policy is effective-dated, always
-- ---------------------------------------------------------------------------

create table kh.scheme (
  code                text primary key,   -- 'NFSP'
  name                text not null,
  administering_body  text not null
);

create table kh.scheme_season (
  id              uuid primary key default gen_random_uuid(),
  scheme_code     text not null references kh.scheme(code),
  code            text not null,          -- '2025_LONG_RAINS'
  label_en        text not null,
  label_sw        text not null,
  effective_from  date not null,
  effective_to    date not null,
  citation_id     text not null references kh.citation(id),
  unique (scheme_code, code),
  check (effective_to >= effective_from),
  -- One scheme cannot have two overlapping seasons: a date must resolve to
  -- exactly one rule set, or the verdict is not deterministic.
  exclude using gist (
    scheme_code with =,
    daterange(effective_from, effective_to, '[]') with &&
  )
);

-- ---------------------------------------------------------------------------
-- Question 3: allocation cap and official cost
-- ---------------------------------------------------------------------------

create table kh.allocation_rule (
  season_id                 uuid primary key references kh.scheme_season(id) on delete cascade,
  planting_bags_per_acre    numeric(6,3) not null check (planting_bags_per_acre >= 0),
  topdress_bags_per_acre    numeric(6,3) not null check (topdress_bags_per_acre >= 0),
  max_total_bags            integer      not null check (max_total_bags > 0),
  bag_weight_kg             numeric(6,2) not null default 50,
  rounding_mode             text         not null default 'FLOOR'
    check (rounding_mode in ('FLOOR','CEIL','NEAREST')),
  cap_split                 text         not null default 'PRO_RATA'
    check (cap_split in ('PRO_RATA','PLANTING_FIRST','TOPDRESS_FIRST')),
  min_acres                 numeric(8,3) not null default 0.25,
  citation_id               text         not null references kh.citation(id)
);

comment on column kh.allocation_rule.rounding_mode is 'How to resolve fractional bags from fractional acreage. An interpretation, not gazetted - keep it in data so it can be corrected without a code change.';
comment on column kh.allocation_rule.cap_split is 'How to divide max_total_bags between planting and top-dressing once the cap binds.';

create table kh.fertilizer_type (
  code        text primary key,           -- 'DAP', 'CAN', 'UREA', 'NPK', 'MOP', 'SA'
  name_en     text not null,
  name_sw     text not null,
  sort_order  smallint not null default 100
);

create table kh.price (
  season_id           uuid not null references kh.scheme_season(id) on delete cascade,
  fertilizer_code     text not null references kh.fertilizer_type(code),
  purpose             text not null check (purpose in ('PLANTING','TOPDRESS','ANY')),
  price_kes_per_bag   numeric(10,2) not null check (price_kes_per_bag > 0),
  citation_id         text not null references kh.citation(id),
  primary key (season_id, fertilizer_code, purpose)
);

comment on table kh.price is 'Gazetted selling price per bag. This is the number a farmer is shown so an official cannot overcharge them. It is never an estimate and never a market rate.';

-- ---------------------------------------------------------------------------
-- Questions 1 and 2: the gate rules
-- ---------------------------------------------------------------------------

create table kh.rule (
  id            uuid primary key default gen_random_uuid(),
  season_id     uuid not null references kh.scheme_season(id) on delete cascade,
  code          text not null,            -- 'DOC_NATIONAL_ID_ORIGINAL', 'DEPOT_OPEN', ...
  kind          text not null check (kind in ('DOCUMENT','ELIGIBILITY','TEMPORAL','LOGISTICS')),
  document_code text references kh.document(code),
  applies_when  jsonb,                    -- predicate DSL; NULL = always applies
  severity      text not null check (severity in ('BLOCKER','ADVISORY')),
  message_en    text not null,
  message_sw    text not null,
  remedy_en     text,
  remedy_sw     text,
  citation_id   text not null references kh.citation(id),
  eval_order    smallint not null default 100,
  is_enabled    boolean not null default true,
  unique (season_id, code),
  -- A DOCUMENT rule is meaningless without the artifact it demands.
  check ((kind = 'DOCUMENT') = (document_code is not null))
);

comment on column kh.rule.applies_when is 'Closed predicate DSL over the triage input vocabulary. See docs/design/backend-database.md. No expressions, no code, no eval.';
comment on column kh.rule.severity is 'BLOCKER => DO_NOT_TRAVEL. ADVISORY => shown but does not change the verdict.';

-- ---------------------------------------------------------------------------
-- The compiled, immutable snapshot the engine actually consumes
-- ---------------------------------------------------------------------------

create table kh.rule_pack (
  version       text primary key,          -- 'NFSP-2025_LONG_RAINS-0001'
  scheme_code   text not null references kh.scheme(code),
  season_code   text not null,
  payload       jsonb not null,
  checksum      text  not null,            -- sha256 of the canonical payload
  built_at      timestamptz not null default now(),
  built_by      text,
  published_at  timestamptz,
  is_active     boolean not null default false,
  notes         text
);

-- Exactly one active pack per scheme. The engine resolves a season inside the
-- pack; it never has to choose between packs.
create unique index rule_pack_one_active_per_scheme
  on kh.rule_pack(scheme_code) where is_active;

comment on table kh.rule_pack is 'Immutable once published. A verdict is a pure function of (triage input, rule_pack.version) - so a pack must never change under a version.';
