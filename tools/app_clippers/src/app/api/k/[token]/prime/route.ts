/** 24/10 (Gaëtan : « dans les versements, un truc par rapport à l'objectif ») : les Reels de la période de paie en cours sur les
 *  comptes de croissance du clipper, pour la carte « Prime volume » de l'onglet Versements. Les clics payés, eux, viennent de
 *  /versements (GAML) : cette route ne lit que l'onglet « Comptes app », donc une panne Google ne casse jamais les versements. */
import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { mesComptes } from "@/lib/comptesApp";
import { comptesAffiches } from "@/lib/comptesVisibles";
import { comptesReels } from "@/lib/comptesReels";
import { pilotage } from "@/lib/pilotage";
import { suiviIg } from "@/lib/igSource";
import { appliquerIg, porteursDeLien } from "@/lib/igSuivi";
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
    // 24/10 : les mêmes comptes que l'onglet Comptes (LOG DASHBOARD, lib/comptesReels) et les chiffres du suivi RapidAPI
    const [{ comptes }, stats, ig] = await Promise.all([mesComptes(c.cle), pilotage().catch(() => null), suiviIg(aujourdhui).catch(() => null)]);
    const liens = porteursDeLien(stats?.comptes ?? []);
    const miens = comptesAffiches(comptesReels(c.prenom, comptes, stats?.comptes ?? null).map((x) => appliquerIg(x, ig, aujourdhui, liens)));
    return NextResponse.json(reelsPrime(miens, p.debut, p.fin, aujourdhui), { headers: ENTETES });
  } catch (e) {
    return NextResponse.json({ erreur: "Reels en cours de mise à jour", detail: (e as Error).message }, { status: 503, headers: ENTETES });
  }
}
