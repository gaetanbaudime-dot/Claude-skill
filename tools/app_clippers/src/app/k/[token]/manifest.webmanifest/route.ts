/** Manifeste d'app web propre à chaque clipper.
 *  iOS « Sur l'écran d'accueil » et Android « Ajouter à l'écran d'accueil » n'enregistrent pas l'adresse de la page mais le
 *  `start_url` du manifeste : avec un manifeste global (start_url « / »), l'icône ouvrirait la page d'accueil générique.
 *  Ici le start_url porte le jeton du clipper, donc l'icône ouvre directement son espace.
 *  Android Chrome : `theme_color`, icônes 192 et 512 en `any` et en `maskable` (entrées séparées), `display: standalone`. */
import { NextResponse } from "next/server";
import { clipperParJeton } from "@/lib/clippers";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { token: string } }) {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return new NextResponse("introuvable", { status: 404 });
  const chemin = `/k/${c.jeton}`;
  const manifeste = {
    id: chemin,
    name: "G&M",
    short_name: "G&M",
    description: `Ton espace clipper G&M, ${c.prenom} : Drive, Reels, versements.`,
    lang: "fr",
    start_url: chemin,
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#070f1c",
    theme_color: "#070f1c",
    icons: [
      { src: "/icones/icone-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icones/icone-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icones/icone-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icones/icone-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
  return NextResponse.json(manifeste, {
    headers: { "Content-Type": "application/manifest+json; charset=utf-8", "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" },
  });
}
