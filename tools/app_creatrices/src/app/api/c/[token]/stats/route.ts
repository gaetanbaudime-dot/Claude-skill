import { NextRequest, NextResponse } from "next/server";
import { creatriceParJeton } from "@/lib/config";
import { stats } from "@/lib/stats";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, { params }: { params: { token: string } }) {
  const c = creatriceParJeton(params.token);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  const cle = req.nextUrl.searchParams.get("periode") || "hier";
  try {
    const s = await stats(c, cle);
    return NextResponse.json(s, { headers: { "Cache-Control": "private, no-store" } });
  } catch (e) {
    return NextResponse.json({ erreur: "données indisponibles", detail: (e as Error).message }, { status: 502 });
  }
}
