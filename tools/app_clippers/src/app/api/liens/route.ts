/** POST /api/liens : écrit l'onglet « Liens app » du tableur d'usage (lib/liensApp.ts), pour le bot Discord qui le lit ensuite
 *  avec le compte de service. Sans clé : la réponse ne donne que le nombre de clippers, jamais un lien ni un identifiant ;
 *  au plus une écriture par minute et par instance (la liste GAML est de toute façon en cache 10 minutes). */
import { NextResponse } from "next/server";
import { publierLiens } from "@/lib/liensApp";

export const dynamic = "force-dynamic";

const ENTETES = { "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow" };
let dernier = 0;
let dernierN = 0;

export async function POST() {
  if (Date.now() - dernier < 60_000) return NextResponse.json({ ok: true, clippers: dernierN, recent: true }, { headers: ENTETES });
  dernier = Date.now();
  try {
    dernierN = await publierLiens();
    return NextResponse.json({ ok: true, clippers: dernierN }, { headers: ENTETES });
  } catch (e) {
    dernier = 0;
    console.warn("liens app :", (e as Error).message);
    return NextResponse.json({ ok: false }, { status: 503, headers: ENTETES });
  }
}
