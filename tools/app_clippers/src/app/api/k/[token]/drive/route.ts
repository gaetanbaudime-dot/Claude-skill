import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { cibleClipper, TUILES } from "@/lib/drive";

export const dynamic = "force-dynamic";

/** Le dossier racine ouvert par chacune des quatre tuiles (nom et adresse), pour vérification ; l'app n'en a pas besoin. */
export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  const out: Record<string, { racine: string; url: string } | null> = {};
  await Promise.all(TUILES.map(async (t) => {
    try { const x = await cibleClipper(c, t); out[t] = { racine: x.racine, url: x.url }; }
    catch { out[t] = null; }
  }));
  return NextResponse.json(out, { headers: { "Cache-Control": "private, no-store" } });
}
