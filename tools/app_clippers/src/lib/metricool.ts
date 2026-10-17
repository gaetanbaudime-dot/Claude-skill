import { ajouterLignes, assurerOnglet, lirePlage, tableur } from "./usage";
import { mesComptes, mesDemandes, nettoyerHandle } from "./comptesApp";
import { connexionAutorisee, eligible } from "./metricoolPolicy";

export const ONGLET_METRICOOL = "Metricool · demandes";
export const ENTETE_METRICOOL = ["Date ISO", "Clé app", "N°", "@", "Followers", "Vérifiés le ISO", "Statut",
  "Marque ID", "Marque agence (oui)", "Accès récupération agence (oui)", "Marques utilisées après création",
  "Capacité vérifiée le ISO", "Lien Metricool", "Lien créé le ISO"];
const PLAGE = `'${ONGLET_METRICOOL}'!A2:N`;
export type EtatMetricool = { n: number; eligible: boolean; statut: "disponible" | "attente" | "pret" | "connecte" | "renouveler" };

async function demandes() {
  const id = await tableur();
  await assurerOnglet(id, ONGLET_METRICOOL, ENTETE_METRICOOL);
  return { id, lignes: await lirePlage(id, PLAGE) };
}

function derniere(lignes: string[][], cle: string, n: number, handle: string) {
  return lignes.filter(r => r[1] === cle && r[2] === String(n) && nettoyerHandle(r[3]) === nettoyerHandle(handle)).at(-1);
}
function lien(r: string[]) {
  if (r[6] !== "prêt") return null;
  return connexionAutorisee({ marque: r[7] || "", proprietaireMarque: r[8] || "", accesAgence: r[9] || "",
    nombreMarques: r[10] || "", capaciteVerifieeLe: r[11] || "", lien: r[12] || "", creeLe: r[13] || "" });
}

export async function etatsMetricool(cle: string) {
  const [{ comptes }, pseudos, { lignes }] = await Promise.all([mesComptes(cle), mesDemandes(cle), demandes()]);
  return comptes.map(c => {
    const changement = pseudos.some(d => d.n === c.n && !d.statut && d.handle !== c.handle);
    const ok = eligible(c) && !changement;
    const r = derniere(lignes, cle, c.n, c.handle);
    const statut: EtatMetricool["statut"] = !r ? "disponible" : r[6] === "connecté" ? "connecte" :
      r[6] === "prêt" ? (ok && lien(r) ? "pret" : "renouveler") : "attente";
    return { n: c.n, eligible: ok, statut };
  });
}

export async function demanderMetricool(cle: string, n: number) {
  // Le client n'envoie jamais le @, le nombre de followers ou une URL.
  const [{ comptes }, pseudos] = await Promise.all([mesComptes(cle), mesDemandes(cle)]);
  const c = comptes.find(c => c.n === n);
  if (!c || !eligible(c) || pseudos.some(d => d.n === n && !d.statut && d.handle !== c.handle)) return false;
  const { id, lignes } = await demandes();
  if (derniere(lignes, cle, n, c.handle)) return true;
  await ajouterLignes(id, `'${ONGLET_METRICOOL}'!A:N`, [[new Date().toISOString(), cle, String(n), c.handle,
    String(c.followers), c.followersVerifiesLe || "", "demandé", "", "", "", "", "", "", ""]]);
  return true;
}

export async function connexionMetricool(cle: string, n: number): Promise<string | null> {
  const etats = await etatsMetricool(cle);
  if (!etats.some(e => e.n === n && e.eligible && e.statut === "pret")) return null;
  const { comptes } = await mesComptes(cle);
  const c = comptes.find(c => c.n === n);
  const { lignes } = await demandes();
  const r = c && derniere(lignes, cle, n, c.handle);
  return r ? lien(r) : null;
}
