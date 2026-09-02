import { NextResponse } from "next/server";

import { DepotApiError, getWards } from "@/lib/depot-api";

export const runtime = "nodejs";

/** Proxy for the wards of one constituency. See ../constituencies/route.ts. */
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const county = params.get("county");
  const constituency = params.get("constituency");
  if (!county || !constituency) {
    return NextResponse.json(
      { error: "county and constituency are required" },
      { status: 400 }
    );
  }

  try {
    return NextResponse.json(await getWards(county, constituency));
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
