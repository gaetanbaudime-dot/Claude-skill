"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { signaler } from "@/lib/signal";
/** Graduations courtes de l'axe Y : 1 800 → « 1,8 k », pour tenir dans la marge gauche sur téléphone. */
const compact = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} k` : `${Math.round(v)}`);
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Jour = { jour: string; of: number; mym: number; subsOf: number; subsMym: number; saisi: boolean };
type Totaux = { total: number; of: number; mym: number; subs: number; subsOf: number; subsMym: number; jours: number };
type Stats = {
  periode: { cle: string; libelle: string; debut: string; fin: string; libelleDates: string };
  totaux: Totaux; precedent: Totaux; serie: Jour[]; dernierJourSaisi: string | null; enAttente: { of: string[]; mym: string[] };
  taux: { valeur: number; date: string; source: string }; periodes: { cle: string; libelle: string }[];
};
const PERIODES = [{ cle: "hier", libelle: "Hier" }, { cle: "j7", libelle: "7J" }, { cle: "j30", libelle: "30J" }, { cle: "m", libelle: "M" }, { cle: "m1", libelle: "M-1" }];
const fmtEur = (n: number, dec = 0) => new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: dec, minimumFractionDigits: dec }).format(n);
const fmtNb = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const jourCourt = (j: string) => { const d = new Date(j + "T12:00:00Z"); return `${d.getUTCDate()}/${String(d.getUTCMonth() + 1).padStart(2, "0")}`; };

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

function Delta({ actuel, avant }: { actuel: number; avant: number }) {
  if (!avant) return <span className="text-[12px] text-argent2">—</span>;
  const d = ((actuel - avant) / avant) * 100;
  const hausse = d >= 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[12px] font-semibold ${Math.abs(d) < 0.5 ? "text-argent2" : hausse ? "text-emerald-400" : "text-rose-400"}`}>
      {Math.abs(d) < 0.5 ? "=" : hausse ? "▲" : "▼"} {Math.abs(d).toFixed(0)} %
    </span>
  );
}

function Infobulle({ active, payload, label, euros }: { active?: boolean; payload?: { value: number; dataKey: string }[]; label?: string; euros: boolean }) {
  if (!active || !payload?.length) return null;
  const of = payload.find((p) => p.dataKey === (euros ? "of" : "subsOf"))?.value ?? 0;
  const mym = payload.find((p) => p.dataKey === (euros ? "mym" : "subsMym"))?.value ?? 0;
  const f = euros ? (n: number) => fmtEur(n, 0) : fmtNb;
  return (
    <div className="carte px-3 py-2 text-[12px]" style={{ borderRadius: 12 }}>
      <div className="text-argent2 mb-1">{label}</div>
      <div className="font-semibold">{f(of + mym)}</div>
      <div className="flex gap-3 mt-1"><span className="text-of">OF {f(of)}</span><span className="text-mym">MYM {f(mym)}</span></div>
    </div>
  );
}

export default function StatsTab({ jeton }: { jeton: string }) {
  const [periode, setPeriode] = useState("hier");
  const [stats, setStats] = useState<Stats | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [chargement, setChargement] = useState(true);
  useEffect(() => { try { const p = localStorage.getItem("gm-periode"); if (p && PERIODES.some((x) => x.cle === p)) setPeriode(p); } catch { /* privé */ } }, []);
  useEffect(() => {
    let vivant = true; setChargement(true); setErreur(null);
    fetch(`/api/c/${jeton}/stats?periode=${periode}`).then(async (r) => { if (!r.ok) throw new Error((await r.json()).erreur || "erreur"); return r.json(); })
      .then((d: Stats) => { if (vivant) { setStats(d); setChargement(false); } })
      .catch((e: Error) => { if (vivant) { setErreur(e.message); setChargement(false); } });
    return () => { vivant = false; };
  }, [jeton, periode]);
  const choisir = (p: string) => { setPeriode(p); signaler(jeton, `stats:${p}`); try { localStorage.setItem("gm-periode", p); } catch { /* privé */ } };
  const index = PERIODES.findIndex((p) => p.cle === periode);
  const serie = useMemo(() => (stats?.serie || []).map((j) => ({ ...j, label: jourCourt(j.jour) })), [stats]);
  const unJour = stats ? stats.periode.debut === stats.periode.fin : false;
  const t = stats?.totaux, av = stats?.precedent;

  return (
    <section className="space-y-3">
      <div className="segment apparait" role="tablist">
        <div className="pastille" style={{ left: `calc(4px + ${index} * (100% - 8px) / ${PERIODES.length})`, width: `calc((100% - 8px) / ${PERIODES.length})` }} />
        {PERIODES.map((p) => <button key={p.cle} role="tab" aria-pressed={p.cle === periode} onClick={() => choisir(p.cle)}>{p.libelle}</button>)}
      </div>

      {erreur && <div className="carte apparait p-5 text-center text-argent2">Les chiffres sont indisponibles pour le moment. <button className="text-accent font-semibold ml-1" onClick={() => choisir(periode)}>Réessayer</button></div>}

      <div className={`carte apparait-2 p-5 ${chargement ? "opacity-60" : ""}`} style={{ transition: "opacity 200ms" }}>
        <div className="flex items-baseline justify-between">
          <div className="text-[13px] text-argent2 font-medium">{stats ? `${stats.periode.libelle} · ${stats.periode.libelleDates}` : "Chargement…"}</div>
          {t && av && <Delta actuel={t.total} avant={av.total} />}
        </div>
        <div className="titre-argent text-[40px] font-bold leading-none mt-2 tabular-nums">{t ? <Compteur valeur={t.total} format={(n) => fmtEur(n, 0)} /> : <span className="squelette inline-block h-9 w-40" />}</div>
        <div className="text-[12px] text-argent2 mt-1">revenus nets</div>
        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="rounded-2xl p-3" style={{ background: "rgba(89,182,255,0.09)" }}>
            <div className="text-[11px] font-bold tracking-widest text-of">ONLYFANS</div>
            <div className="text-[20px] font-bold mt-1 tabular-nums">{t ? <Compteur valeur={t.of} format={(n) => fmtEur(n, 0)} /> : "—"}</div>
            <div className="flex items-center justify-between mt-1"><span className="text-[12px] text-argent2">{t ? `${fmtNb(t.subsOf)} abonnés` : ""}</span>{t && av && <Delta actuel={t.of} avant={av.of} />}</div>
          </div>
          <div className="rounded-2xl p-3" style={{ background: "rgba(255,122,162,0.09)" }}>
            <div className="text-[11px] font-bold tracking-widest text-mym">MYM</div>
            <div className="text-[20px] font-bold mt-1 tabular-nums">{t ? <Compteur valeur={t.mym} format={(n) => fmtEur(n, 0)} /> : "—"}</div>
            <div className="flex items-center justify-between mt-1"><span className="text-[12px] text-argent2">{t ? `${fmtNb(t.subsMym)} abonnés` : ""}</span>{t && av && <Delta actuel={t.mym} avant={av.mym} />}</div>
          </div>
        </div>
        {t && t.jours === 0 && <div className="text-[12px] text-amber-300/90 mt-3">Pas encore de chiffres saisis sur cette période.</div>}
      </div>

      {!unJour && (
        <div className="carte apparait-3 p-4">
          <div className="flex items-baseline justify-between mb-1"><div className="text-[14px] font-semibold">Revenus par jour</div><div className="text-[11px] text-argent2"><span className="text-of">● OF</span> <span className="text-mym ml-2">● MYM</span></div></div>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={serie} margin={{ top: 8, right: 4, left: -6, bottom: 0 }}>
                <defs>
                  <linearGradient id="gOf" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#59b6ff" stopOpacity={0.55} /><stop offset="100%" stopColor="#59b6ff" stopOpacity={0.05} /></linearGradient>
                  <linearGradient id="gMym" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ff7aa2" stopOpacity={0.55} /><stop offset="100%" stopColor="#ff7aa2" stopOpacity={0.05} /></linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="label" tick={{ fill: "#8b96a8", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={28} />
                <YAxis tick={{ fill: "#8b96a8", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={compact} width={40} />
                <Tooltip content={<Infobulle euros />} cursor={{ stroke: "rgba(255,255,255,0.15)" }} />
                <Area type="monotone" dataKey="mym" stackId="1" stroke="#ff7aa2" fill="url(#gMym)" strokeWidth={2} animationDuration={700} />
                <Area type="monotone" dataKey="of" stackId="1" stroke="#59b6ff" fill="url(#gOf)" strokeWidth={2} animationDuration={700} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!unJour && (
        <div className="carte apparait-4 p-4">
          <div className="flex items-baseline justify-between mb-1"><div className="text-[14px] font-semibold">Nouveaux abonnés par jour</div><div className="text-[11px] text-argent2">{t ? `${fmtNb(t.subs)} au total` : ""}</div></div>
          <div style={{ height: 160 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={serie} margin={{ top: 8, right: 4, left: -6, bottom: 0 }} barCategoryGap="28%">
                <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="label" tick={{ fill: "#8b96a8", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={28} />
                <YAxis tick={{ fill: "#8b96a8", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={compact} width={40} allowDecimals={false} />
                <Tooltip content={<Infobulle euros={false} />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />
                <Bar dataKey="subsOf" stackId="s" fill="#59b6ff" radius={[0, 0, 0, 0]} animationDuration={700} />
                <Bar dataKey="subsMym" stackId="s" fill="#ff7aa2" radius={[6, 6, 0, 0]} animationDuration={700} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {unJour && t && (
        <div className="carte apparait-3 p-4 grid grid-cols-2 gap-3 text-center">
          <div><div className="text-[11px] text-argent2 uppercase tracking-widest">Abonnés OF</div><div className="text-[24px] font-bold text-of tabular-nums">{fmtNb(t.subsOf)}</div></div>
          <div><div className="text-[11px] text-argent2 uppercase tracking-widest">Abonnés MYM</div><div className="text-[24px] font-bold text-mym tabular-nums">{fmtNb(t.subsMym)}</div></div>
        </div>
      )}

      {stats && (
        <p className="text-[11px] text-argent2/70 text-center px-4 leading-relaxed">
          {stats.dernierJourSaisi ? `Chiffres à jour au ${jourCourt(stats.dernierJourSaisi)}` : "Aucun chiffre saisi"}
          {stats.enAttente.of.length ? ` · OnlyFans pas encore saisi pour le ${stats.enAttente.of.map(jourCourt).join(", ")}` : ""}
          {stats.enAttente.mym.length ? ` · MYM pas encore saisi pour le ${stats.enAttente.mym.map(jourCourt).join(", ")}` : ""}
          {" "}· OnlyFans converti à 1 $ = {stats.taux.valeur.toFixed(2).replace(".", ",")} € · en euros nets, hors frais de plateforme
        </p>
      )}
    </section>
  );
}
