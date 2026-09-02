-- DEV ONLY. Do not run this on Supabase.
--
-- Supabase provides the `auth` schema, the `anon` / `authenticated` /
-- `service_role` roles, and `auth.uid()` / `auth.jwt()`. A plain local Postgres
-- does not. This shim creates just enough of that surface for the real
-- migrations to apply unchanged, so what we develop against is what deploys.
--
-- The shape is deliberately faithful in the parts the app depends on:
--   * auth.users(id, phone, email, raw_user_meta_data) - the columns
--     identity.handle_new_auth_user() reads.
--   * auth.uid() resolves from `request.jwt.claims`, exactly as on Supabase, so
--     every RLS policy behaves the same locally.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end;
$$;

create schema if not exists auth;

create table if not exists auth.users (
  id                  uuid primary key default gen_random_uuid(),
  phone               text unique,
  email               text unique,
  encrypted_password  text,
  raw_user_meta_data  jsonb not null default '{}'::jsonb,
  created_at          timestamptz not null default now(),
  last_sign_in_at     timestamptz
);

-- Local stand-in for Supabase Auth's OTP store.
create table if not exists auth.otp_challenge (
  id           uuid primary key default gen_random_uuid(),
  phone        text not null,
  code_hash    text not null,
  expires_at   timestamptz not null,
  consumed_at  timestamptz,
  attempts     integer not null default 0,
  created_at   timestamptz not null default now()
);

create index if not exists otp_challenge_phone_idx on auth.otp_challenge (phone, created_at desc);

-- Same contract as Supabase: read the verified claims the connection set.
create or replace function auth.jwt() returns jsonb
language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb,
    '{}'::jsonb
  );
$$;

create or replace function auth.uid() returns uuid
language sql stable as $$
  select nullif(auth.jwt() ->> 'sub', '')::uuid;
$$;

create or replace function auth.role() returns text
language sql stable as $$
  select auth.jwt() ->> 'role';
$$;

grant usage on schema auth to authenticated, anon, service_role;
grant select on auth.users to authenticated;
