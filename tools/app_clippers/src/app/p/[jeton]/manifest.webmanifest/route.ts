/** Manifeste du pilotage : start_url avec le jeton, pour que l'icône de l'écran d'accueil ouvre le tableau de Gaëtan. */
import { NextResponse } from "next/server";
import { jetonValide } from "@/lib/pilotage";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { jeton: string } }) {
  if (!jetonValide(params.jeton)) return new NextResponse("introuvable", { status: 404 });
  const chemin = `/p/${params.jeton}`;
  return NextResponse.json({
    id: chemin, name: "Pilotage G&M", short_name: "Pilotage", lang: "fr", start_url: chemin, scope: "/", display: "standalone",
    orientation: "portrait", background_color: "#070f1c", theme_color: "#070f1c",
    icons: [
      { src: "/icones/icone-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icones/icone-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icones/icone-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icones/icone-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  }, { headers: { "Content-Type": "application/manifest+json; charset=utf-8", "Cache-Control": "private, no-store" } });
}
