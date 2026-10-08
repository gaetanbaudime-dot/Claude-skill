"use client";
import { useEffect, useState } from "react";

import { signaler } from "@/lib/signal";

type Etat = { racine: string; courant: string[]; statut: "plein" | "en_cours" | "vide" | "inconnu"; libelle: string; fichiers: number };
/** Les quatre tuiles (08/10, Gaëtan) : Carrousel · Reels · Stories · TOP 20 Reels, les Reels à droite (plus faciles au pouce).
 *  Chaque tuile ouvre le dossier racine de la section et dit l'état du dossier du moment : ✅ plein · ⏳ en cours · ❌ vide. */
const TUILES = [
  { type: "carrousel", titre: "Carrousel", sous: "Posts", lettre: "C", teinte: "from-[#8b5cf6]/40 to-[#c4b5fd]/10" },
  { type: "reels", titre: "Reels", sous: "À monter", lettre: "R", teinte: "from-[#2b6cff]/40 to-[#7aa7ff]/10" },
  { type: "stories", titre: "Stories", sous: "Chaque jour", lettre: "S", teinte: "from-[#f59e0b]/40 to-[#fcd34d]/10" },
  { type: "top", titre: "TOP 20 Reels", sous: "Pour toi", lettre: "T", teinte: "from-[#ff3d7f]/40 to-[#ff7aa2]/10" },
] as const;
const COULEUR: Record<Etat["statut"], string> = { plein: "text-[#7ef0b2]", en_cours: "text-[#fcd34d]", vide: "text-[#ff8a9a]", inconnu: "text-argent2" };

export default function DriveTab({ jeton, creatrice }: { jeton: string; creatrice: string }) {
  const [etat, setEtat] = useState<Record<string, Etat> | null>(null);
  useEffect(() => {
    let vivant = true;
    fetch(`/api/k/${jeton}/drive`).then((r) => (r.ok ? r.json() : null)).then((d) => { if (vivant) setEtat(d || {}); }).catch(() => { if (vivant) setEtat({}); });
    return () => { vivant = false; };
  }, [jeton]);
  return (
    <section>
      <p className="apparait text-argent2 text-[14px] mt-1 mb-4 px-1">Touche une tuile : Google Drive s'ouvre sur le dossier{creatrice ? ` de ${creatrice}` : ""}, tu descends dans le mois ou la semaine.</p>
      <div className="grid grid-cols-2 gap-3">
        {TUILES.map((t, i) => {
          const e = etat?.[t.type];
          const ou = e ? (e.courant.length ? e.courant.slice(-2).reverse().join(" · ") : e.racine || "Ton dossier Drive") : "";   // « Semaine 2 · Octobre » : une seule ligne sur téléphone
          return (
            <a key={t.type} href={`/api/k/${jeton}/drive/${t.type}`} target="_blank" rel="noopener" onClick={() => signaler(jeton, `drive:${t.type}`)}
               className={`tuile carte apparait-${i + 1} relative overflow-hidden p-4 aspect-[0.92] flex flex-col justify-between`}>
              <div className={`absolute inset-0 bg-gradient-to-br ${t.teinte} opacity-90`} />
              <div className="relative flex items-start justify-between">
                <span className="text-[44px] leading-none font-black titre-argent">{t.lettre}</span>
                <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-argent2 mt-1">{t.sous}</span>
              </div>
              <div className="relative">
                <div className="text-[17px] font-bold leading-tight">{t.titre}</div>
                {etat === null ? <div className="squelette h-3 w-24 mt-2" /> : (
                  <>
                    <div className={`text-[12.5px] font-semibold mt-1 leading-snug ${COULEUR[e?.statut || "inconnu"]}`}>{e?.libelle || "état inconnu"}</div>
                    <div className="text-[11px] text-argent2 leading-snug min-h-[1.1em] truncate">{ou}</div>
                  </>
                )}
              </div>
              <svg className="absolute right-3 bottom-3 text-argent2/70" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M9 7h8v8" /></svg>
            </a>
          );
        })}
      </div>
      <p className="apparait-4 text-argent2/70 text-[12px] mt-5 px-1 leading-relaxed">✅ plein : du contenu t'attend. ⏳ en cours de remplissage : l'agence dépose. ❌ dossier vide : rien pour l'instant. Reels : l'état de la semaine en cours. Carrousel et Stories : l'état du mois. TOP 20 Reels : tes variantes uniques, déposées par l'agence. Modifie chaque vidéo avant de la publier.</p>
    </section>
  );
}
