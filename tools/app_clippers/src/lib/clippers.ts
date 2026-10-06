/** Les clippers viennent en direct de GAML : chaque lien dont la note est « Clipping Prénom » (même règle que
 *  `_prenom_note` dans paie_clics.py), regroupé par prénom normalisé (un clipper peut avoir plusieurs liens, chez
 *  plusieurs créatrices : on additionne ; sa créatrice = le `name` du lien le plus récent, premier mot).
 *  Zéro configuration : le jeton d'un clipper est dérivé de son prénom avec le secret de l'app, donc un nouveau
 *  clipper est dans l'app dès que son lien GAML existe. Un jeton inconnu ne révèle rien (404). */
import { createHmac } from "crypto";
import { liensGaml, type LienGaml } from "./gaml";

/** Prénoms jamais traités comme clippers (CLICS_EXCLURE du bot), sans accent ni majuscule. */
const EXCLURE = new Set(["rianah", "gaetan", "jonas", "x", "y"]);

export type Clipper = {
  prenom: string;                                                  // tel qu'écrit dans la note GAML du lien le plus récent
  cle: string;                                                     // prénom normalisé (minuscules, sans accents)
  jeton: string;
  creatrice: string;                                               // premier mot du `name` du lien le plus récent
  liens: { id: string; url: string; creeLe: string; enabled: boolean }[];
};

export function normaliser(t: string): string {
  return (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

export function prenomNote(note: string): string {
  const m = /^\s*clipping\s+(.+)$/i.exec(note || "");
  return m ? m[1].trim() : "";
}

/** HMAC-SHA256(CLIPPERS_SECRET, prénom normalisé), base64url, 24 caractères. */
export function jetonDe(cle: string): string {
  const secret = process.env.CLIPPERS_SECRET;
  if (!secret) throw new Error("CLIPPERS_SECRET absent");
  return createHmac("sha256", secret).update(cle).digest("base64url").slice(0, 24);
}

function premierMot(t: string): string {
  return (t || "").trim().split(/\s+/)[0] || "";
}

export function regrouper(liens: LienGaml[]): Clipper[] {
  const parCle = new Map<string, { liens: LienGaml[] }>();
  for (const l of liens) {
    const prenom = prenomNote(l.note);
    const cle = normaliser(prenom);
    if (!prenom || prenom.length < 3 || EXCLURE.has(cle)) continue;
    const g = parCle.get(cle) || { liens: [] };
    g.liens.push(l);
    parCle.set(cle, g);
  }
  const out: Clipper[] = [];
  parCle.forEach((g, cle) => {
    const tries = [...g.liens].sort((a, b) => (b.createdAt > a.createdAt ? 1 : b.createdAt < a.createdAt ? -1 : 0));
    const recent = tries[0];
    out.push({
      prenom: prenomNote(recent.note), cle, jeton: jetonDe(cle), creatrice: premierMot(recent.name),
      liens: tries.map((l) => ({ id: l.id, url: l.url, creeLe: l.createdAt.slice(0, 10), enabled: l.enabled })),
    });
  });
  return out.sort((a, b) => a.cle.localeCompare(b.cle));
}

export async function clippers(): Promise<Clipper[]> {
  return regrouper(await liensGaml());
}

export async function clipperParJeton(jeton: string | undefined): Promise<Clipper | null> {
  if (!jeton || !/^[A-Za-z0-9_-]{24}$/.test(jeton)) return null;
  return (await clippers()).find((c) => c.jeton === jeton) || null;
}
