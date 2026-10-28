/** 12/10 : les comptes Instagram du clipper (onglet « Comptes app » publié par le bot) et ses demandes de changement de @.
 *  GET : { comptes, demandes, tl } ; POST { n, handle } : ajoute la demande à « Pseudos app », le bot l'applique sous 15 minutes
 *  avec la règle de `!pseudo`. 5 demandes par minute et par clipper au plus.
 *  24/10 : `comptes` = tous les comptes qu'il gère selon le LOG DASHBOARD (comptesReels, puis comptesAffiches : n° 4+ compris,
 *  sans BAN ni ancien @) ; le pilotage
 *  personnel garde sa règle des n° 1 à 3. Un @ se corrige sur n'importe lequel de ses comptes, le bot vérifie qu'il est à lui. */
import { NextRequest, NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { demanderPseudo, mesComptes, mesDemandes, nettoyerHandle } from "@/lib/comptesApp";
import { comptesAffiches } from "@/lib/comptesVisibles";
import { comptesReels } from "@/lib/comptesReels";
import { pilotage } from "@/lib/pilotage";
import { pilotageEquipe } from "@/lib/classement";
import { semaine } from "@/lib/activite";
import { suiviIg } from "@/lib/igSource";
import { appliquerIg, porteursDeLien } from "@/lib/igSuivi";
import { aujourdhuiParis } from "@/lib/dates";
import { regimeDe } from "@/lib/regimes";

export const dynamic = "force-dynamic";
const ENTETES = { "Cache-Control": "private, no-store" };
const recents = new Map<string, number[]>();

export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const [m, demandes, stats, regime] = await Promise.all([mesComptes(c.cle), mesDemandes(c.cle), pilotage().catch(() => null), regimeDe(c.cle)]);
    const parcours = m.comptes.filter(x => x.n >= 1 && x.n <= 3);
    const personnel = stats ? pilotageEquipe(stats, [{ prenom: c.prenom, creatrice: c.creatrice, comptes: parcours }]) : null;
    // 24/10 : la liste part du LOG DASHBOARD (Gérant), la fiche du bot donne les n° pour corriger un @ (lib/comptesReels)
    const jour = stats?.aujourdhui || aujourdhuiParis();
    const ig = await suiviIg(jour).catch(() => null);                    // 24/10 : chiffres du suivi RapidAPI (lib/igSuivi)
    const liens = porteursDeLien(stats?.comptes ?? []);                  // le compte qui reçoit les clics est le compte du lien
    const comptes = comptesAffiches(comptesReels(c.prenom, m.comptes, stats?.comptes ?? null).map((x) => appliquerIg(x, ig, jour, liens)));
    // 24/10 : « Ma semaine » = ses Reels (inputs), vues, followers et clics payés des 7 derniers jours clos
    let clicsParJour: Record<string, number> | null = null;
    if (personnel) {
      clicsParJour = {};
      for (const k of personnel.clics) if (k.axe === "Horizontal" && k.source === "Clipper") clicsParJour[k.jour] = (clicsParJour[k.jour] || 0) + k.visites;
    }
    const sem = semaine(comptes, jour, clicsParJour);
    // 28/10 : au fixe, ses clics ne sont pas payés (« Ma semaine » ne dit plus « Payés, soit … $ »)
    return NextResponse.json({ comptes, tl: m.tl, demandes, pilotage: personnel, semaine: sem, fixe: regime?.regime === "fixe" }, { headers: ENTETES });
  } catch (e) {
    return NextResponse.json({ erreur: "comptes en cours de mise à jour", detail: (e as Error).message }, { status: 503, headers: ENTETES });
  }
}

export async function POST(req: NextRequest, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  const maintenant = Date.now();
  const miens = (recents.get(c.cle) || []).filter((t) => maintenant - t < 60_000);
  if (miens.length >= 5) return NextResponse.json({ erreur: "Trop de demandes : réessaie dans une minute." }, { status: 429, headers: ENTETES });
  let corps: { n?: unknown; handle?: unknown } = {};
  try { corps = await req.json(); } catch { /* corps vide */ }
  const n = Number(corps.n);
  const handle = nettoyerHandle(String(corps.handle || ""));
  if (!Number.isInteger(n) || n < 1 || n > 20) return NextResponse.json({ erreur: "Numéro de compte invalide." }, { status: 400, headers: ENTETES });
  if (!handle) return NextResponse.json({ erreur: "Ce @ n'est pas valide : lettres, chiffres, points et tirets bas seulement." }, { status: 400, headers: ENTETES });
  try {
    const { comptes } = await mesComptes(c.cle);
    const actuel = comptes.find((x) => x.n === n);
    if (!actuel) return NextResponse.json({ erreur: `Tu n'as pas encore de compte ${n}.` }, { status: 400, headers: ENTETES });
    if (actuel.handle === handle) return NextResponse.json({ erreur: "C'est déjà ce @." }, { status: 400, headers: ENTETES });
    await demanderPseudo(c.cle, n, handle);
    recents.set(c.cle, [...miens, maintenant]);
    return NextResponse.json({ ok: true, n, handle }, { headers: ENTETES });
  } catch (e) {
    return NextResponse.json({ erreur: "Enregistrement impossible pour l'instant, réessaie dans une minute.", detail: (e as Error).message }, { status: 503, headers: ENTETES });
  }
}
