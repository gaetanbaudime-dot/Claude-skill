"use client";
import { useState } from "react";
import type { Pilotage } from "@/lib/pilotage";
import Horizontal from "./Horizontal";
import { PERIODES, type Periode } from "./calc";

/** Le même pilotage que l'admin et les TL ; la route ne livre que les données de ce clipper. */
export default function PilotageClipper({ d }: { d: Pilotage }) {
  const [periode, setPeriode] = useState<Periode>("j7");
  const index = PERIODES.findIndex(p => p.cle === periode);
  return <section aria-label="Mon activité">
    <h2 className="text-[18px] font-bold mb-3">Mon activité</h2>
    <div className="segment" role="group" aria-label="Période du pilotage">
      <span className="pastille" style={{ left: `calc(4px + ${index} * (100% - 8px) / ${PERIODES.length})`, width: `calc((100% - 8px) / ${PERIODES.length})` }} />
      {PERIODES.map(p => <button key={p.cle} aria-pressed={p.cle === periode} onClick={() => setPeriode(p.cle)}>{p.libelle}</button>)}
    </div>
    <Horizontal d={d} periode={periode} filtre="" />
  </section>;
}
