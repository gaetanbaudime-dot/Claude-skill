import { NextRequest, NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";
import { connexionMetricool, demanderMetricool, etatsMetricool } from "@/lib/metricool";

export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer" };
type Contexte = { params: { token: string } };

export async function GET(req: NextRequest, { params }: Contexte) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404, headers });
  try {
    if (req.nextUrl.searchParams.has("n")) {
      const n = Number(req.nextUrl.searchParams.get("n"));
      const url = Number.isInteger(n) && n >= 1 && n <= 3 ? await connexionMetricool(c.cle, n) : null;
      return url ? new NextResponse(null, { status: 303, headers: { ...headers, Location: url } }) :
        NextResponse.json({ erreur: "Connexion indisponible : recharge tes comptes ou demande à l’agence de renouveler le lien." }, { status: 403, headers });
    }
    return NextResponse.json({ comptes: await etatsMetricool(c.cle) }, { headers });
  } catch {
    return NextResponse.json({ erreur: "Metricool est momentanément indisponible." }, { status: 503, headers });
  }
}

export async function POST(req: NextRequest, { params }: Contexte) {
  // Refuse les formulaires et les requêtes provenant d'une autre origine.
  if (!req.headers.get("content-type")?.startsWith("application/json") ||
      (req.headers.get("origin") && req.headers.get("origin") !== req.nextUrl.origin)) {
    return NextResponse.json({ erreur: "Requête invalide." }, { status: 403, headers });
  }
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return NextResponse.json({ erreur: "lien invalide" }, { status: 404, headers });
  let corps;
  try { corps = await req.json(); } catch { return NextResponse.json({ erreur: "Requête invalide." }, { status: 400, headers }); }
  const n = corps?.n;
  if (!Number.isInteger(n) || n < 1 || n > 3) return NextResponse.json({ erreur: "Compte invalide." }, { status: 400, headers });
  try {
    if (!await demanderMetricool(c.cle, n)) return NextResponse.json({ erreur: "Il faut au moins 500 abonnés vérifiés depuis moins de 48 h, sans changement de @ en cours." }, { status: 403, headers });
    return NextResponse.json({ ok: true }, { headers });
  } catch {
    return NextResponse.json({ erreur: "La demande n’a pas pu être enregistrée. Réessaie." }, { status: 503, headers });
  }
}
