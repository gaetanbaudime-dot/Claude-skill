import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { jetonValide } from "@/lib/pilotage";
import Pilotage from "@/components/pilotage/Pilotage";

export const dynamic = "force-dynamic";

/** Le manifeste du pilotage (start_url avec le jeton) : l'icône de l'écran d'accueil ouvre directement le tableau de Gaëtan. */
export async function generateMetadata({ params }: { params: { jeton: string } }): Promise<Metadata> {
  if (!jetonValide(params.jeton)) return {};
  return {
    title: "Pilotage G&M",
    manifest: `/p/${params.jeton}/manifest.webmanifest`,
    appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Pilotage" },
  };
}

export default function Page({ params }: { params: { jeton: string } }) {
  if (!jetonValide(params.jeton)) notFound();
  return <Pilotage jeton={params.jeton} />;
}
