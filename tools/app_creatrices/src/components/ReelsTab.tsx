import Logo from "./Logo";

// The canonical module keeps all personal apps on the same verified release.
// Do not include the personal app token or any credentials in this public URL.
const DUPLICATEUR_URL = "https://duplicateur-de-reels.vercel.app";

export default function ReelsTab() {
  return (
    <section className="apparait carte mt-2 px-6 py-10 flex flex-col items-center text-center">
      <Logo taille={64} />
      <h2 className="titre-argent text-xl font-bold mt-5">Duplicateur de Reels</h2>
      <p className="text-argent2 mt-2 max-w-xs leading-relaxed">Importe ton Reel et récupère six variantes HD avec sous-titres, prêtes à publier.</p>
      <a href={DUPLICATEUR_URL} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer"
         className="mt-6 inline-flex min-h-12 w-full max-w-xs items-center justify-center rounded-2xl bg-white px-5 py-3 font-semibold text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white">
        Créer mes 6 variantes
        <span className="sr-only"> — ouvre un nouvel onglet</span>
      </a>
      <p className="mt-4 max-w-xs text-[13px] leading-relaxed text-argent2">Un nouvel onglet garde ton montage ouvert pendant que tu utilises l’app. Tu peux télécharger chaque vidéo ou les six ensemble.</p>
    </section>
  );
}
