"use client";
import { useEffect, useState } from "react";
import Logo from "./Logo";
import DriveTab from "./DriveTab";
import ReelsTab from "./ReelsTab";
import VersementsTab from "./VersementsTab";
import ComptesTab from "./ComptesTab";
import EquipeTab from "./EquipeTab";
import Installer from "./Installer";
import { modeApp, signaler } from "@/lib/signal";

type Onglet = "drive" | "reels" | "comptes" | "equipe" | "versements";

/** Les trois onglets, dans l'ordre du dessin de Gaëtan : nuage (Drive), flèche (Reels), dollar (Versements). */
const ONGLETS: { cle: Onglet; libelle: string; icone: (actif: boolean) => JSX.Element }[] = [
  { cle: "drive", libelle: "Drive", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 18.5h10.5a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.3 9.2 4.7 4.7 0 0 0 7 18.5z" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} />
      <path d="M12 15.5v-5M9.6 12.9 12 10.5l2.4 2.4" />
    </svg>) },
  { cle: "reels", libelle: "Reels", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="5" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} />
      <path d="M8 16 16 8M10 8h6v6" />
    </svg>) },
  { cle: "comptes", libelle: "Comptes", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3.5" y="3.5" width="17" height="17" rx="5" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} />
      <circle cx="12" cy="12" r="3.8" /><circle cx="17" cy="7" r="0.9" fill="currentColor" />
    </svg>) },
  { cle: "equipe", libelle: "Équipe", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="7.5" r="3" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} /><circle cx="5.5" cy="10" r="2.2" /><circle cx="18.5" cy="10" r="2.2" />
      <path d="M6.5 20a5.5 5.5 0 0 1 11 0M1.8 18.5a3.8 3.8 0 0 1 4-3.3M22.2 18.5a3.8 3.8 0 0 0-4-3.3" />
    </svg>) },
  { cle: "versements", libelle: "Versements", icone: (a) => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9.5" fill={a ? "currentColor" : "none"} fillOpacity={a ? 0.18 : 0} />
      <path d="M12 6.5v11" /><path d="M14.6 9.2a2.6 2.6 0 0 0-2.3-1.2h-.8a2.1 2.1 0 0 0 0 4.2h1a2.1 2.1 0 0 1 0 4.2h-.8a2.6 2.6 0 0 1-2.3-1.2" />
    </svg>) },
];

export default function App({ prenom, creatrice, jeton, tl = false }: { prenom: string; creatrice: string; jeton: string; tl?: boolean }) {
  const [onglet, setOnglet] = useState<Onglet>(tl ? "equipe" : "drive");
  const onglets = ONGLETS.filter((o) => o.cle !== "equipe" || tl);         // 12/10 : l'onglet Équipe, pour un Team Leader seulement
  useEffect(() => {
    try { const m = localStorage.getItem("gm-clipper-onglet") as Onglet | null; if (m && ONGLETS.some((o) => o.cle === m) && (m !== "equipe" || tl)) setOnglet(m); } catch { /* privé */ }
    signaler(jeton, "ouverture", modeApp());
    // Le service worker rend l'app installable d'un geste sur Android (Chrome, Samsung Internet) et donne une page hors ligne.
    try { if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("/sw.js").catch(() => undefined); } catch { /* rien */ }
  }, [jeton, tl]);
  const choisir = (o: Onglet) => { setOnglet(o); signaler(jeton, `onglet:${o}`); try { localStorage.setItem("gm-clipper-onglet", o); } catch { /* privé */ } };
  const heure = new Date().getHours();
  const salut = heure < 5 ? "Bonne nuit" : heure < 12 ? "Bonjour" : heure < 18 ? "Bon après-midi" : "Bonsoir";
  return (
    <div className="min-h-dvh flex flex-col" style={{ paddingTop: "var(--safe-haut)" }}>
      <header className="px-5 pt-5 pb-3 flex items-center gap-3">
        <Logo taille={42} />
        <div className="leading-tight">
          <div className="text-[13px] text-argent2 font-medium">{salut}{creatrice ? ` · équipe ${creatrice}` : ""}</div>
          <div className="titre-argent text-[22px] font-bold">{prenom}</div>
        </div>
      </header>
      <main className="flex-1 px-4 pb-28">
        <Installer jeton={jeton} />
        {onglet === "drive" && <DriveTab jeton={jeton} creatrice={creatrice} />}
        <ReelsTab actif={onglet === "reels"} />
        {onglet === "comptes" && <ComptesTab jeton={jeton} />}
        {onglet === "equipe" && tl && <EquipeTab key={jeton} jeton={jeton} />}
        {onglet === "versements" && <VersementsTab jeton={jeton} />}
      </main>
      <nav className={`barre fixed bottom-0 inset-x-0 ${onglets.length > 4 ? "px-1" : "px-4"} pt-2`} style={{ paddingBottom: "calc(var(--safe-bas) + 10px)" }} aria-label="Onglets">
        <div className={`grid ${onglets.length > 4 ? "grid-cols-5" : "grid-cols-4"} max-w-md mx-auto`}>
          {onglets.map((o) => {
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
