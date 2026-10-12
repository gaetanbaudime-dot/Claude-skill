"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Pilotage as Donnees } from "@/lib/pilotage";
import { couleur, creatrices, PERIODES, type Periode } from "./calc";
import Vertical from "./Vertical";
import Horizontal from "./Horizontal";
import Subs from "./Subs";

type Onglet = "vertical" | "horizontal" | "subs";
const RAFRAICHIR_MS = 5 * 60 * 1000;

const ONGLETS: { cle: Onglet; libelle: string; icone: (a: boolean) => JSX.Element }[] = [
  { cle: "vertical", libelle: "Vertical", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="6.5" y="2.5" width="11" height="19" rx="3" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} /><path d="M12 15.5v-7M9.3 11 12 8.3l2.7 2.7" />
    </svg>) },
  { cle: "horizontal", libelle: "Horizontal", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="7" r="3" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} /><circle cx="5" cy="16" r="2.4" /><circle cx="19" cy="16" r="2.4" /><path d="M8.6 18.8h6.8M10 9.6 6.4 14M14 9.6l3.6 4.4" />
    </svg>) },
  { cle: "subs", libelle: "Subs", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9.5" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} /><path d="M15.5 9.2a3.6 3.6 0 1 0 0 5.6M8 11h5M8 13.2h5" />
    </svg>) },
];

function depuis(iso: string): { texte: string; vieux: boolean } {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return { texte: "jamais publié", vieux: true };
  const min = Math.round((Date.now() - t) / 60000);
  const texte = min < 1 ? "à l'instant" : min < 60 ? `il y a ${min} min` : min < 48 * 60 ? `il y a ${Math.round(min / 60)} h` : `il y a ${Math.round(min / 1440)} j`;
  return { texte, vieux: min > 60 };
}

export default function Pilotage({ jeton }: { jeton: string }) {
  const [d, setD] = useState<Donnees | null>(null);
  const [erreur, setErreur] = useState("");
  const [onglet, setOnglet] = useState<Onglet>("horizontal");
  const [periode, setPeriode] = useState<Periode>("hier");
  const [filtre, setFiltre] = useState<string>("");                    // "" = toutes les créatrices

  const charger = useCallback(async () => {
    try {
      const r = await fetch(`/api/p/${jeton}`, { cache: "no-store" });
      if (!r.ok) throw new Error(r.status === 503 ? "Le tableur ne répond pas, réessaie dans une minute." : `Erreur ${r.status}`);
      setD((await r.json()) as Donnees);
      setErreur("");
    } catch (e) {
      setErreur((e as Error).message);
    }
  }, [jeton]);

  useEffect(() => {
    try {
      const o = localStorage.getItem("gm-pilotage-onglet") as Onglet | null;
      if (o && ONGLETS.some((x) => x.cle === o)) setOnglet(o);
      const p = localStorage.getItem("gm-pilotage-periode") as Periode | null;
      if (p && PERIODES.some((x) => x.cle === p)) setPeriode(p);
    } catch { /* navigation privée */ }
    charger();
    const id = setInterval(() => { if (document.visibilityState === "visible") charger(); }, RAFRAICHIR_MS);
    const vu = () => { if (document.visibilityState === "visible") charger(); };
    document.addEventListener("visibilitychange", vu);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", vu); };
  }, [charger]);

  const choisirOnglet = (o: Onglet) => { setOnglet(o); try { localStorage.setItem("gm-pilotage-onglet", o); } catch { /* rien */ } window.scrollTo({ top: 0 }); };
  const choisirPeriode = (p: Periode) => { setPeriode(p); try { localStorage.setItem("gm-pilotage-periode", p); } catch { /* rien */ } };
  const liste = useMemo(() => (d ? creatrices(d) : []), [d]);
  const idx = PERIODES.findIndex((p) => p.cle === periode);
  const fraiche = d ? depuis(d.publie) : null;

  return (
    <div className="min-h-dvh pb-28" style={{ paddingTop: "calc(var(--safe-haut) + 14px)" }}>
      <header className="px-4">
        <div className="flex items-center justify-between">
          <h1 className="titre-argent text-[26px] font-bold">{ONGLETS.find((o) => o.cle === onglet)?.libelle}</h1>
          {fraiche ? (
            <button onClick={charger} className={`text-[11.5px] px-2.5 py-1 rounded-full ${fraiche.vieux ? "bg-amber-400/15 text-amber-200" : "bg-white/5 text-argent2"}`}>
              {fraiche.vieux ? "⚠ " : ""}MAJ {fraiche.texte}
            </button>
          ) : null}
        </div>
        <div className="segment mt-3">
          <span className="pastille" style={{ left: `calc(4px + ${idx} * (100% - 8px) / ${PERIODES.length})`, width: `calc((100% - 8px) / ${PERIODES.length})` }} />
          {PERIODES.map((p) => <button key={p.cle} aria-pressed={p.cle === periode} onClick={() => choisirPeriode(p.cle)}>{p.libelle}</button>)}
        </div>
        {liste.length > 1 ? (
          <div className="flex gap-2 overflow-x-auto no-scrollbar mt-3 -mx-4 px-4 pb-1">
            {["", ...liste].map((c, i) => (
              <button key={c || "toutes"} onClick={() => setFiltre(c)}
                className={`shrink-0 text-[12.5px] px-3 py-1.5 rounded-full border transition ${filtre === c ? "bg-white/15 border-white/20 text-white" : "bg-white/[0.03] border-white/[0.06] text-argent2"}`}>
                {c ? <span className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle" style={{ background: couleur(c, i) }} /> : null}{c || "Toutes"}
              </button>
            ))}
          </div>
        ) : null}
      </header>

      <main className="px-4 mt-2">
        {erreur && !d ? <div className="carte p-5 mt-6 text-center text-argent2">{erreur}</div> : null}
        {!d && !erreur ? <div className="space-y-3 mt-4">{[0, 1, 2].map((i) => <div key={i} className="squelette h-28" />)}</div> : null}
        {d && !d.publie ? (
          <div className="carte p-5 mt-6 text-argent2 text-[14px] leading-relaxed">
            Le bot n'a encore rien publié. Les onglets « Pilotage » du tableur se remplissent au prochain passage du Dashboard (15 minutes au plus après le déploiement du bot).
          </div>
        ) : null}
        {d && d.publie ? (
          <>
            {onglet === "vertical" ? <Vertical d={d} periode={periode} filtre={filtre} /> : null}
            {onglet === "horizontal" ? <Horizontal d={d} periode={periode} filtre={filtre} /> : null}
            {onglet === "subs" ? <Subs d={d} periode={periode} filtre={filtre} /> : null}
            {d.fraicheur ? <p className="text-[11px] text-argent2/80 mt-8 px-1 leading-relaxed">Sources : {d.fraicheur}</p> : null}
          </>
        ) : null}
      </main>

      <nav className="barre fixed bottom-0 inset-x-0 z-20" style={{ paddingBottom: "calc(var(--safe-bas) + 6px)" }}>
        <div className="grid grid-cols-3 max-w-md mx-auto">
          {ONGLETS.map((o) => {
            const actif = o.cle === onglet;
            return (
              <button key={o.cle} onClick={() => choisirOnglet(o.cle)} className={`flex flex-col items-center gap-0.5 pt-2.5 pb-1 ${actif ? "text-white" : "text-argent2"}`}>
                {o.icone(actif)}
                <span className="text-[10.5px] font-medium">{o.libelle}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
