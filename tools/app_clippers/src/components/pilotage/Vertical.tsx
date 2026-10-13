"use client";
import { useMemo } from "react";
import type { Clic, Compte, Pilotage } from "@/lib/pilotage";
import { couleur, creatrices, decaler, fenetre, fmt, meme, pct, serieParJour, somme, sommeBoutons, variation, type Periode } from "./calc";
import { ouvrirInstagram } from "@/lib/instagram";
import { BarresJour, Courbe, Delta, Ecart, Kpi, Titre } from "./ui";

/** Vertical = ce que les créatrices font percer elles-mêmes : leurs gros comptes (le compte principal et ses doublons) et leurs
 *  pages (page principale, bio Instagram, YouTube, Facebook). Chiffres du bot : visites payables GAML, followers et Reels relevés
 *  par le scan du matin (Apify) et Metricool. */
const COULEURS_SOURCES: Record<string, string> = {
  "Bio Instagram": "#f06292", "Page principale": "#7aa7ff", YouTube: "#ef5350", Facebook: "#5c8df6", "Autre page": "#b0bec5",
};

function LigneCompte({ c, i }: { c: Compte; i: number }) {
  const dVues = c.vues7 !== null && c.vues7Avant !== null ? variation(c.vues7, c.vues7Avant) : null;
  return (
    <div className={`py-3 ${i ? "border-t border-white/[0.06]" : ""}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <button onClick={() => ouvrirInstagram(c.handle)} className="text-[14px] font-semibold truncate text-white active:opacity-60">@{c.handle} <span className="text-accent text-[12px]">↗</span></button>
          <div className="text-[11.5px] text-argent2 truncate">{c.etat || "–"}{c.dernierReel ? ` · dernier Reel ${c.dernierReel}` : ""}</div>
        </div>
        <Courbe valeurs={c.courbe} couleurTrait={couleur(c.creatrice)} />
        <div className="text-right shrink-0">
          <div className="text-[17px] font-bold tabular-nums">{c.followers !== null ? fmt(c.followers) : "–"}</div>
          <div className="text-[11.5px]"><Ecart v={c.d24} /> <span className="text-argent2">24 h</span> · <Ecart v={c.d7} /> <span className="text-argent2">7 j</span></div>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-2 mt-2.5 text-center">
        {[["Reels hier", c.reelsHier], ["Reels 7 j", c.reels7], ["Vues 7 j", c.vuesRecentes ?? c.vues7], ["Clics 7 j", c.clics7]].map(([t, v]) => (
          <div key={t as string} className="rounded-xl bg-white/[0.04] py-1.5">
            <div className="text-[14px] font-semibold tabular-nums">{v === null || v === undefined ? "–" : fmt(v as number)}</div>
            <div className="text-[10.5px] text-argent2">{t}{t === "Vues 7 j" && dVues !== null ? <> <Delta v={dVues} petit /></> : null}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Vertical({ d, periode, filtre }: { d: Pilotage; periode: Periode; filtre: string }) {
  const f = fenetre(d.aujourdhui, periode);
  const garde = (cr: string) => !filtre || meme(cr, filtre);
  const clics = useMemo(() => d.clics.filter((c) => c.axe === "Vertical" && garde(c.creatrice)), [d, filtre]);   // eslint-disable-line react-hooks/exhaustive-deps
  const comptes = useMemo(() => d.comptes.filter((c) => c.axe === "Vertical" && garde(c.creatrice)), [d, filtre]); // eslint-disable-line react-hooks/exhaustive-deps
  const cur = somme(clics, f.debut, f.fin), avant = somme(clics, f.avantDebut, f.avantFin);
  const followers = comptes.reduce((s, c) => s + (c.followers || 0), 0);
  const d7 = comptes.some((c) => c.d7 !== null) ? comptes.reduce((s, c) => s + (c.d7 || 0), 0) : null;
  const d24 = comptes.some((c) => c.d24 !== null) ? comptes.reduce((s, c) => s + (c.d24 || 0), 0) : null;
  // jamais un faux 0 : « – » tant qu'aucun gros compte n'a de valeur relevée
  const total = (v: (c: Compte) => number | null) => comptes.some((c) => v(c) !== null) ? comptes.reduce((s, c) => s + (v(c) || 0), 0) : null;
  const reels7 = total((c) => c.reels7), reelsHier = total((c) => c.reelsHier), vues7 = total((c) => c.vuesRecentes ?? c.vues7);
  const nf = (n: number | null) => (n === null ? "–" : fmt(n));
  // 13/10 (Gaëtan : « surtout les clics des 30 derniers jours de toute la partie verticale, de toutes les créatrices ») : toujours
  // affichés, quelle que soit la période choisie, contre les 30 jours d'avant
  const f30 = fenetre(d.aujourdhui, "j30");
  const c30 = somme(clics, f30.debut, f30.fin), c30Avant = somme(clics, f30.avantDebut, f30.avantFin);

  const debutGraph = decaler(d.aujourdhui, -29);
  const graph = useMemo(() => filtre
    ? serieParJour<Clic>(clics, (c) => c.jour, (c) => c.source, (c) => c.visites, debutGraph, d.aujourdhui)
    : serieParJour<Clic>(clics, (c) => c.jour, (c) => c.creatrice, (c) => c.visites, debutGraph, d.aujourdhui), [clics, filtre, debutGraph, d.aujourdhui]);

  const liste = creatrices(d).filter(garde)
    .map((cr) => ({ cr, v: somme(clics.filter((c) => meme(c.creatrice, cr)), f30.debut, f30.fin).visites }))
    .sort((a, b) => b.v - a.v).map((x) => x.cr);
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 mt-3">
        <div className="col-span-2">
          <Kpi titre={filtre ? `Clics vertical de ${filtre} · 30 derniers jours` : "Clics vertical · toutes les créatrices · 30 derniers jours"}
            valeur={fmt(c30.visites)} delta={variation(c30.visites, c30Avant.visites)} partiel={c30.manquants > 0}
            sous={`${fmt(c30Avant.visites)} sur les 30 jours d'avant · ${fmt(c30.visites / 30)} par jour`} />
        </div>
        {periode === "j30" ? null : <div className="col-span-2">
          <Kpi titre={`Clics vertical · ${periode === "auj" ? "aujourd'hui" : periode === "hier" ? "hier" : periode === "j7" ? "7 derniers jours" : "30 derniers jours"}`} valeur={fmt(cur.visites)} delta={f.compare ? variation(cur.visites, avant.visites) : null}
            partiel={cur.manquants > 0}
            sous={`${f.compare ? `${fmt(avant.visites)} sur les ${f.libelleAvant}` : "jusqu'au dernier relevé"}${cur.manquants ? ` · ${cur.manquants} relevé(s) en attente` : ""}`} />
        </div>}
        <Kpi titre="Followers (gros comptes)" valeur={fmt(followers)} sous={`${d24 !== null ? `${d24 >= 0 ? "+" : "−"}${fmt(Math.abs(d24))} en 24 h` : "–"} · ${d7 !== null ? `${d7 >= 0 ? "+" : "−"}${fmt(Math.abs(d7))} en 7 j` : "–"}`} />
        <Kpi titre="Reels hier · Reels 7 j" valeur={`${nf(reelsHier)} · ${nf(reels7)}`} sous={`${nf(vues7)} vues sur les Reels des 7 derniers jours`} />
      </div>

      <Titre droite="30 derniers jours">{filtre ? `Visites de ${filtre}, par source` : "Visites par créatrice"}</Titre>
      <div className="carte p-3"><BarresJour data={graph.data} groupes={graph.groupes} unite="visites" couleurs={filtre ? COULEURS_SOURCES : undefined} /></div>

      {liste.map((cr, i) => {
        const k = clics.filter((c) => meme(c.creatrice, cr));
        const s = somme(k, f.debut, f.fin), a = somme(k, f.avantDebut, f.avantFin);
        const s30 = somme(k, f30.debut, f30.fin);
        const b = sommeBoutons(d, f.debut, f.fin, (x) => x.axe === "Vertical" && meme(x.creatrice, cr));
        const sources = new Map<string, number>();
        k.filter((c) => c.jour >= f.debut && c.jour <= f.fin).forEach((c) => sources.set(c.source, (sources.get(c.source) || 0) + c.visites));
        const siens = comptes.filter((c) => meme(c.creatrice, cr)).sort((x, y) => (y.followers || 0) - (x.followers || 0));
        if (!s.visites && !a.visites && !siens.length) return null;
        return (
          <section key={cr}>
            <Titre droite={<span className="inline-flex items-center gap-2"><span className="tabular-nums text-white/90 font-semibold">{s.manquants ? "≈ " : ""}{fmt(s.visites)} visites</span>{f.compare ? <Delta v={variation(s.visites, a.visites)} petit /> : null}</span>}>
              <span className="inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle" style={{ background: couleur(cr, i) }} />{cr}
            </Titre>
            <div className="carte px-4 pt-3 pb-1">
              <div className="text-[12px] text-argent2 pb-2"><b className="text-white tabular-nums">{s30.manquants ? "≈ " : ""}{fmt(s30.visites)}</b> clics sur 30 jours{b.releve ? <> · <b className="text-white tabular-nums">{fmt(b.of + b.mym)}</b> clics OF / MYM ({pct(b.taux)} des visites)</> : null}</div>
              {sources.size ? (
                <div className="flex flex-wrap gap-1.5 pb-2">
                  {[...sources.entries()].sort((x, y) => y[1] - x[1]).map(([src, v]) => (
                    <span key={src} className="text-[11.5px] rounded-full px-2.5 py-1 bg-white/[0.05]">
                      <span style={{ color: COULEURS_SOURCES[src] || "#b0bec5" }}>●</span> {src} <b className="tabular-nums">{fmt(v)}</b>
                    </span>
                  ))}
                </div>
              ) : null}
              {siens.length ? siens.map((c, j) => <LigneCompte key={c.handle} c={c} i={j} />) : (
                <div className="text-[12.5px] text-argent2 py-3">Aucun compte de la créatrice au classeur (Gérant = son prénom, ou Utilisation « Compte de la créatrice »).</div>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
