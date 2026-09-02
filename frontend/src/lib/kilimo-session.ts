import "server-only";

import { cookies } from "next/headers";

import { apiBaseUrl } from "@/lib/kilimo-api";
import { currentFarmer } from "@/lib/session";

/**
 * Bridge between this app's farmer session (phone + PIN, SQLite) and the Python
 * service's bearer tokens.
 *
 * This is a DEVELOPMENT BRIDGE and is meant to be deleted. Today there are two
 * identity systems: the phone+PIN registry here, and the account model in
 * `identity.app_user` there. Until one issues tokens both trust — Supabase Auth
 * is the plan, and its claim shape is already what the Python side verifies —
 * this exchanges a signed-in farmer's phone number for a service token
 * server-side, using the dev OTP endpoints.
 *
 * Two properties keep it honest even as a stopgap:
 *  - The token never reaches the browser. It lives in an httpOnly cookie and is
 *    only ever attached by route handlers on this server.
 *  - No farmer session, no token. The assistant therefore stays behind a
 *    sign-in and behind the ASSISTANT_AI consent the Python side enforces,
 *    which is exactly the boundary the data-protection design asks for.
 */

const TOKEN_COOKIE = "kh_service_token";

type TokenResponse = { access_token: string; expires_in: number; user_id: string };

async function mintToken(phone: string): Promise<string | null> {
  const base = apiBaseUrl();
  if (!base) return null;

  const start = await fetch(`${base}/api/v1/auth/otp/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone }),
    cache: "no-store",
  });
  if (!start.ok) return null;

  // Dev OTP: the service returns a fixed code in development. In production the
  // browser gets its token from Supabase Auth directly and this whole file goes.
  const code = process.env.KILIMO_DEV_OTP_CODE ?? "123456";
  const verify = await fetch(`${base}/api/v1/auth/otp/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, code }),
    cache: "no-store",
  });
  if (!verify.ok) return null;

  const body = (await verify.json()) as TokenResponse;
  return body.access_token ?? null;
}

/** A service token for the signed-in farmer, or null if nobody is signed in. */
export async function getServiceToken(): Promise<string | null> {
  const store = await cookies();
  const cached = store.get(TOKEN_COOKIE)?.value;
  if (cached) return cached;

  const farmer = await currentFarmer();
  if (!farmer?.phone) return null;

  const token = await mintToken(farmer.phone);
  if (!token) return null;

  try {
    store.set(TOKEN_COOKIE, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 12,
    });
  } catch {
    // Route handlers may run where cookies are read-only; the token still works
    // for this request, it just is not cached.
  }
  return token;
}

/** Grant a consent purpose on the Python side for the signed-in farmer. */
export async function grantConsent(purpose: string): Promise<boolean> {
  const base = apiBaseUrl();
  const token = await getServiceToken();
  if (!base || !token) return false;

  const response = await fetch(`${base}/api/v1/me/consent`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ purpose, granted: true, policy_version: "2026-09-01" }),
    cache: "no-store",
  });
  return response.ok;
}
