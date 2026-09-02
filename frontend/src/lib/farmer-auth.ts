import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

/**
 * Farmer accounts.
 *
 * Sign-in is phone number + a 6-digit PIN, not an email and password. That is
 * the pattern Kenyan farmers already use for mobile money, it is typeable on a
 * feature-phone keypad, and it does not assume an email address.
 *
 * A 6-digit PIN is only a million combinations, so the hash has to be slow and
 * the endpoint has to be rate limited. Both are handled here and in the route.
 */

const KEY_LENGTH = 64;
const SCRYPT_COST = { N: 16384, r: 8, p: 1 };

export function hashPin(pin: string): string {
  const salt = randomBytes(16);
  const derived = scryptSync(pin, salt, KEY_LENGTH, SCRYPT_COST);
  return `${salt.toString("hex")}:${derived.toString("hex")}`;
}

export function verifyPin(pin: string, stored: string | null): boolean {
  if (!stored) return false;

  const [saltHex, keyHex] = stored.split(":");
  if (!saltHex || !keyHex) return false;

  const derived = scryptSync(
    pin,
    Buffer.from(saltHex, "hex"),
    KEY_LENGTH,
    SCRYPT_COST
  );
  const expected = Buffer.from(keyHex, "hex");

  return derived.length === expected.length && timingSafeEqual(derived, expected);
}

export const FARMER_COOKIE = "kh_farmer";

const encoder = new TextEncoder();
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // a month; farmers check seasonally

function requireSecret(): string {
  const value = process.env.FARMER_SESSION_SECRET;
  if (!value) {
    // Fail closed rather than sign sessions with a guessable default.
    throw new Error("FARMER_SESSION_SECRET is not set — see .env.example");
  }
  return value;
}

async function sign(payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(requireSecret()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  return Buffer.from(signature).toString("base64url");
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function issueFarmerSession(farmerId: string): Promise<string> {
  const payload = `${farmerId}|${Date.now() + SESSION_TTL_MS}`;
  return `${Buffer.from(payload).toString("base64url")}.${await sign(payload)}`;
}

/** Returns the farmer id, or null if the cookie is absent, forged or expired. */
export async function readFarmerSession(
  token: string | undefined
): Promise<string | null> {
  if (!token) return null;

  const [encoded, signature] = token.split(".");
  if (!encoded || !signature) return null;

  let payload: string;
  try {
    payload = Buffer.from(encoded, "base64url").toString("utf8");
  } catch {
    return null;
  }

  if (!constantTimeEqual(signature, await sign(payload))) return null;

  const [farmerId, expiresAt] = payload.split("|");
  if (!farmerId || Number(expiresAt) < Date.now()) return null;

  return farmerId;
}

export const farmerCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
  maxAge: SESSION_TTL_MS / 1000,
};

/**
 * In-memory rate limit on PIN attempts, keyed by phone number.
 *
 * A 6-digit PIN falls to brute force in minutes without this. In-memory means
 * it resets on deploy and does not work across instances — acceptable for a
 * single-node sprint deployment, and called out in CLAUDE.md as something a
 * real deployment must replace with a shared store.
 */
const ATTEMPT_WINDOW_MS = 15 * 60 * 1000;
const MAX_ATTEMPTS = 5;
const attempts = new Map<string, { count: number; firstAt: number }>();

export function rateLimitPin(key: string): { allowed: boolean; retryAfterMs: number } {
  const now = Date.now();
  const record = attempts.get(key);

  if (!record || now - record.firstAt > ATTEMPT_WINDOW_MS) {
    attempts.set(key, { count: 1, firstAt: now });
    return { allowed: true, retryAfterMs: 0 };
  }

  record.count += 1;
  if (record.count > MAX_ATTEMPTS) {
    return {
      allowed: false,
      retryAfterMs: ATTEMPT_WINDOW_MS - (now - record.firstAt),
    };
  }
  return { allowed: true, retryAfterMs: 0 };
}

export function clearPinAttempts(key: string): void {
  attempts.delete(key);
}
