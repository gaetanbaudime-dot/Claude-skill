/** 08/10 (Gaëtan : « envoie automatiquement l'app dans le salon Discord privé du clippeur, une fois seulement qu'il a créé les
 *  3 IG, l'app + son lien de tracking GAML ») : le bot doit connaître le lien personnel de chaque clipper sans détenir le secret
 *  des jetons, qui ne quitte pas Vercel. L'app écrit donc « clipper → lien de l'app » dans l'onglet « Liens app » du tableur
 *  « App clippers · usage » (Drive agence, partagé avec le compte de service, que le bot lit déjà pour les adresses USDC) :
 *      Clipper | Créatrice | Lien de l'app | Liens GAML | Clé | Mis à jour
 *  Écrit à la demande du bot (`POST /api/liens`), et seulement si la liste a changé depuis la dernière écriture de l'instance.
 *  Ce tableur contient donc les liens personnels : il reste privé (Gaëtan et le compte de service). */
import { clippers } from "./clippers";
import { assurerOnglet, ecrirePlage, maintenantParis, tableur, viderPlage } from "./usage";

export const ONGLET_LIENS = "Liens app";
const ENTETE = ["Clipper", "Créatrice", "Lien de l'app", "Liens GAML", "Clé", "Mis à jour"];
/** Toujours l'adresse de production, jamais l'en-tête Host de la requête : un lien envoyé aux clippers ne dépend pas de l'appelant. */
export const BASE_APP = (process.env.APP_URL || "https://app-clippers.vercel.app").replace(/\/+$/, "");

let derniere = "";                                                     // la dernière liste écrite par cette instance
let enCours: Promise<number> | null = null;

async function ecrire(): Promise<number> {
  const liste = await clippers();
  const lignes = liste.map((c) => [c.prenom, c.creatrice, `${BASE_APP}/k/${c.jeton}`, c.liens.map((l) => l.url).join(" "), c.cle]);
  const signature = JSON.stringify(lignes);
  if (signature === derniere) return lignes.length;
  const id = await tableur();
  await assurerOnglet(id, ONGLET_LIENS, ENTETE);
  const { date, heure } = maintenantParis();
  const datees = lignes.map((l) => [...l, `${date} ${heure}`]);
  if (datees.length) await ecrirePlage(id, `'${ONGLET_LIENS}'!A2:F${datees.length + 1}`, datees);
  await viderPlage(id, `'${ONGLET_LIENS}'!A${datees.length + 2}:F`);   // un clipper disparu de GAML (note retirée) disparaît d'ici
  derniere = signature;
  return lignes.length;
}

/** Écrit l'onglet, une écriture à la fois par instance. Renvoie le nombre de clippers listés. */
export function publierLiens(): Promise<number> {
  if (!enCours) enCours = ecrire().finally(() => { enCours = null; });
  return enCours;
}
