"use client";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { compact, couleur, fmt, jourCourt, texteDelta } from "./calc";

/** « ▲ 12 % » vert, « ▼ 8 % » rouge, rien si pas comparable. */
export function Delta({ v, petit = false }: { v: number | null | undefined; petit?: boolean }) {
  if (v === null || v === undefined || !Number.isFinite(v)) return null;
  const haut = v > 0, nul = v === 0;
  const cls = nul ? "text-argent2 bg-white/5" : haut ? "text-emerald-300 bg-emerald-400/10" : "text-rose-300 bg-rose-400/10";
  return (
    <span className={`inline-flex items-center rounded-full font-semibold tabular-nums ${petit ? "text-[11px] px-1.5 py-0.5" : "text-[12px] px-2 py-0.5"} ${cls}`}>
      {nul ? "=" : haut ? "▲" : "▼"} {nul ? "0 %" : texteDelta(v)}
    </span>
  );
}

/** Écart absolu signé (« +120 », « −35 »), coloré. */
export function Ecart({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined) return <span className="text-argent2">–</span>;
  const cls = v > 0 ? "text-emerald-300" : v < 0 ? "text-rose-300" : "text-argent2";
  return <span className={`tabular-nums ${cls}`}>{v > 0 ? "+" : v < 0 ? "−" : ""}{fmt(Math.abs(v))}</span>;
}

export function Kpi({ titre, valeur, sous, delta, partiel }: { titre: string; valeur: string; sous?: string; delta?: number | null; partiel?: boolean }) {
  return (
    <div className="carte p-4 apparait">
      <div className="text-[12px] text-argent2 font-medium">{titre}</div>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 mt-1">
        <div className={`${valeur.length > 7 ? "text-[22px]" : "text-[26px]"} leading-none font-bold tabular-nums titre-argent whitespace-nowrap`}>{partiel ? "≈ " : ""}{valeur}</div>
        <span className="whitespace-nowrap"><Delta v={delta} /></span>
      </div>
      {sous ? <div className="text-[11.5px] text-argent2 mt-1.5 leading-snug">{sous}</div> : null}
    </div>
  );
}

/** Courbe en SVG (followers sur 7 jours, clics sur 14) : trous laissés vides, jamais remplis par 0. */
export function Courbe({ valeurs, couleurTrait = "#7aa7ff", largeur = 84, hauteur = 26 }: { valeurs: (number | null)[]; couleurTrait?: string; largeur?: number; hauteur?: number }) {
  const lus = valeurs.map((v, i) => [i, v] as const).filter(([, v]) => v !== null) as [number, number][];
  if (lus.length < 2) return <div style={{ width: largeur, height: hauteur }} />;
  const lo = Math.min(...lus.map(([, v]) => v)), hi = Math.max(...lus.map(([, v]) => v));
  const x = (i: number) => (i / Math.max(1, valeurs.length - 1)) * (largeur - 4) + 2;
  const y = (v: number) => (hi === lo ? hauteur / 2 : hauteur - 3 - ((v - lo) / (hi - lo)) * (hauteur - 6));
  const d = lus.map(([i, v], k) => `${k ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const [di, dv] = lus[lus.length - 1];
  return (
    <svg width={largeur} height={hauteur} viewBox={`0 0 ${largeur} ${hauteur}`} aria-hidden>
      <path d={d} fill="none" stroke={couleurTrait} strokeWidth={1.8} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(di)} cy={y(dv)} r={2.4} fill={couleurTrait} />
    </svg>
  );
}

function Bulle({ active, payload, label, unite }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; unite: string }) {
  if (!active || !payload?.length) return null;
  const tot = payload.reduce((s, p) => s + (p.value || 0), 0);
  return (
    <div className="carte px-3 py-2 text-[12px]" style={{ borderRadius: 12 }}>
      <div className="text-argent2 mb-1">{label ? jourCourt(label) : ""} · <b className="text-white">{fmt(tot)}</b> {unite}</div>
      {[...payload].reverse().filter((p) => p.value).map((p) => (
        <div key={p.name} className="flex justify-between gap-4"><span style={{ color: p.color }}>{p.name}</span><span className="tabular-nums">{fmt(p.value)}</span></div>
      ))}
    </div>
  );
}

/** Barres empilées par jour (une couleur par créatrice ou par groupe). */
export function BarresJour({ data, groupes, unite, couleurs }: { data: Record<string, number | string>[]; groupes: string[]; unite: string; couleurs?: Record<string, string> }) {
  return (
    <div className="h-44 -mx-1">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 4, left: -6, bottom: 0 }}>
          <XAxis dataKey="jour" tickFormatter={jourCourt} tick={{ fill: "#8b96a8", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={18} />
          <YAxis tickFormatter={compact} tick={{ fill: "#8b96a8", fontSize: 10 }} axisLine={false} tickLine={false} width={40} />
          <Tooltip content={<Bulle unite={unite} />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />
          {groupes.map((g, i) => (
            <Bar key={g} dataKey={g} name={g} stackId="a" fill={couleurs?.[g] || couleur(g, i)} radius={i === groupes.length - 1 ? [4, 4, 0, 0] : 0} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Pastille({ texte, couleurFond }: { texte: string; couleurFond: string }) {
  return <span className="inline-block w-2.5 h-2.5 rounded-full mr-1.5 align-middle" style={{ background: couleurFond }} aria-label={texte} />;
}

export function Titre({ children, droite }: { children: React.ReactNode; droite?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between mt-6 mb-2 px-1">
      <h2 className="text-[15px] font-semibold text-white/90">{children}</h2>
      {droite ? <div className="text-[11.5px] text-argent2">{droite}</div> : null}
    </div>
  );
}
