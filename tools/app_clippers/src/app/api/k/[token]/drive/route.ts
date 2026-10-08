import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { cibleClipper, LIBELLES_STATUT, TUILES, type Statut } from "@/lib/drive";

export const dynamic = "force-dynamic";

export type EtatTuile = { racine: string; courant: string[]; statut: Statut; libelle: string; fichiers: number };

/** L'état des quatre tuiles : la racine ouverte, le dossier du moment et son état (✅ plein · ⏳ en cours · ❌ vide). */
export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  const out: Record<string, EtatTuile> = {};
  await Promise.all(TUILES.map(async (t) => {
    try { const x = await cibleClipper(c, t); out[t] = { racine: x.racine, courant: x.courant, statut: x.statut, libelle: LIBELLES_STATUT[x.statut], fichiers: x.fichiers }; }
    catch { out[t] = { racine: "", courant: [], statut: "inconnu", libelle: LIBELLES_STATUT.inconnu, fichiers: 0 }; }
  }));
  return NextResponse.json(out, { headers: { "Cache-Control": "private, no-store" } });
}
