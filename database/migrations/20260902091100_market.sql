-- Kilimo Hakika - market module: supplier-declared prices and demand/supply signals.
--
-- INVARIANT 2, enforced structurally: nothing in this schema may present itself
-- as statutory. Statutory prices live in kh.price with a citation; these carry
-- an author. The `price_authority` column is pinned to a single value by a CHECK
-- constraint so no code path, migration or admin console can promote a supplier
-- quote to "official".
--
-- There is no order, cart, transaction, payment or matching table here, and
-- none may be added: the no-payments boundary still stands. This module informs;
-- it does not trade.

create schema if not exists market;
comment on schema market is 'Commercial prices and demand/supply signals from verified organisations. Never statutory, never transactional.';

-- ---------------------------------------------------------------------------
-- Product catalogue
-- ---------------------------------------------------------------------------

create table market.product (
  code              text primary key,
  name_en           text not null,
  name_sw           text not null,
  category          text not null check (category in ('FERTILIZER','SEED','PRODUCE','OTHER_INPUT')),
  fertilizer_code   text references kh.fertilizer_type(code),
  default_unit      text not null check (default_unit in ('BAG_50KG','BAG_25KG','KG','LITRE','TONNE')),
  is_active         boolean not null default true
);

comment on column market.product.fertilizer_code is
  'Optional link to the subsidy catalogue, so a UI can show "this is the product your e-voucher covers". It links the two catalogues; it does not merge their prices.';

-- ---------------------------------------------------------------------------
-- Supplier-declared prices
-- ---------------------------------------------------------------------------

create table market.price_quote (
  id               uuid primary key default gen_random_uuid(),
  organisation_id  uuid not null references identity.organisation(id) on delete cascade,
  product_code     text not null references market.product(code),
  quote_kind       text not null check (quote_kind in ('RETAIL','WHOLESALE')),
  unit             text not null check (unit in ('BAG_50KG','BAG_25KG','KG','LITRE','TONNE')),
  price_kes        numeric(12,2) not null check (price_kes > 0),
  county_code      text references kh.county(code),
  valid_from       date not null,
  valid_to         date not null,
  status           text not null default 'DRAFT' check (status in ('DRAFT','PUBLISHED','WITHDRAWN')),
  price_authority  text not null default 'SUPPLIER_DECLARED'
                     check (price_authority = 'SUPPLIER_DECLARED'),
  created_by       uuid not null references identity.app_user(id),
  created_at       timestamptz not null default now(),
  published_by     uuid references identity.app_user(id),
  published_at     timestamptz,
  withdrawn_at     timestamptz,
  note_en          text,
  note_sw          text,
  check (valid_to >= valid_from),
  check ((status = 'PUBLISHED') = (published_at is not null and published_by is not null))
);

-- One live published price per organisation, product, unit, kind and county.
-- Two overlapping quotes would leave a farmer choosing between two numbers from
-- the same source, which is worse than no number.
alter table market.price_quote
  add constraint price_quote_no_overlap
  exclude using gist (
    organisation_id with =,
    product_code with =,
    quote_kind with =,
    unit with =,
    coalesce(county_code, '*') with =,
    daterange(valid_from, valid_to, '[]') with &&
  ) where (status = 'PUBLISHED');

create index price_quote_lookup_idx
  on market.price_quote (product_code, county_code, quote_kind, valid_from desc)
  where status = 'PUBLISHED';

comment on table market.price_quote is
  'A price one organisation declares. Render it with the organisation''s name attached, in body text - never in gazette brass, never labelled official. See CLAUDE.md invariant 2.';

-- ---------------------------------------------------------------------------
-- Demand and supply signals
-- ---------------------------------------------------------------------------

create table market.signal (
  id               uuid primary key default gen_random_uuid(),
  organisation_id  uuid not null references identity.organisation(id) on delete cascade,
  direction        text not null check (direction in ('DEMAND','SUPPLY')),
  product_code     text not null references market.product(code),
  county_code      text references kh.county(code),
  period_start     date not null,
  period_end       date not null,
  quantity         numeric(14,3) check (quantity > 0),
  unit             text check (unit in ('BAG_50KG','BAG_25KG','KG','LITRE','TONNE')),
  headline_en      text not null,
  headline_sw      text not null,
  detail_en        text,
  detail_sw        text,
  status           text not null default 'DRAFT' check (status in ('DRAFT','PUBLISHED','WITHDRAWN')),
  created_by       uuid not null references identity.app_user(id),
  created_at       timestamptz not null default now(),
  published_by     uuid references identity.app_user(id),
  published_at     timestamptz,
  check (period_end >= period_start),
  check ((status = 'PUBLISHED') = (published_at is not null and published_by is not null))
);

create index signal_lookup_idx
  on market.signal (product_code, county_code, period_start desc)
  where status = 'PUBLISHED';

comment on table market.signal is
  'An association telling farmers and businesses where demand or supply is heading. A notice, not an offer: it has no price, no counterparty and no accept action.';

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table market.product     enable row level security;
alter table market.price_quote enable row level security;
alter table market.signal      enable row level security;

create policy product_read on market.product for select using (is_active);

-- Anyone signed in may read what has been published and is not withdrawn.
-- Drafts are visible only inside the authoring organisation.
create policy price_quote_read on market.price_quote
  for select using (
    (status = 'PUBLISHED' and identity.has_permission('market.read'))
    or organisation_id in (select identity.orgs_with_permission('market.price.draft.own_org'))
  );

create policy price_quote_draft on market.price_quote
  for insert with check (
    organisation_id in (select identity.orgs_with_permission('market.price.draft.own_org'))
    and status = 'DRAFT'
    and created_by = identity.uid()
  );

-- Publishing is a separate permission from drafting, and the row must belong to
-- a VERIFIED organisation - orgs_with_permission() filters on that.
create policy price_quote_publish on market.price_quote
  for update using (
    organisation_id in (select identity.orgs_with_permission('market.price.draft.own_org'))
  )
  with check (
    case
      when status = 'PUBLISHED'
        then organisation_id in (select identity.orgs_with_permission('market.price.publish.own_org'))
      else true
    end
  );

create policy signal_read on market.signal
  for select using (
    (status = 'PUBLISHED' and identity.has_permission('market.read'))
    or organisation_id in (select identity.orgs_with_permission('market.signal.publish.own_org'))
  );

create policy signal_write on market.signal
  for all using (
    organisation_id in (select identity.orgs_with_permission('market.signal.publish.own_org'))
  )
  with check (
    organisation_id in (select identity.orgs_with_permission('market.signal.publish.own_org'))
    and created_by = identity.uid()
  );

grant usage on schema market to authenticated;
grant select on market.product to authenticated;
grant select, insert, update on market.price_quote, market.signal to authenticated;
