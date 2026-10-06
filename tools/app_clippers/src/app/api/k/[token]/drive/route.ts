import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { cibleClipper, TUILES } from "@/lib/drive";

export const dynamic = "force-dynamic";

/** Les quatre destinations du moment (libellés), pour les afficher sous les tuiles. */
export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  const out: Record<string, { chemin: string[]; complet: boolean }> = {};
  await Promise.all(TUILES.map(async (t) => {
    try { const x = await cibleClipper(c, t); out[t] = { chemin: x.chemin, complet: x.complet }; }
    catch { out[t] = { chemin: [], complet: false }; }
  }));
  return NextResponse.json(out, { headers: { "Cache-Control": "private, no-store" } });
}
