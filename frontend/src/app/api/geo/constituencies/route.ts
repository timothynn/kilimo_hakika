import { NextResponse } from "next/server";

import { DepotApiError, getConstituencies } from "@/lib/depot-api";

export const runtime = "nodejs";

/**
 * Proxy for the verdict engine's reference geography.
 *
 * The wizard needs the cascade client-side, but the full 47/290/1450 tree is
 * ~250KB — far too much to push to a farmer on a rural connection. Fetching
 * one county's constituencies is a few hundred bytes. Proxied rather than
 * called directly so the upstream URL stays server-side.
 */
export async function GET(request: Request) {
  const county = new URL(request.url).searchParams.get("county");
  if (!county) {
    return NextResponse.json({ error: "county is required" }, { status: 400 });
  }

  try {
    return NextResponse.json(await getConstituencies(county));
  } catch (error) {
    if (error instanceof DepotApiError) {
      return NextResponse.json(
        { error: error.message },
        { status: error.unreachable ? 503 : error.status }
      );
    }
    throw error;
  }
}
