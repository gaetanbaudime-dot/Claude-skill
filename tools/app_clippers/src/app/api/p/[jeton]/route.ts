/** GET /api/p/<jeton> : les tables du pilotage (lib/pilotage.ts), pour Gaëtan seulement. Un jeton faux → 404 muet. */
import { NextResponse } from "next/server";
import { jetonValide, pilotage } from "@/lib/pilotage";

export const dynamic = "force-dynamic";

const ENTETES = { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" };

export async function GET(_req: Request, { params }: { params: { jeton: string } }) {
  if (!jetonValide(params.jeton)) return new NextResponse(null, { status: 404 });
  try {
    return NextResponse.json(await pilotage(), { headers: ENTETES });
  } catch (e) {
    console.warn("pilotage :", (e as Error).message);
    return NextResponse.json({ erreur: "tableur indisponible" }, { status: 503, headers: ENTETES });
  }
}
