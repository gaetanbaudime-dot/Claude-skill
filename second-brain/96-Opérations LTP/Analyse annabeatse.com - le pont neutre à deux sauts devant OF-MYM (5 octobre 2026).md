---
titre: "Analyse annabeatse.com - le pont neutre à deux sauts devant OF-MYM (5 octobre 2026)"
type: décision
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-10-05
tags: [ops/trafic, ops/cgu, ofm/risques, ops/clipping]
liens_forts: ["[[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]]", "[[Veille réglementaire Meta (contrôles 2026-2027)]]", "[[Trafic et réseaux sociaux pour l'OFM]]", "[[Risques légaux et éthiques de l'OFM]]", "[[Journal de coaching]]"]
---

# Analyse annabeatse.com - le pont neutre à deux sauts devant OF-MYM (5 octobre 2026)

> [!tip] Verdict
> `annabeatse.com` n'est pas une page de liens, c'est un **pont neutre** : une page faite main (quinze lignes de code, une photo, le prénom « Anna », un bouton « Click Here »), identique pour les humains et pour les robots, sans un seul mot adulte, qui mène à une page Link.me où se trouvent les boutons OF et MYM, et seulement là. Le robot de Meta qui suit le lien de sa bio ne lit rien d'adulte. **On copie le principe, pas l'exécution** : un pont neutre sur un domaine à chaque créatrice, hébergé sur notre Vercel, qui mène à **notre page GAML** (et non à Link.me, qui ferait perdre la sortie d'Instagram, le 18+, le géofiltre et les visiteurs comptés). À tester en A/B sur les comptes de clipping témoins dès le retour du lien, lecture le 12/10, les comptes principaux ensuite. Ce reste un contournement de l'esprit de la règle « produits adultes dans le profil » : **dette assumée et documentée**, pas une tactique normalisée. Et le test révèle un trou chez nous : au 05/10, le robot Facebook reçoit notre page GAML avec **l'adresse OnlyFans en clair dans le code** et « GetAllMyLinks » dans le titre.

## 1. Ce qu'il y a derrière l'adresse [C]

Tout a été vérifié le 05/10 au matin en téléchargeant les pages avec trois identités (iPhone, robot Facebook, robot Google).

| Saut | Page | Ce qu'un visiteur voit | Ce qu'un robot lit |
|---|---|---|---|
| 1 | `annabeatse.com` (Cloudflare, `noindex`) | une photo plein écran avec dégradé sombre, un avatar rond, « Anna », un bouton pilule « Click Here » qui pulse, une fausse barre d'accueil iOS | `<title>Anna</title>`, un seul lien sortant vers Link.me, aucun pixel, aucun script, aucun mot adulte ; **la même page aux trois identités** (451 Ko, octet pour octet) |
| 2 | Link.me (profil « anna », badge vérifié) | deux boutons « 0F ---> GRATUIT 🌸 » et « M¥M ---> FREE 🩷 », icône Instagram | zéro occurrence de « onlyfans » ou « mym » dans le code ; les destinations sont derrière des redirections de clic Link.me qui ne s'ouvrent qu'en JavaScript ; mêmes 29 Ko aux trois identités |
| 3 | OnlyFans gratuit, MYM gratuit | | |

Détails qui disent comment c'est fait : la photo (960 × 1280) est **incrustée en base64 deux fois** dans la page (fond et avatar), d'où 451 Ko pour une page vide ; un commentaire en français dans le code (« Lien vers la vraie landing page ») signe une page écrite ou générée à la main par un francophone, pas un outil ; pas de favicon, pas de plan du site. Côté compte : un profil Instagram à environ 81 000 abonnés pour 13 publications d'après l'aperçu de recherche, autour de 139 000 d'après un compteur tiers [S], une bio banale (« Vision claire • Ootd / ongles »), un deuxième compte Instagram listé sur Link.me et sur X. Le profil de la fille (blonde, essayages de lingerie en vidéo, cible francophone, « GRATUIT ») est exactement celui de nos créatrices.

## 2. Face à notre page (Chloé, GAML, 05/10 au matin) [C]

| Critère | Son pont | Notre page GAML |
|---|---|---|
| Ce que lit le robot Meta sur le lien de la bio | « Anna », « Click Here », un lien vers link.me | titre « GetAllMyLinks - Chloé », description « Find all Chloé links on GetAllMyLinks… Plateforme exclusive », **l'URL OnlyFans complète et l'URL MYM en clair** dans la configuration de la page |
| Même page pour tous (pas de cloaking) | oui, vérifié | oui au 05/10 : l'identité « robot Facebook » reçoit la même page de 40 Ko que l'iPhone (le 403 observé le 02/10 ne se reproduit pas : shield coupé entre-temps ou filtrage par adresse IP, à vérifier) |
| Redirection automatique | aucune, il faut cliquer | aucune vers un autre domaine ; la sortie du navigateur Instagram reste au clic |
| Mot adulte ou prix sur le premier saut | aucun | « Plateforme exclusive » (codé, pas adulte) mais les adresses OF/MYM sont lisibles |
| Signal de prix | « GRATUIT » / « FREE » au second saut : **interdit** par la règle de Meta sur les liens d'abonnement adulte (aucun signe de prix ou de transaction) | aucun |
| 18+ | aucun | oui |
| Sortie du navigateur Instagram | non (Link.me et OF s'ouvrent dans Instagram) | oui, le levier de conversion utile |
| Géofiltre, visiteurs comptés | non (statistiques Link.me seulement) | oui (GAML) |
| Indexation | `noindex` | aucune balise, page indexable sous le nom de l'outil |
| Poids | 451 Ko (photo en double) | 40 Ko + CDN |
| Libellés | anglais pour une audience française, « 0F » et « M¥M » codés | « Plateforme exclusive » codé, à remplacer par les vrais noms (plan du 02/10) |

Lecture : elle gagne sur **ce que lit le robot** (rien) et perd sur **tout le reste** (conversion, mesure, conformité des libellés, poids). Nous, c'est l'inverse : bonne mécanique de conversion, mais le premier saut dit au robot tout ce qu'il ne doit pas lire.

## 3. Ce qu'on copie, ce qu'on ne copie pas

**On copie le pont neutre**, devant notre page GAML, pour les comptes principaux au moment du retour du lien (étapes 4 et 5 du plan dans [[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]]) :

1. Un domaine neutre par créatrice (prénom-nom, sans mot adulte, ≈ 8 € par an), celui déjà prévu pour la page principale.
2. Une page statique hébergée sur notre Vercel (même projet que l'[[App créatrices - une app par créatrice pour le Drive, les stats et les Reels (4 octobre 2026)|app créatrices]], ou un projet à part) : photo, prénom, un bouton **en français et honnête** (« Mes liens 👉 », pas « Click Here »), `noindex`, **même page pour tous**, aucun pixel, aucune redirection automatique, image servie en fichier (pas en base64).
3. Le bouton mène à la page GAML sur son domaine, qui garde le 18+, la sortie d'Instagram, le géofiltre, les visiteurs comptés et les vrais libellés « OnlyFans » / « MYM ».
4. Test A/B sur les comptes de clipping témoins dès le 05/10 : dix comptes avec le lien GAML direct, dix avec le pont ; lecture le 12/10 sur deux chiffres, la part de comptes restés verts et les visiteurs GAML par compte. Les comptes principaux ne bougent qu'après.

**On ne copie pas** : Link.me comme second saut (perte de conversion et de mesure, et ses conditions sur le contenu adulte restent à vérifier), les libellés codés et le mot « GRATUIT » (signal de prix interdit, déjà classé dette chez nous), l'absence de 18+, la photo en base64, l'anglais.

Ce que ça change dans le plan du 02/10 : rien n'est retiré, une variante s'ajoute au test des témoins. Le goulot reste celui de l'[[Goulot de l'agence - l'équation du scale|équation du scale]] : des comptes qui restent recommandés, pas l'outil de liens.

## 4. Avocat du diable [P]

- **Rien ne prouve que son compte est recommandé.** On voit un nombre d'abonnés qui monte et 13 publications, pas la portée chez les non-abonnés ni le statut du compte. Un compte peut grossir par Reels tout en étant sorti de l'Explorer. La seule preuve admissible est notre propre test sur les témoins.
- **Un saut de plus coûte des clics.** Chaque écran intermédiaire perd une part des visiteurs (ordre de grandeur 15 à 30 % [S]) ; son bouton pulsant plein écran limite la casse, et le pont peut lui-même mettre le 18+ et sortir d'Instagram, mais c'est à mesurer, pas à supposer.
- **Meta peut suivre le bouton.** Aucune source ne dit que le robot de Meta s'arrête au premier saut, ni qu'il va plus loin [S]. Si la vague de septembre a touché « tous fournisseurs, domaines perso compris », c'est parce que les pages lisaient OF/MYM en clair, comme la nôtre ; un pont neutre n'a rien à lire, sauf si le robot clique.
- **CGU.** Ni cloaking, ni redirection automatique, ni prix, ni libellé trompeur si on écrit « Mes liens » : la lettre des règles vérifiées le 02/10 est respectée. L'esprit de la règle « ne pas promouvoir de produits adultes depuis le profil » ne l'est pas. Dette, à écrire comme telle ; mineurs hors de question, le 18+ reste sur GAML et la page ne porte aucun teaser.
- **Le vrai trou est chez nous.** Tant que le robot Facebook lit « onlyfans.com » dans notre page, aucun pont ne sert à rien si le lien de la bio pointe encore directement sur GAML : d'abord vérifier le shield (coupé ou pas, et pour qui), puis décider du pont.

## Prédictions (05/10, revue le 12/10)

- Sur les comptes témoins, le groupe « pont » garde au moins 80 % de comptes verts à 7 jours, contre 70 % ou moins pour le lien direct (45 %).
- Le pont perd moins de 25 % de visiteurs GAML par compte par rapport au lien direct (50 %).
- Son compte principal affiche encore plus de 13 publications et plus d'abonnés le 12/10, signe qu'il n'a pas été restreint de façon visible (60 %, lecture indirecte).

Le cadre réglementaire est dans la [[Veille réglementaire Meta (contrôles 2026-2027)]], la mécanique du trafic dans [[Trafic et réseaux sociaux pour l'OFM]], le classement des risques dans [[Risques légaux et éthiques de l'OFM]] ; la décision et ses prédictions sont dans le [[Journal de coaching]] (entrée du 5 octobre 2026).
