"use client";
import { signaler } from "@/lib/signal";

/** Le Duplicateur de Reels s'ouvre dans son propre onglet : c'est la version
 *  maintenue (montage, finitions, enregistrement dans Photos), toujours à jour. */
export const DUPLICATEUR_URL = "https://duplicateur-de-reels.vercel.app/";

const REGLES = [
  ["10 à 30 secondes", "60 s maximum. Plus c'est court, plus c'est rapide."],
  ["La créatrice parle", "Face caméra, en français : les sous-titres viennent de sa voix."],
  ["Aucun texte à l'écran", "Pas de sous-titres, titres ou stickers déjà incrustés."],
] as const;

export default function ReelsTab({ actif, jeton }: { actif: boolean; jeton: string }) {
  if (!actif) return null;
  return (
    <section className="carte p-5 apparait" aria-label="Duplicateur de Reels">
      <div className="text-[12px] font-semibold tracking-[0.14em] text-argent2 uppercase">Duplicateur de Reels</div>
      <h2 className="titre-argent text-[22px] font-bold mt-1 leading-tight">Un Reel. Six variantes prêtes à poster.</h2>
      <p className="text-[13.5px] text-argent2 mt-2 leading-relaxed">
        Importe ton rush brut : l'IA G&amp;M le retourne, le monte et livre six vidéos HD avec des sous-titres différents, en 3 à 5 minutes.
      </p>
      <ul className="mt-4 space-y-2">
        {REGLES.map(([titre, detail]) => (
          <li key={titre} className="rounded-xl bg-white/[0.04] border border-white/[0.06] px-3.5 py-2.5">
            <div className="text-[13.5px] font-semibold text-white">{titre}</div>
            <div className="text-[12px] text-argent2 mt-0.5">{detail}</div>
          </li>
        ))}
      </ul>
      <a href={DUPLICATEUR_URL} target="_blank" rel="noopener noreferrer" onClick={() => signaler(jeton, "duplicateur:ouvrir")}
         className="mt-5 flex items-center justify-center gap-2 w-full rounded-2xl bg-white text-nuit font-semibold text-[15px] py-3.5 active:scale-[0.98] transition">
        Ouvrir le Duplicateur de Reels
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M8 16 16 8M10 8h6v6" />
        </svg>
      </a>
      <p className="text-[11.5px] text-argent2 mt-3 text-center">S'ouvre dans ton navigateur : garde la page ouverte pendant le montage.</p>
    </section>
  );
}
