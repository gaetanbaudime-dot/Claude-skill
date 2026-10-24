"use client";
import { useCallback, useEffect, useState } from "react";
import { evaluerPrime, PALIERS, type ReelsPrime } from "@/lib/activite";

/** 24/10 (Gaëtan : « dans les versements, un truc par rapport à l'objectif, j'ai rajouté un objectif de Reels et d'input ») :
 *  la prime volume annoncée le 21/10, suivie sur la période de paie en cours. Les Reels viennent de /prime (suivi RapidAPI, lib/igSuivi),
 *  les clics payés de la carte du dessus (GAML). La prime est validée par l'agence en fin de période. */
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
  // 24/10 (Gaëtan : « il faut que la moyenne du compte 1 soit supérieure à 3, il faut que la moyenne du compte 2 soit supérieure
  // à 3 ») : chaque compte de croissance face au palier, sans « cadence retenue » à interpréter
  const deux = r && r.mesure && r.joursEcoules > 0 ? r.parCompte.slice(0, 2) : [];
  const manqueCompte = (palier: number) => deux.map((c, i) => c.moyenne !== null && c.moyenne < palier
    ? (() => { const m = Math.round((palier - c.moyenne) * 10) / 10; return `${dec(m)} Reel${m >= 2 ? "s" : ""} par jour sur le compte ${i + 1}`; })() : "").filter(Boolean);
  return (
    <div className="carte apparait-2 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-[14px] font-semibold">🔥 Prime volume</div>
        <span className="text-[11px] text-argent2">{libelle}</span>
      </div>
      <p className="text-[12.5px] text-argent2 mt-1 leading-relaxed">En plus de tes clics. Ton compte 1 et ton compte 2 de croissance doivent chacun tenir la moyenne de Reels par jour.</p>

      {!r && !erreur ? <div className="squelette h-20 mt-3" /> : null}
      {erreur && !r ? <p className="text-[12.5px] text-argent2 mt-3">Tes Reels sont en cours de mise à jour. <button onClick={charger} className="text-accent font-semibold">Réessayer</button></p> : null}
      {r && !r.mesure ? <p className="text-[12.5px] text-argent2 mt-3">Tes comptes ne sont pas encore suivis. C'est de notre côté, on s'en occupe.</p> : null}
      {r && r.mesure && r.joursEcoules === 0 ? <p className="text-[12.5px] text-argent2 mt-3">La période commence aujourd'hui. Tes moyennes s'affichent demain.</p> : null}
      {r && r.mesure && r.joursEcoules > 0 && r.manque === "deuxieme_non_lu" ? <p className="text-[12.5px] text-amber-200 mt-3">Ton 2e compte n'est pas encore suivi. C'est de notre côté, on s'en occupe.</p> : null}
      {r && r.mesure && r.joursEcoules > 0 && r.manque === "deuxieme_compte" ? <p className="text-[12.5px] text-amber-200 mt-3">Tu n'as qu'un compte de croissance. La prime en demande 2.</p> : null}

      {deux.length ? (
        <div className="mt-3 space-y-2">
          {deux.map((c, i) => (
            <div key={c.handle} className="rounded-xl px-3 py-2.5" style={{ background: "rgba(255,255,255,0.04)" }}>
              <div className="flex items-baseline justify-between gap-2 text-[13px]">
                <span className="truncate"><span className="text-argent2">Compte {i + 1}</span> · @{c.handle}</span>
                <b className="tabular-nums shrink-0 text-[15px]">{c.moyenne !== null ? `${dec(c.moyenne)}` : "–"}<span className="text-[11px] text-argent2 font-normal"> / jour</span></b>
              </div>
              {c.moyenne !== null ? (
                <div className="relative mt-2 h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.08)" }}>
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, (c.moyenne / MAX_JAUGE) * 100)}%`, background: "linear-gradient(90deg,#2b6cff,#7ef0b2)", transition: "width 600ms ease" }} />
                  {PALIERS.map((p) => <div key={p.reels} className="absolute -top-0.5 h-2.5 w-0.5 rounded-full bg-white/50" style={{ left: `${(p.reels / MAX_JAUGE) * 100}%` }} />)}
                </div>
              ) : <div className="text-[11.5px] text-amber-200 mt-1">Pas encore suivi</div>}
            </div>
          ))}
          <div className="text-[11.5px] text-argent2">Moyenne sur {r!.joursEcoules} jour{r!.joursEcoules > 1 ? "s" : ""}, à jour d'hier. Repères à 3, 6 et 9.</div>
        </div>
      ) : null}

      <div className="mt-3 rounded-2xl overflow-hidden text-[13px]" style={{ background: "rgba(255,255,255,0.04)" }}>
        {paliers.map((p, i) => (
          <div key={p.reels} className={`px-3 py-2.5 ${i ? "border-t border-white/[0.06]" : ""}`}>
            <div className="flex items-center justify-between gap-2">
              <span>{p.emoji} {p.reels} Reels / jour sur chaque compte + {fmt(p.clics)} clics</span>
              <b className={`tabular-nums whitespace-nowrap shrink-0 ${p.atteint ? "text-emerald-300" : ""}`}>+{p.bonus} $</b>
            </div>
            <div className={`text-[11.5px] mt-0.5 ${p.atteint ? "text-emerald-300" : "text-argent2"}`}>
              {p.atteint ? "Atteint à ce jour" : (() => {
                const manque = [...manqueCompte(p.reels), clics !== null && !p.okClics ? `${fmt(p.manqueClics)} clics` : ""].filter(Boolean);
                return manque.length ? `Il manque ${manque.join(", ")}` : "À suivre";
              })()}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 rounded-2xl p-3 text-[13px] font-semibold" style={{ background: atteint ? "rgba(52,211,153,0.10)" : "rgba(122,167,255,0.09)" }}>
        {atteint ? `Si la période finissait hier : +${atteint.bonus} $ en plus de tes clics.`
          : prochain ? `Premier objectif : ${prochain.reels} Reels par jour sur chaque compte et ${fmt(prochain.clics)} clics.` : ""}
      </div>
      <p className="text-[11px] text-argent2/80 mt-2 leading-relaxed">Un clip différent sur chaque compte. Comptes en règle. Reels relevés 3 fois par jour sur Instagram. La prime est validée par l'agence à la fin de la période.</p>
    </div>
  );
}
