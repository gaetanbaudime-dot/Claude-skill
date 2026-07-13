---
titre: "Kit Emma - mode d'emploi"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-13
tags: [ops/délégation, ops/formation, ops/contenu]
liens_forts: ["[[Méthode de délégation - Emma (kit de passation)]]", "[[SOP - Machine à contenu hebdomadaire]]", "[[Scorecard - Creator Success Manager (Emma)]]", "[[Sprint été - croissance sans moi]]"]
---

# Kit Emma : les fiches imprimables (mode d'emploi)

> [!tip] Verdict
> Le vault est écrit pour TOI (dense, avec le pourquoi) ; **Emma reçoit l'inverse : 11 fiches A4, une page chacune, que des checklists** — dans le dossier `Kit Emma/` (PDF, lisibles dans Obsidian et imprimables). Règle de conception : 1 fiche = 1 page = 1 checklist + 1 règle d'escalade. **Ne lui donne PAS tout le paquet lundi** : la passation se fait en couches — fiche 1 à la conversation, fiche 2 en fin d'entretien, les profils créatrice au fil de la première semaine. Un kit remis d'un bloc est un kit non lu.

## Les 11 fiches

| Fiche | Pour qui | Contenu | Source vault |
|---|---|---|---|
| **1 — Ta mission** | Emma | Mission, 4 résultats chiffrés, décide seule / jamais seule, règle 1-3-1, non-négociable safe | [[Scorecard - Creator Success Manager (Emma)]] |
| **2 — Ta semaine type** | Emma | Lundi→dimanche en cases à cocher, tableau de contenu, boucle ×2/×3 | [[SOP - Machine à contenu hebdomadaire]] |
| **3 — Checklist tournage batch** | À transférer aux créatrices | Réglages, préparation, matrice 5 tenues × 10 trends = 50 clips, règle d'or | [[Checklist créatrice - Tournage batch]] |
| **4 — Quand ça coince** | Emma | Les 5 pannes → quoi faire seule / quand escalader, format 1-3-1, spécial absence 21/07-21/09 | [[Méthode de délégation - Emma (kit de passation)]] |
| **5 — Profil créatrice (modèle)** | Emma | Le gabarit vierge pour toute nouvelle créatrice | [[SOP - Machine à contenu hebdomadaire]] §profil |
| **Profils : Sophie · Chloé · Sarah · Maddy · Alice · Jade** | Emma | Le levier de management de chacune, ses trends, ses limites, ses chiffres au 13/07 | Specs dictées par Gaëtan le 13/07 + [[Analyse créatrices 30-60 jours (13 juillet 2026)]] |

## L'essentiel des profils (dicté le 13/07 — la version cherchable)

- **Sophie** (tourne avec son mari) : être **directive** — exemples précis + « fais exactement ça », zéro brainstorming ; idées faisables dans leur quotidien (camion, courses) ; ils tournent très vite quand la consigne est claire.
- **Chloé** : **un seul format** — « J'adore les hommes qui font X/Y/Z », variantes déjà en banque (métiers, personnalité, physique, relations, habitudes, routine…) ; filtre : **réalisable dans son appartement**.
- **Sarah** : la plus flexible, tout passe ; reproduire d'abord ce qui a déjà marché ; bon terrain de test des nouvelles trends.
- **Maddy** : le levier = **la confiance** — féliciter explicitement à chaque livraison (« ton contenu nous aide énormément ») ; briefs simples, jamais de critique sèche, pas de sur-réflexion.
- **Alice** (`to-verify` : nom entendu « Axel » en vocal — à confirmer) : jeune étudiante **ultra soft** — pas de ventre, pas de maillot, rien de sexy, tenues simples ; accompagner pas à pas.
- **Jade** : cadence maintenue mais **diagnostic en cours** (déclin -40 %) — préférences de contenu à compléter ; pas de TikTok.

## Comment s'en servir lundi (la passation en couches)

1. **Conversation Emma (1 h)** : dérouler le [[Méthode de délégation - Emma (kit de passation)|script]], remettre la **fiche 1** et la lire ensemble (2 min), puis la **fiche 2**.
2. **Le Loom** : tu fais un cycle complet commenté ; Emma écrit le SOP avec ses mots ; tu valides.
3. **Dans la semaine** : donner les **profils créatrice un par un**, au moment où Emma prend chaque créatrice (l'échelle d'autonomie : Maddy d'abord).
4. **La fiche 3** part aux créatrices avec le premier brief du lundi ; la **fiche 4** se donne vendredi, avant la répétition générale.

## Maintenance

- Les specs vivent dans les PDF ET ici (version cherchable). **Toute mise à jour = les deux.**
- Régénération des PDF : `python3 tools/kit_emma/generer_fiches.py` (le générateur est versionné dans le repo — modifier le texte dedans, relancer, commit).
- À compléter : confirmation « Alice », préférences de contenu Jade, les champs vides des profils (créneaux, matériel) — à remplir AVEC Emma, pas à sa place ([[Malédiction de la connaissance|elle voit les marches que tu ne vois plus]]).
