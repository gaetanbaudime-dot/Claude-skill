/** 12/10 : l'équipe d'un Team Leader — ses clippers et leurs comptes Instagram (onglet « Comptes app »), avec leurs visites payées
 *  de la période et la prime en cours (onglet « Équipes », écrit par le bot à chaque relecture des clics). 404 si ce n'est pas un TL. */
import { NextResponse } from "next/server";
import { clipperParJeton, normaliser } from "@/lib/clippers";
import { monEquipe } from "@/lib/comptesApp";
import { equipeDe } from "@/lib/equipes";

export const dynamic = "force-dynamic";
const ENTETES = { "Cache-Control": "private, no-store" };

export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const [membres, eq] = await Promise.all([monEquipe(c.cle), equipeDe(c.cle).catch(() => null)]);
    if (!membres.length) return NextResponse.json({ erreur: "pas de team leader" }, { status: 404, headers: ENTETES });
    const stats = new Map<string, { visites: number | null; auSeuil: boolean; manquants: number }>();
    for (const e of eq?.equipes || []) for (const m of e.membres) stats.set(normaliser(m.prenom).split(" ")[0], m);
    const seuil = eq?.equipes?.[0]?.seuil || 500;
    return NextResponse.json({
      seuil, prime: eq?.prime ?? null, primee: eq?.primee ?? null, debut: eq?.debut || "", fin: eq?.fin || "",
      membres: membres.map((m) => ({ ...m, ...(stats.get(normaliser(m.prenom).split(" ")[0]) || { visites: null, auSeuil: false, manquants: 0 }) })),
    }, { headers: ENTETES });
  } catch (e) {
    return NextResponse.json({ erreur: "équipe en cours de mise à jour", detail: (e as Error).message }, { status: 503, headers: ENTETES });
  }
}
