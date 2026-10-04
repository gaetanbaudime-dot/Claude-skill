"use client";
import { useEffect, useState } from "react";
import Logo from "./Logo";
import DriveTab from "./DriveTab";
import ReelsTab from "./ReelsTab";
import StatsTab from "./StatsTab";

type Onglet = "drive" | "reels" | "stats";

const ONGLETS: { cle: Onglet; libelle: string; icone: (actif: boolean) => JSX.Element }[] = [
  { cle: "drive", libelle: "Drive", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.6a2 2 0 0 1 1.6.8l1 1.4a2 2 0 0 0 1.6.8h5.2A2.5 2.5 0 0 1 21 10.5v6A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} />
    </svg>) },
  { cle: "reels", libelle: "Reels", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="5" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} /><path d="M3 9h18M9 3l3 6M15 3l3 6" /><path d="M10.5 12.5v5l4-2.5z" fill="currentColor" stroke="none" />
    </svg>) },
  { cle: "stats", libelle: "Stats", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19V5M4 19h16" /><path d="M8 15l3.5-4 3 2.5L19 8" /><circle cx="19" cy="8" r="1.6" fill="currentColor" stroke="none" />
    </svg>) },
];

export default function App({ prenom, jeton, mym }: { prenom: string; jeton: string; mym: boolean }) {
  const [onglet, setOnglet] = useState<Onglet>("stats");
  useEffect(() => {
    try { const m = localStorage.getItem("gm-onglet") as Onglet | null; if (m && ONGLETS.some((o) => o.cle === m)) setOnglet(m); } catch { /* privé */ }
  }, []);
  const choisir = (o: Onglet) => { setOnglet(o); try { localStorage.setItem("gm-onglet", o); } catch { /* privé */ } };
  const heure = new Date().getHours();
  const salut = heure < 5 ? "Bonne nuit" : heure < 12 ? "Bonjour" : heure < 18 ? "Bon après-midi" : "Bonsoir";
  return (
    <div className="min-h-dvh flex flex-col" style={{ paddingTop: "var(--safe-haut)" }}>
      <header className="px-5 pt-5 pb-3 flex items-center gap-3">
        <Logo taille={42} />
        <div className="leading-tight">
          <div className="text-[13px] text-argent2 font-medium">{salut}</div>
          <div className="titre-argent text-[22px] font-bold">{prenom}</div>
        </div>
      </header>
      <main className="flex-1 px-4 pb-28" key={onglet}>
        {onglet === "drive" && <DriveTab jeton={jeton} mym={mym} />}
        {onglet === "reels" && <ReelsTab />}
        {onglet === "stats" && <StatsTab jeton={jeton} />}
      </main>
      <nav className="barre fixed bottom-0 inset-x-0 px-6 pt-2" style={{ paddingBottom: "calc(var(--safe-bas) + 10px)" }} aria-label="Onglets">
        <div className="grid grid-cols-3 max-w-md mx-auto">
          {ONGLETS.map((o) => {
            const actif = o.cle === onglet;
            return (
              <button key={o.cle} onClick={() => choisir(o.cle)} aria-current={actif ? "page" : undefined}
                      className={`flex flex-col items-center gap-1 py-1 ${actif ? "text-white" : "text-argent2"}`}>
                {o.icone(actif)}
                <span className="text-[11px] font-semibold tracking-wide">{o.libelle}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
