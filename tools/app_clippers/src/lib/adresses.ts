/** L'adresse USDC (ERC-20) de chaque clipper, pour les virements du 5 et du 20 (08/10, Gaëtan : « il faut stocker cette data afin
 *  que je puisse l'avoir de mon côté »). Stockée dans l'onglet « Adresses USDC » du tableur « App clippers · usage » (Drive agence) :
 *  une ligne par clipper (clé = prénom normalisé), remplacée à chaque nouvel enregistrement, avec la date. Lisible par Gaëtan dans
 *  le tableur, par le bot ou par `/api/admin/adresses`. Une adresse ERC-20 = 0x suivi de 40 caractères hexadécimaux ; on la garde
 *  telle que saisie (la casse porte la somme de contrôle), sans espace. */
import { ajouterLignes, assurerOnglet, ecrirePlage, lirePlage, maintenantParis, tableur } from "./usage";
import type { Clipper } from "./clippers";

export const ONGLET_ADRESSES = "Adresses USDC";
const ENTETE = ["Clipper", "Créatrice", "Adresse USDC (ERC-20)", "Mise à jour", "Clé"];
export type Adresse = { prenom: string; creatrice: string; adresse: string; majLe: string; cle: string };

export function adresseValide(brut: string): string | null {
  const a = (brut || "").trim();
  return /^0x[0-9a-fA-F]{40}$/.test(a) ? a : null;
}

let prete: { id: string; expire: number } | null = null;
async function feuille(): Promise<string> {
  if (prete && prete.expire > Date.now()) return prete.id;
  const id = await tableur();
  await assurerOnglet(id, ONGLET_ADRESSES, ENTETE);
  prete = { id, expire: Date.now() + 6 * 60 * 60 * 1000 };
  return id;
}

export async function toutes(): Promise<Adresse[]> {
  const id = await feuille();
  const lignes = await lirePlage(id, `${ONGLET_ADRESSES}!A2:E`);
  return lignes.filter((l) => l[2]).map((l) => ({ prenom: l[0] || "", creatrice: l[1] || "", adresse: l[2] || "", majLe: l[3] || "", cle: l[4] || "" }));
}

export async function lire(clipper: Clipper): Promise<Adresse | null> {
  return (await toutes()).find((a) => a.cle === clipper.cle) || null;
}

/** Enregistre (ou remplace) l'adresse du clipper. Renvoie la ligne écrite. */
export async function enregistrerAdresse(clipper: Clipper, adresse: string): Promise<Adresse> {
  const id = await feuille();
  const { date, heure } = maintenantParis();
  const majLe = `${date} ${heure}`;
  const ligne = [clipper.prenom, clipper.creatrice, adresse, majLe, clipper.cle];
  const lignes = await lirePlage(id, `${ONGLET_ADRESSES}!A2:E`);
  const i = lignes.findIndex((l) => (l[4] || "") === clipper.cle);
  if (i >= 0) await ecrirePlage(id, `${ONGLET_ADRESSES}!A${i + 2}:E${i + 2}`, [ligne]);
  else await ajouterLignes(id, `${ONGLET_ADRESSES}!A:E`, [ligne]);
  prete = null;                                                        // la prochaine lecture repasse par le tableur
  return { prenom: clipper.prenom, creatrice: clipper.creatrice, adresse, majLe, cle: clipper.cle };
}
