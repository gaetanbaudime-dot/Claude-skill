/** 12/10 : les comptes Instagram du clipper (onglet « Comptes app » publié par le bot) et ses demandes de changement de @.
 *  GET : { comptes, demandes, tl } ; POST { n, handle } : ajoute la demande à « Pseudos app », le bot l'applique sous 15 minutes
 *  avec la règle de `!pseudo`. 5 demandes par minute et par clipper au plus. */
import { NextRequest, NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { demanderPseudo, mesComptes, mesDemandes, nettoyerHandle } from "@/lib/comptesApp";

export const dynamic = "force-dynamic";
const ENTETES = { "Cache-Control": "private, no-store" };
const recents = new Map<string, number[]>();

export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const [m, demandes] = await Promise.all([mesComptes(c.cle), mesDemandes(c.cle)]);
    return NextResponse.json({ comptes: m.comptes, tl: m.tl, demandes }, { headers: ENTETES });
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
  if (!Number.isInteger(n) || n < 1 || n > 3) return NextResponse.json({ erreur: "Numéro de compte invalide." }, { status: 400, headers: ENTETES });
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
