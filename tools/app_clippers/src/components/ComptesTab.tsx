"use client";
import { useCallback, useEffect, useState } from "react";
import { signaler } from "@/lib/signal";
import type { Pilotage } from "@/lib/pilotage";
import PilotageClipper from "./pilotage/PilotageClipper";
import MonEquipe from "./MonEquipe";

/** 12/10 (Gaëtan : « un onglet où il peut mettre à jour le @ de ses 3 comptes Instagram, ça nous permettra d'avoir toujours les
 *  bons ») : ses comptes dans l'ordre du parcours, chacun avec un lien direct vers Instagram et « Modifier le @ ». Le nouveau @
 *  part au bot (onglet « Pseudos app »), qui l'applique sous 15 minutes avec la règle de `!pseudo` et dit « fait » ou pourquoi
 *  c'est refusé. */
type Compte = { n: number; handle: string; etat: string; creatrice: string; followers: number | null; reels7: number | null; vues7: number | null };
type Demande = { n: number; handle: string; statut: string; detail: string; date: string };
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const NOMS = ["", "Compte 1", "Compte 2", "Compte 3"];

type Metricool = { n: number; eligible: boolean; statut: "disponible" | "attente" | "pret" | "connecte" | "renouveler" };
function MetricoolBouton({ jeton, n, etat, charger }: { jeton: string; n: number; etat?: Metricool; charger: () => Promise<void> }) {
  const [message, setMessage] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const demander = async () => {
    setEnvoi(true); setMessage("");
    try {
      const r = await fetch(`/api/k/${jeton}/metricool`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ n }) });
      const d = await r.json();
      if (!r.ok) { setMessage(d.erreur || "Réessaie dans une minute."); return; }
      setMessage("Demande enregistrée. Le bot prépare ta marque et ton lien après contrôle des accès de l’agence (jusqu’à 15 minutes).");
      await charger();
    } catch { setMessage("Envoi impossible, réessaie."); } finally { setEnvoi(false); }
  };
  if (!etat?.eligible) return null;
  return <div className="mt-4 border-t border-white/10 pt-3 text-[13px]">
    {etat.statut === "pret" ? <a href={`/api/k/${jeton}/metricool?n=${n}`} target="_blank" rel="noopener noreferrer"
      className="inline-block rounded-xl px-4 py-2.5 font-semibold bg-accent text-[#071226]">Connecter Metricool ↗</a> :
      etat.statut === "disponible" ? <button disabled={envoi} onClick={demander}
        className="rounded-xl px-4 py-2.5 font-semibold bg-accent text-[#071226] disabled:opacity-40">{envoi ? "Envoi…" : "Préparer Metricool"}</button> :
      <p className="text-accent">{etat.statut === "connecte" ? "Metricool connecté · validé par l’agence" :
        etat.statut === "renouveler" ? "Lien à renouveler par l’agence" : "Connexion Metricool demandée · validation agence en attente"}</p>}
    <p className="mt-2 text-argent2">Dès 500 abonnés vérifiés, le bot crée la marque de l’agence et prépare ton lien temporaire, selon les places disponibles et les accès de récupération validés.</p>
    {message ? <p role="status" className="mt-2 text-argent2">{message}</p> : null}
  </div>;
}

function Ligne({ c, demande, jeton, recharger, metricool, rechargerMetricool }: { c: Compte; demande?: Demande; jeton: string; recharger: () => void; metricool?: Metricool; rechargerMetricool: () => Promise<void> }) {
  const [edition, setEdition] = useState(false);
  const [saisie, setSaisie] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [message, setMessage] = useState("");
  const enAttente = demande && !demande.statut && demande.handle !== c.handle;
  const envoyer = async () => {
    setEnvoi(true); setMessage("");
    try {
      const r = await fetch(`/api/k/${jeton}/comptes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ n: c.n, handle: saisie }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setMessage(d.erreur || "Pas enregistré, réessaie."); return; }
      signaler(jeton, "compte:modifie");
      setEdition(false); setSaisie(""); recharger();
    } finally { setEnvoi(false); }
  };
  return (
    <div className="carte p-4 apparait">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-bold tracking-widest uppercase text-argent2">{NOMS[c.n] || `Compte ${c.n}`}{c.etat ? ` · ${c.etat}` : ""}</div>
          <a href={`https://www.instagram.com/${c.handle}/`} target="_blank" rel="noopener" onClick={() => signaler(jeton, "compte:instagram")}
             className="block text-[18px] font-bold truncate mt-0.5 text-white">@{c.handle} <span className="text-accent text-[14px]">↗</span></a>
        </div>
        <div className="text-right shrink-0 text-[12px] text-argent2 leading-tight">
          <div><b className="text-white text-[15px] tabular-nums">{c.followers !== null ? fmt(c.followers) : "–"}</b> followers</div>
          <div>{c.reels7 !== null ? `${c.reels7} Reels en 7 j` : ""}</div>
        </div>
      </div>
      {enAttente ? <div className="mt-3 text-[12.5px] rounded-xl px-3 py-2 bg-amber-400/10 text-amber-200">⏳ Changement vers @{demande!.handle} en cours : le bot le fait sous 15 minutes.</div> : null}
      {demande?.statut === "refusé" ? <div className="mt-3 text-[12.5px] rounded-xl px-3 py-2 bg-rose-400/10 text-rose-200">❌ @{demande.handle} refusé : {demande.detail}</div> : null}
      {edition ? (
        <div className="mt-3 flex gap-2">
          <input value={saisie} onChange={(e) => setSaisie(e.target.value)} placeholder="ton vrai @" autoCapitalize="none" autoCorrect="off" spellCheck={false}
                 className="flex-1 min-w-0 rounded-xl bg-white/[0.06] border border-white/10 px-3 py-2.5 text-[15px] outline-none focus:border-accent/60" />
          <button disabled={envoi || !saisie.trim()} onClick={envoyer} className="rounded-xl px-4 font-semibold bg-accent/90 text-[#071226] disabled:opacity-40">{envoi ? "…" : "OK"}</button>
          <button onClick={() => { setEdition(false); setMessage(""); }} className="rounded-xl px-3 text-argent2">✕</button>
        </div>
      ) : (
        <button onClick={() => setEdition(true)} className="mt-3 text-[13px] font-semibold text-accent">Ce n'est pas le bon @ ? Modifier</button>
      )}
      {message ? <div className="mt-2 text-[12.5px] text-rose-200">{message}</div> : null}
      <MetricoolBouton key={c.handle} jeton={jeton} n={c.n} etat={metricool} charger={rechargerMetricool} />
    </div>
  );
}

function MesComptes({ jeton }: { jeton: string }) {
  const [d, setD] = useState<{ comptes: Compte[]; demandes: Demande[]; pilotage: Pilotage | null } | null>(null);
  const [erreur, setErreur] = useState(false);
  const [metricool, setMetricool] = useState<Metricool[]>([]);
  const chargerMetricool = useCallback(async () => {
    try {
      const r = await fetch(`/api/k/${jeton}/metricool`, { cache: "no-store" });
      if (!r.ok) { setMetricool([]); return; }
      setMetricool((await r.json()).comptes);
    } catch { setMetricool([]); }
  }, [jeton]);
  const charger = useCallback(async () => {
    try {
      const r = await fetch(`/api/k/${jeton}/comptes`, { cache: "no-store" });
      if (!r.ok) throw new Error();
      setD(await r.json()); setErreur(false);
    } catch { setErreur(true); }
  }, [jeton]);
  useEffect(() => { charger(); const id = setInterval(charger, 60_000); return () => clearInterval(id); }, [charger]);
  useEffect(() => { chargerMetricool(); const id = setInterval(chargerMetricool, 60_000); return () => clearInterval(id); }, [chargerMetricool]);
  return (
    <section className="space-y-3">
      {!d && !erreur ? [0, 1, 2].map((i) => <div key={i} className="squelette h-28" />) : null}
      {erreur && !d ? <div className="carte p-5 text-center text-argent2">Les comptes sont en cours de mise à jour. <button className="text-accent font-semibold" onClick={charger}>Réessayer</button></div> : null}
      {erreur && d ? <p className="text-[12px] text-amber-200" role="status">Actualisation indisponible : dernières données affichées. <button onClick={charger} className="underline">Réessayer</button></p> : null}
      {d?.pilotage ? <PilotageClipper d={d.pilotage} /> : d ? <div className="carte p-4 text-[13px] text-argent2">Tes statistiques sont en cours de mise à jour. <button className="text-accent" onClick={charger}>Réessayer</button></div> : null}
      {d && !d.comptes.length ? <div className="carte p-5 text-center text-argent2">Pas encore de compte : ton compte 1 arrive dans ton salon Discord.</div> : null}
      {d?.comptes.length ? <details className="carte p-4">
        <summary className="cursor-pointer text-[14px] font-semibold">Gérer mes comptes et Metricool</summary>
        <p className="text-argent2 text-[13px] mt-3 leading-relaxed">Tu as changé un @ ? Corrige-le ici pour que tes Reels soient comptés sur le bon compte.</p>
        <div className="space-y-3 mt-3">{d.comptes.map((c) => <Ligne key={c.n} c={c} demande={d.demandes.find((x) => x.n === c.n)} jeton={jeton} recharger={charger}
        metricool={metricool.find(e => e.n === c.n)} rechargerMetricool={chargerMetricool} />)}
        </div>
      </details> : null}
    </section>
  );
}

/** 24/10 (Gaëtan : « dans les comptes, les comptes du team leader et ensuite les comptes de son équipe… deux onglets ») : un TL a
 *  deux vues dans Comptes. « Mes comptes » = exactement l'onglet d'un clipper (ses stats, ses @ modifiables, Metricool) ; « Mon
 *  équipe » = le pilotage de ses clippers (clics, Reels, vues, chaque @ vers Instagram), filtré côté serveur sur son équipe. Un
 *  clipper qui n'est pas TL ne voit aucun changement. Le choix est retenu sur le téléphone. */
type Vue = "moi" | "equipe";
export default function ComptesTab({ jeton, tl = false }: { jeton: string; tl?: boolean }) {
  const [vue, setVue] = useState<Vue>("moi");
  useEffect(() => {
    if (!tl) return;
    try { if (localStorage.getItem("gm-tl-comptes") === "equipe") setVue("equipe"); } catch { /* privé */ }
  }, [tl]);
  if (!tl) return <MesComptes jeton={jeton} />;
  const choisir = (v: Vue) => {
    setVue(v);
    signaler(jeton, v === "equipe" ? "onglet:equipe" : "onglet:comptes");
    try { localStorage.setItem("gm-tl-comptes", v); } catch { /* privé */ }
  };
  return (
    <div className="space-y-3">
      <div className="flex gap-2" role="tablist" aria-label="Comptes">
        {([["moi", "Mes comptes"], ["equipe", "Mon équipe"]] as const).map(([cle, titre]) =>
          <button key={cle} role="tab" aria-selected={vue === cle} onClick={() => choisir(cle)}
                  className={`flex-1 rounded-xl py-3 text-[14px] font-semibold ${vue === cle ? "bg-white text-black" : "bg-white/10 text-argent2"}`}>{titre}</button>)}
      </div>
      {vue === "moi" ? <MesComptes jeton={jeton} /> : <MonEquipe jeton={jeton} />}
    </div>
  );
}
