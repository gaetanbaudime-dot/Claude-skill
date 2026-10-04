import { NextResponse } from "next/server";
import { creatriceParJeton } from "@/lib/config";
import { cible, TYPES } from "@/lib/drive";

export const dynamic = "force-dynamic";

/** Les quatre destinations du moment (libellés), pour les afficher sous les boutons. */
export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = creatriceParJeton(params.token);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  const out: Record<string, { chemin: string[]; complet: boolean }> = {};
  await Promise.all(TYPES.map(async (t) => {
    try { const x = await cible(c, t); out[t] = { chemin: x.chemin, complet: x.complet }; }
    catch { out[t] = { chemin: [], complet: false }; }
  }));
  return NextResponse.json(out, { headers: { "Cache-Control": "private, no-store" } });
}
