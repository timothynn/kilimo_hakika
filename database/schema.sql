-- Kilimo Hakika registry schema.
--
-- National IDs are never stored in the clear. We keep a SHA-256 hash for
-- exact-match lookup (a depot officer types the full ID, we hash and compare)
-- and the last four digits for on-screen confirmation. A leaked copy of this
-- file therefore does not hand over ID numbers.
--
-- Names and phone numbers ARE stored in the clear because a depot officer has
-- to read them off the screen to verify the person at the gate. Keep that in
-- mind before pointing this at real farmers: see CLAUDE.md, "Data protection".

CREATE TABLE IF NOT EXISTS farmers (
  id                TEXT PRIMARY KEY,
  full_name         TEXT NOT NULL,
  national_id_hash  TEXT NOT NULL UNIQUE,
  national_id_last4 TEXT NOT NULL,
  phone             TEXT NOT NULL UNIQUE,
  county            TEXT NOT NULL,
  acres             REAL NOT NULL,
  -- scrypt of the farmer's PIN, formatted "salt:derivedKey" (both hex).
  -- Nullable: rows seeded before accounts existed have no PIN and simply
  -- cannot sign in until they set one.
  pin_hash          TEXT,
  consent_given_at  TEXT NOT NULL,
  registered_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_farmers_national_id_hash
  ON farmers (national_id_hash);
CREATE INDEX IF NOT EXISTS idx_farmers_county ON farmers (county);

-- One row per triage check. Kept so a depot officer can see what the farmer
-- was told before they travelled, and so oversight can count rejection
-- reasons. `missing_json` is the itemised gap list as rendered.
CREATE TABLE IF NOT EXISTS check_events (
  id            TEXT PRIMARY KEY,
  farmer_id     TEXT REFERENCES farmers (id) ON DELETE CASCADE,
  depot_id      TEXT NOT NULL,
  acres         REAL NOT NULL,
  verdict       TEXT NOT NULL CHECK (verdict IN ('PROCEED', 'DO_NOT_TRAVEL')),
  bags          INTEGER NOT NULL,
  total_kes     INTEGER NOT NULL,
  missing_json  TEXT NOT NULL,
  rules_version TEXT NOT NULL,
  checked_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_check_events_farmer ON check_events (farmer_id);
CREATE INDEX IF NOT EXISTS idx_check_events_depot ON check_events (depot_id);
CREATE INDEX IF NOT EXISTS idx_check_events_checked_at ON check_events (checked_at);

-- A farmer marked served at the gate. Separate from check_events: a check is
-- what we predicted, a service record is what actually happened.
CREATE TABLE IF NOT EXISTS service_records (
  id         TEXT PRIMARY KEY,
  farmer_id  TEXT NOT NULL REFERENCES farmers (id) ON DELETE CASCADE,
  depot_id   TEXT NOT NULL,
  bags       INTEGER NOT NULL,
  total_kes  INTEGER NOT NULL,
  -- Free text so an officer can record why reality diverged from the verdict.
  note       TEXT,
  served_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_service_records_farmer ON service_records (farmer_id);
