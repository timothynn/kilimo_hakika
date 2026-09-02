-- Kilimo Hakika - identity, organisations, roles, consent, audit.
--
-- Supabase Auth (`auth.users`) owns credentials. Phone numbers and emails live
-- there and are deliberately NOT copied here: the less PII this schema holds,
-- the less there is to leak. `identity.app_user` is profile and status only.
--
-- Unlike `kh`, these tables are reached under the caller's own identity: the
-- backend opens each request's transaction as the `authenticated` role with the
-- request's JWT claims set, so RLS is live. App-level permission checks in
-- FastAPI are the first gate; these policies are the one that holds if that
-- gate has a bug.

create schema if not exists identity;
comment on schema identity is 'Accounts, organisations, roles, consent, audit. RLS-enforced under the caller identity.';

-- ---------------------------------------------------------------------------
-- Users
-- ---------------------------------------------------------------------------

create table identity.app_user (
  id              uuid primary key references auth.users(id) on delete cascade,
  display_name    text,
  locale          text not null default 'en' check (locale in ('en','sw')),
  status          text not null default 'ACTIVE'
                    check (status in ('ACTIVE','SUSPENDED','DELETED')),
  created_at      timestamptz not null default now(),
  last_seen_at    timestamptz
);

comment on table identity.app_user is 'Profile only. Credentials, phone and email stay in auth.users.';

-- Supabase Auth creates the credential row; this creates the profile row beside
-- it. Without this trigger a freshly signed-up user has no app_user record, and
-- every policy below - all of which key off it - silently denies them.
create or replace function identity.handle_new_auth_user()
returns trigger
language plpgsql security definer set search_path = identity, public as $$
begin
  insert into identity.app_user (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', null))
  on conflict (id) do nothing;

  -- Every account starts as a farmer: a SELF-scoped role that can run a triage
  -- and nothing else. Staff roles are granted on top, by a human, and recorded
  -- in identity.audit_event. Nothing self-elevates.
  insert into identity.membership (user_id, role_code)
  values (new.id, 'farmer')
  on conflict do nothing;

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function identity.handle_new_auth_user();

-- What a farmer would otherwise retype every season. This is the payoff of
-- requiring a login, and the only reason farmer PII exists at all.
create table identity.farmer_profile (
  user_id                   uuid primary key references identity.app_user(id) on delete cascade,
  registration_county_code  text references kh.county(code),
  default_acreage_acres     numeric(8,3) check (default_acreage_acres > 0),
  land_tenure               text check (land_tenure in ('OWNED','LEASED','FAMILY_UNREGISTERED','UNKNOWN')),
  kiamis_registered         boolean,
  national_id_hmac          bytea unique,
  updated_at                timestamptz not null default now()
);

comment on column identity.farmer_profile.national_id_hmac is
  'Keyed HMAC-SHA256 of the ID number, pepper held outside the database. Never store the number itself. Sufficient to recognise a returning farmer or match an NCPB register export; useless to an attacker who dumps this table. Drop to plaintext ONLY if a confirmed NCPB integration demands it, and then only in Supabase Vault.';

-- ---------------------------------------------------------------------------
-- Organisations
-- ---------------------------------------------------------------------------

create table identity.organisation (
  id                   uuid primary key default gen_random_uuid(),
  name                 text not null,
  kind                 text not null
                         check (kind in ('RETAIL','WHOLESALE','SUPPLIER_ASSOCIATION','GOVERNMENT','PLATFORM')),
  registration_number  text,
  county_code          text references kh.county(code),
  status               text not null default 'PENDING_VERIFICATION'
                         check (status in ('PENDING_VERIFICATION','VERIFIED','SUSPENDED')),
  verified_at          timestamptz,
  verified_by          uuid references identity.app_user(id),
  created_at           timestamptz not null default now(),
  unique (kind, registration_number)
);

-- An unverified organisation must never be able to publish a price a farmer
-- could mistake for authoritative.
alter table identity.organisation
  add constraint organisation_verified_fields
  check ((status = 'VERIFIED') = (verified_at is not null and verified_by is not null));

comment on table identity.organisation is 'Retailers, wholesalers and supplier associations. Retained for identity and verification only: this platform has no marketplace, so no organisation publishes prices or listings anywhere in it.';

-- ---------------------------------------------------------------------------
-- Roles and permissions
-- ---------------------------------------------------------------------------

create table identity.permission (
  code        text primary key,
  description text not null
);

create table identity.role (
  code        text primary key,
  label       text not null,
  scope       text not null check (scope in ('SELF','ORGANISATION','PLATFORM')),
  description text not null
);

create table identity.role_permission (
  role_code       text not null references identity.role(code) on delete cascade,
  permission_code text not null references identity.permission(code) on delete cascade,
  primary key (role_code, permission_code)
);

create table identity.membership (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references identity.app_user(id) on delete cascade,
  organisation_id  uuid references identity.organisation(id) on delete cascade,
  role_code        text not null references identity.role(code),
  granted_by       uuid references identity.app_user(id),
  granted_at       timestamptz not null default now(),
  revoked_at       timestamptz,
  revoked_by       uuid references identity.app_user(id)
);

-- One live grant of a role per user per org.
create unique index membership_live_unique
  on identity.membership (user_id, coalesce(organisation_id, '00000000-0000-0000-0000-000000000000'::uuid), role_code)
  where revoked_at is null;

create index membership_user_idx on identity.membership (user_id) where revoked_at is null;
create index membership_org_idx  on identity.membership (organisation_id) where revoked_at is null;

comment on table identity.membership is 'Grants are revoked, never deleted - who could do what on a given date must stay answerable.';

insert into identity.permission (code, description) values
 ('triage.run',                  'Run a depot triage and receive a verdict'),
 ('triage.history.read.self',    'Read own triage history'),
 ('profile.write.self',          'Edit own profile'),
 ('org.member.manage.own_org',   'Invite and remove members of own organisation'),
 ('org.verify',                  'Verify or suspend an organisation'),
 ('policy.author',               'Create and edit statutory rules, prices and depots in kh'),
 ('policy.review',               'Review authored policy changes and their citations'),
 ('policy.publish',              'Build and publish a rule pack'),
 ('assistant.chat',              'Use the assistant'),
 ('analytics.read',              'Read aggregate triage analytics'),
 ('audit.read',                  'Read the audit trail'),
 ('user.suspend',                'Suspend or reinstate a user account');

insert into identity.role (code, label, scope, description) values
 ('farmer',                 'Farmer',                      'SELF',         'Runs triage, keeps a profile and history'),
 ('org_staff',              'Business staff',              'ORGANISATION', 'Retail or wholesale staff: reads published policy'),
 ('org_admin',              'Business administrator',      'ORGANISATION', 'Manages members and publishes for the organisation'),
 ('policy_author',          'Policy author',               'PLATFORM',     'Writes statutory rules and their citations'),
 ('policy_reviewer',        'Policy reviewer',             'PLATFORM',     'Checks a rule against its cited source'),
 ('policy_publisher',       'Policy publisher',            'PLATFORM',     'Builds and publishes rule packs'),
 ('analyst',                'Analyst',                     'PLATFORM',     'Reads aggregate analytics'),
 ('moderator',              'Moderator',                   'PLATFORM',     'Verifies organisations, suspends abusive accounts'),
 ('platform_admin',         'Platform administrator',      'PLATFORM',     'Full administrative access'),
 ('developer',              'Developer',                   'PLATFORM',     'Engineering access to diagnostics and audit');

insert into identity.role_permission (role_code, permission_code) values
 ('farmer','triage.run'), ('farmer','triage.history.read.self'),
 ('farmer','profile.write.self'), ('farmer','assistant.chat'),
 ('org_staff','assistant.chat'), ('org_staff','triage.run'),
 ('org_admin','org.member.manage.own_org'), ('org_admin','assistant.chat'), ('org_admin','triage.run'),

 ('policy_author','policy.author'), ('policy_author','triage.run'),
 ('policy_reviewer','policy.review'), ('policy_reviewer','triage.run'),
 ('policy_publisher','policy.publish'), ('policy_publisher','policy.review'), ('policy_publisher','triage.run'),

 ('analyst','analytics.read'),
 ('moderator','org.verify'), ('moderator','user.suspend'),

 ('developer','audit.read'), ('developer','analytics.read'),

 ('platform_admin','org.verify'), ('platform_admin','user.suspend'),
 ('platform_admin','analytics.read'), ('platform_admin','audit.read'), ('platform_admin','org.member.manage.own_org');

-- Deliberately absent from every role, including platform_admin:
--   * policy.author / policy.review / policy.publish are never held together.
--     A rule that decides whether a farmer travels gets two pairs of eyes.
--   * No supplier role holds any policy.* permission. Nobody outside the
--     platform can edit what the app presents as the law.

-- ---------------------------------------------------------------------------
-- Authorization helpers used by every policy below
-- ---------------------------------------------------------------------------

create or replace function identity.uid() returns uuid
language sql stable as $$ select auth.uid() $$;

create or replace function identity.has_permission(p_permission text)
returns boolean
language sql stable security definer set search_path = identity, public as $$
  select exists (
    select 1
    from identity.membership m
    join identity.role_permission rp on rp.role_code = m.role_code
    where m.user_id = auth.uid()
      and m.revoked_at is null
      and rp.permission_code = p_permission
  );
$$;

-- Organisations the caller may act for, holding a given permission.
create or replace function identity.orgs_with_permission(p_permission text)
returns setof uuid
language sql stable security definer set search_path = identity, public as $$
  select distinct m.organisation_id
  from identity.membership m
  join identity.role_permission rp on rp.role_code = m.role_code
  join identity.organisation o on o.id = m.organisation_id
  where m.user_id = auth.uid()
    and m.revoked_at is null
    and m.organisation_id is not null
    and o.status = 'VERIFIED'
    and rp.permission_code = p_permission;
$$;

comment on function identity.has_permission is
  'Source of truth for authorization. JWT claims are used to shape the UI; writes are always checked against the membership table, so a revoked grant takes effect immediately rather than at token expiry.';

-- ---------------------------------------------------------------------------
-- Consent, erasure, and per-farmer triage history
-- ---------------------------------------------------------------------------

create table identity.consent (
  user_id        uuid not null references identity.app_user(id) on delete cascade,
  purpose        text not null
                   check (purpose in ('ACCOUNT','ASSISTANT_AI','ANALYTICS')),
  policy_version text not null,
  granted_at     timestamptz not null default now(),
  withdrawn_at   timestamptz,
  primary key (user_id, purpose, policy_version)
);

comment on table identity.consent is 'Kenya Data Protection Act 2019: consent is per purpose, versioned against the privacy notice, and withdrawable. ASSISTANT_AI gates sending anything of a farmer''s to a model.';

create table identity.erasure_request (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references identity.app_user(id) on delete cascade,
  requested_at  timestamptz not null default now(),
  completed_at  timestamptz,
  notes         text
);

-- The farmer-owned view of their own triage history. Deliberately separate from
-- kh.triage_log: erasure deletes this row and the anonymous audit row survives,
-- so a farmer's right to be forgotten never costs us the ability to replay a
-- disputed verdict.
create table identity.triage_history (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references identity.app_user(id) on delete cascade,
  triage_log_id  uuid not null references kh.triage_log(id),
  verdict        text not null check (verdict in ('PROCEED','DO_NOT_TRAVEL')),
  depot_code     text not null,
  total_bags     integer,
  gap_state      jsonb not null default '{}'::jsonb,   -- {"EVOUCHER_CODE":"RESOLVED"}
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index triage_history_user_idx on identity.triage_history (user_id, created_at desc);

comment on column identity.triage_history.gap_state is 'Per-document progress a farmer ticks off after a DO_NOT_TRAVEL. This is the "tracking" surface: what was missing, and whether it has been fixed.';

-- ---------------------------------------------------------------------------
-- Audit
-- ---------------------------------------------------------------------------

create table identity.audit_event (
  id             bigserial primary key,
  occurred_at    timestamptz not null default now(),
  actor_user_id  uuid references identity.app_user(id),
  actor_role     text,
  action         text not null,          -- 'policy.rule.update', 'org.verify', ...
  entity         text not null,
  entity_id      text,
  before         jsonb,
  after          jsonb,
  reason         text
);

create index audit_event_actor_idx  on identity.audit_event (actor_user_id, occurred_at desc);
create index audit_event_entity_idx on identity.audit_event (entity, entity_id, occurred_at desc);

comment on table identity.audit_event is 'Append-only. Every write to kh.*, every organisation verification, every role grant and every account suspension lands here.';

create or replace function identity.audit_no_mutate() returns trigger
language plpgsql as $$
begin
  raise exception 'identity.audit_event is append-only';
end;
$$;

create trigger audit_event_no_update before update on identity.audit_event
  for each row execute function identity.audit_no_mutate();
create trigger audit_event_no_delete before delete on identity.audit_event
  for each row execute function identity.audit_no_mutate();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table identity.app_user        enable row level security;
alter table identity.farmer_profile  enable row level security;
alter table identity.organisation    enable row level security;
alter table identity.membership      enable row level security;
alter table identity.consent         enable row level security;
alter table identity.erasure_request enable row level security;
alter table identity.triage_history  enable row level security;
alter table identity.audit_event     enable row level security;
alter table identity.role            enable row level security;
alter table identity.permission      enable row level security;
alter table identity.role_permission enable row level security;

-- Own record.
create policy app_user_self_read on identity.app_user
  for select using (id = identity.uid());
create policy app_user_self_update on identity.app_user
  for update using (id = identity.uid())
  with check (id = identity.uid() and status = 'ACTIVE');

create policy farmer_profile_self on identity.farmer_profile
  for all using (user_id = identity.uid()) with check (user_id = identity.uid());

create policy consent_self on identity.consent
  for all using (user_id = identity.uid()) with check (user_id = identity.uid());

create policy erasure_self on identity.erasure_request
  for select using (user_id = identity.uid());
create policy erasure_self_insert on identity.erasure_request
  for insert with check (user_id = identity.uid());

create policy triage_history_self on identity.triage_history
  for all using (user_id = identity.uid()) with check (user_id = identity.uid());

-- Verified organisations are public: a farmer must be able to see who is behind
-- a price. Unverified ones are visible only to their own members.
create policy organisation_read on identity.organisation
  for select using (
    status = 'VERIFIED'
    or id in (select organisation_id from identity.membership
              where user_id = identity.uid() and revoked_at is null)
  );
create policy organisation_moderate on identity.organisation
  for update using (identity.has_permission('org.verify'));

create policy membership_read_self on identity.membership
  for select using (
    user_id = identity.uid()
    or organisation_id in (select identity.orgs_with_permission('org.member.manage.own_org'))
  );
create policy membership_manage_own_org on identity.membership
  for all using (organisation_id in (select identity.orgs_with_permission('org.member.manage.own_org')))
  with check (
    organisation_id in (select identity.orgs_with_permission('org.member.manage.own_org'))
    -- An org admin may never grant a platform-scoped role.
    and role_code in (select code from identity.role where scope = 'ORGANISATION')
  );

create policy audit_read on identity.audit_event
  for select using (identity.has_permission('audit.read'));

-- The role catalogue is reference data every client needs to render itself.
create policy role_read            on identity.role            for select using (true);
create policy permission_read      on identity.permission      for select using (true);
create policy role_permission_read on identity.role_permission for select using (true);

grant usage on schema identity to authenticated;
grant select on identity.role, identity.permission, identity.role_permission to authenticated;
grant select, insert, update on identity.app_user, identity.farmer_profile,
  identity.consent, identity.triage_history to authenticated;
grant select, insert on identity.erasure_request to authenticated;
grant select on identity.organisation, identity.membership, identity.audit_event to authenticated;
grant update on identity.organisation to authenticated;
grant insert, update on identity.membership to authenticated;
