import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { clipperParJeton } from "@/lib/clippers";
import App from "@/components/App";
import Logo from "@/components/Logo";

export const dynamic = "force-dynamic";

/** Le manifeste de ce clipper (start_url avec son jeton) remplace le manifeste global :
 *  c'est lui qu'iOS et Android lisent quand il ajoute l'app à son écran d'accueil. */
export async function generateMetadata({ params }: { params: { token: string } }): Promise<Metadata> {
  const c = await clipperParJeton(params.token).catch(() => null);
  if (!c) return {};
  return {
    manifest: `/k/${c.jeton}/manifest.webmanifest`,
    appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "G&M", startupImage: ["/icones/splash-1170x2532.png"] },
  };
}

export default async function Espace({ params }: { params: { token: string } }) {
  let c = null, panne = false;
  try { c = await clipperParJeton(params.token); } catch { panne = true; }      // GAML injoignable : on ne dit pas « lien invalide » à tort
  if (!c && !panne) notFound();
  if (!c) {
    return (
      <main className="min-h-dvh flex flex-col items-center justify-center px-8 text-center">
        <Logo taille={72} />
        <h1 className="titre-argent text-2xl font-bold mt-6">Une minute…</h1>
        <p className="text-argent2 mt-3 max-w-xs leading-relaxed">Les chiffres sont en cours de mise à jour. Réouvre l'app dans une minute.</p>
      </main>
    );
  }
  return <App prenom={c.prenom} creatrice={c.creatrice} jeton={c.jeton} />;
}
