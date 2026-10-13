"use client";
import { useCallback, useEffect, useState } from "react";
import { signaler } from "@/lib/signal";
import { ouvrirInstagram } from "@/lib/instagram";

/** 12/10 (Gaëtan : « une application pour les team leaders… un onglet avec un lien direct vers Instagram pour voir les comptes de
 *  ses clippeurs, comme ça le team leader peut aller faire un retour rapidement ; genre sous Romaric, ses 3 comptes ») : chaque
 *  clipper de son équipe (colonne « Team leader » du classeur), ses visites payées de la période et le seuil des 500, puis ses
 *  comptes, chacun ouvrant Instagram d'un appui. */
type Compte = { n: number; handle: string; etat: string; followers: number | null; reels7: number | null; vues7: number | null };
type Membre = { cle: string; prenom: string; creatrice: string; comptes: Compte[]; visites: number | null; auSeuil: boolean; manquants: number };
type Equipe = { seuil: number; prime: number; primee: boolean; debut: string; fin: string; membres: Membre[] };
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const usd = (n: number) => `${n.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} $`;

export default function EquipeTab({ jeton }: { jeton: string }) {
  const [e, setE] = useState<Equipe | null>(null);
  const [erreur, setErreur] = useState(false);
  const charger = useCallback(async () => {
    try {
      const r = await fetch(`/api/k/${jeton}/equipe`, { cache: "no-store" });
      if (!r.ok) throw new Error();
      setE(await r.json()); setErreur(false);
    } catch { setErreur(true); }
  }, [jeton]);
  useEffect(() => { charger(); const id = setInterval(charger, 5 * 60_000); return () => clearInterval(id); }, [charger]);
  if (!e) {
    return erreur ? <div className="carte p-5 text-center text-argent2 mt-2">Ton équipe est en cours de mise à jour. <button className="text-accent font-semibold" onClick={charger}>Réessayer</button></div>
      : <div className="space-y-3 mt-2">{[0, 1, 2].map((i) => <div key={i} className="squelette h-32" />)}</div>;
  }
  const auSeuil = e.membres.filter((m) => m.auSeuil).length;
  return (
    <section className="space-y-3">
      <div className="carte p-4 apparait">
        <div className="text-[12px] text-argent2 font-medium">Ton équipe · {e.membres.length} clipper{e.membres.length > 1 ? "s" : ""}</div>
        <div className="flex items-baseline gap-2 mt-1">
          <div className="titre-argent text-[28px] font-bold tabular-nums">{e.primee ? usd(e.prime) : "–"}</div>
          <div className="text-[12px] text-argent2">{e.primee ? "prime d'équipe en cours" : "pas de prime d'équipe sur cette période"}</div>
        </div>
        <div className="text-[12px] text-argent2 mt-1">10 $ par clipper à {fmt(e.seuil)} visites payées ou plus sur la quinzaine · {auSeuil} sur {e.membres.length} pour l'instant</div>
      </div>
      <p className="text-[12.5px] text-argent2 px-1 leading-relaxed">Touche un compte pour l'ouvrir dans Instagram et faire ton retour au clipper.</p>
      {e.membres.map((m) => {
        const part = m.visites !== null ? Math.min(1, m.visites / Math.max(1, e.seuil)) : 0;
        return (
          <div key={m.cle} className="carte p-4 apparait">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[17px] font-bold">{m.prenom}</div>
                {m.creatrice ? <div className="text-[11.5px] text-argent2">{m.creatrice}</div> : null}
                {m.cle.startsWith("~") ? <div className="text-[11.5px] text-amber-200">En démarrage : comptes en création, pas encore de lien</div> : null}
              </div>
              <div className="text-right">
                <div className="text-[17px] font-bold tabular-nums">{m.visites !== null ? fmt(m.visites) : "–"} {m.auSeuil ? <span className="text-emerald-300">✓</span> : null}</div>
                <div className="text-[11px] text-argent2">visites payées{m.manquants ? ` · ${m.manquants} j non relevés` : ""}</div>
              </div>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden mt-2" style={{ background: "rgba(255,255,255,0.08)" }}>
              <div className="h-full rounded-full" style={{ width: `${Math.round(part * 100)}%`, background: m.auSeuil ? "#7ef0b2" : "linear-gradient(90deg,#2b6cff,#7aa7ff)" }} />
            </div>
            <div className="mt-3 space-y-1.5">
              {m.comptes.length ? m.comptes.map((c) => (
                <a key={c.handle} href={`https://www.instagram.com/${c.handle}/`} target="_blank" rel="noopener" onClick={(ev) => { ev.preventDefault(); signaler(jeton, "equipe:instagram"); ouvrirInstagram(c.handle); }}
                   className="flex items-center justify-between rounded-xl bg-white/[0.05] px-3 py-2.5 active:scale-[0.98] transition">
                  <div className="min-w-0">
                    <div className="text-[14px] font-semibold truncate">@{c.handle} <span className="text-accent">↗</span></div>
                    <div className="text-[11px] text-argent2">Compte {c.n}{c.etat ? ` · ${c.etat}` : ""}</div>
                  </div>
                  <div className="text-right text-[11.5px] text-argent2 shrink-0 leading-tight">
                    <div><b className="text-white tabular-nums">{c.followers !== null ? fmt(c.followers) : "–"}</b> fol.</div>
                    <div>{c.reels7 !== null ? `${c.reels7} Reels 7 j` : ""}</div>
                  </div>
                </a>
              )) : <div className="text-[12.5px] text-argent2">Pas encore de compte.</div>}
            </div>
          </div>
        );
      })}
    </section>
  );
}
