"use client";
import { signaler } from "@/lib/signal";

/** Le Duplicateur de Reels s'ouvre dans son propre onglet : c'est la version
 *  maintenue (montage, finitions, enregistrement dans Photos), toujours à jour. */
export const DUPLICATEUR_URL = "https://duplicateur-de-reels.vercel.app/";

/** 31/10 (Gaëtan : « simplifie à mort ») : les trois règles du rush tiennent en trois mots chacune. */
const REGLES = ["10 à 30 secondes", "La créatrice parle en français", "Aucun texte à l'écran"] as const;

export default function ReelsTab({ actif, jeton }: { actif: boolean; jeton: string }) {
  if (!actif) return null;
  return (
    <section className="carte p-5 apparait" aria-label="Duplicateur de Reels">
      <div className="text-[12px] font-semibold tracking-[0.14em] text-argent2 uppercase">Duplicateur de Reels</div>
      <h2 className="titre-argent text-[22px] font-bold mt-1 leading-tight">Un rush. Six Reels prêts à poster.</h2>
      <ul className="mt-4 space-y-2">
        {REGLES.map((r) => (
          <li key={r} className="flex items-center gap-2.5 text-[14px]"><span className="text-emerald-300">✓</span>{r}</li>
        ))}
      </ul>
      <a href={DUPLICATEUR_URL} target="_blank" rel="noopener noreferrer" onClick={() => signaler(jeton, "duplicateur:ouvrir")}
         className="mt-5 flex items-center justify-center gap-2 w-full rounded-2xl bg-white text-nuit font-semibold text-[15px] py-3.5 active:scale-[0.98] transition">
        Ouvrir le Duplicateur de Reels
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M8 16 16 8M10 8h6v6" />
        </svg>
      </a>
      <p className="text-[11.5px] text-argent2 mt-3 text-center">Garde la page ouverte pendant le montage.</p>
    </section>
  );
}
