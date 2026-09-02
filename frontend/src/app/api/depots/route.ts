import { NextResponse } from "next/server";

import { DepotApiError, getDepots } from "@/lib/depot-api";

export const runtime = "nodejs";

/**
 * Gazetted Government (NCPB) depots, filtered to those whose catchment covers
 * a county. Only Government depots are ever listed — this is not a vendor
 * directory and carries no commercial listings of any kind.
 */
export async function GET(request: Request) {
  const county = new URL(request.url).searchParams.get("county") ?? undefined;

  try {
    return NextResponse.json(await getDepots(county));
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
