import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

const dataDir = () =>
  process.env.DATABASE_DIR ?? path.join(process.cwd(), "..", "database");

let db: DatabaseSync | null = null;

/**
 * SQLite via node:sqlite — a Node builtin, so there is no native module to
 * compile and no ORM in the way. The registry is small and single-node; this
 * is enough.
 */
export function getDb(): DatabaseSync {
  if (db) return db;

  const dir = dataDir();
  const handle = new DatabaseSync(path.join(dir, "kilimo.db"));
  handle.exec("PRAGMA journal_mode = WAL");
  handle.exec("PRAGMA foreign_keys = ON");
  handle.exec(readFileSync(path.join(dir, "schema.sql"), "utf8"));
  migrate(handle);

  db = handle;
  return db;
}

/**
 * Adds columns that schema.sql introduced after a database was first created.
 *
 * `CREATE TABLE IF NOT EXISTS` is a no-op on an existing table, so a column
 * added to schema.sql never reaches a database that predates it — the app
 * then fails at runtime on a column that "obviously" exists. SQLite has no
 * `ADD COLUMN IF NOT EXISTS`, so check pragma output first.
 */
function migrate(handle: DatabaseSync): void {
  const columns = handle
    .prepare("SELECT name FROM pragma_table_info('farmers')")
    .all() as { name: string }[];
  const present = new Set(columns.map((c) => c.name));

  if (!present.has("pin_hash")) {
    handle.exec("ALTER TABLE farmers ADD COLUMN pin_hash TEXT");
  }
}

/**
 * Hash a national ID for storage and lookup.
 *
 * Salted with NATIONAL_ID_HASH_SECRET. A bare SHA-256 of a 7-9 digit number
 * is trivially brute-forced — the whole keyspace is under a billion entries —
 * so without a secret pepper the hash would offer no real protection. The
 * secret is required, not defaulted: a silent fallback would produce a
 * database that looks protected and is not.
 */
export function hashNationalId(nationalId: string): string {
  const secret = process.env.NATIONAL_ID_HASH_SECRET;
  if (!secret) {
    throw new Error(
      "NATIONAL_ID_HASH_SECRET is not set. Refusing to store or look up national IDs without it — see .env.example."
    );
  }
  return createHash("sha256").update(`${secret}:${nationalId}`).digest("hex");
}

export type FarmerRow = {
  id: string;
  full_name: string;
  national_id_last4: string;
  phone: string;
  county: string;
  acres: number;
  registered_at: string;
};

export type Farmer = {
  id: string;
  fullName: string;
  nationalIdLast4: string;
  phone: string;
  county: string;
  acres: number;
  registeredAt: string;
};

const toFarmer = (row: FarmerRow): Farmer => ({
  id: row.id,
  fullName: row.full_name,
  nationalIdLast4: row.national_id_last4,
  phone: row.phone,
  county: row.county,
  acres: row.acres,
  registeredAt: row.registered_at,
});

export function registerFarmer(input: {
  fullName: string;
  nationalId: string;
  phone: string;
  county: string;
  acres: number;
  /** scrypt hash from hashPin(). Omitted for a registration without an account. */
  pinHash?: string;
}): Farmer {
  const now = new Date().toISOString();
  const row = {
    id: randomUUID(),
    full_name: input.fullName,
    national_id_hash: hashNationalId(input.nationalId),
    national_id_last4: input.nationalId.slice(-4),
    phone: input.phone,
    county: input.county,
    acres: input.acres,
    pin_hash: input.pinHash ?? null,
    consent_given_at: now,
    registered_at: now,
  };

  getDb()
    .prepare(
      `INSERT INTO farmers (id, full_name, national_id_hash, national_id_last4,
                            phone, county, acres, pin_hash, consent_given_at,
                            registered_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .run(
      row.id,
      row.full_name,
      row.national_id_hash,
      row.national_id_last4,
      row.phone,
      row.county,
      row.acres,
      row.pin_hash,
      row.consent_given_at,
      row.registered_at
    );

  return toFarmer(row as unknown as FarmerRow);
}

/**
 * Looks a farmer up by phone for sign-in, returning the PIN hash alongside.
 * Separate from the other finders because nothing else should ever pull the
 * hash out of the database.
 */
export function findFarmerCredentialsByPhone(
  phone: string
): { farmer: Farmer; pinHash: string | null } | null {
  const row = getDb()
    .prepare(
      `SELECT id, full_name, national_id_last4, phone, county, acres,
              registered_at, pin_hash
         FROM farmers WHERE phone = ?`
    )
    .get(phone) as (FarmerRow & { pin_hash: string | null }) | undefined;

  return row ? { farmer: toFarmer(row), pinHash: row.pin_hash } : null;
}

export function findFarmerByNationalId(nationalId: string): Farmer | null {
  const row = getDb()
    .prepare(
      `SELECT id, full_name, national_id_last4, phone, county, acres, registered_at
         FROM farmers WHERE national_id_hash = ?`
    )
    .get(hashNationalId(nationalId)) as FarmerRow | undefined;

  return row ? toFarmer(row) : null;
}

export function findFarmerById(id: string): Farmer | null {
  const row = getDb()
    .prepare(
      `SELECT id, full_name, national_id_last4, phone, county, acres, registered_at
         FROM farmers WHERE id = ?`
    )
    .get(id) as FarmerRow | undefined;

  return row ? toFarmer(row) : null;
}

/**
 * Update the parts of a profile a farmer owns: land size and county.
 *
 * Deliberately narrow. Name, phone and national ID are gate-identity fields —
 * an officer reads them back against the card — so they are not self-editable.
 * Returns null if the row is gone, which happens when a session outlives it.
 */
export function updateFarmerProfile(input: {
  id: string;
  county: string;
  acres: number;
}): Farmer | null {
  getDb()
    .prepare(`UPDATE farmers SET county = ?, acres = ? WHERE id = ?`)
    .run(input.county, input.acres, input.id);

  return findFarmerById(input.id);
}

export function listFarmers(options: { county?: string } = {}): Farmer[] {
  const rows = options.county
    ? (getDb()
        .prepare(
          `SELECT id, full_name, national_id_last4, phone, county, acres, registered_at
             FROM farmers WHERE county = ? ORDER BY full_name`
        )
        .all(options.county) as FarmerRow[])
    : (getDb()
        .prepare(
          `SELECT id, full_name, national_id_last4, phone, county, acres, registered_at
             FROM farmers ORDER BY full_name`
        )
        .all() as FarmerRow[]);

  return rows.map(toFarmer);
}

export type CheckEvent = {
  id: string;
  farmerId: string | null;
  depotId: string;
  acres: number;
  verdict: "PROCEED" | "DO_NOT_TRAVEL";
  bags: number;
  totalKes: number;
  missing: { id: string; label: string }[];
  rulesVersion: string;
  checkedAt: string;
};

type CheckEventRow = {
  id: string;
  farmer_id: string | null;
  depot_id: string;
  acres: number;
  verdict: "PROCEED" | "DO_NOT_TRAVEL";
  bags: number;
  total_kes: number;
  missing_json: string;
  rules_version: string;
  checked_at: string;
};

const toCheckEvent = (row: CheckEventRow): CheckEvent => ({
  id: row.id,
  farmerId: row.farmer_id,
  depotId: row.depot_id,
  acres: row.acres,
  verdict: row.verdict,
  bags: row.bags,
  totalKes: row.total_kes,
  missing: JSON.parse(row.missing_json),
  rulesVersion: row.rules_version,
  checkedAt: row.checked_at,
});

export function recordCheck(input: {
  farmerId: string | null;
  depotId: string;
  acres: number;
  verdict: "PROCEED" | "DO_NOT_TRAVEL";
  bags: number;
  totalKes: number;
  missing: { id: string; label: string }[];
  rulesVersion: string;
}): void {
  getDb()
    .prepare(
      `INSERT INTO check_events (id, farmer_id, depot_id, acres, verdict, bags,
                                 total_kes, missing_json, rules_version, checked_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .run(
      randomUUID(),
      input.farmerId,
      input.depotId,
      input.acres,
      input.verdict,
      input.bags,
      input.totalKes,
      JSON.stringify(input.missing),
      input.rulesVersion,
      new Date().toISOString()
    );
}

export function listChecksForFarmer(farmerId: string): CheckEvent[] {
  const rows = getDb()
    .prepare(
      `SELECT * FROM check_events WHERE farmer_id = ? ORDER BY checked_at DESC`
    )
    .all(farmerId) as CheckEventRow[];

  return rows.map(toCheckEvent);
}

export function markServed(input: {
  farmerId: string;
  depotId: string;
  bags: number;
  totalKes: number;
  note?: string;
}): void {
  getDb()
    .prepare(
      `INSERT INTO service_records (id, farmer_id, depot_id, bags, total_kes, note, served_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    )
    .run(
      randomUUID(),
      input.farmerId,
      input.depotId,
      input.bags,
      input.totalKes,
      input.note ?? null,
      new Date().toISOString()
    );
}

export type ServiceRecord = {
  id: string;
  depotId: string;
  bags: number;
  totalKes: number;
  note: string | null;
  servedAt: string;
};

export function listServiceRecords(farmerId: string): ServiceRecord[] {
  const rows = getDb()
    .prepare(
      `SELECT id, depot_id, bags, total_kes, note, served_at
         FROM service_records WHERE farmer_id = ? ORDER BY served_at DESC`
    )
    .all(farmerId) as {
    id: string;
    depot_id: string;
    bags: number;
    total_kes: number;
    note: string | null;
    served_at: string;
  }[];

  return rows.map((row) => ({
    id: row.id,
    depotId: row.depot_id,
    bags: row.bags,
    totalKes: row.total_kes,
    note: row.note,
    servedAt: row.served_at,
  }));
}

export function registryStats(): {
  farmers: number;
  checks: number;
  proceed: number;
  doNotTravel: number;
  served: number;
} {
  const one = (sql: string) =>
    (getDb().prepare(sql).get() as { n: number }).n ?? 0;

  return {
    farmers: one("SELECT COUNT(*) AS n FROM farmers"),
    checks: one("SELECT COUNT(*) AS n FROM check_events"),
    proceed: one(
      "SELECT COUNT(*) AS n FROM check_events WHERE verdict = 'PROCEED'"
    ),
    doNotTravel: one(
      "SELECT COUNT(*) AS n FROM check_events WHERE verdict = 'DO_NOT_TRAVEL'"
    ),
    served: one("SELECT COUNT(*) AS n FROM service_records"),
  };
}
