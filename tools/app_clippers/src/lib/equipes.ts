/** L'équipe d'un Team Leader et sa prime en cours (lot L11, revue du 10/10 : « l'app du TL affiche sa prime en cours »). Le bot
 *  écrit l'onglet « Équipes » du tableur « App clippers · usage » (`paie_clics.publier_equipes`, à chaque relecture horaire, seulement
 *  s'il a changé) pour la période de paie en cours : une ligne par TL (total d'équipe, VA au seuil « 2/6 »), une par VA de son
 *  équipe (visites payées, ✓ au seuil), une par équipe managée (total, ✓ au seuil), et une « Prime » par bénéficiaire (la prime telle
 *  que la liste de paie la porterait aujourd'hui). Les chiffres sont ceux de la paie (`paie_clics.payees`), jusqu'à hier : l'app ne
 *  fait aucun appel GAML de plus. Lu ici avec 10 minutes de cache ; onglet absent ou illisible → null, et l'app ne montre rien.
 *  Colonnes : Discord, Clé app, Ligne, Créatrice, Début, Fin, Prénom, Visites payées, Seuil, Atteint, Prime en cours ($), Primée,
 *  Jours non relevés (reprise L11 : vide à 0 ; sinon la somme est partielle, l'app le dit au lieu de la montrer comme un total). */
import { lirePlage, tableur } from "./usage";

export const ONGLET_EQUIPES = "Équipes";

// `manquants` : jours de la période pas encore relevés dans GAML (0 = complet jusqu'à hier) ; au-dessus de 0, la somme est provisoire
export type MembreEquipe = { prenom: string; visites: number | null; auSeuil: boolean; manquants: number };
export type EquipeTL = { creatrice: string; total: number; seuil: number; auSeuil: string; manquants: number; membres: MembreEquipe[] };
export type EquipeManagee = { creatrice: string; total: number; seuil: number; atteint: boolean; manquants: number };
export type MonEquipe = {
  debut: string; fin: string;
  primee: boolean;                 // période ouverte aux primes d'équipe (avant le 20/10/2026 : non)
  prime: number;                   // la prime d'équipe en cours, TL et manager réunis (0 si aucun VA au seuil)
  equipes: EquipeTL[];             // les équipes dont il est TL
  managees: EquipeManagee[];       // les équipes dont il est manager
};

let cache: { t: number; lignes: string[][] } | null = null;

async function lignes(): Promise<string[][]> {
  if (cache && Date.now() - cache.t < 10 * 60 * 1000) return cache.lignes;
  const l = await lirePlage(await tableur(), `'${ONGLET_EQUIPES}'!A2:M`);
  cache = { t: Date.now(), lignes: l };
  return l;
}

const nombre = (x: string | undefined): number => {
  const n = parseFloat(String(x ?? "").replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : 0;
};

/** Ce que l'onglet dit de la personne derrière cette clé d'app (TL ou manager), ou null (elle n'en est ni l'un ni l'autre, onglet
 *  absent, tableur indisponible). */
export async function equipeDe(cle: string): Promise<MonEquipe | null> {
  if (!cle) return null;
  let toutes: string[][];
  try {
    toutes = await lignes();
  } catch {
    return null;
  }
  const miennes = toutes.filter((l) => (l[1] || "").trim() === cle);
  if (!miennes.length) return null;
  const out: MonEquipe = { debut: miennes[0][4] || "", fin: miennes[0][5] || "", primee: (miennes[0][11] || "") === "oui", prime: 0, equipes: [], managees: [] };
  const parCreatrice = new Map<string, EquipeTL>();
  for (const l of miennes) {
    const [, , ligne, creatrice, , , prenom, visites, seuil, atteint, prime, , jours] = l;
    const manquants = Math.max(0, Math.round(nombre(jours)));
    if (ligne === "TL") {
      const e: EquipeTL = { creatrice: creatrice || "", total: nombre(visites), seuil: nombre(seuil), auSeuil: atteint || "", manquants, membres: [] };
      parCreatrice.set(e.creatrice, e);
      out.equipes.push(e);
    } else if (ligne === "VA") {
      const e = parCreatrice.get(creatrice || "");
      if (e) e.membres.push({ prenom: prenom || "", visites: (visites ?? "") === "" ? null : nombre(visites), auSeuil: atteint === "✓", manquants });
    } else if (ligne === "Manager") {
      out.managees.push({ creatrice: creatrice || "", total: nombre(visites), seuil: nombre(seuil), atteint: atteint === "✓", manquants });
    } else if (ligne === "Prime") {
      out.prime = Math.round(nombre(prime) * 100) / 100;
    }
  }
  return out.equipes.length || out.managees.length ? out : null;
}
