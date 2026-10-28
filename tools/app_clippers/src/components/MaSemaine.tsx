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

export default function MaSemaine({ s, fixe = false }: { s: Semaine; fixe?: boolean }) {
  const max = Math.max(1, ...s.jours.map((j) => j.reels || 0));
  return (
    <section className="carte p-4 apparait" aria-label="Ma semaine">
      <div className="flex items-baseline justify-between">
        <h2 className="text-[18px] font-bold">Ma semaine</h2>
        <span className="text-[11px] text-argent2">7 derniers jours</span>
      </div>
      <div className="grid grid-cols-2 gap-2.5 mt-3">
        <Tuile titre="Cadence" valeur={s.cadence !== null ? s.cadence.toLocaleString("fr-FR") : "–"} unite="Reels / jour"
               sous={s.reels !== null ? `${pluriel(s.reels, "Reel")} publié${s.reels > 1 ? "s" : ""}` : "Reels pas encore relevés"} />
        <Tuile titre="Vues" valeur={s.vues !== null ? compact(s.vues) : "–"} sous="Sur tes Reels de la semaine" />
        <Tuile titre="Followers" valeur={s.followers !== null ? fmt(s.followers) : "–"} sous="Sur tous tes comptes" />
        <Tuile titre="Clics" valeur={s.clics !== null ? fmt(s.clics) : "–"}
               sous={s.clics === null ? "Pas encore relevés" : fixe ? "Visites francophones, pour info" : `Payés, soit ${usd(s.clics)} $`} />
      </div>
      {s.parJour ? (
        <div className="mt-4">
          <div className="grid grid-cols-7 gap-1.5 items-end" style={{ height: 92 }}>
            {s.jours.map((j) => {
              const r = j.reels || 0;
              return (
                <div key={j.jour} className="flex flex-col items-center justify-end h-full">
                  <span className="text-[11px] font-semibold tabular-nums mb-1">{r}</span>
                  <div className="w-full rounded-md" style={{ height: `${Math.max(4, Math.round((r / max) * 64))}px`, background: r ? "linear-gradient(180deg,#7aa7ff,#2b6cff)" : "rgba(255,255,255,0.08)" }} />
                </div>
              );
            })}
          </div>
          <div className="grid grid-cols-7 gap-1.5 mt-1.5 text-center">
            {s.jours.map((j) => (
              <div key={j.jour} className="leading-tight">
                <div className="text-[10.5px] text-argent2">{jourCourt(j.jour)}</div>
                <div className="text-[10.5px] text-emerald-300 tabular-nums mt-0.5">{j.clics !== null ? fmt(j.clics) : "–"}</div>
              </div>
            ))}
          </div>
          <div className="text-[11px] text-argent2/80 mt-2 flex gap-3"><span><span className="text-accent">●</span> Reels publiés</span><span><span className="text-emerald-300">●</span> {fixe ? "clics" : "clics payés"}</span></div>
        </div>
      ) : null}
    </section>
  );
}
