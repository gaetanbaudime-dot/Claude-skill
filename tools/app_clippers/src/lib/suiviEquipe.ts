/** 24/10 : « À suivre » de l'onglet Mon équipe d'un TL (src/components/MonEquipe.tsx). Ce qui demande une action pour chaque
 *  clipper de son équipe, compte par compte : banni, appel à faire, à créer, état inconnu, aucun compte, clics pas encore
 *  relevés. Un compte GOOD ne remonte jamais ; les jours non relevés ne comptent que pour un clipper qui a un compte actif. */
import { alerteMesure } from "./comptesReels";

export type CompteMembre = { n: number; handle: string; etat: string; followers: number | null; reels7: number | null; vues7: number | null;
  role?: string; mesure?: string; dernierReel?: string };
export type Membre = { cle: string; prenom: string; creatrice: string; comptes: CompteMembre[]; visites: number | null; auSeuil: boolean; manquants: number };
export type Point = { handle?: string; texte: string; grave: boolean };

const sansAccent = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

/** Ce qui demande une action pour ce clipper, compte par compte. Un compte GOOD ne remonte jamais. */
export function pointsDe(m: Membre): Point[] {
  const out: Point[] = [];
  if (!m.comptes.length) out.push({ texte: "Aucun compte renseigné", grave: false });
  for (const c of m.comptes) {
    const e = sansAccent(c.etat);
    if (e === "good" || e === "warmup" || e === "prive") {
      // 24/10 : un compte actif dont le dernier relevé Instagram ne garantit pas le chiffre (introuvable, lecture limitée, plus de Reel)
      const a = alerteMesure(c);
      if (a) out.push({ handle: c.handle, texte: a.texte, grave: a.grave });
      continue;
    }
    if (e === "ban") out.push({ handle: c.handle, texte: "banni", grave: true });
    else if (e.includes("appel")) out.push({ handle: c.handle, texte: "appel à faire", grave: true });
    else if (e === "a creer") out.push({ handle: c.handle, texte: "à créer", grave: false });
    else out.push({ handle: c.handle, texte: c.etat ? c.etat.toLocaleLowerCase("fr") : "état à vérifier", grave: false });
  }
  const actif = m.comptes.some((c) => sansAccent(c.etat) === "good");
  if (actif && m.manquants > 0) out.push({ texte: `clics : ${m.manquants} jour(s) pas encore relevé(s)`, grave: false });
  return out;
}

