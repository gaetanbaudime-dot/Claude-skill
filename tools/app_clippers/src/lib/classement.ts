import type { Clic, Clipper360, Compte, Pilotage } from "./pilotage";
import { estGood, fenetre, jours, meme, normaliser } from "@/components/pilotage/calc";

export type CompteClassement = Compte & { numero: number };
export type FicheClipper = {
  id: string; prenom: string; creatrices: string[]; comptes: CompteClassement[]; liens: string[];
  clics7: number | null; avant7: number | null; manquants: number; serie: (number | null)[];
  reels7: number | null; vues7: number | null; partielReels: boolean; partielVues: boolean;
};
const handle = (h: string) => h.trim().replace(/^@/, "").toLowerCase();
const hors = new Set(["avant reprise", "sans detenteur"]);
const horsClippers = new Set(["gaetan", "jonas", "x", "y"]);

/** Une égalité complète d'abord. Le prénom seul ne suffit que s'il est unique dans le référentiel. */
export function identiteDe(nom: string, personnes: Clipper360[]): Clipper360 | undefined {
  const n = normaliser(nom);
  const exacts = personnes.filter(p => normaliser(p.prenom) === n);
  if (exacts.length) return exacts.length === 1 ? exacts[0] : undefined;
  const premier = n.split(/\s+/)[0];
  const candidats = personnes.filter(p => normaliser(p.prenom).split(/\s+/)[0] === premier);
  return candidats.length === 1 ? candidats[0] : undefined;
}

export function liensPublics(valeur: string): string[] {
  return [...new Set(valeur.split(/\s*·\s*|[\s,]+/).flatMap(v => {
    try { const u = new URL(v); return ["https:", "http:"].includes(u.protocol) ? [u.href] : []; } catch { return []; }
  }))];
}

const total = (comptes: CompteClassement[], lire: (c: CompteClassement) => number | null) => {
  const connus = comptes.map(lire).filter((n): n is number => n !== null);
  return { valeur: connus.length ? connus.reduce((s, n) => s + n, 0) : null, partiel: connus.length < comptes.length };
};

/** Toujours sept journées closes en heure de Paris, comme les Reels du Dashboard. Aucun zéro inventé. */
export function classementClippers(d: Pilotage, filtre = ""): FicheClipper[] {
  const personnes = d.clippers || [];
  const par = new Map<string, { ref?: Clipper360; nom: string; comptes: Compte[]; clics: Clic[] }>();
  const garde = (cr: string) => !filtre || meme(cr, filtre);
  const cle = (nom: string) => identiteDe(nom, personnes)?.uid || `nom:${normaliser(nom)}`;
  for (const p of personnes) {
    if (p.role === "Manager" || horsClippers.has(normaliser(p.prenom)) || !garde(p.creatrice)) continue;
    par.set(p.uid, { ref: p, nom: p.prenom, comptes: [], clics: [] });
  }
  for (const c of d.comptes) {
    if (c.axe !== "Horizontal" || c.type !== "Clipper" || !garde(c.creatrice) || !c.gerant || horsClippers.has(normaliser(c.gerant))) continue;
    const refHandle = personnes.filter(p => p.comptes.some(a => handle(a.handle) === handle(c.handle)));
    const ref = refHandle.length === 1 ? refHandle[0] : identiteDe(c.gerant, personnes);
    const k = ref?.uid || cle(c.gerant);
    const l = par.get(k) || { ref, nom: ref?.prenom || c.gerant, comptes: [], clics: [] };
    l.comptes.push(c); par.set(k, l);
  }
  for (const c of d.clics) {
    if (c.axe !== "Horizontal" || c.source !== "Clipper" || hors.has(normaliser(c.qui)) || horsClippers.has(normaliser(c.qui)) || !garde(c.creatrice)) continue;
    const k = cle(c.qui);
    const ref = identiteDe(c.qui, personnes);
    const l = par.get(k) || { ref, nom: ref?.prenom || c.qui, comptes: [], clics: [] };
    l.clics.push(c); par.set(k, l);
  }
  const f = fenetre(d.aujourdhui, "j7"), js = jours(f.debut, f.fin);
  return [...par].map(([id, l]): FicheClipper => {
    const numeros = new Map(l.ref?.comptes.map((c, i) => [handle(c.handle), c.numero ?? i + 1]));
    const places = new Map<number, CompteClassement>();
    // Numéro avant filtrage : un compte 2 reste le compte 2 si le 1 est banni.
    const ordonnes = l.comptes.map(c => ({ c, n: c.numero ?? numeros.get(handle(c.handle)) }));
    // Le classeur peut déjà porter un @ corrigé alors que le parcours garde l'ancien.
    // Un trio de même propriétaire avec un seul emplacement vacant peut afficher son compte actuel.
    // Aucune mesure n'est copiée entre @ ; aucun compte 4+ ne remplace un compte banni.
    if (ordonnes.length <= 3) {
      const libres = [1, 2, 3].filter(n => !ordonnes.some(x => x.n === n));
      const inconnus = ordonnes.filter(x => !x.n);
      if (inconnus.length === 1 && libres.length === 1) inconnus[0].n = libres[0];
    }
    const attribues = ordonnes.filter((x): x is { c: Compte; n: number } => !!x.n && x.n >= 1 && x.n <= 3).sort((a, b) => a.n - b.n);
    let croissanceNumero = 0;
    for (const { c, n } of attribues) {
      const prive = c.roleCompte ? normaliser(c.roleCompte) === "prive" : ["prive", "privé"].includes(normaliser(c.etat)) || n === 3;
      const affichage = prive ? 3 : ++croissanceNumero;
      const actif = estGood(c.etat) || (prive && normaliser(c.etat) === "prive");
      if (actif && affichage <= 3 && !places.has(affichage)) places.set(affichage, { ...c, numero: affichage });
    }
    const comptes = [...places.values()].sort((a, b) => a.numero - b.numero);
    const croissance = comptes.filter(c => c.numero < 3);
    const reels = total(croissance, c => c.reels7), vues = total(croissance, c => c.vuesRecentes);
    const semaine = l.clics.filter(c => c.jour >= f.debut && c.jour <= f.fin);
    const avant = l.clics.filter(c => c.jour >= f.avantDebut && c.jour <= f.avantFin);
    const creatrices = [l.ref?.creatrice || "", ...comptes.map(c => c.creatrice), ...l.clics.map(c => c.creatrice)].filter((c, i, all) => c && !all.slice(0, i).some(x => meme(x, c)));
    return {
      id, prenom: normaliser(l.nom) === "rianah" ? "Rianah clipping" : l.nom, creatrices, comptes,
      liens: liensPublics(l.ref?.gaml || ""),
      clics7: semaine.some(c => (c.liens ?? 1) > c.manquants) ? semaine.reduce((s, c) => s + c.visites, 0) : null,
      avant7: avant.length && !avant.some(c => c.manquants) ? avant.reduce((s, c) => s + c.visites, 0) : null,
      manquants: semaine.reduce((s, c) => s + c.manquants, 0),
      serie: js.map(j => { const lignes = semaine.filter(c => c.jour === j); return lignes.length && !lignes.some(c => c.manquants) ? lignes.reduce((s, c) => s + c.visites, 0) : null; }),
      reels7: reels.valeur, vues7: vues.valeur, partielReels: reels.partiel, partielVues: vues.partiel,
    };
  }).sort((a, b) => (b.clics7 ?? -1) - (a.clics7 ?? -1) || a.prenom.localeCompare(b.prenom, "fr"));
}

/** Le serveur retire toutes les autres équipes, leurs subs/CA et les clés d'app avant sérialisation. */
export function pilotageEquipe(d: Pilotage, membres: { prenom: string; creatrice?: string; comptes: { handle: string; n: number; etat?: string }[] }[]): Pilotage {
  const autorises = new Set(membres.flatMap(m => m.comptes.map(c => handle(c.handle))));
  const noms = new Set(membres.map(m => normaliser(m.prenom)));
  const refs = (d.clippers || []).filter(p => {
    if (p.comptes.length) return p.comptes.some(c => autorises.has(handle(c.handle)));
    return noms.has(normaliser(p.prenom)) && (d.clippers || []).filter(x => normaliser(x.prenom) === normaliser(p.prenom)).length === 1;
  });
  for (const m of membres) {
    if (refs.some(p => normaliser(p.prenom) === normaliser(m.prenom) || p.comptes.some(c => m.comptes.some(a => handle(a.handle) === handle(c.handle))))) continue;
    refs.push({ uid: `equipe:${normaliser(m.prenom)}`, prenom: m.prenom, role: "Clipper", creatrice: m.creatrice || "",
      tl: "", tlUid: "", manager: "", managerUid: "", app: false,
      comptes: m.comptes.map(c => ({ handle: c.handle, etat: c.etat || "", numero: c.n })),
      totalIg: m.comptes.length, gaml: "", gamlUuids: "", liens: 0, visites7: null, qualiteVisites: "", reels7: null, anomalies: "" });
  }
  const numeros = new Map(membres.flatMap(m => m.comptes.map(c => [handle(c.handle), c.n] as const)));
  const comptes = d.comptes.filter(c => (numeros.get(handle(c.handle)) ?? c.numero ?? 1) <= 3 && c.axe === "Horizontal" && c.type === "Clipper" && (autorises.has(handle(c.handle))
    || (noms.has(normaliser(c.gerant)) && (d.clippers || []).filter(p => normaliser(p.prenom) === normaliser(c.gerant)).length <= 1)))
    .map(c => ({ ...c, numero: numeros.get(handle(c.handle)) ?? c.numero }));
  const clics = d.clics.filter(c => {
    if (c.axe !== "Horizontal" || c.source !== "Clipper") return false;
    const ref = identiteDe(c.qui, d.clippers || []);
    if (ref) return refs.some(p => p.uid === ref.uid);
    const exacts = (d.clippers || []).filter(p => normaliser(p.prenom) === normaliser(c.qui));
    return !exacts.length && noms.has(normaliser(c.qui)) && !((d.clippers || []).filter(p => normaliser(p.prenom).split(/\s+/)[0] === normaliser(c.qui).split(/\s+/)[0]).length > 1);
  });
  return { ...d, comptes, clics, clippers: refs.map(p => ({ ...p, comptes: p.comptes.filter(c => autorises.has(handle(c.handle))) })), subs: [], boutons: [] };
}
