"use client";
import { useMemo } from "react";
import type { Clic, Pilotage } from "@/lib/pilotage";
import { decaler, estGood, fenetre, fmt, fmtUsd, meme, serieParJour, somme, variation, type Periode } from "./calc";
import { estSalarie } from "@/lib/salaries";
import { BarresJour, Delta, Kpi, Titre } from "./ui";
import ClassementClippers from "./ClassementClippers";

/** Horizontal = la machine des clippers : leurs liens GAML (visites payables, celles de la paie) et leurs comptes Instagram.
 *  26/10 (Gaëtan : « Enlève le coût des clippers de l'application des TL ; enlève Rianah de tous les trucs aussi, elle est au
 *  salaire ») : le coût (0,05 $ par visite payable d'un clipper, la paie) ne s'affiche que dans le pilotage de l'admin ; l'app d'un
 *  TL et celle d'un clipper n'en parlent plus. Rianah (clipping et Metricool) sort des visites des clippers, du coût, des comptes
 *  GOOD et du classement ; l'admin garde ce trafic sur une seule ligne « Au salaire », hors classement. Les données d'un TL et d'un
 *  clipper sont déjà réduites à leur équipe par le serveur. */
const TAUX = 0.05;
const COULEURS_SOURCES: Record<string, string> = { Clipper: "#7aa7ff", Metricool: "#ffb74d", "Libéré": "#90a4ae" };
const HORS_CLASSEMENT = new Set(["Avant reprise", "Sans détenteur"]);
const AU_SALAIRE = "Au salaire";

export default function Horizontal({ d, periode, filtre, admin = false }: { d: Pilotage; periode: Periode; filtre: string; admin?: boolean }) {
  const f = fenetre(d.aujourdhui, periode);
  const garde = (cr: string) => !filtre || meme(cr, filtre);
  const clics = useMemo(() => d.clics.filter((c) => c.axe === "Horizontal" && garde(c.creatrice)), [d, filtre]);  // eslint-disable-line react-hooks/exhaustive-deps
  const comptes = useMemo(() => d.comptes.filter((c) => c.axe === "Horizontal" && garde(c.creatrice)), [d, filtre]); // eslint-disable-line react-hooks/exhaustive-deps
  const salarie = (c: Clic) => admin && (c.source === "Metricool" || estSalarie(c.qui));
  const deClippers = (c: Clic) => c.source === "Clipper" && !salarie(c);
  const auClassement = (c: Clic) => deClippers(c) && !HORS_CLASSEMENT.has(c.qui);
  const cur = somme(clics, f.debut, f.fin, deClippers), avant = somme(clics, f.avantDebut, f.avantFin, deClippers);
  const actifs = useMemo(() => new Set(clics.filter((c) => auClassement(c) && c.visites > 0 && c.jour >= f.debut && c.jour <= f.fin)
    .map((c) => c.qui)).size, [clics, f.debut, f.fin]);                 // eslint-disable-line react-hooks/exhaustive-deps

  const autres = useMemo(() => {
    const m = new Map<string, { source: string; qui: string; visites: number; avant: number }>();
    for (const c of clics) {
      if (auClassement(c)) continue;
      const source = salarie(c) ? "Salaire" : c.source, qui = salarie(c) ? AU_SALAIRE : c.qui;
      const k = `${source}|${qui}`;
      const x = m.get(k) || { source, qui, visites: 0, avant: 0 };
      if (c.jour >= f.debut && c.jour <= f.fin) x.visites += c.visites;
      if (c.jour >= f.avantDebut && c.jour <= f.avantFin) x.avant += c.visites;
      m.set(k, x);
    }
    return [...m.values()].filter((x) => x.visites || x.avant).sort((a, b) => b.visites - a.visites);
  }, [clics, f.debut, f.fin, f.avantDebut, f.avantFin]);               // eslint-disable-line react-hooks/exhaustive-deps

  const debutGraph = decaler(d.aujourdhui, -29);
  const graph = useMemo(() => filtre
    ? serieParJour<Clic>(clics.filter((c) => !salarie(c)), (c) => c.jour, (c) => c.source, (c) => c.visites, debutGraph, d.aujourdhui)
    : serieParJour<Clic>(clics.filter(auClassement), (c) => c.jour, (c) => c.creatrice, (c) => c.visites, debutGraph, d.aujourdhui),
  [clics, filtre, debutGraph, d.aujourdhui]);                            // eslint-disable-line react-hooks/exhaustive-deps
  const verts = comptes.filter((c) => estGood(c.etat) && !(admin && (c.type === "Metricool" || estSalarie(c.gerant))));
  const followers = verts.reduce((s, c) => s + (c.followers || 0), 0);
  const reels7 = verts.reduce((s, c) => s + (c.reels7 || 0), 0);

  return (
    <div>
      <div className="grid grid-cols-2 gap-3 mt-3">
        <div className="col-span-2">
          <Kpi titre="Visites horizontales des clippers" valeur={fmt(cur.visites)}
            delta={f.compare ? variation(cur.visites, avant.visites) : null} partiel={cur.manquants > 0}
            sous={`${fmt(actifs)} clipper${actifs > 1 ? "s" : ""} actif${actifs > 1 ? "s" : ""}${f.compare ? ` · ${fmt(avant.visites)} sur les ${f.libelleAvant}` : ""}${cur.manquants ? ` · ${cur.manquants} relevé(s) en attente` : ""}`} />
        </div>
        {admin ? <Kpi titre="Coût clippers" valeur={fmtUsd(cur.visites * TAUX)} sous="0,05 $ la visite payable" /> : null}
        <div className={admin ? "" : "col-span-2"}>
          <Kpi titre="Comptes GOOD" valeur={fmt(verts.length)} sous={`${fmt(followers)} followers · ${fmt(reels7)} Reels en 7 j`} />
        </div>
      </div>

      <Titre droite="30 derniers jours">{filtre ? `Visites ${filtre}, par source` : "Visites des clippers par créatrice"}</Titre>
      <div className="carte p-3"><BarresJour data={graph.data} groupes={graph.groupes} unite="visites" couleurs={filtre ? COULEURS_SOURCES : undefined} /></div>

      <Titre droite="Clics · 7 jours clos">Classement</Titre>
      <ClassementClippers d={d} filtre={filtre} sansSalaries={admin} />

      {autres.length ? (
        <>
          <Titre>Hors classement</Titre>
          <div className="carte px-4 py-1">
            {autres.map((x, i) => (
              <div key={`${x.source}|${x.qui}`} className={`flex items-center justify-between py-2.5 ${i ? "border-t border-white/[0.06]" : ""}`}>
                <div className="min-w-0">
                  <div className="text-[13.5px] font-medium truncate">{x.qui}</div>
                  <div className="text-[11px]" style={{ color: COULEURS_SOURCES[x.source] || "#8b96a8" }}>{x.source === "Clipper" ? "lien de clipper" : x.source === "Salaire" ? "Metricool et clipping · hors coût clippers" : x.source}</div>
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
