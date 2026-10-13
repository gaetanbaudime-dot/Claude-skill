"use client";
import { useMemo, useState } from "react";
import type { Pilotage as Donnees, Clipper360 } from "@/lib/pilotage";

const fmt = (n: number | null) => n == null ? "—" : new Intl.NumberFormat("fr-FR").format(n);
const norm = (x: string) => x.toLocaleLowerCase("fr-FR");

export default function Equipe360({ d, filtre }: { d: Donnees; filtre: string }) {
  const [recherche, setRecherche] = useState("");
  const tous = d.clippers || [];
  const liste = useMemo(() => tous.filter(x =>
    (!filtre || norm(x.creatrice) === norm(filtre)) &&
    (!recherche || norm([x.prenom, x.creatrice, x.tl, x.manager, ...x.comptes.map(a => a.handle)].join(" ")).includes(norm(recherche)))
  ), [tous, filtre, recherche]);
  const vas = liste.filter(x => x.role === "Clipper");
  const leads = liste.filter(x => x.role === "Team Leader");
  const managers = new Set(liste.map(x => x.managerUid).filter(Boolean));
  const alerts = vas.filter(x => x.anomalies !== "OK");
  const missing = vas.filter(x => x.visites7 == null).length;
  const visits = vas.reduce((sum, x) => sum + (x.visites7 || 0), 0);
  if (!tous.length) return <div className="carte p-5 mt-4 text-sm text-argent2">
    Le référentiel des clippers n'est pas encore disponible. Le bot doit publier « Référentiel clippers »
    dans le tableur privé. Aucune attribution n'est inventée en l'absence des données.
  </div>;
  return <div className="space-y-4 pt-2">
    <div className="grid grid-cols-2 gap-2">
      {[
        ["Clippers", String(vas.length) + " / 100"],
        ["Team Leaders / Managers", leads.length + " / " + managers.size],
        ["Comptes IG attribués", fmt(vas.reduce((n, x) => n + x.totalIg, 0))],
        ["Dossiers à vérifier", String(alerts.length)],
      ].map(([name, count]) => <div key={name} className="carte p-3">
        <p className="text-[11px] text-argent2">{name}</p>
        <p className="text-[25px] font-bold mt-1">{count}</p>
      </div>)}
    </div>
    <div className="carte p-3">
      <p className="text-xs font-semibold">Visites payables · 7 jours clos</p>
      <p className="text-2xl font-bold mt-1">{fmt(visits)}</p>
      {missing > 0 ? <p className="text-[11px] text-amber-200 mt-1">⚠ {missing} clipper(s) non entièrement mesurés : total partiel</p> : null}
      <p className="text-[11px] text-argent2 mt-1">Coût théorique sur les visites connues : {(visits * 0.05).toFixed(2)} $ à 0,05 $/visite, hors fixes et primes.</p>
    </div>
    {leads.length ? <section className="carte p-3">
      <h2 className="text-[13px] font-bold mb-3">Capacité TL · 10 clippers chacun</h2>
      <div className="space-y-3">
        {leads.map(tl => {
          const count = tous.filter(x => x.role === "Clipper" && x.tlUid === tl.uid).length;
          return <div key={tl.uid}>
            <div className="flex justify-between text-xs"><span>{tl.prenom} · {tl.creatrice}</span><span className={count > 10 ? "text-red-300" : "text-argent2"}>{count}/10</span></div>
            <div className="h-1.5 bg-white/10 rounded-full mt-1.5 overflow-hidden"><div className={count > 10 ? "h-full bg-red-400" : "h-full bg-sky-300"} style={{width: String(Math.min(count * 10, 100)) + "%"}} /></div>
          </div>;
        })}
      </div>
    </section> : null}
    <div className="flex justify-between items-center">
      <h2 className="text-base font-bold">Référentiel individuel</h2>
      <span className="text-xs text-argent2">{liste.length} personne(s)</span>
    </div>
    <input type="search" value={recherche} onChange={e => setRecherche(e.target.value)}
      placeholder="Prénom, créatrice, @ Instagram, TL…" aria-label="Rechercher un clipper"
      className="w-full rounded-xl px-3.5 py-3 bg-white/[0.06] border border-white/10 text-[13px] text-white placeholder:text-argent2" />
    <div className="space-y-3">
      {liste.map((x: Clipper360) => <article key={x.uid} className="carte p-3.5">
        <div className="flex justify-between gap-2">
          <div><h3 className="font-bold text-[15px]">{x.prenom} <span className="font-normal text-xs text-argent2">· {x.role}</span></h3>
            <p className="text-xs text-argent2">{x.creatrice || "Créatrice inconnue"}</p>
          </div>
          <span className={x.anomalies === "OK" ? "text-xs text-emerald-200" : "text-xs text-amber-200"}>{x.anomalies === "OK" ? "Conforme" : "À vérifier"}</span>
        </div>
        <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
          <div><p className="text-argent2">Team Leader</p><p>{x.tl || "Non attribué"}</p></div>
          <div><p className="text-argent2">Manager</p><p>{x.manager || "Non attribué"}</p></div>
          <div><p className="text-argent2">Application</p><p>{x.app ? "Connectée" : "Non associée"}</p></div>
          <div><p className="text-argent2">GAML</p><p>{x.liens} lien(s)</p></div>
        </div>
        <div className="space-y-1 mt-3">
          {x.comptes.map((c, i) => <div key={x.uid + "-" + i} className="flex justify-between gap-2 bg-white/[0.04] rounded-lg px-2.5 py-2 text-xs">
            <span className="truncate">{i + 1}. @{c.handle}</span><span className="text-argent2 shrink-0">{c.etat || "?"}</span>
          </div>)}
          {!x.comptes.length ? <p className="text-xs text-amber-200">Aucun compte Instagram relié</p> : null}
        </div>
        <p className="text-xs mt-3">Visites 7 j : <b>{fmt(x.visites7)}</b> · Reels 7 j : <b>{fmt(x.reels7)}</b></p>
        {x.anomalies !== "OK" ? <p className="text-xs mt-2 text-amber-200">{x.anomalies}</p> : null}
        <p className="text-[10px] text-argent2 mt-2">Discord UID {x.uid} · {x.qualiteVisites}</p>
      </article>)}
    </div>
    {!liste.length ? <p className="text-sm text-argent2 text-center">Aucune personne trouvée.</p> : null}
    <p className="text-[11px] text-argent2 pb-3">Vue en lecture seule. Les cas ambigus sont signalés et ne déclenchent aucune réattribution.</p>
  </div>;
}
