"use client";
import { useCallback, useEffect, useState } from "react";
import { evaluerPrime, PALIERS, type ReelsPrime } from "@/lib/activite";

/** 24/10 (Gaëtan : « dans les versements, un truc par rapport à l'objectif, j'ai rajouté un objectif de Reels et d'input ») :
 *  la prime volume annoncée le 21/10, suivie sur la période de paie en cours. Les Reels viennent de /prime (onglet « Comptes app »),
 *  les clics payés de la carte du dessus (GAML). Une estimation : la prime est validée par l'agence en fin de période. */
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const dec = (n: number) => n.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
const MAX_JAUGE = 10;

export default function PrimeVolume({ jeton, clics, libelle }: { jeton: string; clics: number | null; libelle: string }) {
  const [r, setR] = useState<ReelsPrime | null>(null);
  const [erreur, setErreur] = useState(false);
  const charger = useCallback(async () => {
    try {
      const x = await fetch(`/api/k/${jeton}/prime`, { cache: "no-store" });
      if (!x.ok) throw new Error();
      setR(await x.json()); setErreur(false);
    } catch { setErreur(true); }
  }, [jeton]);
  useEffect(() => { charger(); const id = setInterval(charger, 5 * 60_000); return () => clearInterval(id); }, [charger]);

  const moyenne = r && r.mesure ? r.moyenne : null;
  const { paliers, atteint } = evaluerPrime(moyenne, clics);
  const prochain = paliers.find((p) => !p.atteint);
  return (
    <div className="carte apparait-2 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-[14px] font-semibold">🔥 Prime volume</div>
        <span className="text-[11px] text-argent2">{libelle}</span>
      </div>
      <p className="text-[12.5px] text-argent2 mt-1 leading-relaxed">En plus de tes clics. Ta moyenne de Reels par jour sur chacun de tes 2 comptes de croissance.</p>

      {!r && !erreur ? <div className="squelette h-20 mt-3" /> : null}
      {erreur && !r ? <p className="text-[12.5px] text-argent2 mt-3">Tes Reels sont en cours de mise à jour. <button onClick={charger} className="text-accent font-semibold">Réessayer</button></p> : null}
      {r && !r.mesure ? <p className="text-[12.5px] text-argent2 mt-3">Le bot ne lit pas encore les Reels de tes comptes de croissance. Ta moyenne s'affiche dès qu'il les voit.</p> : null}
      {r && r.mesure && r.joursEcoules === 0 ? <p className="text-[12.5px] text-argent2 mt-3">La période commence aujourd'hui. Ta moyenne s'affiche demain.</p> : null}

      {r && r.mesure && moyenne !== null ? (
        <>
          <div className="mt-3 leading-none">
            <span className="titre-argent text-[32px] font-bold tabular-nums">{dec(moyenne)}</span>
            <span className="text-[13px] text-argent2 ml-1.5">Reels / jour / compte</span>
          </div>
          <div className="text-[12px] text-argent2 mt-1.5">{fmt(r.reels)} Reels sur tes comptes de croissance en {r.joursEcoules} jour{r.joursEcoules > 1 ? "s" : ""}, à jour d'hier</div>
          <div className="relative mt-4 h-2 rounded-full" style={{ background: "rgba(255,255,255,0.08)" }}>
            <div className="h-full rounded-full" style={{ width: `${Math.min(100, (moyenne / MAX_JAUGE) * 100)}%`, background: "linear-gradient(90deg,#2b6cff,#7ef0b2)", transition: "width 600ms ease" }} />
            {PALIERS.map((p) => (
              <div key={p.reels} className="absolute -top-1 h-4 w-0.5 rounded-full bg-white/50" style={{ left: `${(p.reels / MAX_JAUGE) * 100}%` }} />
            ))}
          </div>
          <div className="relative h-4 mt-1 text-[10.5px] text-argent2">
            {PALIERS.map((p) => <span key={p.reels} className="absolute -translate-x-1/2 tabular-nums" style={{ left: `${(p.reels / MAX_JAUGE) * 100}%` }}>{p.reels}</span>)}
          </div>
        </>
      ) : null}

      <div className="mt-3 rounded-2xl overflow-hidden text-[13px]" style={{ background: "rgba(255,255,255,0.04)" }}>
        {paliers.map((p, i) => (
          <div key={p.reels} className={`px-3 py-2.5 ${i ? "border-t border-white/[0.06]" : ""}`}>
            <div className="flex items-center justify-between gap-2">
              <span>{p.emoji} {p.reels} Reels / jour + {fmt(p.clics)} clics</span>
              <b className={`tabular-nums ${p.atteint ? "text-emerald-300" : ""}`}>+{p.bonus} $</b>
            </div>
            <div className={`text-[11.5px] mt-0.5 ${p.atteint ? "text-emerald-300" : "text-argent2"}`}>
              {p.atteint ? "Atteint à ce jour" : (() => {
                const manque = [
                  moyenne !== null && !p.okReels ? `${dec(p.manqueReels)} Reel${p.manqueReels > 1 ? "s" : ""} par jour` : "",
                  clics !== null && !p.okClics ? `${fmt(p.manqueClics)} clics` : "",
                ].filter(Boolean);
                return manque.length ? `Il manque ${manque.join(" et ")}` : "À suivre";
              })()}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 rounded-2xl p-3 text-[13px] font-semibold" style={{ background: atteint ? "rgba(52,211,153,0.10)" : "rgba(122,167,255,0.09)" }}>
        {atteint ? `Si la période finissait hier : +${atteint.bonus} $ en plus de tes clics.`
          : prochain ? `Premier objectif : ${prochain.reels} Reels par jour sur chaque compte et ${fmt(prochain.clics)} clics.` : ""}
      </div>
      <p className="text-[11px] text-argent2/80 mt-2 leading-relaxed">Un clip différent sur chaque compte. Comptes en règle. Estimation d'après les Reels vus par le bot : la prime est validée par l'agence à la fin de la période.</p>
    </div>
  );
}
