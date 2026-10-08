---
titre: "App clippers - une app par clipper pour le Drive, les Reels et les versements (6 octobre 2026)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-10-06
tags: [ops/clippers, ops/paie, outil/app, ops/automatisation]
liens_forts: ["[[App créatrices - une app par créatrice pour le Drive, les stats et les Reels (4 octobre 2026)]]", "[[Machine horizontale v2 - paie au clic, ce que les clippers rapportent (23 septembre 2026)]]", "[[Fiche de poste - Manager marketing (Jonas)]]", "[[Audit du bot Discord clippers - inventaire et refonte en trois lots (5 octobre 2026)]]", "[[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]]", "[[Journal de coaching]]"]
---

# App clippers : une app par clipper pour le Drive, les Reels et les versements (6 octobre 2026)

> [!tip] Verdict
> **En ligne le 06/10 : `app-clippers.vercel.app`, un lien personnel par clipper, zéro configuration.** Même rendu que l'[[App créatrices - une app par créatrice pour le Drive, les stats et les Reels (4 octobre 2026)|app créatrices]], trois onglets dans l'ordre du dessin de Gaëtan : **Drive** (quatre tuiles qui ouvrent le bon dossier : Reels de la semaine, Photos du mois, Top Reels = ses variantes uniques déposées par le bot, Stories), **Reels** (le duplicateur, « Bientôt »), **Versements** (ses visites francophones GetAllMyLinks jour par jour, rafraîchies toutes les 5 minutes, le montant de la période en cours à 0,05 $ la visite et la phrase « Prochain versement : 40,90 $ le 20 octobre »). La liste des clippers vient en direct des liens GAML notés « Clipping Prénom » : un nouveau clipper a son app dès que son lien existe. 30 clippers ce jour. **Ce qu'il reste à Gaëtan : envoyer son lien à chaque clipper (guide dans le scratchpad), aligner la paie de l'équipe de Jonas sur la règle au clic que l'app affiche, et corriger quatre notes GAML douteuses.**

## 1. Ce que le clipper voit

| Onglet | Contenu | Source |
|---|---|---|
| **Drive** (défaut, icône nuage) | **Depuis le 08/10 (Gaëtan, après un premier essai avec états le matin) : quatre tuiles Carrousel · TOP 20 Reels · Story · Reels, les deux tuiles Reels à droite, qui ouvrent le dossier racine de la section (« on ne s'embête pas, le clipper fouille dedans »), sans état ni emoji, un texte explicatif en haut et un en bas.** Carrousel, Reels, Story = les sous-dossiers du dossier Instagram de sa créatrice (le parent de « 🎬 Clippers », capture de Gaëtan du 08/10 : Clippers, Carrousel, Reels, Story), trouvés par leur nom, sources `DRIVE_SOURCES` en secours ; TOP 20 Reels = le sous-dossier de son dossier personnel où le bot dépose ses variantes uniques (sinon le TOP 20 de la créatrice). Redirection 302 vers l'app Google Drive. Un premier essai le matin comptait les fichiers du dossier du moment (✅ plein / ⏳ en cours / ❌ vide) : retiré à la demande de Gaëtan. | `DRIVE_SOURCES`, `CREATRICES_JSON`, compte de service Google en lecture |
| **Reels** (flèche) | Le duplicateur de Reels, écran « Bientôt » identique à l'app créatrices. | — |
| **Versements** (dollar) | Montant de la période en cours, « Prochain versement : X $ le 20 (ou le 5) », aujourd'hui et hier, graphique des visites francophones sur 14 jours (période en cours en bleu, aujourd'hui en blanc), versements précédents (montant et date), **son lien public à mettre dans la bio du compte 3**, bouton Copier. Rafraîchi toutes les 5 minutes tant que l'onglet est ouvert. **Sous le lien, depuis le 08/10 : son adresse USDC (ERC-20)**, collée une fois, validée (0x + 40 caractères), affichée en entier, enregistrée dans l'onglet « Adresses USDC » du tableur « App clippers · usage » (une ligne par clipper, remplacée, datée) : c'est là que Gaëtan lit les adresses pour les virements du 5 et du 20 (`/api/admin/adresses`, JSON ou CSV). | API GetAllMyLinks `analytics/countries`, robots exclus, pays de `PAYS_PAYES`, heure de Paris ; tableur d'usage pour les adresses |

La règle de paie est celle du bot, reprise à l'identique de `paie_clics.py` ([[Machine horizontale v2 - paie au clic, ce que les clippers rapportent (23 septembre 2026)]]) : **0,05 $ par visite francophone**, quinzaine du 1 au 15 versée le 20, du 16 à la fin du mois versée le 5 du mois suivant. Historique limité au 16/09 (début des relevés) et aux périodes où le clipper avait un lien.

## 2. Comment ça marche (pour l'agence)

- **Jeton** = HMAC-SHA256 d'un secret Vercel et du prénom normalisé, tronqué à 24 caractères, route `/k/<jeton>` ; jeton inconnu → 404 muet. Pas de liste à tenir : la liste des clippers est lue dans GAML (`GET /links`, notes « Clipping Prénom », regroupées par prénom, liens additionnés, créatrice = premier mot du nom du lien le plus récent), cache 10 minutes, prénoms exclus comme dans le bot (Rianah, Gaëtan, Jonas).
- **Distribution** : route `/api/admin/liens?cle=<secret>` (JSON ou `&format=texte`) qui renvoie « prénom → lien personnel » ; le guide du 06/10 (scratchpad, jamais dans le dépôt) contient les 30 liens et le message WhatsApp (iPhone : Safari → Partager → Sur l'écran d'accueil ; Android : Chrome → trois points → Ajouter à l'écran d'accueil). Révocation : renommer ou supprimer la note GAML du clipper, ou changer le secret pour tout régénérer.
- **Budget d'appels GAML** (60 par minute pour toute l'agence, bot compris) : jours passés en cache 7 jours, jour en cours 5 minutes, liste des liens 10 minutes ; première ouverture d'un clipper ≈ 15 appels par lots de 4, ensuite 1 à 2 ; en-têtes de limite suivis, un 429 donne une réponse partielle « chiffres en cours de mise à jour », jamais une erreur.
- **PWA** : manifeste par jeton (`start_url` avec le jeton, icônes 192/512 any + maskable, `standalone`, `theme_color`), en-têtes `noindex` et `no-referrer`, pas de mot de passe. Vérifié sur Chrome Android et Safari iPhone par le manifeste ; captures 390 × 844 relues.
- **Journal d'usage** : tableur « App clippers · usage » créé dans le Drive agence (dossier Interne), partagé en modification avec le compte de service, un événement par ouverture, onglet et tuile (mécanisme de l'app créatrices). Sert à juger si l'app est utilisée.
- **Code** : `tools/app_clippers/` (Next.js 14, Tailwind, Recharts), projet Vercel `app-clippers` connecté au dépôt, déploiement automatique à chaque push sur `main` qui touche le dossier. Six variables d'environnement, jamais dans le dépôt.

## 3. Vérifié le 06/10

Build sans erreur ; prod : jeton réel 200, jeton inconnu 404, quatre redirections Drive en 302 ; versements égaux au relevé GAML brut pour trois clippers (Caroline : 817 visites du 1 au 15/10 = 40,85 $ au moment du test, 2 133 visites du 16 au 30/09 = 106,65 $ versés le 05/10 ; Simon 68 visites = 3,40 $ ; Andry 0, liens du 1er et du 3/10) ; écart app / brut nul.

## 4. Avocat du diable [P]

- **L'app affiche de l'argent, donc elle crée une promesse.** Elle calcule « au clic » pour les 30 clippers, y compris les onze de l'équipe de Jonas que le [[Rentabilité des clippers de Jonas, de Jonas et de Julien - paie de septembre (5 octobre 2026)|rapport du 05/10]] payait encore au fixe ou à 0,50 € par abonné. Gaëtan a dit le 06/10 « ils vont tous être payés sur les visites de leur lien bio » : il faut que la paie réelle du 20/10 suive, sinon Caroline verra 40 $ dans l'app et touchera autre chose.
- **L'API GAML renvoie 50 liens et n'expose aucune pagination** (testé le 06/10 : `page`, `limit`, `offset` sans effet ; en JSON-LD, `totalItems` = 50 et pas de `view`). Le compte a exactement 50 liens ce jour, donc rien n'est perdu encore ; au 51ᵉ, personne ne sait si l'API tronque. Garde-fou à poser dans le bot et l'app : lire `totalItems` et alerter s'il dépasse le nombre reçu ; et supprimer les liens morts (Meiji, Adam, Gordon, Raphaël, liens de test) avant la prochaine vague.
- **Quatre notes GAML douteuses** créent des apps à part : « LATE2 », « Mie02 », « Antoinr », « Ricado » (à côté de « Ricardo »). Corriger la note suffit, l'app suit.
- **Le tableur d'usage de l'app créatrices n'existe pas** (recherche vide le 06/10) : son journal d'usage n'a jamais rien écrit. À créer de la même façon si on veut mesurer.
- **Captures prises sur le serveur local du build**, pas sur la prod (Chromium du conteneur refuse le certificat du proxy) ; la prod a été vérifiée par les codes HTTP et les JSON, pas à l'œil.

- **Deux carnets d'adresses coexistent** : le bot Discord garde les adresses saisies par `!wallet` (USDC ou IBAN) dans son état, l'app écrit les siennes dans le tableur. Tant que `!paie-clics` ne lit pas le tableur, Gaëtan doit croiser les deux le 5 et le 20 ; la jonction (le bot lit l'onglet « Adresses USDC » et complète ses `wallets` par prénom) est le prochain pas.
- **L'adresse est en clair dans un tableur Drive** partagé avec le compte de service : c'est une adresse publique de réception, pas une clé, mais une erreur de saisie d'un clipper (adresse d'un autre réseau, adresse d'échange sans mémo) fait perdre le virement. L'app ne vérifie que la forme ERC-20, pas le réseau sur lequel le clipper a créé l'adresse.
- **Les dossiers Carrousel, Reels et Story sont trouvés par leur nom dans le dossier Instagram** de chaque créatrice : une créatrice dont le dossier s'appelle autrement (« Photos », « Stories ») tombe sur les sources du bot, et sans source la tuile ouvre son dossier personnel sans le dire.

## 5. Ce qui vient

Le bot Discord peut poser le lien personnel dans le salon du clipper à l'ouverture de son compte 3 (route admin, prénom connu) : un clipper qui arrive au lien a son app sans que Gaëtan envoie un message. Le duplicateur de Reels arrivera dans l'onglet du milieu, comme pour les créatrices. Le process complet des comptes et des étapes est dans l'[[Audit du bot Discord clippers - inventaire et refonte en trois lots (5 octobre 2026)|audit du 05/10]] ; la règle du lien dans la bio du compte 3 dans [[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]].
