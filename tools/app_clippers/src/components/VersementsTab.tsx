"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { signaler } from "@/lib/signal";

type Jour = { jour: string; visites: number; complet: boolean };
type Bloc = { debut: string; fin: string; paie: string; libelle: string; libellePaie: string; visites: number; montant: number; complet: boolean };
type Versements = {
  prenom: string; creatrice: string; taux: number;
  liens: { url: string; creeLe: string }[];
  periode: Bloc; aujourdhui: Jour; hier: Jour; serie: Jour[];
  precedents: (Bloc & { versee: boolean })[];
  partiel: boolean; majA: string;
};

const RAFRAICHIR_MS = 5 * 60 * 1000;                                   // le jour en cours bouge : on relit toutes les 5 minutes
const fmtNb = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
/** « 130 $ » quand c'est rond, « 130,45 $ » sinon ; toujours deux décimales si `exact`. */
const fmtUsd = (n: number, exact = false) => `${n.toLocaleString("fr-FR", { minimumFractionDigits: exact || !Number.isInteger(n) ? 2 : 0, maximumFractionDigits: 2 })} $`;
const jourCourt = (j: string) => { const d = new Date(j + "T12:00:00Z"); return `${d.getUTCDate()}/${String(d.getUTCMonth() + 1).padStart(2, "0")}`; };
const compact = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} k` : `${Math.round(v)}`);

function Compteur({ valeur, format }: { valeur: number; format: (n: number) => string }) {
  const [affiche, setAffiche] = useState(0);
  const depuis = useRef(0);
  useEffect(() => {
    const debut = depuis.current, cible = valeur, t0 = performance.now(), duree = 650;
    let id = 0;
    const pas = (t: number) => { const p = Math.min(1, (t - t0) / duree); const e = 1 - Math.pow(1 - p, 3); setAffiche(debut + (cible - debut) * e); if (p < 1) id = requestAnimationFrame(pas); else depuis.current = cible; };
    id = requestAnimationFrame(pas);
    return () => cancelAnimationFrame(id);
  }, [valeur]);
  return <>{format(affiche)}</>;
}

function Infobulle({ active, payload, label, taux }: { active?: boolean; payload?: { value: number }[]; label?: string; taux: number }) {
  if (!active || !payload?.length) return null;
  const v = payload[0].value ?? 0;
  return (
    <div className="carte px-3 py-2 text-[12px]" style={{ borderRadius: 12 }}>
      <div className="text-argent2 mb-1">{label}</div>
      <div className="font-semibold">{fmtNb(v)} visite{v > 1 ? "s" : ""}</div>
      <div className="text-emerald-300 mt-0.5">{fmtUsd(Math.round(v * taux * 100) / 100, true)}</div>
    </div>
  );
}

export default function VersementsTab({ jeton }: { jeton: string }) {
  const [v, setV] = useState<Versements | null>(null);
  const [erreur, setErreur] = useState(false);
  const [chargement, setChargement] = useState(true);
  const [copie, setCopie] = useState(false);
  const derniere = useRef(0);

  const charger = useCallback(async () => {
    setChargement(true);
    try {
      const r = await fetch(`/api/k/${jeton}/versements`, { cache: "no-store" });
      if (!r.ok) throw new Error("indisponible");
      setV((await r.json()) as Versements); setErreur(false); derniere.current = Date.now();
    } catch { setErreur(true); }
    setChargement(false);
  }, [jeton]);

  useEffect(() => {
    charger();
    const id = setInterval(charger, RAFRAICHIR_MS);
    const visible = () => { if (document.visibilityState === "visible" && Date.now() - derniere.current > 60 * 1000) charger(); };
    document.addEventListener("visibilitychange", visible);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", visible); };
  }, [charger]);

  const serie = useMemo(() => (v?.serie || []).map((j) => ({ ...j, label: jourCourt(j.jour) })), [v]);
  const copier = async (url: string) => {
    try { await navigator.clipboard.writeText(url); setCopie(true); signaler(jeton, "lien:copie"); setTimeout(() => setCopie(false), 1800); } catch { /* le clipper copiera à la main */ }
  };
  const p = v?.periode;

  return (
    <section className="space-y-3">
      {erreur && !v && <div className="carte apparait p-5 text-center text-argent2">Les chiffres sont en cours de mise à jour. <button className="text-accent font-semibold ml-1" onClick={charger}>Réessayer</button></div>}

      <div className={`carte apparait p-5 ${chargement && v ? "opacity-70" : ""}`} style={{ transition: "opacity 200ms" }}>
        <div className="flex items-baseline justify-between">
          <div className="text-[13px] text-argent2 font-medium">{p ? `Période en cours · ${p.libelle}` : "Chargement…"}</div>
          {v && <span className="text-[11px] text-argent2/70">{fmtUsd(v.taux, true)} la visite</span>}
        </div>
        <div className="titre-argent text-[40px] font-bold leading-none mt-2 tabular-nums">{p ? <Compteur valeur={p.montant} format={(n) => fmtUsd(Math.round(n * 100) / 100, true)} /> : <span className="squelette inline-block h-9 w-40" />}</div>
        <div className="text-[12px] text-argent2 mt-1">{p ? `${fmtNb(p.visites)} visite${p.visites > 1 ? "s" : ""} francophone${p.visites > 1 ? "s" : ""} depuis le ${jourCourt(p.debut)}` : "visites francophones"}</div>
        <div className="mt-4 rounded-2xl p-3 flex items-center gap-3" style={{ background: "rgba(52,211,153,0.10)" }}>
          <svg className="text-emerald-300 shrink-0" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="16" rx="4" /><path d="M3 10h18M8 3v4M16 3v4" /><path d="m9.5 15.5 1.8 1.8 3.4-3.6" /></svg>
          <div className="leading-tight">
            <div className="text-[11px] font-bold tracking-widest uppercase text-emerald-300">Prochain versement</div>
            <div className="text-[17px] font-bold mt-0.5">{p ? `${fmtUsd(p.montant)} le ${p.libellePaie}` : "—"}</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="rounded-2xl p-3" style={{ background: "rgba(122,167,255,0.09)" }}>
            <div className="text-[11px] font-bold tracking-widest text-accent">AUJOURD'HUI</div>
            <div className="text-[20px] font-bold mt-1 tabular-nums">{v ? <Compteur valeur={v.aujourdhui.visites} format={(n) => fmtNb(Math.round(n))} /> : "—"}</div>
            <div className="text-[12px] text-argent2 mt-1">{v ? `visites · ${fmtUsd(Math.round(v.aujourdhui.visites * v.taux * 100) / 100, true)}` : ""}</div>
          </div>
          <div className="rounded-2xl p-3" style={{ background: "rgba(255,255,255,0.05)" }}>
            <div className="text-[11px] font-bold tracking-widest text-argent2">HIER</div>
            <div className="text-[20px] font-bold mt-1 tabular-nums">{v ? <Compteur valeur={v.hier.visites} format={(n) => fmtNb(Math.round(n))} /> : "—"}</div>
            <div className="text-[12px] text-argent2 mt-1">{v ? `visites · ${fmtUsd(Math.round(v.hier.visites * v.taux * 100) / 100, true)}` : ""}</div>
          </div>
        </div>
        {v?.partiel && <div className="text-[12px] text-amber-300/90 mt-3">Chiffres en cours de mise à jour : certains jours ne sont pas encore comptés.</div>}
      </div>

      <div className="carte apparait-2 p-4">
        <div className="flex items-baseline justify-between mb-1">
          <div className="text-[14px] font-semibold">Visites francophones par jour</div>
          <div className="text-[11px] text-argent2">{serie.length ? `${serie.length} jours` : ""}</div>
        </div>
        <div style={{ height: 180 }}>
          {v ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={serie} margin={{ top: 8, right: 4, left: -6, bottom: 0 }} barCategoryGap="28%">
                <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="label" tick={{ fill: "#8b96a8", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={28} />
                <YAxis tick={{ fill: "#8b96a8", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={compact} width={40} allowDecimals={false} />
                <Tooltip content={<Infobulle taux={v.taux} />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />
                <Bar dataKey="visites" radius={[6, 6, 0, 0]} animationDuration={700}>
                  {serie.map((j) => <Cell key={j.jour} fill={j.jour === v.aujourdhui.jour ? "#ffffff" : j.jour >= v.periode.debut ? "#7aa7ff" : "rgba(122,167,255,0.38)"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="squelette h-full w-full" />}
        </div>
        <div className="text-[11px] text-argent2/70 mt-2 flex gap-3"><span><span className="text-accent">●</span> période en cours</span><span><span className="text-white">●</span> aujourd'hui</span><span>mis à jour toutes les 5 min</span></div>
      </div>

      {v && v.precedents.length > 0 && (
        <div className="carte apparait-3 p-4">
          <div className="text-[14px] font-semibold mb-2">Versements précédents</div>
          <div className="divide-y divide-white/5">
            {v.precedents.map((b) => (
              <div key={b.debut} className="flex items-center justify-between py-2.5">
                <div className="leading-tight">
                  <div className="text-[14px] font-semibold">{b.libelle}</div>
                  <div className="text-[12px] text-argent2 mt-0.5">{fmtNb(b.visites)} visite{b.visites > 1 ? "s" : ""} · {b.versee ? "versé le" : "prévu le"} {b.libellePaie}</div>
                </div>
                <div className={`text-[18px] font-bold tabular-nums ${b.versee ? "text-emerald-300" : "text-argent"}`}>{fmtUsd(b.montant, true)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {v && v.liens.length > 0 && (
        <div className="carte apparait-4 p-4">
          <div className="text-[14px] font-semibold">Ton lien</div>
          <p className="text-[12px] text-argent2 mt-1 leading-relaxed">À mettre dans la bio de ton compte privé, et nulle part ailleurs. C'est lui qui compte tes visites.</p>
          {v.liens.map((l) => (
            <div key={l.url} className="mt-3 flex items-center gap-2 rounded-2xl px-3 py-2.5" style={{ background: "rgba(255,255,255,0.05)" }}>
              <span className="flex-1 text-[14px] font-semibold break-all tabular-nums">{l.url.replace(/^https?:\/\//, "")}</span>
              <button onClick={() => copier(l.url)} className="shrink-0 text-[12px] font-bold text-accent px-2.5 py-1.5 rounded-xl" style={{ background: "rgba(122,167,255,0.12)" }}>{copie ? "Copié ✓" : "Copier"}</button>
            </div>
          ))}
        </div>
      )}

      {v && (
        <p className="text-[11px] text-argent2/70 text-center px-4 leading-relaxed">
          {fmtUsd(v.taux, true)} par visite francophone (France, Belgique, Suisse, Canada, Luxembourg, Monaco, DOM-TOM), robots exclus, heure de Paris.
          {" "}Du 1 au 15 → versé le 20 ; du 16 à la fin du mois → versé le 5 du mois suivant.
        </p>
      )}
    </section>
  );
}
