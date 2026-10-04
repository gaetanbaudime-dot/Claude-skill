"use client";
import { useEffect, useState } from "react";

type Dest = { chemin: string[]; complet: boolean };
const TUILES = [
  { type: "reels", titre: "Reels", sous: "Instagram", lettre: "R", teinte: "from-[#2b6cff]/40 to-[#7aa7ff]/10" },
  { type: "photos", titre: "Photos", sous: "Instagram", lettre: "P", teinte: "from-[#8b5cf6]/40 to-[#c4b5fd]/10" },
  { type: "feed", titre: "Feed", sous: "MYM", lettre: "F", teinte: "from-[#ff3d7f]/40 to-[#ff7aa2]/10" },
  { type: "scripts", titre: "Scripts", sous: "MYM", lettre: "S", teinte: "from-[#f59e0b]/40 to-[#fcd34d]/10" },
] as const;

export default function DriveTab({ jeton, mym }: { jeton: string; mym: boolean }) {
  const [dest, setDest] = useState<Record<string, Dest> | null>(null);
  useEffect(() => {
    let vivant = true;
    fetch(`/api/c/${jeton}/drive`).then((r) => (r.ok ? r.json() : null)).then((d) => { if (vivant) setDest(d); }).catch(() => { if (vivant) setDest({}); });
    return () => { vivant = false; };
  }, [jeton]);
  return (
    <section>
      <p className="apparait text-argent2 text-[14px] mt-1 mb-4 px-1">Touche une tuile : Google Drive s'ouvre directement dans le bon dossier, prêt pour tes imports.</p>
      <div className="grid grid-cols-2 gap-3">
        {TUILES.map((t, i) => {
          const d = dest?.[t.type];
          const ou = d ? (d.chemin.length ? d.chemin.join(" · ") : (t.type === "feed" || t.type === "scripts") && !mym ? "Ton dossier Drive" : `Dossier ${t.titre}`) : "";
          return (
            <a key={t.type} href={`/api/c/${jeton}/drive/${t.type}`} target="_blank" rel="noopener"
               className={`tuile carte apparait-${i + 1} relative overflow-hidden p-4 aspect-[0.92] flex flex-col justify-between`}>
              <div className={`absolute inset-0 bg-gradient-to-br ${t.teinte} opacity-90`} />
              <div className="relative flex items-start justify-between">
                <span className="text-[44px] leading-none font-black titre-argent">{t.lettre}</span>
                <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-argent2 mt-1">{t.sous}</span>
              </div>
              <div className="relative">
                <div className="text-[17px] font-bold">{t.titre}</div>
                {dest === null ? <div className="squelette h-3 w-24 mt-2" /> : <div className="text-[12px] text-argent2 mt-1 leading-snug min-h-[1.1em]">{ou}</div>}
              </div>
              <svg className="absolute right-3 bottom-3 text-argent2/70" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M9 7h8v8" /></svg>
            </a>
          );
        })}
      </div>
      <p className="apparait-4 text-argent2/70 text-[12px] mt-5 px-1 leading-relaxed">Reels : le dossier de la semaine en cours. Photos : le dossier du mois. Les dossiers sont créés par l'agence au fil du calendrier.</p>
    </section>
  );
}
