import Logo from "@/components/Logo";

export default function Introuvable() {
  return (
    <main className="min-h-dvh flex flex-col items-center justify-center px-8 text-center">
      <Logo taille={72} />
      <h1 className="titre-argent text-2xl font-bold mt-6">Lien invalide</h1>
      <p className="text-argent2 mt-3 max-w-xs leading-relaxed">Ce lien ne correspond à aucun espace. Demande ton lien personnel à l'agence.</p>
    </main>
  );
}
