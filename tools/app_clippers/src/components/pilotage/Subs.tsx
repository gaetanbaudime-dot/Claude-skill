"use client";
import { useMemo } from "react";
import type { Pilotage, Sub } from "@/lib/pilotage";
import { couleur, creatrices, decaler, fenetre, fmt, fmtEur, meme, pct, serieParJour, somme, sommeBoutons, sommeSubs, variation, type Periode } from "./calc";
import { BarresJour, Delta, Kpi, Titre } from "./ui";

/** Subs = ce que tout ce trafic rapporte : nouveaux abonnés OnlyFans et MYM et CA (Data G&M, saisi chaque jour par Rianah, en
 *  général le lendemain). Le CA OnlyFans est converti en euros au taux du bot. « Subs pour 100 visites » rapporte les abonnés aux
 *  visites payables de tous les liens (pages et clippers) de la même période : la conversion du trafic. */
export default function Subs({ d, periode, filtre }: { d: Pilotage; periode: Periode; filtre: string }) {
  const f = fenetre(d.aujourdhui, periode);
  const garde = (cr: string) => !filtre || meme(cr, filtre);
  const subs = useMemo(() => d.subs.filter((s) => garde(s.creatrice)), [d, filtre]);   // eslint-disable-line react-hooks/exhaustive-deps
  const cur = sommeSubs(subs, f.debut, f.fin, d.taux), avant = sommeSubs(subs, f.avantDebut, f.avantFin, d.taux);
  const visites = somme(d.clics, f.debut, f.fin, (c) => garde(c.creatrice));
  const parAbonne = cur.subs ? cur.caEur / cur.subs : null;
  const parAbonneAvant = avant.subs ? avant.caEur / avant.subs : null;
  // 13/10 : l'entonnoir complet — visites (tous pays, hors robots) → clics sur les boutons OF / MYM → abonnés → CA
  const bt = sommeBoutons(d, f.debut, f.fin, (x) => garde(x.creatrice));
  const subsPour100Clics = bt.releve && bt.of + bt.mym ? cur.subs / (bt.of + bt.mym) * 100 : null;

  const debutGraph = decaler(d.aujourdhui, -29);
  const graph = useMemo(() => filtre
    ? (() => {
        const lignes = subs.flatMap((s) => [{ jour: s.jour, k: "OnlyFans", v: s.subsOf }, { jour: s.jour, k: "MYM", v: s.subsMym }]);
        return serieParJour(lignes, (x) => x.jour, (x) => x.k, (x) => x.v, debutGraph, d.aujourdhui);
      })()
    : serieParJour<Sub>(subs, (s) => s.jour, (s) => s.creatrice, (s) => s.subsOf + s.subsMym, debutGraph, d.aujourdhui),
  [subs, filtre, debutGraph, d.aujourdhui]);

  const liste = creatrices(d).filter(garde);
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 mt-3">
        <div className="col-span-2">
          <Kpi titre="Nouveaux abonnés" valeur={fmt(cur.subs)} delta={f.compare ? variation(cur.subs, avant.subs) : null}
            sous={`OnlyFans ${fmt(cur.subsOf)} · MYM ${fmt(cur.subsMym)}${f.compare ? ` · ${fmt(avant.subs)} sur les ${f.libelleAvant}` : ""}${cur.nonSaisis ? ` · ⚠ ${cur.nonSaisis} jour(s) non saisi(s)` : ""}`} />
        </div>
        <Kpi titre="CA net" valeur={fmtEur(cur.caEur)} delta={f.compare ? variation(cur.caEur, avant.caEur) : null}
          sous={parAbonne !== null ? `${parAbonne.toFixed(1).replace(".", ",")} € par abonné` : "–"} />
        <Kpi titre="Subs pour 100 visites" valeur={visites.visites ? (cur.subs / visites.visites * 100).toFixed(1).replace(".", ",") : "–"}
          sous={`${fmt(visites.visites)} visites payables${visites.manquants ? " (partiel)" : ""}`} />
      </div>
      <Titre droite={bt.releve ? "" : "relevé en cours"}>Entonnoir</Titre>
      <div className="carte p-4 apparait">
        {[
          ["Visites des pages", fmt(bt.releve ? bt.visitesTous : visites.visites), bt.releve ? "tous pays, hors robots" : "visites payables"],
          ["Clics OnlyFans + MYM", bt.releve ? fmt(bt.of + bt.mym) : "–", bt.releve ? `${pct(bt.taux)} des visites · OF ${fmt(bt.of)} · MYM ${fmt(bt.mym)}` : "premier relevé sous 3 h"],
          ["Nouveaux abonnés", fmt(cur.subs), subsPour100Clics !== null ? `${pct(subsPour100Clics)} des clics sur les boutons` : ""],
          ["CA net", fmtEur(cur.caEur), parAbonne !== null ? `${parAbonne.toFixed(1).replace(".", ",")} € par abonné` : ""],
        ].map(([t, v, s], i) => (
          <div key={t} className={`flex items-center justify-between py-2 ${i ? "border-t border-white/[0.06]" : ""}`}>
            <div className="min-w-0"><div className="text-[13.5px] font-semibold">{t}</div><div className="text-[11px] text-argent2">{s}</div></div>
            <div className="text-[17px] font-bold tabular-nums shrink-0">{v}</div>
          </div>
        ))}
      </div>
      {periode === "auj" ? <p className="text-[11.5px] text-argent2 mt-2 px-1">Les subs sont saisis le lendemain : la journée en cours est souvent vide.</p> : null}
      {f.compare && parAbonne !== null && parAbonneAvant !== null ? (
        <p className="text-[11.5px] text-argent2 mt-2 px-1">€ par abonné : {parAbonne.toFixed(1).replace(".", ",")} € contre {parAbonneAvant.toFixed(1).replace(".", ",")} € sur les {f.libelleAvant}.</p>
      ) : null}

      <Titre droite="30 derniers jours">{filtre ? `Abonnés de ${filtre}, OnlyFans et MYM` : "Abonnés par créatrice"}</Titre>
      <div className="carte p-3"><BarresJour data={graph.data} groupes={graph.groupes} unite="abonnés" couleurs={filtre ? { OnlyFans: "#59b6ff", MYM: "#ff7aa2" } : undefined} /></div>

      <Titre>Par créatrice</Titre>
      <div className="carte px-4 py-1">
        {liste.map((cr, i) => {
          const s = sommeSubs(subs, f.debut, f.fin, d.taux, (x) => meme(x.creatrice, cr));
          const a = sommeSubs(subs, f.avantDebut, f.avantFin, d.taux, (x) => meme(x.creatrice, cr));
          const v = somme(d.clics, f.debut, f.fin, (c) => meme(c.creatrice, cr));
          const b = sommeBoutons(d, f.debut, f.fin, (x) => meme(x.creatrice, cr));
          if (!s.subs && !a.subs && !s.caEur && !v.visites) return null;
          return (
            <div key={cr} className={`py-3 ${i ? "border-t border-white/[0.06]" : ""}`}>
              <div className="flex items-center justify-between">
                <div className="text-[14.5px] font-semibold"><span className="inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle" style={{ background: couleur(cr, i) }} />{cr}</div>
                <div className="flex items-center gap-2">
                  <span className="text-[16px] font-bold tabular-nums">{fmt(s.subs)}</span>
                  {f.compare ? <Delta v={variation(s.subs, a.subs)} petit /> : null}
                </div>
              </div>
              <div className="grid grid-cols-4 gap-2 mt-2 text-center">
                {[["OF", fmt(s.subsOf)], ["MYM", fmt(s.subsMym)], ["CA", fmtEur(s.caEur)], ["/100 vis.", v.visites ? (s.subs / v.visites * 100).toFixed(1).replace(".", ",") : "–"]].map(([t, x]) => (
                  <div key={t} className="rounded-xl bg-white/[0.04] py-1.5">
                    <div className="text-[13.5px] font-semibold tabular-nums">{x}</div>
                    <div className="text-[10.5px] text-argent2">{t}</div>
                  </div>
                ))}
              </div>
              {b.releve ? <div className="text-[11.5px] text-argent2 mt-1.5">Clics OF {fmt(b.of)} · MYM {fmt(b.mym)} · {pct(b.taux)} des visites{b.of + b.mym ? ` · ${pct(s.subs / (b.of + b.mym) * 100)} des clics deviennent abonnés` : ""}</div> : null}
              {s.nonSaisis ? <div className="text-[11px] text-amber-200/90 mt-1.5">⚠ {s.nonSaisis} jour(s) non saisi(s) dans Data G&M sur la période</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
