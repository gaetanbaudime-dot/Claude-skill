/** Pour l'agence seulement : les adresses USDC enregistrées par les clippers, pour les paies du 5 et du 20.
 *  Protégée par ADMIN_SECRET (`?cle=…`) ; `?format=csv` renvoie un CSV (séparateur `;`, locale française) prêt pour Google Sheets. */
import { timingSafeEqual } from "crypto";
import { NextRequest, NextResponse } from "next/server";
import { toutes } from "@/lib/adresses";

export const dynamic = "force-dynamic";

function cleValide(cle: string): boolean {
  const attendu = process.env.ADMIN_SECRET || "";
  if (!attendu || !cle || cle.length !== attendu.length) return false;
  return timingSafeEqual(Buffer.from(cle), Buffer.from(attendu));
}

export async function GET(req: NextRequest) {
  if (!cleValide(req.nextUrl.searchParams.get("cle") || "")) return new NextResponse(null, { status: 404 });
  let liste;
  try { liste = await toutes(); }
  catch (e) { return NextResponse.json({ erreur: "tableur indisponible", detail: (e as Error).message }, { status: 503 }); }
  const entetes = { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" };
  if (req.nextUrl.searchParams.get("format") === "csv") {
    const lignes = ["prenom;creatrice;adresse_usdc;mise_a_jour", ...liste.map((a) => `${a.prenom};${a.creatrice};${a.adresse};${a.majLe}`)];
    return new NextResponse(lignes.join("\n") + "\n", { headers: { ...entetes, "Content-Type": "text/csv; charset=utf-8" } });
  }
  return NextResponse.json(liste.map(({ prenom, creatrice, adresse, majLe }) => ({ prenom, creatrice, adresse, majLe })), { headers: entetes });
}
