"use client";
import { useCallback, useEffect, useState } from "react";
import { evaluerPrime, PALIERS, rythmeNecessaire, type CadenceCompte, type ReelsPrime } from "@/lib/activite";
import { MOIS_COURTS } from "@/lib/dates";
import { couleurCompte } from "./MaSemaine";

/** 24/10 (Gaëtan : « dans les versements, un truc par rapport à l'objectif, j'ai rajouté un objectif de Reels et d'input ») :
 *  la prime volume annoncée le 21/10, suivie sur la période de paie en cours. Les Reels viennent de /prime (suivi RapidAPI, lib/igSuivi),
 *  les clics payés de la carte du dessus (GAML). La prime est validée par l'agence en fin de période. */
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const dec = (n: number) => n.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
const MAX_JAUGE = 10;
const jourFin = (j: string) => { const d = new Date(j + "T12:00:00Z"); return `${d.getUTCDate()} ${MOIS_COURTS[d.getUTCMonth()]}`; };
const reelsTxt = (n: number) => `${dec(n)} Reel${n >= 2 ? "s" : ""}`;

/** 31/10 (Gaëtan : « l'objectif pour atteindre, d'augmenter la cadence sur le compte 1 ou le compte 2 afin d'augmenter la moyenne
 *  pour débloquer le bonus ») : ce qu'il faut publier sur CE compte, d'aujourd'hui à la fin de la période, pour finir à `cible`. */
function planCompte(c: CadenceCompte, r: ReelsPrime, cible: number): { texte: string; ton: "ok" | "effort" | "perdu" } | null {
  if (c.moyenne === null || c.suspendu) return null;
  const besoin = rythmeNecessaire(c.reels, r.totalJours, r.joursRestants, cible);
  if (besoin === null) return null;
  if (besoin === 0) return { texte: `${cible} / jour assurés sur cette période`, ton: "ok" };
  if (besoin > 20) return { texte: `${cible} / jour n'est plus atteignable d'ici le ${jourFin(r.fin)}`, ton: "perdu" };
  if (besoin <= c.moyenne) return { texte: `Garde ton rythme : ${reelsTxt(besoin)} par jour suffisent jusqu'au ${jourFin(r.fin)}`, ton: "ok" };
  return { texte: `Publie ${reelsTxt(besoin)} par jour jusqu'au ${jourFin(r.fin)} pour finir à ${cible} / jour`, ton: "effort" };
}

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
  // 31/10 : les deux comptes retenus (les plus actifs), affichés dans l'ordre de l'app (« Compte 1 », « Compte 2 », mêmes couleurs
  // que Ma semaine)
  const deux = r && r.mesure && r.joursEcoules > 0 ? [...r.parCompte.slice(0, 2)].sort((a, b) => (a.rang ?? 0) - (b.rang ?? 0)) : [];
  const manqueCompte = (palier: number) => deux.map((c) => c.moyenne !== null && c.moyenne < palier
    ? (() => { const m = Math.round((palier - c.moyenne) * 10) / 10; return `${reelsTxt(m)} par jour sur le compte ${c.rang}`; })() : "").filter(Boolean);
  // l'objectif : le premier palier dont les Reels ne sont pas tenus par ses deux comptes
  const cible = r && r.manque === "" ? PALIERS.find((p) => deux.some((c) => (c.moyenne ?? 0) < p.reels)) || null : null;
  const plans = cible && r ? deux.map((c) => ({ c, plan: planCompte(c, r, cible.reels) })) : [];
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
          {deux.map((c) => (
            <div key={c.handle} className="rounded-xl px-3 py-2.5" style={{ background: "rgba(255,255,255,0.04)" }}>
              <div className="flex items-baseline justify-between gap-2 text-[13px]">
                <span className="flex items-center gap-2 min-w-0">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0 self-center" style={{ background: couleurCompte(c.rang) }} />
                  <span className="truncate"><span className="text-argent2">Compte {c.rang}</span> · @{c.handle}</span>
                </span>
                <b className="tabular-nums shrink-0 text-[15px]">{c.moyenne !== null ? `${dec(c.moyenne)}` : "–"}<span className="text-[11px] text-argent2 font-normal"> / jour</span></b>
              </div>
              {c.moyenne !== null ? (
                <div className="relative mt-2 h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.08)" }}>
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, (c.moyenne / MAX_JAUGE) * 100)}%`, background: "linear-gradient(90deg,#2b6cff,#7ef0b2)", transition: "width 600ms ease" }} />
                  {PALIERS.map((p) => <div key={p.reels} className="absolute -top-0.5 h-2.5 w-0.5 rounded-full bg-white/50" style={{ left: `${(p.reels / MAX_JAUGE) * 100}%` }} />)}
                </div>
              ) : <div className="text-[11.5px] text-amber-200 mt-1">Pas encore suivi</div>}
              {c.suspendu ? <div className="text-[11.5px] text-amber-200 mt-1.5">{c.introuvable
                ? "Compte introuvable sur Instagram : vérifie le @ ou fais appel. Il compte pour 0."
                : "Compte suspendu : fais appel. Il compte pour 0 tant qu'il est suspendu."}</div> : null}
              {(() => {
                const p = plans.find((x) => x.c.handle === c.handle)?.plan;
                return p ? <div className={`text-[12px] mt-1.5 leading-snug ${p.ton === "ok" ? "text-emerald-300" : p.ton === "perdu" ? "text-argent2" : "text-white"}`}>
                  {p.ton === "ok" ? "✅ " : p.ton === "effort" ? "🎯 " : ""}{p.texte}</div> : null;
              })()}
            </div>
          ))}
          <div className="text-[11.5px] text-argent2">Moyenne sur {r!.joursEcoules} jour{r!.joursEcoules > 1 ? "s" : ""} sur {r!.totalJours}, à jour d'hier. Repères à 3, 6 et 9.{r!.joursRestants > 0 ? ` Encore ${r!.joursRestants} jour${r!.joursRestants > 1 ? "s" : ""} pour monter ta moyenne.` : ""}</div>
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

      <div className="mt-3 rounded-2xl p-3 text-[13px]" style={{ background: atteint ? "rgba(52,211,153,0.10)" : "rgba(122,167,255,0.09)" }}>
        <div className="font-semibold">{atteint ? `Si la période finissait hier : +${atteint.bonus} $ en plus de tes clics.`
          : prochain ? `Premier objectif : ${prochain.reels} Reels par jour sur chaque compte et ${fmt(prochain.clics)} clics.` : ""}</div>
        {cible && plans.some((x) => x.plan && x.plan.ton === "effort") ? (
          <div className="mt-1.5 text-argent2 leading-snug">
            Pour {cible.emoji} +{cible.bonus} $ d'ici le {jourFin(r!.fin)} :{" "}
            {plans.filter((x) => x.plan).map((x) => {
              const b = rythmeNecessaire(x.c.reels, r!.totalJours, r!.joursRestants, cible.reels) || 0;
              return b === 0 ? `compte ${x.c.rang} déjà assuré` : `compte ${x.c.rang} → ${reelsTxt(b)} par jour`;
            }).join(", ")}
            {clics !== null && clics < cible.clics ? `, et ${fmt(cible.clics - clics)} clics de plus` : ""}.
          </div>
        ) : null}
      </div>
      <p className="text-[11px] text-argent2/80 mt-2 leading-relaxed">Un clip différent sur chaque compte. Comptes en règle. Reels relevés 3 fois par jour sur Instagram. La prime est validée par l'agence à la fin de la période.</p>
    </div>
  );
}
