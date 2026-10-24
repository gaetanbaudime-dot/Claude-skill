/** 24/10 (Gaëtan : « assure-toi que ça marche une bonne fois pour toutes ») : la clé Google de l'app, sur Vercel, a été refusée du
 *  22 au 24/10 sans que personne le voie : l'onglet Comptes restait « en cours de mise à jour ». Cette route dit si Google accepte
 *  la clé ; le bot l'interroge toutes les 5 minutes et alerte le salon admin (bot_discord.surveiller_google). Rien de secret :
 *  la raison donnée par Google et le début de l'identifiant public de la clé. */
import { NextResponse } from "next/server";
import { jetonGoogle } from "@/lib/google";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    await jetonGoogle();
    return NextResponse.json({ google: "ok" }, { headers: { "Cache-Control": "no-store" } });
  } catch (e) {
    return NextResponse.json({ google: "refusée", detail: (e as Error).message.slice(0, 200) }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
