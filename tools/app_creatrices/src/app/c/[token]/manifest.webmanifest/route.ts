/** Manifeste d'app web propre à chaque créatrice.
 *  iOS « Sur l'écran d'accueil » n'enregistre pas l'adresse de la page mais le `start_url` du manifeste :
 *  avec le manifeste global (start_url « / »), l'icône ouvrait la page d'accueil générique au lieu de l'espace de la créatrice.
 *  Ici le start_url porte son jeton, donc l'icône ouvre directement son espace. */
import { NextResponse } from "next/server";
import { creatriceParJeton } from "@/lib/config";

export const dynamic = "force-dynamic";

export function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = creatriceParJeton(params.token);
  if (!c) return new NextResponse("introuvable", { status: 404 });
  const chemin = `/c/${c.jeton}`;
  const manifeste = {
    id: chemin,
    name: "G&M",
    short_name: "G&M",
    description: `Ton espace créatrice G&M, ${c.prenom} : Drive, Reels, statistiques.`,
    lang: "fr",
    start_url: chemin,
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#070f1c",
    theme_color: "#070f1c",
    icons: [
      { src: "/icones/icone-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icones/icone-512.png", sizes: "512x512", type: "image/png", purpose: "any maskable" },
    ],
  };
  return NextResponse.json(manifeste, {
    headers: { "Content-Type": "application/manifest+json; charset=utf-8", "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" },
  });
}
