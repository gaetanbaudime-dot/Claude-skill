/** L'adresse USDC (ERC-20) du clipper : GET la renvoie (ou null), POST {adresse} l'enregistre après validation.
 *  Au plus 5 enregistrements par clipper et par minute. Jamais de détail d'erreur côté clipper. */
import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { adresseValide, enregistrerAdresse, lire } from "@/lib/adresses";

export const dynamic = "force-dynamic";
const compteur = new Map<string, { n: number; minute: number }>();

export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  try {
    const a = await lire(c);
    return NextResponse.json({ adresse: a?.adresse || null, majLe: a?.majLe || null }, { headers: { "Cache-Control": "private, no-store" } });
  } catch {
    return NextResponse.json({ adresse: null, majLe: null, indisponible: true }, { headers: { "Cache-Control": "private, no-store" } });
  }
}

export async function POST(req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404 });
  const minute = Math.floor(Date.now() / 60000);
  const x = compteur.get(c.jeton);
  const n = x && x.minute === minute ? x.n + 1 : 1;
  compteur.set(c.jeton, { n, minute });
  if (n > 5) return NextResponse.json({ erreur: "trop d'essais, attends une minute" }, { status: 429 });
  let brut = "";
  try { brut = String(((await req.json()) as { adresse?: unknown }).adresse || ""); } catch { return NextResponse.json({ erreur: "requête invalide" }, { status: 400 }); }
  const adresse = adresseValide(brut);
  if (!adresse) return NextResponse.json({ erreur: "Ce n'est pas une adresse USDC ERC-20 : elle commence par 0x et fait 42 caractères." }, { status: 400 });
  try {
    const a = await enregistrerAdresse(c, adresse);
    return NextResponse.json({ ok: true, adresse: a.adresse, majLe: a.majLe }, { headers: { "Cache-Control": "private, no-store" } });
  } catch (e) {
    console.warn("adresse :", (e as Error).message);
    return NextResponse.json({ erreur: "Enregistrement impossible pour l'instant, réessaie dans une minute." }, { status: 503 });
  }
}
