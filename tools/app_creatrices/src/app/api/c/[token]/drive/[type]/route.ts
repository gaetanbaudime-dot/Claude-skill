import { NextResponse } from "next/server";
import { creatriceParJeton } from "@/lib/config";
import { cible, TYPES, type TypeDossier } from "@/lib/drive";

export const dynamic = "force-dynamic";

/** Redirige vers le bon dossier Drive : sur iPhone, Google Drive s'ouvre directement dedans. */
export async function GET(_req: Request, { params }: { params: { token: string; type: string } }) {
  const c = creatriceParJeton(params.token);
  if (!c || !TYPES.includes(params.type as TypeDossier)) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const x = await cible(c, params.type as TypeDossier);
    return NextResponse.redirect(x.url, 302);
  } catch {
    return NextResponse.redirect(`https://drive.google.com/drive/folders/${c.racine}`, 302);
  }
}
