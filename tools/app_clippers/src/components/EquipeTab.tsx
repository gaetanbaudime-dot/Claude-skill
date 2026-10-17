"use client";
import { useCallback, useEffect, useState } from "react";
import type { Pilotage } from "@/lib/pilotage";
import Horizontal from "./pilotage/Horizontal";
import { PERIODES, type Periode } from "./pilotage/calc";

/** Même pilotage horizontal que l'admin, sur une projection filtrée côté serveur par les attributions du TL. */
type Compte = { n: number; handle: string; etat: string; followers: number | null; reels7: number | null; vues7: number | null };
type Membre = { cle: string; prenom: string; creatrice: string; comptes: Compte[]; visites: number | null; auSeuil: boolean; manquants: number };
type Equipe = { seuil: number; prime: number | null; primee: boolean | null; debut: string; fin: string; membres: Membre[]; pilotage: Pilotage | null };
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const usd = (n: number) => `${n.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} $`;

export default function EquipeTab({ jeton }: { jeton: string }) {
  const [e, setE] = useState<Equipe | null>(null);
  const [erreur, setErreur] = useState(false);
  const [vue, setVue] = useState<"traiter" | "equipe" | "resultats">("equipe");
  const [periode, setPeriode] = useState<Periode>("j7");
  const [filtre, setFiltre] = useState("");
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
  const incomplets = e.membres.filter((m) => m.visites === null || m.manquants > 0).length;
  const problemes = e.membres.flatMap((m) => {
    const lignes: { cle: string; membre: string; probleme: string; action: string }[] = [];
    if (!m.comptes.length) lignes.push({ cle: `${m.cle}:comptes`, membre: m.prenom, probleme: "Aucun compte renseigné", action: "Faire vérifier le dossier avant toute création." });
    for (const c of m.comptes) {
      const etat = c.etat.trim().toLocaleLowerCase("fr");
      if (etat !== "good") lignes.push({ cle: `${m.cle}:${c.handle}`, membre: m.prenom, probleme: `@${c.handle} · ${["ban", "faire appel", "à créer", "a creer"].includes(etat) ? c.etat : "état à vérifier"}`, action: etat === "ban" || etat === "faire appel" ? "Vérifier la preuve datée et le recours possible ; aucun remplacement." : "Faire vérifier la prochaine étape et ses preuves dans le dossier." });
    }
    if (m.visites === null || m.manquants > 0) lignes.push({ cle: `${m.cle}:releves`, membre: m.prenom, probleme: "Visites non mesurées ou incomplètes", action: "Vérifier les relevés avant de conclure sur les résultats." });
    return lignes;
  });
  return (
    <section className="space-y-3">
      <div className="flex gap-2" role="group" aria-label="Accueil de l’équipe">
        {([ ["traiter", "À traiter"], ["equipe", "Équipe"], ["resultats", "Résultats"] ] as const).map(([cle, titre]) =>
          <button key={cle} onClick={() => setVue(cle)} aria-pressed={vue === cle} className={`flex-1 rounded-xl py-3 text-sm font-semibold ${vue === cle ? "bg-white text-black" : "bg-white/10 text-argent2"}`}>{titre}</button>)}
      </div>
      {erreur ? <p role="status" className="text-amber-200 text-sm">Actualisation indisponible : dernières données affichées. <button onClick={charger} className="underline">Réessayer</button></p> : null}
      {vue === "traiter" ? <div className="space-y-3">
        <p className="text-sm text-argent2">{problemes.length ? `${problemes.length} point(s) à vérifier` : "Aucun point bloquant détecté dans les données disponibles."}</p>
        {problemes.map((p) => <article key={p.cle} className="carte p-4">
          <h2 className="font-semibold">{p.membre} · {p.probleme}</h2>
          <p className="text-sm text-argent2 mt-2">{p.action}</p>
          <button className="text-accent mt-3 text-sm font-semibold" onClick={() => setVue("equipe")}>Voir l’équipe</button>
        </article>)}
      </div> : null}
      {vue === "resultats" ? <div className="carte p-4 apparait">
        <div className="text-[12px] text-argent2 font-medium">Ton équipe · {e.membres.length} clipper{e.membres.length > 1 ? "s" : ""}</div>
        <div className="flex items-baseline gap-2 mt-1">
          <div className="titre-argent text-[28px] font-bold tabular-nums">{e.primee === true && e.prime !== null ? usd(e.prime) : "–"}</div>
          <div className="text-[12px] text-argent2">{e.primee === null ? "prime non mesurée" : e.primee ? "prime d’équipe en cours, provisoire" : "pas de prime d’équipe sur cette période"}</div>
        </div>
        <div className="text-[12px] text-argent2 mt-1">Période : {e.debut || "non renseignée"} au {e.fin || "non renseignée"} · {auSeuil} seuil(s) confirmé(s) à {fmt(e.seuil)} visites. {incomplets ? `${incomplets} dossier(s) incomplet(s) : résultat provisoire.` : "Relevés disponibles sur cette période."}</div>
        <p className="text-sm text-argent2 mt-3">Marge et activité J30 : non mesurées.</p>
      </div> : null}
      {vue === "equipe" ? <>
        <div className="segment" role="group" aria-label="Période du pilotage">
          <span className="pastille" style={{ left: `calc(4px + ${PERIODES.findIndex(p => p.cle === periode)} * (100% - 8px) / 4)`, width: "calc((100% - 8px) / 4)" }} />
          {PERIODES.map(p => <button key={p.cle} aria-pressed={p.cle === periode} onClick={() => setPeriode(p.cle)}>{p.libelle}</button>)}
        </div>
        <div className="flex gap-2 overflow-x-auto no-scrollbar" role="group" aria-label="Créatrice">
          {["", ...Array.from(new Set(e.membres.map(m => m.creatrice).filter(Boolean)))].map(c => <button key={c || "toutes"} aria-pressed={filtre === c} onClick={() => setFiltre(c)} className={`shrink-0 rounded-full px-3 py-2 text-xs ${filtre === c ? "bg-white/15 text-white" : "bg-white/5 text-argent2"}`}>{c || "Toutes"}</button>)}
        </div>
        {e.pilotage ? <Horizontal d={e.pilotage} periode={periode} filtre={filtre} /> : <div className="carte p-4 text-sm text-argent2">Les statistiques de ton équipe sont en cours de mise à jour. <button onClick={charger} className="text-accent">Réessayer</button></div>}
      </> : null}
    </section>
  );
}
