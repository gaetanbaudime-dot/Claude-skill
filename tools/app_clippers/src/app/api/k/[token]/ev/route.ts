/** Réception d'un événement d'usage (POST {e, m}) : jeton valide, événement dans la liste fermée, puis une ligne dans le journal. */
import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { enregistrer } from "@/lib/usage";

export const dynamic = "force-dynamic";

const EVENEMENT = /^(ouverture|onglet:(drive|reels|versements)|drive:(carrousel|reels|photos|top|story|stories)|lien:copie|adresse:enregistree)$/;
const compteur = new Map<string, { n: number; minute: number }>();

export async function POST(req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return new NextResponse(null, { status: 404 });
  let e = "", m = "";
  try {
    const corps = (await req.json()) as { e?: unknown; m?: unknown };
    e = String(corps.e || ""); m = corps.m === "app" ? "app" : "navigateur";
  } catch {
    return new NextResponse(null, { status: 400 });
  }
  if (!EVENEMENT.test(e)) return new NextResponse(null, { status: 400 });
  const minute = Math.floor(Date.now() / 60000);                     // au plus 60 événements par clipper et par minute
  const x = compteur.get(c.jeton);
  const n = x && x.minute === minute ? x.n + 1 : 1;
  compteur.set(c.jeton, { n, minute });
  if (n > 60) return new NextResponse(null, { status: 204 });
  const erreur = await enregistrer(c.prenom, e, m);
  if (erreur && req.headers.get("x-debug") === "1") return NextResponse.json({ erreur }, { status: 200 });   // diagnostic, jamais visible dans l'app
  return new NextResponse(null, { status: 204 });
}
