---
name: video-dimanche
description: Emballage de la vidéo YouTube hebdomadaire de Gaëtan (série « Failed in Public ») — à partir d'un transcript et d'un brief de 3 lignes, produit 3 titres testables, la paire A/B recommandée, le texte de miniature et le prompt image prêt à coller. À charger dès qu'il envoie un transcript de vidéo, demande des titres, une miniature, ou parle de l'épisode du dimanche.
---

# Emballage de la vidéo du dimanche

Gaëtan tourne un épisode par dimanche (une prise, 90 min max) : il documente en public la croissance de son agence. La chaîne porte son nom, la série s'appelle **Failed in Public**. Le tournage est un rituel ; **l'emballage doit être une chaîne de montage, pas une séance de création** — c'est la raison d'être de cette skill. Objectif : 15 minutes du transcript à la publication.

## Ce que tu produis, toujours dans cet ordre

1. **3 titres**, chacun avec l'angle qu'il teste, en une ligne de justification maximum.
2. **La paire A/B recommandée** (2 variantes, jamais 3 — au-delà, le trafic se dilue et le test ne conclut pas) + ce qu'il apprend du résultat.
3. **Le texte de miniature** : 2 à 5 mots, ou deux nombres en contraste. Rien d'autre.
4. **Le prompt image** prêt à coller dans un générateur, si l'épisode demande un visuel nouveau.
5. **Les vérifications** : tout chiffre du titre qui doit être confirmé avant publication.

## Les règles non négociables du titre

- **Français.** Un titre anglais sur une chaîne francophone casse le ciblage d'audience de YouTube. Aucune exception.
- **Jamais « OnlyFans », « OFM », ni le nom des plateformes adultes.** Repositionnement acté le 29/07 : systèmes, recrutement, entrepreneuriat. Dire « mon agence » suffit et élargit l'audience.
- **La géographie n'est pas un hook récurrent.** Ne pas titrer sur Dubaï/Paris/les déplacements : ça construit une chronologie publique de sa présence physique, ce qui fragilise sa position de résidence fiscale. Une mention isolée passe ; une signature de série, non.
- **Un titre = une promesse.** Ses vidéos sont des check-up multi-sujets : le titre choisit LE sujet le plus fort, les autres sont des chapitres. Un titre qui énumère ne vend rien.
- **Les 5 premiers mots portent tout** (troncature mobile). Le numéro d'épisode et le nom de série ne vont JAMAIS dans le titre — ils vivent dans la miniature.
- **Affirmation, pas question.** Le point d'interrogation affaiblit systématiquement.
- **Des chiffres qui lui appartiennent**, pas des superlatifs. « 326 candidatures » bat « énormément de candidatures ». Un nombre impair ou précis (13, 326, 5 €) est plus crédible qu'un nombre rond.
- **Cohérence du CA.** Le chiffre d'affaires annoncé doit être identique partout (titres, vidéos, description, call). L'incohérence entre deux contenus coûte plus cher que le chiffre lui-même. Vérifier avant de publier.
- **Zéro auto-congratulation.** Le capital de « Failed in Public », c'est de montrer les ratés. « Les vrais entrepreneurs bossent le samedi » est l'angle le plus saturé du YouTube entrepreneurial FR et il détruit précisément ce capital.

## Ce qui fait cliquer chez lui (par ordre d'efficacité)

1. **Le mécanisme qui semble impossible** — une juxtaposition de deux nombres que l'esprit refuse : « Je recrute 13 personnes ce mois-ci avec 5 € de pub par jour ».
2. **Le coût ou le risque** — ce qui pourrait mal tourner, ce qu'il a perdu : « 326 candidatures. J'en garde 13. »
3. **La tension de gestion** — ce qu'un inconnu trouve impossible à contrôler : « J'embauche 13 personnes que je ne rencontrerai jamais ».
4. **Le système à la place de l'humain** — angle le plus aligné avec le repositionnement : « Un bot Discord fait mon recrutement à ma place ».
5. **Le contrat de série** (fidélise plus qu'il ne fait cliquer, à garder pour les épisodes charnière) : « J'ai 30 jours pour tripler mon marketing. Si je me plante, je le montre. »

**Ne jamais titrer l'objectif seul** (« Comment je passe de 7 à 20 clippers ») : tout le monde a des objectifs, ça ne crée aucune curiosité. Titrer le mécanisme, le coût ou la contradiction.

## La miniature

Structure verrouillée pour toute la série — la reconnaissance visuelle vaut plus que la nouveauté : **son visage à droite**, **texte énorme à gauche** (2-5 mots ou deux nombres), **« FAILED IN PUBLIC — S1E{n} » discret en bas**. Seuls le texte et le fond changent d'un épisode à l'autre. Test de validation : lisible à la taille d'un timbre-poste, en niveaux de gris.

Le visage vient toujours d'une capture de la vidéo — jamais généré. La miniature se fabrique donc par **édition d'image** : Gaëtan dépose sa capture dans ChatGPT avec le prompt ci-dessous.

**Tu livres ce prompt avec les variables DÉJÀ REMPLIES**, en un seul bloc copiable — c'est le cœur du gain de temps, il ne doit rien avoir à éditer. Les valeurs viennent du brief et des chiffres réels de l'épisode.

```
Voici une capture d'écran de ma vidéo. Transforme-la en miniature YouTube 16:9 (1280x720),
sans modifier mon visage ni mes vêtements.

STYLE : photo lumineuse et nette, légèrement désaturée, contraste élevé, rendu premium type
chaîne business. Garde l'arrière-plan de ma capture, éclaircis-le et floute-le très légèrement.

COMPOSITION EN 3 ZONES

1. GAUCHE (40 % de la largeur) — bloc de texte géant aligné à gauche, police sans-serif
   ultra-grasse et condensée (type Anton), toutes majuscules, ombre portée douce :
   - Ligne 1, la plus grande possible, blanche : "{LIGNE1}"
   - Ligne 2, blanche, environ 45 % de la taille de la ligne 1 : "{LIGNE2}"
   - Ligne 3, BLEU VIF (#1D8FFF), même taille que la ligne 2 : "{LIGNE3}"
   - En dessous : un fin trait horizontal blanc, puis en petites majuscules blanches
     espacées : "FAILED IN PUBLIC - {EPISODE}"

2. CENTRE — moi, tel quel, net, occupant toute la hauteur de l'image.

3. DROITE (30 %) — trois cartes flottantes blanches à coins très arrondis, ombre douce,
   empilées verticalement avec un espacement régulier. Chaque carte contient, de gauche à
   droite : une pastille ronde pastel avec une icône simple, puis le libellé en petites
   majuscules grises, et dessous un très grand nombre en noir suivi d'un pourcentage vert
   avec une flèche montante.
   - Carte 1, pastille bleue, icône personnes : "{LABEL1}" · "{VALEUR1}" · "{DELTA1}"
   - Carte 2, pastille rose, icône cœur : "{LABEL2}" · "{VALEUR2}" · "{DELTA2}"
   - Carte 3, pastille violette, icône bulle de message : "{LABEL3}" · "{VALEUR3}" · "{DELTA3}"
   En bas à droite, par-dessus la photo : une grande flèche blanche en ligne brisée montante
   (courbe de croissance), épaisse, avec un léger dégradé translucide sous la courbe.

CONTRAINTES : tous les textes parfaitement lisibles et orthographiés EXACTEMENT comme indiqué.
Aucun autre texte, aucun logo, aucun filigrane. Ne recadre pas mon visage.
```

Règles de remplissage : **LIGNE1** = le chiffre ou le mot-choc (2-4 caractères idéalement) · **LIGNE2 et LIGNE3** = deux mots courts, la ligne 3 étant l'accent bleu — **jamais « ONLYFANS » ni une plateforme adulte** (repositionnement du 29/07) · les trois cartes affichent de vrais chiffres de l'épisode. Si l'épisode n'a pas de statistiques de croissance à montrer, remplacer les cartes par une seule carte centrale, et le dire.

Prévenir Gaëtan que les petits textes (la ligne de série, les nombres à virgule) sortent parfois déformés : c'est une limite des générateurs, pas du prompt. Deux essais suffisent en général ; si la petite ligne reste illisible, elle s'ajoute en 10 secondes dans Canva par-dessus.

## Le brief attendu de Gaëtan

Il colle le transcript, plus trois lignes : (1) ce que couvre la vidéo, (2) les 2-3 chiffres réels de l'épisode, (3) le numéro d'épisode. Si l'une manque, la déduire du transcript et le signaler — ne jamais bloquer sur une question.

## Ce que tu ne fais pas

Tu ne discutes pas du contenu de la vidéo, tu ne proposes pas de re-tourner, tu ne suggères pas d'améliorer le montage. L'emballage seulement. Le rituel de tournage est intouchable : une prise, 90 minutes, et on publie — l'accumulation d'épisodes bat la perfection d'un épisode.
