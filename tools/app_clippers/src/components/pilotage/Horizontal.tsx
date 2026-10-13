"use client";
import { useMemo, useState } from "react";
import type { Clic, Compte, Pilotage } from "@/lib/pilotage";
import { compact, couleur, decaler, estGood, fenetre, fmt, fmtUsd, jours, meme, normaliser, pct, serieParJour, somme, sommeBoutons, variation, type Periode } from "./calc";
import { ouvrirInstagram } from "@/lib/instagram";
import { BarresJour, Courbe, Delta, Ecart, Kpi, Titre } from "./ui";

/** Horizontal = la machine des clippers : leurs liens GAML (visites payables, celles de la paie), leurs comptes Instagram, plus
 *  les comptes Metricool de Rianah et les liens libérés. Le coût est celui de la paie : 0,05 $ par visite payable d'un clipper. */
const TAUX = 0.05;
const COULEURS_SOURCES: Record<string, string> = { Clipper: "#7aa7ff", Metricool: "#ffb74d", "Libéré": "#90a4ae" };
const HORS_CLASSEMENT = new Set(["Avant reprise", "Sans détenteur"]);
/** 13/10 (Gaëtan : « deux Rianah : une Rianah clipping et une Rianah Metricool ; Metricool au classement et dans les statistiques
 *  de tout le monde, mais pas dans le coût clipper : c'est un fixe ») : tous les liens Metricool font une seule ligne. */
const RIANAH_METRICOOL = "Rianah Metricool";
const libelle = (qui: string) => (normaliser(qui) === "rianah" ? "Rianah clipping" : qui);

type Ligne = { qui: string; creatrices: string[]; visites: number; avant: number; manquants: number; serie: (number | null)[]; comptes: Compte[]; metricool: boolean };

function rattacher(qui: string, comptes: Compte[]): Compte[] {
  const n = normaliser(qui);
  const exacts = comptes.filter((c) => normaliser(c.gerant) === n);
  if (exacts.length) return exacts;
  const premier = n.split(/\s+/)[0];
  const parPrenom = comptes.filter((c) => normaliser(c.gerant).split(/\s+/)[0] === premier);
  const gerants = new Set(parPrenom.map((c) => normaliser(c.gerant)));
  return gerants.size === 1 ? parPrenom : [];                          // deux Gérants du même prénom : on ne devine pas
}

function Detail({ comptes }: { comptes: Compte[] }) {
  if (!comptes.length) return <div className="text-[12px] text-argent2 py-2">Aucun compte GOOD à son nom au classeur.</div>;
  return (
    <div className="mt-2 space-y-1.5">
      {comptes.sort((a, b) => (b.followers || 0) - (a.followers || 0)).map((c) => (
        <div key={c.handle} className="flex items-center justify-between gap-2 rounded-xl bg-white/[0.04] px-3 py-2">
          <div className="min-w-0">
            <button onClick={() => ouvrirInstagram(c.handle)} className="block max-w-full text-left text-[13.5px] font-semibold truncate text-white active:opacity-60">
              @{c.handle} <span className="text-accent text-[12px]">↗</span>
            </button>
            <div className="text-[11px] text-argent2 truncate">{c.etat || "–"} · Reels 7 j {c.reels7 ?? "–"} · vues {c.vues7 !== null ? fmt(c.vues7) : "–"}</div>
          </div>
          <div className="text-right shrink-0">
            <div className="text-[13px] font-semibold tabular-nums">{c.followers !== null ? fmt(c.followers) : "–"}</div>
            <div className="text-[11px]"><Ecart v={c.d7} /> <span className="text-argent2">7 j · {c.clics7 ?? "–"} clics</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Horizontal({ d, periode, filtre }: { d: Pilotage; periode: Periode; filtre: string }) {
  const [ouvert, setOuvert] = useState<string>("");
  const f = fenetre(d.aujourdhui, periode);
  const garde = (cr: string) => !filtre || meme(cr, filtre);
  const clics = useMemo(() => d.clics.filter((c) => c.axe === "Horizontal" && garde(c.creatrice)), [d, filtre]);  // eslint-disable-line react-hooks/exhaustive-deps
  const comptes = useMemo(() => d.comptes.filter((c) => c.axe === "Horizontal" && garde(c.creatrice)), [d, filtre]); // eslint-disable-line react-hooks/exhaustive-deps
  const deClippers = (c: Clic) => c.source === "Clipper";
  const deMetricool = (c: Clic) => c.source === "Metricool";
  const auClassement = (c: Clic) => deMetricool(c) || (deClippers(c) && !HORS_CLASSEMENT.has(c.qui));
  const cur = somme(clics, f.debut, f.fin, deClippers), avant = somme(clics, f.avantDebut, f.avantFin, deClippers);
  const met = somme(clics, f.debut, f.fin, deMetricool), metAvant = somme(clics, f.avantDebut, f.avantFin, deMetricool);

  const j14 = jours(decaler(d.aujourdhui, -13), d.aujourdhui);
  const lignes: Ligne[] = useMemo(() => {
    const par = new Map<string, Ligne>();
    for (const c of clics) {
      if (!deClippers(c) && !deMetricool(c)) continue;
      const qui = deMetricool(c) ? RIANAH_METRICOOL : libelle(c.qui);
      const l = par.get(qui) || { qui, creatrices: [], visites: 0, avant: 0, manquants: 0, serie: j14.map(() => null), comptes: [], metricool: deMetricool(c) };
      if (!l.creatrices.some((x) => meme(x, c.creatrice))) l.creatrices.push(c.creatrice);
      if (c.jour >= f.debut && c.jour <= f.fin) { l.visites += c.visites; l.manquants += c.manquants; }
      if (c.jour >= f.avantDebut && c.jour <= f.avantFin) l.avant += c.visites;
      const i = j14.indexOf(c.jour);
      if (i >= 0) l.serie[i] = (l.serie[i] || 0) + c.visites;
      par.set(qui, l);
    }
    // 13/10 (Gaëtan : « uniquement les comptes qui sont verts ; les comptes bannis, je m'en fous ») : GOOD seulement
    const clippersComptes = comptes.filter((c) => c.type === "Clipper" && estGood(c.etat));
    const metricoolComptes = comptes.filter((c) => c.type === "Metricool" && estGood(c.etat));
    return [...par.values()].map((l) => ({ ...l, comptes: l.metricool ? metricoolComptes : rattacher(l.qui === "Rianah clipping" ? "Rianah" : l.qui, clippersComptes) }))
      .filter((l) => l.visites || l.avant || l.serie.some((v) => v))
      .sort((a, b) => b.visites - a.visites || b.avant - a.avant);
  }, [clics, comptes, f.debut, f.fin, f.avantDebut, f.avantFin]);       // eslint-disable-line react-hooks/exhaustive-deps

  const classement = lignes.filter((l) => !HORS_CLASSEMENT.has(l.qui));
  const actifs = classement.filter((l) => l.visites > 0 && !l.metricool).length;
  const autres = useMemo(() => {
    const m = new Map<string, { source: string; qui: string; visites: number; avant: number }>();
    for (const c of clics) {
      if (auClassement(c)) continue;
      const k = `${c.source}|${c.qui}`;
      const x = m.get(k) || { source: c.source, qui: c.qui, visites: 0, avant: 0 };
      if (c.jour >= f.debut && c.jour <= f.fin) x.visites += c.visites;
      if (c.jour >= f.avantDebut && c.jour <= f.avantFin) x.avant += c.visites;
      m.set(k, x);
    }
    return [...m.values()].filter((x) => x.visites || x.avant).sort((a, b) => b.visites - a.visites);
  }, [clics, f.debut, f.fin, f.avantDebut, f.avantFin]);               // eslint-disable-line react-hooks/exhaustive-deps

  const debutGraph = decaler(d.aujourdhui, -29);
  const graph = useMemo(() => filtre
    ? serieParJour<Clic>(clics, (c) => c.jour, (c) => c.source, (c) => c.visites, debutGraph, d.aujourdhui)
    : serieParJour<Clic>(clics.filter(auClassement), (c) => c.jour, (c) => c.creatrice, (c) => c.visites, debutGraph, d.aujourdhui),
  [clics, filtre, debutGraph, d.aujourdhui]);                            // eslint-disable-line react-hooks/exhaustive-deps
  const verts = comptes.filter((c) => estGood(c.etat));
  const followers = verts.reduce((s, c) => s + (c.followers || 0), 0);
  const reels7 = verts.reduce((s, c) => s + (c.reels7 || 0), 0);

  return (
    <div>
      <div className="grid grid-cols-2 gap-3 mt-3">
        <div className="col-span-2">
          <Kpi titre="Visites horizontales (clippers + Rianah Metricool)" valeur={fmt(cur.visites + met.visites)}
            delta={f.compare ? variation(cur.visites + met.visites, avant.visites + metAvant.visites) : null} partiel={cur.manquants + met.manquants > 0}
            sous={`${fmt(cur.visites)} clippers · ${fmt(met.visites)} Rianah Metricool${f.compare ? ` · ${fmt(avant.visites + metAvant.visites)} sur les ${f.libelleAvant}` : ""}${cur.manquants + met.manquants ? ` · ${cur.manquants + met.manquants} relevé(s) en attente` : ""}`} />
        </div>
        <Kpi titre="Coût clippers" valeur={fmtUsd(cur.visites * TAUX)} sous={`0,05 $ la visite · ${fmt(actifs)} clipper${actifs > 1 ? "s" : ""} actif${actifs > 1 ? "s" : ""} · Rianah Metricool au fixe, hors coût`} />
        <Kpi titre="Comptes GOOD" valeur={fmt(verts.length)} sous={`${fmt(followers)} followers · ${fmt(reels7)} Reels en 7 j`} />
      </div>

      <Titre droite="30 derniers jours">{filtre ? `Visites ${filtre}, par source` : "Visites des clippers par créatrice"}</Titre>
      <div className="carte p-3"><BarresJour data={graph.data} groupes={graph.groupes} unite="visites" couleurs={filtre ? COULEURS_SOURCES : undefined} /></div>

      <Titre droite={`${classement.length} clippers`}>Classement</Titre>
      <div className="carte px-3 py-1">
        {classement.map((l, i) => {
          const fol = l.comptes.reduce((s, c) => s + (c.followers || 0), 0);
          const ouvre = ouvert === l.qui;
          return (
            <div key={l.qui} className={i ? "border-t border-white/[0.06]" : ""}>
              <button className="w-full flex items-center gap-3 py-2.5 text-left" onClick={() => setOuvert(ouvre ? "" : l.qui)}>
                <span className="w-6 text-[12px] text-argent2 tabular-nums text-right shrink-0">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] font-semibold truncate">{l.qui}</div>
                  <div className="text-[11px] text-argent2 truncate">
                    {l.metricool ? <span className="text-amber-200">fixe, hors coût · </span> : null}
                    {l.creatrices.map((c, k) => <span key={c}>{k ? ", " : ""}<span style={{ color: couleur(c) }}>{c}</span></span>)}
                    {" · "}{l.comptes.length} compte{l.comptes.length > 1 ? "s" : ""} GOOD{fol ? ` · ${compact(fol)} fol.` : ""}
                  </div>
                </div>
                <Courbe valeurs={l.serie} couleurTrait={couleur(l.creatrices[0] || "")} largeur={64} hauteur={22} />
                <div className="text-right shrink-0 w-[72px]">
                  <div className="text-[15px] font-bold tabular-nums">{l.manquants ? "≈" : ""}{fmt(l.visites)}</div>
                  {f.compare ? <Delta v={variation(l.visites, l.avant)} petit /> : null}
                </div>
              </button>
              {ouvre ? <div className="pb-3 pl-9">
                {(() => {
                  const b = sommeBoutons(d, f.debut, f.fin, (x) => x.axe === "Horizontal" && garde(x.creatrice)
                    && (l.metricool ? x.source === "Metricool" : x.source === "Clipper" && (x.qui === l.qui || (l.qui === "Rianah clipping" && normaliser(x.qui) === "rianah"))));
                  return b.releve ? <div className="text-[11.5px] text-argent2 mb-1">Clics OF {fmt(b.of)} · MYM {fmt(b.mym)} · {pct(b.taux)} des visites</div> : null;
                })()}
                <Detail comptes={l.comptes} />
              </div> : null}
            </div>
          );
        })}
        {!classement.length ? <div className="text-[13px] text-argent2 py-4 text-center">Aucune visite de clipper sur la période.</div> : null}
      </div>

      {autres.length ? (
        <>
          <Titre>Hors classement</Titre>
          <div className="carte px-4 py-1">
            {autres.map((x, i) => (
              <div key={`${x.source}|${x.qui}`} className={`flex items-center justify-between py-2.5 ${i ? "border-t border-white/[0.06]" : ""}`}>
                <div className="min-w-0">
                  <div className="text-[13.5px] font-medium truncate">{x.qui}</div>
                  <div className="text-[11px]" style={{ color: COULEURS_SOURCES[x.source] || "#8b96a8" }}>{x.source === "Clipper" ? "lien de clipper" : x.source}</div>
                </div>
                <div className="text-right">
                  <div className="text-[14px] font-semibold tabular-nums">{fmt(x.visites)}</div>
                  {f.compare ? <Delta v={variation(x.visites, x.avant)} petit /> : null}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
