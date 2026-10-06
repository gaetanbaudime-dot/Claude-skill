/** Pour l'agence seulement : « prénom → lien personnel » de tous les clippers connus de GAML, afin de distribuer les liens
 *  (à la main ou par le bot Discord). Protégée par ADMIN_SECRET (`?cle=…`) ; sans la bonne clé, 404 muet.
 *  `?format=texte` renvoie une ligne par clipper, prête à coller. */
import { timingSafeEqual } from "crypto";
import { NextRequest, NextResponse } from "next/server";
import { clippers } from "@/lib/clippers";

export const dynamic = "force-dynamic";

function cleValide(cle: string): boolean {
  const attendu = process.env.ADMIN_SECRET || "";
  if (!attendu || !cle || cle.length !== attendu.length) return false;
  return timingSafeEqual(Buffer.from(cle), Buffer.from(attendu));
}

export async function GET(req: NextRequest) {
  if (!cleValide(req.nextUrl.searchParams.get("cle") || "")) return new NextResponse(null, { status: 404 });
  const hote = req.headers.get("x-forwarded-host") || req.headers.get("host") || "";
  const base = hote ? `https://${hote}` : "";
  let liste;
  try { liste = await clippers(); }
  catch (e) { return NextResponse.json({ erreur: "GAML indisponible", detail: (e as Error).message }, { status: 503 }); }
  const entetes = { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" };
  if (req.nextUrl.searchParams.get("format") === "texte") {
    const lignes = liste.map((c) => `${c.prenom} (${c.creatrice}) : ${base}/k/${c.jeton}`);
    return new NextResponse(lignes.join("\n") + "\n", { headers: { ...entetes, "Content-Type": "text/plain; charset=utf-8" } });
  }
  const out: Record<string, { creatrice: string; url: string; liens: string[] }> = {};
  for (const c of liste) out[c.prenom] = { creatrice: c.creatrice, url: `${base}/k/${c.jeton}`, liens: c.liens.map((l) => l.url) };
  return NextResponse.json(out, { headers: entetes });
}
