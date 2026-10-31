"use client";
import { JOURS_COURTS } from "@/lib/dates";
import type { Semaine } from "@/lib/activite";

/** 24/10 (Gaëtan : « affiche la cadence sur les sept derniers jours, les vues sur les sept derniers jours, les followers et les
 *  clics… qu'on ait accès sur les inputs ») : en haut de l'onglet Comptes, ses 7 derniers jours clos. Les Reels publiés jour par
 *  jour (ce qu'il fait) au-dessus des clics payés (ce que ça rapporte). Un chiffre inconnu s'affiche « – », jamais 0. */
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const compact = (n: number) => (n >= 10000 ? `${(n / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} k` : fmt(n));
const jourCourt = (j: string) => JOURS_COURTS[new Date(j + "T12:00:00Z").getUTCDay()].replace(".", "");

function Tuile({ titre, valeur, unite, sous }: { titre: string; valeur: string; unite?: string; sous: string }) {
  return (
    <div className="rounded-2xl p-3" style={{ background: "rgba(255,255,255,0.05)" }}>
      <div className="text-[11px] font-bold tracking-widest uppercase text-argent2">{titre}</div>
      <div className="mt-1 leading-none"><span className="text-[22px] font-bold tabular-nums">{valeur}</span>{unite ? <span className="text-[12px] text-argent2 ml-1">{unite}</span> : null}</div>
      <div className="text-[11.5px] text-argent2 mt-1.5 leading-snug">{sous}</div>
    </div>
  );
}

const pluriel = (n: number, mot: string) => `${fmt(n)} ${mot}${n > 1 ? "s" : ""}`;
const usd = (clics: number) => (Math.round(clics * 5) / 100).toLocaleString("fr-FR", { minimumFractionDigits: 2 });
const dec = (n: number) => n.toLocaleString("fr-FR", { maximumFractionDigits: 1 });

/** 31/10 : une couleur par compte de croissance, la même dans Ma semaine et dans « Reels → vues → clics ». */
export const COULEURS_COMPTES = ["#5b8cff", "#b48cff", "#38d0c8", "#f5b04c"];
export const couleurCompte = (rang: number) => COULEURS_COMPTES[(Math.max(1, rang) - 1) % COULEURS_COMPTES.length];
export const VERT_CLICS = "#6ee7b7";

/** 31/10 (Gaëtan : « 3,3 Reels par jour de moyenne sur les deux comptes… en bas du graphique, moyenne par jour sur le compte 1,
 *  moyenne par jour sur le compte 2, clics total ») : la cadence vient de ses comptes de croissance seulement ; chaque barre est
 *  empilée compte par compte ; sous le graphique, la moyenne de chaque compte et les clics de la semaine. */
export default function MaSemaine({ s, fixe = false }: { s: Semaine; fixe?: boolean }) {
  const max = Math.max(1, ...s.jours.map((j) => j.reels || 0));
  const comptes = s.croissance || [];
  const nb = comptes.length;
  const surComptes = nb > 1 ? `sur tes ${nb} comptes de croissance` : nb === 1 ? "sur ton compte de croissance" : "";
  return (
    <section className="carte p-4 apparait" aria-label="Ma semaine">
      <div className="flex items-baseline justify-between">
        <h2 className="text-[18px] font-bold">Ma semaine</h2>
        <span className="text-[11px] text-argent2">7 derniers jours</span>
      </div>
      <div className="grid grid-cols-2 gap-2.5 mt-3">
        <Tuile titre="Cadence" valeur={s.cadence !== null ? dec(s.cadence) : "–"} unite="Reels / jour"
               sous={s.reels !== null ? `${pluriel(s.reels, "Reel")} ${surComptes}`.trim() : "Reels pas encore relevés"} />
        <Tuile titre="Vues" valeur={s.vues !== null ? compact(s.vues) : "–"} sous="Sur tes Reels de la semaine" />
        <Tuile titre="Followers" valeur={s.followers !== null ? fmt(s.followers) : "–"} sous="Sur tous tes comptes" />
        <Tuile titre="Clics" valeur={s.clics !== null ? fmt(s.clics) : "–"}
               sous={s.clics === null ? "Pas encore relevés" : fixe ? "Visites francophones, pour info" : `Payés, soit ${usd(s.clics)} $`} />
      </div>
      {s.parJour && s.reels === 0 ? (
        <div className="mt-4 rounded-2xl px-3 py-3 text-[13px] text-argent2 leading-snug" style={{ background: "rgba(255,255,255,0.04)" }}>
          Aucun Reel publié ces 7 derniers jours {surComptes}. Ton prochain Reel relance ta cadence.
        </div>
      ) : s.parJour ? (
        <div className="mt-4" role="img" aria-label={`Reels publiés chaque jour ${surComptes}, et clics du jour`}>
          <div className="grid grid-cols-7 gap-1.5 items-end" style={{ height: 96 }}>
            {s.jours.map((j) => {
              const r = j.reels || 0;
              const parts = j.parCompte && j.parCompte.length ? j.parCompte : [r];
              return (
                <div key={j.jour} className="flex flex-col items-center justify-end h-full">
                  <span className="text-[11px] font-semibold tabular-nums mb-1">{r}</span>
                  {r ? (
                    <div className="w-full rounded-md overflow-hidden flex flex-col-reverse" style={{ height: `${Math.max(6, Math.round((r / max) * 66))}px` }}>
                      {parts.map((x, i) => x ? <div key={i} style={{ flexGrow: x, background: couleurCompte(i + 1) }} /> : null)}
                    </div>
                  ) : <div className="w-full rounded-md" style={{ height: 4, background: "rgba(255,255,255,0.08)" }} />}
                </div>
              );
            })}
          </div>
          <div className="grid grid-cols-7 gap-1.5 mt-1.5 text-center">
            {s.jours.map((j) => (
              <div key={j.jour} className="leading-tight">
                <div className="text-[10.5px] text-argent2">{jourCourt(j.jour)}</div>
                <div className="text-[10.5px] tabular-nums mt-0.5" style={{ color: VERT_CLICS }}>{j.clics !== null ? fmt(j.clics) : "–"}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {comptes.length || s.clics !== null ? (
        <div className="mt-3 rounded-2xl overflow-hidden text-[13px]" style={{ background: "rgba(255,255,255,0.04)" }}>
          {comptes.map((c, i) => (
            <div key={c.handle} className={`flex items-center justify-between gap-2 px-3 py-2 ${i ? "border-t border-white/[0.06]" : ""}`}>
              <span className="flex items-center gap-2 min-w-0">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: couleurCompte(c.rang) }} />
                <span className="truncate"><span className="text-argent2">Compte {c.rang}</span> · @{c.handle}</span>
              </span>
              <b className="tabular-nums shrink-0">{c.moyenne !== null ? dec(c.moyenne) : "–"}<span className="text-[11px] text-argent2 font-normal"> / jour</span></b>
            </div>
          ))}
          {s.clics !== null ? (
            <div className={`flex items-center justify-between gap-2 px-3 py-2 ${comptes.length ? "border-t border-white/[0.06]" : ""}`}>
              <span className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: VERT_CLICS }} />
                <span>{fixe ? "Clics de la semaine" : "Clics payés de la semaine"}</span>
              </span>
              <b className="tabular-nums shrink-0">{fmt(s.clics)}{fixe ? "" : <span className="text-[11px] text-argent2 font-normal"> · {usd(s.clics)} $</span>}</b>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
