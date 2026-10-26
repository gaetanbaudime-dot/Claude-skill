/** 26/10 (Gaëtan : « Enlève Rianah de tous les trucs aussi, elle est au salaire ») : une personne au salaire n'est pas une clippeuse
 *  payée à la visite. Elle sort du classement, du coût des clippers, des statistiques de clippers et des équipes de TL ; sa paie
 *  est au fixe. Toutes ses identités comptent : « Rianah Clipping Chloé », « Rianah Metricool », « Rianah (Metricool) ».
 *  Même liste que `PAIE_SALAIRE` du bot (paie_clics.py). Prénoms sans accents, en minuscules. */
export const SALARIES = new Set(["rianah"]);

const simple = (s: string) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

/** Le premier mot du nom (avant une espace ou une parenthèse) est un prénom au salaire. */
export function estSalarie(nom: string): boolean {
  return SALARIES.has(simple(nom).split(/[\s(]+/)[0] || "");
}
