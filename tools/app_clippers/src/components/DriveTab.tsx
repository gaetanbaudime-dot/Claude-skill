"use client";
import { signaler } from "@/lib/signal";

/** Les quatre tuiles (08/10, Gaëtan) : Carrousel · TOP 20 Reels · Story · Reels, les Reels à droite (plus faciles au pouce).
 *  Chaque tuile ouvre le dossier racine de la section dans Google Drive ; le clipper fouille dedans. Pas d'état, pas d'emoji :
 *  un texte explicatif en haut, un en bas. */
const TUILES = [
  { type: "carrousel", titre: "Carrousel", sous: "Posts", lettre: "C", teinte: "from-[#8b5cf6]/40 to-[#c4b5fd]/10" },
  { type: "top", titre: "TOP 20 Reels", sous: "Pour toi", lettre: "T", teinte: "from-[#ff3d7f]/40 to-[#ff7aa2]/10" },
  { type: "story", titre: "Story", sous: "Chaque jour", lettre: "S", teinte: "from-[#f59e0b]/40 to-[#fcd34d]/10" },
  { type: "reels", titre: "Reels", sous: "À monter", lettre: "R", teinte: "from-[#2b6cff]/40 to-[#7aa7ff]/10" },
] as const;

export default function DriveTab({ jeton, creatrice }: { jeton: string; creatrice: string }) {
  return (
    <section>
      <p className="apparait text-argent2 text-[14px] mt-1 mb-4 px-1 leading-relaxed">Touche une tuile : Google Drive s'ouvre sur le dossier{creatrice ? ` de ${creatrice}` : ""}. Fouille dedans : les mois, les semaines, les tenues.</p>
      <div className="grid grid-cols-2 gap-3">
        {TUILES.map((t, i) => (
          <a key={t.type} href={`/api/k/${jeton}/drive/${t.type}`} target="_blank" rel="noopener" onClick={() => signaler(jeton, `drive:${t.type}`)}
             className={`tuile carte apparait-${i + 1} relative overflow-hidden p-4 aspect-[0.92] flex flex-col justify-between`}>
            <div className={`absolute inset-0 bg-gradient-to-br ${t.teinte} opacity-90`} />
            <div className="relative flex items-start justify-between">
              <span className="text-[44px] leading-none font-black titre-argent">{t.lettre}</span>
              <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-argent2 mt-1">{t.sous}</span>
            </div>
            <div className="relative text-[17px] font-bold leading-tight pr-5">{t.titre}</div>
            <svg className="absolute right-3 bottom-3 text-argent2/70" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M9 7h8v8" /></svg>
          </a>
        ))}
      </div>
      <p className="apparait-4 text-argent2/70 text-[12px] mt-5 px-1 leading-relaxed">Carrousel : les photos à poster en carrousel. TOP 20 Reels : tes variantes uniques, déposées par l'agence, à toi seul. Story : les stories du jour. Reels : les vidéos à monter, rangées par mois et par semaine. Modifie chaque vidéo avant de la publier.</p>
    </section>
  );
}
