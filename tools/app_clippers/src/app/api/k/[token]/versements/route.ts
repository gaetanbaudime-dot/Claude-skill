import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { versements } from "@/lib/versements";

export const dynamic = "force-dynamic";

/** Les chiffres du clipper : visites francophones par jour, période en cours, prochain versement, historique.
 *  Le budget d'appels GAML est tenu côté serveur (cache des jours passés) ; la réponse elle-même n'est jamais mise en cache. */
export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const v = await versements(c);
    return NextResponse.json(v, { headers: { "Cache-Control": "private, no-store" } });
  } catch (e) {
    return NextResponse.json({ erreur: "chiffres en cours de mise à jour", detail: (e as Error).message }, { status: 503, headers: { "Cache-Control": "private, no-store" } });
  }
}
