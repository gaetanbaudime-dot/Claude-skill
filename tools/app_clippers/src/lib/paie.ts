/** Les règles de la paie au clic, reprises à l'identique de `tools/bot_clippers/paie_clics.py`
 *  (`TAUX_CLIC`, `PAYS_PAYES_DEFAUT`, `periode_en_cours`, `prochaine_paie`) :
 *  - 0,05 $ par visite « francophone » sur le lien GetAllMyLinks du clipper, robots exclus par GAML, heure de Paris ;
 *  - paie le 5 et le 20 : du 5 au 19 inclus → versé le 20 ; du 20 au 4 inclus → versé le 5 du mois suivant (09/10).
 *  Le virement reste humain : l'app annonce le montant et la date, elle ne paie pas. */
import { decaler } from "./dates";

export const TAUX_CLIC = 0.05;

/** Noms de pays tels que GAML les renvoie (le Maghreb et l'Afrique francophone restent exclus, comme dans le bot). */
export const PAYS_PAYES = new Set([
  "France", "Belgium", "Switzerland", "Canada", "Luxembourg", "Monaco", "Réunion", "Guadeloupe", "Martinique",
  "French Guiana", "Mayotte", "New Caledonia", "French Polynesia",
]);

/** Début du régime au clic (CLICS_DEPUIS du bot) : « j'ai commencé la rémunération au clic le 5 octobre » (Gaëtan, 09/10).
 *  Aucune paie au clic n'existe avant, inutile de montrer plus ancien. */
export const CLICS_DEPUIS = "2026-10-05";

/** 08/10 (Gaëtan : « tout le monde au variable sauf Caroline, Lilian, Josué, Yves et Rianah. Julien montage vidéo YTB et Jonas
 *  manageur ») : ces prénoms (sans accents, en minuscules) ne sont pas payés au clic. Même liste que `PAIE_FIXE` du bot. */
export const PAIE_FIXE = new Set(["caroline", "lilian", "josue", "yves", "rianah", "jonas"]);   // 09/10 : « julien » retiré (monteur vidéo, hors clipping)

/** Les anciens (premier lien d'avant le 24/09, l'ancien modèle au fixe) passent au clic le 05/10 : leurs visites d'avant
 *  restent au fixe, comme dans le bot (`debut_clic`). */
export const ANCIENS_AVANT = "2026-09-24";
export const BASCULE_CLIC = "2026-10-05";                      // 09/10 (Gaëtan) : « tout le monde au clic depuis le 5 octobre »

export type PeriodePaie = { debut: string; fin: string; paie: string };

/** 09/10 (Gaëtan : « la paie se fait le 5 et le 20 de chaque mois ; du 5 au 19 inclus et du 20 au 4 inclus ») : la période
 *  du 5 au 19 est versée le 20, celle du 20 au 4 est versée le 5 du mois suivant. « J'ai commencé la rémunération au clic le
 *  5 octobre » : la première période est le 5 → 19/10/2026 (CLICS_DEPUIS), sans exception. Même règle que `periode` du bot. */
const pad = (n: number) => String(n).padStart(2, "0");

/** La période de paie qui contient `jour` et sa date de versement. */
export function periodeDe(jour: string): PeriodePaie {
  const annee = parseInt(jour.slice(0, 4), 10), mois = parseInt(jour.slice(5, 7), 10), j = parseInt(jour.slice(8, 10), 10);
  const mm = pad(mois);
  if (j <= 4) {
    const [a1, m1] = mois === 1 ? [annee - 1, 12] : [annee, mois - 1];
    return { debut: `${a1}-${pad(m1)}-20`, fin: `${annee}-${mm}-04`, paie: `${annee}-${mm}-05` };
  }
  if (j <= 19) return { debut: `${annee}-${mm}-05`, fin: `${annee}-${mm}-19`, paie: `${annee}-${mm}-20` };
  const [a2, m2] = mois === 12 ? [annee + 1, 1] : [annee, mois + 1];
  return { debut: `${annee}-${mm}-20`, fin: `${a2}-${pad(m2)}-04`, paie: `${a2}-${pad(m2)}-05` };
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
