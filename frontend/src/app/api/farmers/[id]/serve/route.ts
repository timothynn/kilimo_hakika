import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { z } from "zod";

import { ADMIN_COOKIE, verifySession } from "@/lib/auth";
import { findFarmerById, markServed } from "@/lib/db";

export const runtime = "nodejs";

const serveSchema = z.object({
  depotId: z.string().min(1),
  bags: z.number().int().nonnegative(),
  totalKes: z.number().int().nonnegative(),
  note: z.string().trim().max(500).optional(),
});

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const store = await cookies();
  if (!(await verifySession(store.get(ADMIN_COOKIE)?.value))) {
    return NextResponse.json({ error: "Not authorised" }, { status: 401 });
  }

  const { id } = await params;
  if (!findFarmerById(id)) {
    return NextResponse.json({ error: "Farmer not found" }, { status: 404 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Expected a JSON body" }, { status: 400 });
  }

  const parsed = serveSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid input", issues: parsed.error.issues },
      { status: 400 }
    );
  }

  markServed({ farmerId: id, ...parsed.data });
  return NextResponse.json({ ok: true }, { status: 201 });
}
