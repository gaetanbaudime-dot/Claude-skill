"use client";
import { JOURS_COURTS } from "@/lib/dates";
import type { Correlation, Semaine } from "@/lib/activite";

/** 24/10 (Gaëtan : « affiche la cadence sur les sept derniers jours, les vues, les followers et les clics ») puis 31/10 (« la
 *  cadence par compte de croissance… un graphique pour mettre en corrélation les Reels, les vues et les clics »).
 *  31/10, plus tard (Gaëtan : « simplifie à mort, il y a trop de texte ») : une seule carte au lieu de deux. Trois chiffres
 *  (cadence, vues, clics), un graphique de 7 jours sur trois rangées alignées (Reels de chaque compte, vues, clics), la cadence
 *  de chaque compte en dessous. Plus de tuile Followers (elle est sur chaque compte), plus de phrases d'explication. */
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const compact = (n: number) => (n >= 10000 ? `${(n / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} k` : fmt(n));
const dec = (n: number) => n.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
const jourCourt = (j: string) => JOURS_COURTS[new Date(j + "T12:00:00Z").getUTCDay()].replace(".", "");

/** Une couleur par compte de croissance, la même dans Comptes et dans Versements. */
export const COULEURS_COMPTES = ["#5b8cff", "#b48cff", "#38d0c8", "#f5b04c"];
export const couleurCompte = (rang: number) => COULEURS_COMPTES[(Math.max(1, rang) - 1) % COULEURS_COMPTES.length];
export const VERT_CLICS = "#6ee7b7";
export const AMBRE_VUES = "#f5b04c";

const GRILLE = { gridTemplateColumns: "34px repeat(7, minmax(0, 1fr))" };

function Rangee({ titre, valeurs, couleur }: { titre: string; valeurs: number[]; couleur: string }) {
  const max = Math.max(1, ...valeurs);
  return (
    <div className="grid items-end gap-1.5" style={{ ...GRILLE, height: 34 }}>
      <div className="text-[10px] text-argent2 self-center">{titre}</div>
      {valeurs.map((v, i) => (
        <div key={i} className="w-full rounded-[3px]" style={{ height: v ? `${Math.max(10, Math.round((v / max) * 100))}%` : 2, background: v ? couleur : "rgba(255,255,255,0.08)" }} />
      ))}
    </div>
  );
}

function Chiffre({ valeur, libelle, couleur }: { valeur: string; libelle: string; couleur?: string }) {
  return (
    <div>
      <div className="text-[24px] font-bold tabular-nums leading-none" style={couleur ? { color: couleur } : undefined}>{valeur}</div>
      <div className="text-[11px] text-argent2 mt-1">{libelle}</div>
    </div>
  );
}

export default function MaSemaine({ s, c }: { s: Semaine; c?: Correlation | null }) {
  const comptes = s.croissance || [];
  // les vues jour par jour viennent du suivi des Reels (mêmes 7 jours clos que la semaine)
  const vuesJour = new Map((c?.jours || []).map((j) => [j.jour, j.vues]));
  const avecVues = Boolean(c && c.vues !== null);
  const vues = avecVues ? s.jours.reduce((t, j) => t + (vuesJour.get(j.jour) || 0), 0) : s.vues;
  const maxReels = Math.max(1, ...s.jours.map((j) => j.reels || 0));
  return (
    <section className="carte p-4 apparait" aria-label="Ma semaine">
      <div className="flex items-baseline justify-between">
        <h2 className="text-[18px] font-bold">Ma semaine</h2>
        <span className="text-[11px] text-argent2">7 derniers jours</span>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-3 text-center">
        <Chiffre valeur={s.cadence !== null ? dec(s.cadence) : "–"} libelle="Reels / jour" />
        <Chiffre valeur={vues !== null ? compact(vues) : "–"} libelle="vues" couleur={AMBRE_VUES} />
        <Chiffre valeur={s.clics !== null ? fmt(s.clics) : "–"} libelle="clics" couleur={VERT_CLICS} />
      </div>

      {s.parJour && s.reels === 0 ? (
        <p className="mt-4 text-[13px] text-argent2 text-center">Aucun Reel cette semaine.</p>
      ) : s.parJour ? (
        <div className="mt-4 space-y-1.5" role="img" aria-label="Chaque jour : Reels publiés sur chaque compte, vues de ces Reels, clics">
          <div className="grid items-end gap-1.5" style={{ ...GRILLE, height: 64 }}>
            <div className="text-[10px] text-argent2 self-center">Reels</div>
            {s.jours.map((j) => {
              const r = j.reels || 0;
              const parts = j.parCompte && j.parCompte.length ? j.parCompte : [r];
              return (
                <div key={j.jour} className="h-full flex flex-col items-center justify-end">
                  <span className="text-[10.5px] font-semibold tabular-nums leading-none mb-1">{r || ""}</span>
                  {r ? (
                    <div className="w-full rounded-[3px] overflow-hidden flex flex-col-reverse" style={{ height: `${Math.max(12, Math.round((r / maxReels) * 76))}%` }}>
                      {parts.map((x, i) => x ? <div key={i} style={{ flexGrow: x, background: couleurCompte(i + 1) }} /> : null)}
                    </div>
                  ) : <div className="w-full rounded-[3px]" style={{ height: 2, background: "rgba(255,255,255,0.08)" }} />}
                </div>
              );
            })}
          </div>
          {avecVues ? <Rangee titre="Vues" valeurs={s.jours.map((j) => vuesJour.get(j.jour) || 0)} couleur={AMBRE_VUES} /> : null}
          {s.clics !== null ? <Rangee titre="Clics" valeurs={s.jours.map((j) => j.clics || 0)} couleur={VERT_CLICS} /> : null}
          <div className="grid gap-1.5 text-center" style={GRILLE}>
            <div />
            {s.jours.map((j) => <div key={j.jour} className="text-[10px] text-argent2">{jourCourt(j.jour)}</div>)}
          </div>
        </div>
      ) : null}

      {comptes.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {comptes.map((x) => (
            <span key={x.handle} className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px]" style={{ background: "rgba(255,255,255,0.05)" }}>
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: couleurCompte(x.rang) }} />
              <span className="text-argent2">Compte {x.rang}</span>
              <b className="tabular-nums">{x.moyenne !== null ? dec(x.moyenne) : "–"}</b><span className="text-argent2 text-[11px]">/ jour</span>
            </span>
          ))}
        </div>
      ) : null}

      {s.reels && s.clics === 0 ? (
        <p className="mt-3 text-[12.5px] rounded-xl px-3 py-2 bg-amber-400/10 text-amber-200">0 clic : vérifie ton lien dans la bio de ton compte privé.</p>
      ) : null}
    </section>
  );
}
