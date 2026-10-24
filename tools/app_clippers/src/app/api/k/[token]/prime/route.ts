/** 24/10 (Gaëtan : « dans les versements, un truc par rapport à l'objectif ») : les Reels de la période de paie en cours sur les
 *  comptes de croissance du clipper, pour la carte « Prime volume » de l'onglet Versements. Les clics payés, eux, viennent de
 *  /versements (GAML) : cette route ne lit que l'onglet « Comptes app », donc une panne Google ne casse jamais les versements. */
import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { mesComptes } from "@/lib/comptesApp";
import { comptesAffiches } from "@/lib/comptesVisibles";
import { reelsPrime } from "@/lib/activite";
import { aujourdhuiParis } from "@/lib/dates";
import { periodeEnCours } from "@/lib/paie";

export const dynamic = "force-dynamic";
const ENTETES = { "Cache-Control": "private, no-store" };

export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const aujourdhui = aujourdhuiParis();
    const p = periodeEnCours(aujourdhui);
    const { comptes } = await mesComptes(c.cle);
    return NextResponse.json(reelsPrime(comptesAffiches(comptes), p.debut, p.fin, aujourdhui), { headers: ENTETES });
  } catch (e) {
    return NextResponse.json({ erreur: "Reels en cours de mise à jour", detail: (e as Error).message }, { status: 503, headers: ENTETES });
  }
}
