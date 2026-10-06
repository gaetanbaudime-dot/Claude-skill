import Logo from "@/components/Logo";

export default function Accueil() {
  return (
    <main className="min-h-dvh flex flex-col items-center justify-center px-8 text-center">
      <Logo taille={88} />
      <h1 className="titre-argent text-3xl font-bold mt-6">G&M</h1>
      <p className="text-argent2 mt-3 max-w-xs leading-relaxed">Ouvre le lien personnel que l'agence t'a envoyé pour accéder à ton espace.</p>
      <p className="text-argent2/70 text-sm mt-6 max-w-xs leading-relaxed">Tu arrives ici depuis l'icône de ton écran d'accueil ? Supprime-la, ouvre ton lien personnel dans Safari ou Chrome et ajoute-la à nouveau : elle s'ouvrira directement sur ton espace.</p>
    </main>
  );
}
