"use client";
import { useCallback, useEffect, useState } from "react";
import type { Pilotage } from "@/lib/pilotage";
import { ouvrirInstagram } from "@/lib/instagram";
import { signaler } from "@/lib/signal";
import Horizontal from "./pilotage/Horizontal";
import { PERIODES, type Periode } from "./pilotage/calc";
import { pointsDe, type Membre } from "@/lib/suiviEquipe";

/** 24/10 : « Mon équipe », dans l'onglet Comptes d'un Team Leader (ex-onglet Équipe du 12/10). Le même pilotage horizontal que
 *  l'app d'un clipper (clics, Reels postés, vues, chaque @ ouvre Instagram), sur la projection filtrée côté serveur par
 *  `/api/k/<jeton>/equipe` : le TL ne reçoit que ses clippers, jamais les subs ni le CA. Au-dessus, « À suivre » regroupe par
 *  clipper ce qui demande une action (compte banni, appel à faire, compte à créer, aucun compte, clics pas encore relevés).
 *  La prime d'équipe reste dans Versements. */
type Equipe = { membres: Membre[]; pilotage: Pilotage | null };

export default function MonEquipe({ jeton }: { jeton: string }) {
  const [e, setE] = useState<Equipe | null>(null);
  const [erreur, setErreur] = useState(false);
  const [periode, setPeriode] = useState<Periode>("j7");
  const [filtre, setFiltre] = useState("");
  const charger = useCallback(async () => {
    try {
      const r = await fetch(`/api/k/${jeton}/equipe`, { cache: "no-store" });
      if (!r.ok) throw new Error();
      setE(await r.json()); setErreur(false);
    } catch { setErreur(true); }
  }, [jeton]);
  useEffect(() => { charger(); const id = setInterval(charger, 5 * 60_000); return () => clearInterval(id); }, [charger]);
  if (!e) {
    return erreur ? <div className="carte p-5 text-center text-argent2">Ton équipe est en cours de mise à jour. <button className="text-accent font-semibold" onClick={charger}>Réessayer</button></div>
      : <div className="space-y-3">{[0, 1, 2].map((i) => <div key={i} className="squelette h-28" />)}</div>;
  }
  const creatrices = Array.from(new Set(e.membres.map((m) => m.creatrice).filter(Boolean)));
  const aSuivre = e.membres.map((m) => ({ m, points: pointsDe(m) })).filter((x) => x.points.length)
    .sort((a, b) => Number(b.points.some((p) => p.grave)) - Number(a.points.some((p) => p.grave)) || a.m.prenom.localeCompare(b.m.prenom, "fr"));
  const index = PERIODES.findIndex((p) => p.cle === periode);
  return (
    <section className="space-y-3" aria-label="Mon équipe">
      {erreur ? <p role="status" className="text-amber-200 text-[12px]">Actualisation indisponible : dernières données affichées. <button onClick={charger} className="underline">Réessayer</button></p> : null}
      <div className="text-[13px] text-argent2">{e.membres.length} clipper{e.membres.length > 1 ? "s" : ""} dans ton équipe{creatrices.length === 1 ? ` · ${creatrices[0]}` : ""}</div>

      {aSuivre.length ? <details className="carte p-4">
        <summary className="cursor-pointer text-[14px] font-semibold">À suivre · {aSuivre.length} clipper{aSuivre.length > 1 ? "s" : ""}</summary>
        <div className="mt-3 space-y-3">
          {aSuivre.map(({ m, points }) => <div key={m.cle} className="border-t border-white/[0.06] pt-3 first:border-0 first:pt-0">
            <div className="text-[14px] font-semibold">{m.prenom}{creatrices.length > 1 && m.creatrice ? <span className="text-argent2 font-normal"> · {m.creatrice}</span> : null}</div>
            <ul className="mt-1 space-y-1">
              {points.map((p, i) => <li key={i} className={`text-[12.5px] ${p.grave ? "text-rose-200" : "text-argent2"}`}>
                {p.handle && p.texte !== "à créer"
                  ? <button onClick={() => { signaler(jeton, "equipe:instagram"); ouvrirInstagram(p.handle!); }} className="text-white font-semibold">@{p.handle} <span className="text-accent">↗</span></button>
                  : p.handle ? <span className="text-white">@{p.handle}</span> : null}
                {p.handle ? " · " : ""}{p.texte}
              </li>)}
            </ul>
          </div>)}
        </div>
      </details> : <div className="carte p-4 text-[13px] text-argent2">Rien à suivre : tous les comptes de ton équipe sont actifs.</div>}

      <div className="segment" role="group" aria-label="Période">
        <span className="pastille" style={{ left: `calc(4px + ${index} * (100% - 8px) / ${PERIODES.length})`, width: `calc((100% - 8px) / ${PERIODES.length})` }} />
        {PERIODES.map((p) => <button key={p.cle} aria-pressed={p.cle === periode} onClick={() => setPeriode(p.cle)}>{p.libelle}</button>)}
      </div>
      {creatrices.length > 1 ? <div className="flex gap-2 overflow-x-auto no-scrollbar" role="group" aria-label="Créatrice">
        {["", ...creatrices].map((c) => <button key={c || "toutes"} aria-pressed={filtre === c} onClick={() => setFiltre(c)}
          className={`shrink-0 rounded-full px-3 py-2 text-xs ${filtre === c ? "bg-white/15 text-white" : "bg-white/5 text-argent2"}`}>{c || "Toutes"}</button>)}
      </div> : null}
      {e.pilotage ? <Horizontal d={e.pilotage} periode={periode} filtre={filtre} />
        : <div className="carte p-4 text-[13px] text-argent2">Les statistiques de ton équipe sont en cours de mise à jour. <button onClick={charger} className="text-accent">Réessayer</button></div>}
    </section>
  );
}
