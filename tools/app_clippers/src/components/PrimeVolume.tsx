"use client";
import { useCallback, useEffect, useState } from "react";
import { evaluerPrime, PALIERS, rythmeNecessaire, type CadenceCompte, type ReelsPrime } from "@/lib/activite";
import { MOIS_COURTS } from "@/lib/dates";
import { couleurCompte, VERT_CLICS } from "./MaSemaine";

/** 24/10 (Gaëtan : « dans les versements, un truc par rapport à l'objectif, j'ai rajouté un objectif de Reels et d'input ») :
 *  la prime volume annoncée le 21/10, suivie sur la période de paie en cours. Les Reels viennent de /prime (suivi RapidAPI,
 *  lib/igSuivi), les clics payés de la carte du dessus (GAML).
 *  31/10 (Gaëtan : « l'objectif… d'augmenter la cadence sur le compte 1 ou le compte 2 ») puis, le même jour, « simplifie à
 *  mort » : chaque compte avec sa jauge et le rythme à tenir d'ici la fin de la période, les clics face au palier visé, puis
 *  les trois paliers sur une ligne chacun. Plus de paragraphe d'explication ni de note de bas de carte. */
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const dec = (n: number) => n.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
const MAX_JAUGE = 10;
const MAX_PAR_JOUR = 20;                                               // au-delà, un palier n'est plus atteignable sur la période
const jourFin = (j: string) => { const d = new Date(j + "T12:00:00Z"); return `${d.getUTCDate()} ${MOIS_COURTS[d.getUTCMonth()]}`; };

/** Ce qu'il faut publier sur CE compte, d'aujourd'hui à la fin de la période, pour finir à `cible` Reels par jour. */
function planCompte(c: CadenceCompte, r: ReelsPrime, cible: number): { texte: string; ton: "ok" | "effort" | "perdu" } | null {
  if (c.moyenne === null || c.suspendu) return null;
  const besoin = rythmeNecessaire(c.reels, r.totalJours, r.joursRestants, cible);
  if (besoin === null) return null;
  if (besoin === 0) return { texte: `✓ ${cible} / jour assuré`, ton: "ok" };
  if (besoin > MAX_PAR_JOUR) return { texte: `${cible} / jour hors d'atteinte d'ici le ${jourFin(r.fin)}`, ton: "perdu" };
  if (besoin <= c.moyenne) return { texte: `✓ Garde ce rythme jusqu'au ${jourFin(r.fin)}`, ton: "ok" };
  return { texte: `🎯 Publie ${dec(besoin)} Reel${besoin >= 2 ? "s" : ""} par jour jusqu'au ${jourFin(r.fin)}`, ton: "effort" };
}

function Jauge({ valeur, max, couleur, reperes }: { valeur: number; max: number; couleur: string; reperes?: number[] }) {
  return (
    <div className="relative mt-2 h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.08)" }}>
      <div className="h-full rounded-full" style={{ width: `${Math.min(100, (valeur / max) * 100)}%`, background: couleur, transition: "width 600ms ease" }} />
      {(reperes || []).map((p) => <div key={p} className="absolute -top-0.5 h-2.5 w-0.5 rounded-full bg-white/40" style={{ left: `${(p / max) * 100}%` }} />)}
    </div>
  );
}

export default function PrimeVolume({ jeton, clics }: { jeton: string; clics: number | null }) {
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
  const { paliers } = evaluerPrime(moyenne, clics);
  // 24/10 : chaque compte de croissance face au palier (« la moyenne du compte 1… la moyenne du compte 2 ») ; 31/10 : les deux
  // comptes retenus (les plus actifs), dans l'ordre de l'app, aux couleurs de Ma semaine
  const deux = r && r.mesure && r.joursEcoules > 0 ? [...r.parCompte.slice(0, 2)].sort((a, b) => (a.rang ?? 0) - (b.rang ?? 0)) : [];
  // le palier visé en Reels : le premier que ses deux comptes ne tiennent pas encore ; en clics : le premier pas encore atteint
  const cible = r && r.manque === "" ? PALIERS.find((p) => deux.some((c) => (c.moyenne ?? 0) < p.reels)) || null : null;
  const cibleClics = paliers.find((p) => !p.okClics) ?? paliers[paliers.length - 1];
  return (
    <div className="carte apparait-2 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-[16px] font-bold">🔥 Prime volume</div>
        {r ? <span className="text-[11px] text-argent2">{jourFin(r.debut)} → {jourFin(r.fin)}</span> : null}
      </div>

      {!r && !erreur ? <div className="squelette h-20 mt-3" /> : null}
      {erreur && !r ? <p className="text-[12.5px] text-argent2 mt-3">Mise à jour en cours. <button onClick={charger} className="text-accent font-semibold">Réessayer</button></p> : null}
      {r && !r.mesure ? <p className="text-[12.5px] text-argent2 mt-3">Tes comptes ne sont pas encore suivis.</p> : null}
      {r && r.mesure && r.joursEcoules === 0 ? <p className="text-[12.5px] text-argent2 mt-3">Ta moyenne s'affiche demain.</p> : null}
      {r && r.mesure && r.joursEcoules > 0 && r.manque === "deuxieme_non_lu" ? <p className="text-[12.5px] text-amber-200 mt-3">Ton compte 2 n'est pas encore suivi.</p> : null}
      {r && r.mesure && r.joursEcoules > 0 && r.manque === "deuxieme_compte" ? <p className="text-[12.5px] text-amber-200 mt-3">Il te faut 2 comptes de croissance.</p> : null}

      {deux.length || (r && clics !== null) ? (
        <div className="mt-3 space-y-3">
          {deux.map((c) => {
            const plan = cible && r ? planCompte(c, r, cible.reels) : null;
            return (
              <div key={c.handle}>
                <div className="flex items-baseline justify-between gap-2 text-[13.5px]">
                  <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full self-center" style={{ background: couleurCompte(c.rang) }} />Compte {c.rang}</span>
                  <b className="tabular-nums">{c.moyenne !== null ? dec(c.moyenne) : "–"}<span className="text-[11px] text-argent2 font-normal"> / jour</span></b>
                </div>
                {c.moyenne !== null ? <Jauge valeur={c.moyenne} max={MAX_JAUGE} couleur={couleurCompte(c.rang)} reperes={PALIERS.map((p) => p.reels)} /> : null}
                {c.suspendu ? <div className="text-[12px] text-amber-200 mt-1.5">{c.introuvable ? "Introuvable sur Instagram : compte pour 0" : "Suspendu : fais appel. Compte pour 0"}</div>
                  : c.moyenne === null ? <div className="text-[12px] text-amber-200 mt-1.5">Pas encore suivi</div>
                  : plan ? <div className={`text-[12px] mt-1.5 ${plan.ton === "ok" ? "text-emerald-300" : plan.ton === "perdu" ? "text-argent2" : "text-white"}`}>{plan.texte}</div> : null}
              </div>
            );
          })}
          {clics !== null ? (
            <div>
              <div className="flex items-baseline justify-between gap-2 text-[13.5px]">
                <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full self-center" style={{ background: VERT_CLICS }} />Clics</span>
                {clics >= cibleClics.clics ? <b className="tabular-nums text-emerald-300">{fmt(clics)} ✓</b>
                  : <b className="tabular-nums">{fmt(clics)}<span className="text-[11px] text-argent2 font-normal"> / {fmt(cibleClics.clics)}</span></b>}
              </div>
              <Jauge valeur={clics} max={cibleClics.clics} couleur={VERT_CLICS} />
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 rounded-2xl overflow-hidden text-[13px]" style={{ background: "rgba(255,255,255,0.04)" }}>
        {paliers.map((p, i) => {
          const vise = !p.atteint && cible?.reels === p.reels;
          return (
            <div key={p.reels} className={`flex items-center justify-between gap-2 px-3 py-2.5 ${i ? "border-t border-white/[0.06]" : ""} ${vise ? "bg-white/[0.05]" : ""}`}>
              <span className={p.atteint ? "text-emerald-300" : vise ? "text-white" : "text-argent2"}>
                {p.atteint ? "✓ " : ""}<b>{p.reels} / jour</b> par compte · {fmt(p.clics)} clics
              </span>
              <b className={`tabular-nums shrink-0 ${p.atteint ? "text-emerald-300" : ""}`}>+{p.bonus} $</b>
            </div>
          );
        })}
      </div>
    </div>
  );
}
