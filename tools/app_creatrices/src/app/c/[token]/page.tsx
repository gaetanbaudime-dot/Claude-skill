import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { creatriceParJeton } from "@/lib/config";
import App from "@/components/App";

export const dynamic = "force-dynamic";

/** Le manifeste de cette créatrice (start_url avec son jeton) remplace le manifeste global :
 *  c'est lui qu'iOS lit quand elle ajoute l'app à son écran d'accueil. */
export function generateMetadata({ params }: { params: { token: string } }): Metadata {
  const c = creatriceParJeton(params.token);
  if (!c) return {};
  return {
    manifest: `/c/${c.jeton}/manifest.webmanifest`,
    appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "G&M", startupImage: ["/icones/splash-1170x2532.png"] },
  };
}

export default function Espace({ params }: { params: { token: string } }) {
  const c = creatriceParJeton(params.token);
  if (!c) notFound();
  return <App prenom={c.prenom} jeton={c.jeton} mym={Boolean(c.feed || c.scripts)} />;
}
