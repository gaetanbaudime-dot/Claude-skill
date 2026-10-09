/** Les règles de la paie au clic, reprises à l'identique de `tools/bot_clippers/paie_clics.py`
 *  (`TAUX_CLIC`, `PAYS_PAYES_DEFAUT`, `periode_en_cours`, `prochaine_paie`) :
 *  - 0,05 $ par visite « francophone » sur le lien GetAllMyLinks du clipper, robots exclus par GAML, heure de Paris ;
 *  - quinzaine du 1 au 15 → versée le 20 du mois ; du 16 à la fin du mois → versée le 5 du mois suivant.
 *  Le virement reste humain : l'app annonce le montant et la date, elle ne paie pas. */
import { decaler, finDuMois } from "./dates";

export const TAUX_CLIC = 0.05;

/** Noms de pays tels que GAML les renvoie (le Maghreb et l'Afrique francophone restent exclus, comme dans le bot). */
export const PAYS_PAYES = new Set([
  "France", "Belgium", "Switzerland", "Canada", "Luxembourg", "Monaco", "Réunion", "Guadeloupe", "Martinique",
  "French Guiana", "Mayotte", "New Caledonia", "French Polynesia",
]);

/** Début du régime au clic (CLICS_DEPUIS du bot) : aucune paie au clic n'existe avant, inutile de montrer plus ancien. */
export const CLICS_DEPUIS = "2026-09-16";

/** 08/10 (Gaëtan : « tout le monde au variable sauf Caroline, Lilian, Josué, Yves et Rianah. Julien montage vidéo YTB et Jonas
 *  manageur ») : ces prénoms (sans accents, en minuscules) ne sont pas payés au clic. Même liste que `PAIE_FIXE` du bot. */
export const PAIE_FIXE = new Set(["caroline", "lilian", "josue", "yves", "rianah", "jonas"]);   // 09/10 : « julien » retiré (monteur vidéo, hors clipping)

/** Les anciens (premier lien d'avant le 24/09, l'ancien modèle au fixe) passent au clic le 05/10 : leurs visites d'avant
 *  restent au fixe, comme dans le bot (`debut_clic`). */
export const ANCIENS_AVANT = "2026-09-24";
export const BASCULE_CLIC = "2026-10-05";                      // 09/10 (Gaëtan) : « tout le monde au clic depuis le 5 octobre »

export type PeriodePaie = { debut: string; fin: string; paie: string };

/** La période de paie qui contient `jour` et sa date de versement. */
export function periodeDe(jour: string): PeriodePaie {
  const annee = parseInt(jour.slice(0, 4), 10), mois = parseInt(jour.slice(5, 7), 10), j = parseInt(jour.slice(8, 10), 10);
  const mm = String(mois).padStart(2, "0");
  if (j <= 15) return { debut: `${annee}-${mm}-01`, fin: `${annee}-${mm}-15`, paie: `${annee}-${mm}-20` };
  const [a2, m2] = mois === 12 ? [annee + 1, 1] : [annee, mois + 1];
  return { debut: `${annee}-${mm}-16`, fin: `${annee}-${mm}-${String(finDuMois(annee, mois)).padStart(2, "0")}`, paie: `${a2}-${String(m2).padStart(2, "0")}-05` };
}

export function periodeEnCours(aujourdhui: string): PeriodePaie {
  return periodeDe(aujourdhui);
}

export function prochainePaie(aujourdhui: string): string {
  return periodeDe(aujourdhui).paie;
}

export function periodePrecedente(p: PeriodePaie): PeriodePaie {
  return periodeDe(decaler(p.debut, -1));
}

export function montant(visites: number): number {
  return Math.round(visites * TAUX_CLIC * 100) / 100;
}
