/**
 * Seeds the registry with fictional farmers so the gate console has something
 * to show in a demo.
 *
 * Run from the repo root with the same secret the app uses, or lookups will
 * not match:
 *
 *   NATIONAL_ID_HASH_SECRET=... node database/seed.mjs
 *
 * These are invented people. Never seed a deployed database with real farmer
 * details.
 */
import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

const secret = process.env.NATIONAL_ID_HASH_SECRET;
if (!secret) {
  console.error(
    "NATIONAL_ID_HASH_SECRET is not set. Set it to the same value as frontend/.env, or seeded farmers will be unfindable."
  );
  process.exit(1);
}

const dir = path.join(import.meta.dirname);
const db = new DatabaseSync(path.join(dir, "kilimo.db"));
db.exec("PRAGMA foreign_keys = ON");
db.exec(readFileSync(path.join(dir, "schema.sql"), "utf8"));

const hash = (id) => createHash("sha256").update(`${secret}:${id}`).digest("hex");

const FARMERS = [
  { name: "Wanjiku Kamau", id: "23145678", phone: "0712345678", county: "Uasin Gishu", acres: 2 },
  { name: "Otieno Ochieng", id: "31456789", phone: "0722345678", county: "Trans Nzoia", acres: 6.5 },
  { name: "Chebet Kirui", id: "28765432", phone: "0733456789", county: "Uasin Gishu", acres: 12 },
  { name: "Mutiso Nzioka", id: "19876543", phone: "0745678901", county: "Nakuru", acres: 1.75 },
  { name: "Achieng Odhiambo", id: "34567812", phone: "0756789012", county: "Nakuru", acres: 3 },
];

const now = new Date().toISOString();

const insertFarmer = db.prepare(
  `INSERT OR IGNORE INTO farmers (id, full_name, national_id_hash, national_id_last4,
                                  phone, county, acres, consent_given_at, registered_at)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
);

const insertCheck = db.prepare(
  `INSERT INTO check_events (id, farmer_id, depot_id, acres, verdict, bags,
                             total_kes, missing_json, rules_version, checked_at)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
);

let seeded = 0;
for (const farmer of FARMERS) {
  const farmerId = randomUUID();
  insertFarmer.run(
    farmerId,
    farmer.name,
    hash(farmer.id),
    farmer.id.slice(-4),
    farmer.phone,
    farmer.county,
    farmer.acres,
    now,
    now
  );

  // One check each, alternating verdict, so the dashboard counts are not all
  // one colour.
  const proceed = seeded % 2 === 0;
  const bags = Math.min(Math.floor(farmer.acres * 2), 10);
  insertCheck.run(
    randomUUID(),
    farmerId,
    farmer.county === "Nakuru" ? "ncpb-nakuru" : "ncpb-eldoret",
    farmer.acres,
    proceed ? "PROCEED" : "DO_NOT_TRAVEL",
    bags,
    bags * 2500,
    JSON.stringify(
      proceed ? [] : [{ id: "evoucher_code", label: "E-Voucher SMS code" }]
    ),
    "2024-02",
    now
  );
  seeded += 1;
}

console.log(`Seeded ${seeded} farmers with one check each.`);
console.log(`Try looking up ID ${FARMERS[0].id} in the gate console.`);
db.close();
