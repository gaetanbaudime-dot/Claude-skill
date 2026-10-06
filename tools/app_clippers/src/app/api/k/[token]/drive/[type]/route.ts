import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { cibleClipper, TUILES, urlDeSecours, type TypeTuile } from "@/lib/drive";

export const dynamic = "force-dynamic";

/** Redirige vers le bon dossier Drive : sur le téléphone, Google Drive s'ouvre directement dedans. Jamais d'erreur affichée :
 *  si la cible ne se trouve pas, on ouvre le dossier personnel du clipper. */
export async function GET(_req: Request, { params }: { params: { token: string; type: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c || !TUILES.includes(params.type as TypeTuile)) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const x = await cibleClipper(c, params.type as TypeTuile);
    return NextResponse.redirect(x.url, 302);
  } catch {
    return NextResponse.redirect(await urlDeSecours(c), 302);
  }
}
