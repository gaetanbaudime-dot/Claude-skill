/** 12/10 : l'équipe d'un Team Leader — ses clippers et leurs comptes Instagram (onglet « Comptes app »), avec leurs visites payées
 *  de la période et la prime en cours (onglet « Équipes », écrit par le bot à chaque relecture des clics). 404 si ce n'est pas un TL. */
import { NextResponse } from "next/server";
import { clipperParJeton, normaliser } from "@/lib/clippers";
import { monEquipe } from "@/lib/comptesApp";
import { equipeDe } from "@/lib/equipes";
import { pilotage } from "@/lib/pilotage";
import { pilotageEquipe } from "@/lib/classement";
import { comptesAffiches } from "@/lib/comptesVisibles";
import { comptesReels } from "@/lib/comptesReels";

export const dynamic = "force-dynamic";
const ENTETES = { "Cache-Control": "private, no-store" };

export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const [membres, eq] = await Promise.all([monEquipe(c.cle), equipeDe(c.cle).catch(() => null)]);
    if (!membres.length) return NextResponse.json({ erreur: "pas de team leader" }, { status: 404, headers: ENTETES });
    // 24/10 (Gaëtan : « pars du sheet ») : les comptes de chaque clipper selon le LOG DASHBOARD, n° 4+ et @ hors fiche compris,
    // et le pilotage de l'équipe sur tous ses comptes actifs (plus seulement les n° 1 à 3)
    const d = await pilotage().catch(() => null);
    const reels = membres.map((m) => ({ ...m, comptes: comptesAffiches(comptesReels(m.prenom, m.comptes, d?.comptes ?? null)) }));
    const donnees = d ? (() => { try { return pilotageEquipe(d, reels, { tousActifs: true }); } catch { return null; } })() : null;
    const stats = new Map<string, { visites: number | null; auSeuil: boolean; manquants: number }>();
    for (const e of eq?.equipes || []) for (const m of e.membres) stats.set(normaliser(m.prenom).split(" ")[0], m);
    const seuil = eq?.equipes?.[0]?.seuil || 500;
    return NextResponse.json({
      seuil, prime: eq?.prime ?? null, primee: eq?.primee ?? null, debut: eq?.debut || "", fin: eq?.fin || "",
      membres: reels.map((m) => ({ ...m, ...(stats.get(normaliser(m.prenom).split(" ")[0]) || { visites: null, auSeuil: false, manquants: 0 }) })),
      pilotage: donnees,
    }, { headers: ENTETES });
  } catch (e) {
    return NextResponse.json({ erreur: "équipe en cours de mise à jour", detail: (e as Error).message }, { status: 503, headers: ENTETES });
  }
}
