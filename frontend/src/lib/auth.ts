/**
 * Admin gate for the depot-officer platform.
 *
 * This is a single shared passphrase. It is honest about what it is: enough
 * to keep the officer console off the open internet for a sprint demo, and
 * NOT enough for real farmer data. There is no per-officer identity, so
 * there is no audit trail of who looked at whom — which is exactly what you
 * want before a registry of national IDs goes anywhere near production.
 * See CLAUDE.md, "Data protection", before deploying this.
 *
 * Uses Web Crypto so the same code runs in middleware and in route handlers.
 */

export const ADMIN_COOKIE = "kh_admin";

const encoder = new TextEncoder();

function requireSecret(name: "ADMIN_PASSPHRASE" | "ADMIN_SESSION_SECRET") {
  const value = process.env[name];
  if (!value) {
    // Fail closed. A default would silently ship an unlocked console.
    throw new Error(`${name} is not set — see .env.example`);
  }
  return value;
}

async function hmac(payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(requireSecret("ADMIN_SESSION_SECRET")),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(payload)
  );
  return Buffer.from(signature).toString("base64url");
}

/** Constant-time compare, so a wrong passphrase leaks nothing via timing. */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export function checkPassphrase(candidate: string): boolean {
  return timingSafeEqual(candidate, requireSecret("ADMIN_PASSPHRASE"));
}

const SESSION_TTL_MS = 8 * 60 * 60 * 1000; // one working day at the gate

export async function issueSession(): Promise<string> {
  const expiresAt = Date.now() + SESSION_TTL_MS;
  const payload = String(expiresAt);
  return `${payload}.${await hmac(payload)}`;
}

export async function verifySession(
  token: string | undefined
): Promise<boolean> {
  if (!token) return false;

  const [payload, signature] = token.split(".");
  if (!payload || !signature) return false;

  const expected = await hmac(payload);
  if (!timingSafeEqual(signature, expected)) return false;

  const expiresAt = Number(payload);
  return Number.isFinite(expiresAt) && Date.now() < expiresAt;
}

export const sessionCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
  maxAge: SESSION_TTL_MS / 1000,
};
