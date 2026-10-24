"use client";
import { useMemo } from "react";
import type { Pilotage } from "@/lib/pilotage";
import { classementClippers, type FicheClipper } from "@/lib/classement";
import { lienInstagram, ouvrirInstagram } from "@/lib/instagram";
import { compact, couleur, fmt, variation } from "./calc";
import { Courbe, Delta } from "./ui";
import { alerteMesure } from "@/lib/comptesReels";

const mesure = (v: number | null, partiel = false) => v === null ? "–" : `${partiel ? "≥ " : ""}${fmt(v)}`;

export function CarteClipper({ fiche: l, rang }: { fiche: FicheClipper; rang: number }) {
  const evolution = l.clics7 !== null && l.avant7 !== null && !l.manquants ? variation(l.clics7, l.avant7) : null;
  const prive = l.comptes.find(c => c.prive ?? c.numero === 3);
  return <article className="carte p-3.5" aria-label={`Clipper ${l.prenom}`}>
    <div className="flex items-center gap-2.5">
      <span className="w-4 shrink-0 text-[11px] text-argent2 tabular-nums">{rang}</span>
      <div className="min-w-0 flex-1">
        <h3 className="text-[16px] font-bold truncate">{l.prenom}</h3>
        <p className="text-[11.5px] leading-relaxed">
          {l.creatrices.map((c, i) => <span key={c} style={{ color: couleur(c) }}>{i ? ", " : ""}{c}</span>)}
          <span className="text-argent2">{l.creatrices.length ? " · " : ""}{l.comptes.length} compte{l.comptes.length > 1 ? "s" : ""}</span>
        </p>
      </div>
      <div className="shrink-0" role="img" aria-label="Clics des sept derniers jours clos">
        <Courbe valeurs={l.serie} largeur={52} hauteur={25} couleurTrait={couleur(l.creatrices[0] || "")} />
      </div>
      <div className="shrink-0 text-right">
        <div className="text-[17px] leading-tight font-bold tabular-nums">{l.manquants ? "≈ " : ""}{l.clics7 === null ? "–" : compact(l.clics7)}</div>
        <div className="text-[10px] text-argent2">clics · 7 j</div>
        {evolution !== null ? <Delta v={evolution} petit /> : <div className="text-[10px] text-argent2" title="Comparaison avec les sept jours précédents indisponible">Évol. –</div>}
      </div>
    </div>
    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 mt-3 mb-2.5 text-[12px] text-argent2" aria-label="Totaux des comptes de croissance sur sept jours">
      <span><b className="text-white tabular-nums">{mesure(l.reels7, l.partielReels)}</b> Reels · 7 j</span>
      <span aria-hidden>→</span>
      <span><b className="text-white tabular-nums">{mesure(l.vues7, l.partielVues)}</b> vues · 7 j</span>
    </div>
    <div className="space-y-1.5">
      {l.comptes.map(c => {
        const estPrive = c.prive ?? c.numero === 3;
        const alerte = alerteMesure({ etat: c.etat, mesure: c.mesure, dernierReel: c.dernierReel, role: estPrive ? "privé" : "" });
        return <div key={c.handle} className="rounded-xl bg-white/[0.04] px-2.5 py-2.5">
          <div className="flex items-start gap-2">
            <span className="text-[14px] shrink-0" aria-label={estPrive ? "Compte privé" : c.extra ? "Compte en plus des trois du parcours" : `Compte de croissance ${c.numero}`}>{estPrive ? "🔒" : c.extra ? "➕" : c.numero === 1 ? "1️⃣" : "2️⃣"}</span>
            <div className="min-w-0 flex-1">
              <div className="text-[12px] leading-5 break-words [overflow-wrap:anywhere]">
                <a href={lienInstagram(c.handle)} target="_blank" rel="noopener noreferrer" className="font-semibold text-white active:opacity-60" onClick={e => { e.preventDefault(); ouvrirInstagram(c.handle); }}>@{c.handle}<span className="text-accent"> ↗</span></a>{" "}
                <span className="text-[11px] text-argent2 whitespace-nowrap">({c.followers === null ? "–" : compact(c.followers)})</span>
              </div>
              {!estPrive ? <p className="text-[10.5px] text-argent2 mt-1 leading-relaxed">
                <b className="text-white tabular-nums">{mesure(c.reels7)}</b> Reels · 7 j <span className="text-white/20 mx-0.5">·</span> <b className="text-white tabular-nums">{mesure(c.reelsHier)}</b> hier
              </p> : <div className="mt-1 text-[10.5px] text-argent2 leading-relaxed break-words [overflow-wrap:anywhere]">
                Lien : {l.liens.length ? l.liens.map((url, i) => <span key={url}>{i ? " · " : ""}<a href={url} target="_blank" rel="noopener noreferrer" className="text-accent underline underline-offset-2">{url.replace(/^https?:\/\//, "").replace(/\/$/, "")}</a></span>) : "non renseigné"}
              </div>}
              {alerte ? <p className={`text-[10.5px] mt-1 leading-relaxed ${alerte.grave ? "text-rose-200" : "text-amber-200"}`}>⚠ {alerte.texte}</p> : null}
            </div>
            <div className="shrink-0 text-right pt-0.5">
              <div className="text-[13px] font-semibold tabular-nums">{estPrive ? mesure(l.clics7, Boolean(l.manquants)) : c.vuesRecentes === null ? "–" : compact(c.vuesRecentes)}</div>
              <div className="text-[9.5px] text-argent2">{estPrive ? "clics" : "vues"} · 7 j</div>
            </div>
          </div>
        </div>;
      })}
      {!l.comptes.length ? <p className="text-[12px] text-argent2 py-2">Aucun compte actif renseigné.</p> : null}
    </div>
    {l.comptes.some(c => !(c.prive ?? c.numero === 3)) ? <p className="mt-2.5 text-[10px] text-argent2 leading-relaxed break-words [overflow-wrap:anywhere]">1️⃣ / 2️⃣ → {prive ? `🔒 @${prive.handle}` : "compte privé manquant"} → lien en bio · à vérifier sur Instagram</p> : null}
    {l.manquants ? <p className="mt-2 text-[10.5px] text-amber-200">Clics partiels · {l.manquants} relevé(s) en attente.</p> : null}
  </article>;
}

export default function ClassementClippers({ d, filtre = "" }: { d: Pilotage; filtre?: string }) {
  const fiches = useMemo(() => classementClippers(d, filtre), [d, filtre]);
  return <div className="space-y-3">
    {fiches.map((l, i) => <CarteClipper key={l.id} fiche={l} rang={i + 1} />)}
    {!fiches.length ? <div className="carte p-4 text-[13px] text-argent2 text-center">Aucun clipper sur cette équipe.</div> : null}
    <p className="text-[10.5px] text-argent2 px-1 leading-relaxed">7 jours clos · clics payables · vues relevées sur les Reels récents. « – » : non mesuré ; « ≥ » : total partiel ; ➕ : compte actif en plus des trois du parcours ; ⚠ : le dernier relevé Instagram ne garantit pas le chiffre. Les liens affichés sont ceux attribués au clipper.</p>
  </div>;
}
