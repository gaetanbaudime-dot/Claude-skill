"use client";
import { JOURS_COURTS } from "@/lib/dates";
import type { Correlation } from "@/lib/activite";
import { couleurCompte, VERT_CLICS } from "./MaSemaine";

/** 31/10 (Gaëtan : « un graphique pour mettre en corrélation… les Reels publiés sur les deux comptes de croissance mènent vraiment
 *  aux vues et aux clics. Le but, c'est d'inciter les clippers sur les Reels qui produisent des vues qui produisent des clics ») :
 *  sur 14 jours clos, trois rangées alignées jour par jour (Reels de chaque compte de croissance, vues de ces Reels, clics payés),
 *  ce qu'un Reel rapporte en moyenne et le meilleur jour. Les vues d'un jour sont celles, à ce jour, des Reels publiés ce jour-là. */
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const compact = (n: number) => (n >= 10000 ? `${(n / 1000).toLocaleString("fr-FR", { maximumFractionDigits: n >= 100000 ? 0 : 1 })} k` : fmt(n));
const dec = (n: number) => n.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
const jourCourt = (j: string) => {
  const d = new Date(j + "T12:00:00Z");
  return `${JOURS_COURTS[d.getUTCDay()]} ${d.getUTCDate()}/${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
};
const AMBRE = "#f5b04c";

function Rangee({ titre, valeurs, couleur, hauteur, meilleur, jours }: {
  titre: string; valeurs: number[]; couleur: string; hauteur: number; meilleur: number; jours: number;
}) {
  const max = Math.max(1, ...valeurs);
  return (
    <div className="grid items-end gap-[3px]" style={{ gridTemplateColumns: `38px repeat(${jours}, minmax(0, 1fr))`, height: hauteur }}>
      <div className="text-[10px] text-argent2 self-center leading-tight">{titre}</div>
      {valeurs.map((v, i) => (
        <div key={i} className={`h-full flex items-end rounded-[4px] ${i === meilleur ? "bg-white/[0.06]" : ""}`}>
          <div className="w-full rounded-[3px]" style={{ height: v ? `${Math.max(8, Math.round((v / max) * 100))}%` : 2, background: v ? couleur : "rgba(255,255,255,0.08)" }} />
        </div>
      ))}
    </div>
  );
}

export default function ReelsVuesClics({ c, fixe = false }: { c: Correlation; fixe?: boolean }) {
  const n = c.jours.length;
  const meilleur = c.meilleur ? c.jours.findIndex((j) => j.jour === c.meilleur!.jour) : -1;
  const maxReels = Math.max(1, ...c.jours.map((j) => j.reels.reduce((s, x) => s + x, 0)));
  const usd = (clics: number) => (Math.round(clics * 5) / 100).toLocaleString("fr-FR", { minimumFractionDigits: 2 });
  return (
    <section className="carte p-4 apparait" aria-label="Tes Reels, tes vues, tes clics">
      <div className="flex items-baseline justify-between">
        <h2 className="text-[18px] font-bold">Reels → vues → clics</h2>
        <span className="text-[11px] text-argent2">14 derniers jours</span>
      </div>

      <div className="mt-3 grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center text-center rounded-2xl px-2 py-3" style={{ background: "rgba(255,255,255,0.04)" }}>
        <div><div className="text-[22px] font-bold tabular-nums leading-none">{fmt(c.reels)}</div><div className="text-[11px] text-argent2 mt-1">Reels</div></div>
        <span className="text-argent2" aria-hidden="true">→</span>
        <div><div className="text-[22px] font-bold tabular-nums leading-none" style={{ color: AMBRE }}>{c.vues !== null ? compact(c.vues) : "–"}</div><div className="text-[11px] text-argent2 mt-1">vues</div></div>
        <span className="text-argent2" aria-hidden="true">→</span>
        <div><div className="text-[22px] font-bold tabular-nums leading-none" style={{ color: VERT_CLICS }}>{c.clics !== null ? fmt(c.clics) : "–"}</div><div className="text-[11px] text-argent2 mt-1">{fixe ? "clics" : "clics payés"}</div></div>
      </div>

      {c.reels > 0 && c.clics === 0 ? (
        <p className="text-[13px] mt-3 leading-snug rounded-xl px-3 py-2 bg-amber-400/10 text-amber-200">
          Aucun clic sur 14 jours. Vérifie que ton lien est bien en place sur ton compte privé : sans lien, tes vues ne rapportent rien.
        </p>
      ) : (c.vuesParReel || c.clicsParReel) ? (
        <p className="text-[13.5px] mt-3 leading-snug">
          Un Reel t'apporte en moyenne{" "}
          {c.vuesParReel !== null ? <b style={{ color: AMBRE }}>{fmt(c.vuesParReel)} vues</b> : null}
          {c.vuesParReel !== null && c.clicsParReel !== null ? " et " : null}
          {c.clicsParReel !== null ? <b style={{ color: VERT_CLICS }}>{dec(c.clicsParReel)} clic{c.clicsParReel >= 2 ? "s" : ""}</b> : null}
          {!fixe && c.clicsParReel !== null ? <span className="text-argent2"> ({usd(c.clicsParReel)} $)</span> : null}.
        </p>
      ) : null}

      <div className="mt-4 space-y-1.5" role="img" aria-label="Chaque jour : Reels publiés, vues de ces Reels, clics">
        <div className="grid items-end gap-[3px]" style={{ gridTemplateColumns: `38px repeat(${n}, minmax(0, 1fr))`, height: 58 }}>
          <div className="text-[10px] text-argent2 self-center leading-tight">Reels</div>
          {c.jours.map((j, i) => {
            const total = j.reels.reduce((s, x) => s + x, 0);
            return (
              <div key={j.jour} className={`h-full flex flex-col justify-end items-center rounded-[4px] ${i === meilleur ? "bg-white/[0.06]" : ""}`}>
                <span className="text-[9.5px] font-semibold tabular-nums leading-none mb-0.5">{total || ""}</span>
                {total ? (
                  <div className="w-full rounded-[3px] overflow-hidden flex flex-col-reverse" style={{ height: `${Math.max(10, Math.round((total / maxReels) * 76))}%` }}>
                    {j.reels.map((x, k) => x ? <div key={k} style={{ flexGrow: x, background: couleurCompte(k + 1) }} /> : null)}
                  </div>
                ) : <div className="w-full rounded-[3px]" style={{ height: 2, background: "rgba(255,255,255,0.08)" }} />}
              </div>
            );
          })}
        </div>
        {c.vues !== null ? <Rangee titre="Vues" valeurs={c.jours.map((j) => j.vues || 0)} couleur={AMBRE} hauteur={40} meilleur={meilleur} jours={n} /> : null}
        {c.clics !== null ? <Rangee titre="Clics" valeurs={c.jours.map((j) => j.clics || 0)} couleur={VERT_CLICS} hauteur={40} meilleur={meilleur} jours={n} /> : null}
        <div className="grid gap-[3px] text-center" style={{ gridTemplateColumns: `38px repeat(${n}, minmax(0, 1fr))` }}>
          <div />
          {c.jours.map((j, i) => (
            <div key={j.jour} className={`text-[9.5px] tabular-nums ${i === meilleur ? "text-white font-semibold" : "text-argent2"}`}>{new Date(j.jour + "T12:00:00Z").getUTCDate()}</div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2.5 text-[11px] text-argent2">
        {c.croissance.map((x) => (
          <span key={x.handle} className="flex items-center gap-1.5 min-w-0"><span className="w-2 h-2 rounded-full shrink-0" style={{ background: couleurCompte(x.rang) }} /><span className="truncate max-w-[140px]">Compte {x.rang}</span></span>
        ))}
        {c.vues !== null ? <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full" style={{ background: AMBRE }} />vues</span> : null}
        {c.clics !== null ? <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full" style={{ background: VERT_CLICS }} />clics</span> : null}
      </div>

      {c.meilleur ? (
        <div className="mt-3 rounded-2xl px-3 py-2.5 text-[13px] leading-snug" style={{ background: "rgba(245,176,76,0.10)" }}>
          ⭐ <b>Ton meilleur jour : {jourCourt(c.meilleur.jour)}</b>
          <div className="text-argent2 mt-0.5">
            {c.meilleur.reels} Reel{c.meilleur.reels > 1 ? "s" : ""}
            {c.meilleur.vues !== null ? ` · ${compact(c.meilleur.vues)} vues` : ""}
            {c.meilleur.clics !== null ? ` · ${fmt(c.meilleur.clics)} clic${c.meilleur.clics > 1 ? "s" : ""}` : ""}
          </div>
        </div>
      ) : null}
      <p className="text-[11px] text-argent2/80 mt-2.5 leading-relaxed">Vues : celles des Reels publiés ce jour-là, à ce jour. Les Reels de la veille et du jour montent encore.</p>
    </section>
  );
}
