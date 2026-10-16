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
type Equipe = { seuil: number; prime: number | null; primee: boolean | null; debut: string; fin: string; membres: Membre[] };
const ETATS = [
  { nom: "Good", couleur: "text-emerald-300" },
  { nom: "Faire appel", couleur: "text-orange-300" },
  { nom: "Ban", couleur: "text-red-300" },
  { nom: "À créer", couleur: "text-white" },
];
const etatAffiche = (valeur: string) => ETATS.find((e) => e.nom.toLocaleLowerCase("fr") === valeur.trim().toLocaleLowerCase("fr"))
  || { nom: valeur.trim().toLocaleLowerCase("fr") === "prive" || valeur.trim().toLocaleLowerCase("fr") === "privé" ? "Type privé · état à vérifier" : "État à vérifier", couleur: "text-argent2" };
const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const usd = (n: number) => `${n.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} $`;

export default function EquipeTab({ jeton }: { jeton: string }) {
  const [e, setE] = useState<Equipe | null>(null);
  const [erreur, setErreur] = useState(false);
  const [vue, setVue] = useState<"traiter" | "equipe" | "resultats">("traiter");
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
        <div className="text-[12px] text-argent2 mt-1">Période : {e.debut || "non renseignée"} au {e.fin || "non renseignée"} · {auSeuil} sur {e.membres.length} au seuil de {fmt(e.seuil)} visites. Relevés manquants : résultat provisoire.</div>
        <p className="text-sm text-argent2 mt-3">Marge et activité J30 : non mesurées.</p>
      </div> : null}
      {vue === "equipe" ? <><p className="text-[12.5px] text-argent2 px-1 leading-relaxed">Touche un compte pour l'ouvrir dans Instagram et faire ton retour au clipper.</p>
      <div className="flex flex-wrap gap-3 text-xs" aria-label="États des comptes">{ETATS.map((e) => <span key={e.nom} className={e.couleur}>{e.nom}</span>)}</div>
      {e.membres.map((m) => {
        const part = m.visites !== null ? Math.min(1, m.visites / Math.max(1, e.seuil)) : 0;
        return (
          <div key={m.cle} className="carte p-4 apparait">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[17px] font-bold">{m.prenom}</div>
                {m.creatrice ? <div className="text-[11.5px] text-argent2">{m.creatrice}</div> : null}
                {m.cle.startsWith("~") ? <div className="text-[11.5px] text-amber-200">Rattachement à vérifier : aucun lien confirmé ici</div> : null}
              </div>
              <div className="text-right">
                <div className="text-[17px] font-bold tabular-nums">{m.visites !== null ? fmt(m.visites) : "–"} {m.auSeuil ? <span className="text-emerald-300">✓</span> : null}</div>
                <div className="text-[11px] text-argent2">visites payées{m.manquants ? ` · ${m.manquants} j non relevés` : ""}</div>
              </div>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden mt-2" style={{ background: "rgba(255,255,255,0.08)" }}>
              <div className="h-full rounded-full" style={{ width: `${Math.round(part * 100)}%`, background: m.auSeuil ? "#7ef0b2" : "linear-gradient(90deg,#2b6cff,#7aa7ff)" }} />
            </div>
            <details className="mt-3"><summary className="cursor-pointer text-sm font-semibold">Comptes et mesures disponibles</summary><div className="mt-3 space-y-1.5">
              {m.comptes.length ? m.comptes.map((c) => (
                <a key={c.handle} href={`https://www.instagram.com/${c.handle}/`} target="_blank" rel="noopener" onClick={(ev) => { ev.preventDefault(); signaler(jeton, "equipe:instagram"); ouvrirInstagram(c.handle); }}
                   className="flex items-center justify-between rounded-xl bg-white/[0.05] px-3 py-2.5 active:scale-[0.98] transition">
                  <div className="min-w-0">
                    <div className="text-[14px] font-semibold truncate">@{c.handle} <span className="text-accent">↗</span></div>
                    <div className="text-[11px] text-argent2">Compte {c.n} · <span className={etatAffiche(c.etat).couleur}>{etatAffiche(c.etat).nom}</span></div>
                  </div>
                  <div className="text-right text-[11.5px] text-argent2 shrink-0 leading-tight">
                    <div><b className="text-white tabular-nums">{c.followers !== null ? fmt(c.followers) : "–"}</b> fol.</div>
                    <div>{c.reels7 !== null ? `${c.reels7} Reels 7 j` : ""}</div>
                  </div>
                </a>
              )) : <div className="text-[12.5px] text-argent2">Aucun compte renseigné ; faire vérifier le dossier.</div>}
            </div></details>
          </div>
        );
      })}</> : null}
    </section>
  );
}
