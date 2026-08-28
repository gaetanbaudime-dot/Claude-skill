---
titre: "Étude — Atmosphère des Dunes, site de réservation (août 2026)"
type: analyse
cluster: "98-Rapports"
statut: verified
créé: 2026-08-28
tags: [projet/site-restaurant, business/acquisition, marché/restauration, legal/france]
liens_forts: ["[[Kill-list (NON, pas maintenant)]]", "[[Théorie des contraintes]]", "[[Journal de coaching]]", "[[Projets]]", "[[Coût d'opportunité]]"]
---

# Étude — Atmosphère des Dunes, site de réservation (août 2026)

*Étude commandée le 28/08 (« toutes les recherches possibles, un doc, ensuite on fera le reste »). 10 agents parallèles, ~480 requêtes, sources primaires privilégiées : RDAP/AFNIC, API Sirene, BODACC, INSEE, Vendée Expansion, CNIL, et le HTML brut du site lui-même. Chaque fait est étiqueté [confirmé] / [probable] / [spéculatif]. L'objectif que tu as posé : un site où les clients réservent, offert au restaurateur. L'étude vérifie si ce pitch tient — et ce qu'il faut vendre à la place, parce qu'il ne tient pas tel quel.*

> [!tip] Verdict
> **Le pitch « je t'offre un site avec réservation » est mort à l'arrivée : le resto a DÉJÀ un site avec réservation en ligne** (plateforme Overfull, 0 % de commission, branchée au bouton « Réserver une table » de Google). **Mais l'étude a trouvé mieux : leur site est littéralement invisible sur Google — balise `noindex` sur toutes les pages testées, page d'accueil comprise** [confirmé], sitemap déclaré mais en 404, meta descriptions d'un AUTRE restaurant (« Picota »), aucun email, aucun horaire, absent de la page restaurants de l'Office de Tourisme. Démontrable en 10 secondes sur le téléphone du gérant — c'est ÇA le pitch. L'offre à construire : un site propre, indexé, rapide, carte à jour, SEO local — **en gardant leur module Overfull embarqué**, parce que Google n'accepte que des partenaires logiciels agréés pour le bouton de résa, jamais un moteur maison [confirmé]. Cible : Olivier Migne, gérant de la SARL L.L.O.M. depuis l'ouverture en 2016. Et l'honnêteté du coach : ce projet est une **ligne 13 de ta [[Kill-list (NON, pas maintenant)]] en plein sprint** — l'étude est faite (coût nul sur le goulot), l'exécution attend le 30/09 ou s'assume par écrit avec la règle du [[Coût d'opportunité|coût d'opportunité]].

## 1. Fiche d'identité (à jour 2026-08-28)

| Champ | Valeur | Statut |
|---|---|---|
| Établissement | Atmosphère des Dunes — brasserie, pizzeria, glacier, coffee-shop, resto-concert | confirmé |
| Adresse | 57 avenue des Dunes, 85470 Bretignolles-sur-Mer (Vendée) — face au Camping des Dunes (5★, ~677 emplacements), à ~200 m de la plage | confirmé |
| Téléphone public | 09 73 20 84 93 (annuaires + page Contact du site — absent de la page d'accueil) | confirmé |
| Email public | **aucun** — aucun `mailto:` sur tout le site | confirmé (absence) |
| Site | atmospheredesdunes.fr — Wix, construit par Overfull/SAS IDFULL (Bordeaux) | confirmé |
| Réservation | Overfull (`app.overfull.fr/booking-v2`, widget + boutons), 0 % commission | confirmé |
| Notes | Google **4,0/5 (639 avis)** — le canal dominant ; TripAdvisor ~4,1 (#14 sur ~30-32, 98-106 avis) [probable] ; Facebook 4,6-4,7 (~40-50 avis) [probable] ; fiche Petit Futé ; ni Michelin ni Gault&Millau | mixte |
| Prix | 20-30 €/personne ; formule midi 18 € ; pizzas 13,50-18,50 € ; moules-frites (~800 g) 14,90-17,50 € ; menu enfant 10,90 € | confirmé (carte du site) |
| Positionnement revendiqué | « Premier coffee-shop et resto-concert de Brétignolles », créateur de la « Salade Vendéenne », préfou maison, brochettes flambées « concept breveté » depuis 2023, terrasse plein sud + jardin ombragé | confirmé (texte du site) |
| Hygiène | Alim'confiance « Satisfaisant » (contrôle 07/2025) | probable |
| Presse | **Zéro article trouvé** (Ouest-France, actu.fr, Courrier Vendéen — vérifié via Google Actualités) | confirmé (absence d'indexation) |

La carte complète (26 sections, plus de 100 articles avec prix, extraite du JSON Wix de `/menus`) est en texte structuré, pas en PDF — récupérable telle quelle pour le futur site.

## 2. L'entreprise : une petite SARL solide et discrète

- **SARL L.L.O.M.**, SIREN 820 021 426, RCS La Roche-sur-Yon, capital 1 000 €, créée le **26/04/2016** — création de fonds, pas de rachat (BODACC) ; même exploitant depuis 10 ans [confirmé].
- **Gérant : Olivier Migne** (registre public RNE/BODACC) ; les avis citent « Olivier et Lucie » comme couple de patrons [probable]. Ils répondent aux avis (3/3 vérifiés sur Restaurant Guru) [confirmé].
- Enseigne officielle unique « ATMOSPHERE DES DUNES » depuis l'origine — l'hypothèse d'un ancien resto renommé s'effondre : le slug Facebook `Pizzeria.Brasserie.Glace` (ex-`Creperie.Brasserie.Glacerie` encore indexé par Google) est un nom de page générique jamais changé, pas un ancien exploitant [probable].
- **Comptes déposés chaque année mais confidentiels** (option petite entreprise). Seule année publique : exercice clos 30/09/2018 — **CA 159 650 €, résultat net 5 340 €** [confirmé]. Ordre de grandeur : une affaire familiale saisonnière qui vit, pas une machine. Effectif déclaré « 0 salarié » à la date de référence 2023 (saisonniers probables l'été) [confirmé, nuance].
- Exercice comptable clos au 30/09 — l'année s'arrête à la fin de la saison, cohérent avec un business d'été.

## 3. Le site actuel : l'audit qui fait le pitch

C'est la section en or. Le site existe, il est même correct visuellement — mais il est **techniquement saboté**, et chaque défaut est vérifiable en direct devant le gérant :

| # | Défaut | Preuve | Statut |
|---|---|---|---|
| 1 | **`noindex` sur TOUTES les pages testées (accueil compris)** — le site demande à Google de ne pas l'indexer | balise `<meta name="robots" content="noindex"/>` dans le HTML des 5 pages testées | confirmé |
| 2 | Invisible en SEO local : n'apparaît sur AUCUNE requête « restaurant / pizzeria / brasserie bretignolles-sur-mer » ; absent de la page restaurants de l'Office de Tourisme (qui liste ses concurrents) | 3 requêtes testées + fetch direct de la page OT | confirmé |
| 3 | Meta descriptions d'un autre restaurant : « **Picota** — Barbecue & street food aux saveurs latines » sur 5 pages | HTML brut | confirmé |
| 4 | Sitemap déclaré dans robots.txt mais **en 404** (les deux, FR et EN) | fetch direct | confirmé |
| 5 | Slugs Wix par défaut jamais renommés : `/blank-1` (Photos), `/blank-3` (Contact), `/blank-5` (Mentions légales)… | URLs réelles | confirmé |
| 6 | **Aucun email, aucun horaire, pas de carte Google Maps intégrée, pas de formulaire de contact** sur tout le site | recherche systématique | confirmé |
| 7 | Pas de schema.org Restaurant/LocalBusiness, pas d'`og:image` (un partage Facebook du lien n'affiche aucune image) | HTML brut | confirmé |
| 8 | Version anglaise à moitié traduite, fiche concert restée en texte de démo Wix (« Profitez de cet espace pour donner davantage de détails »), coupe glacée à la description tronquée | fetch des pages | confirmé |
| 9 | Lourd et lent : 714 Ko à 1,24 Mo de HTML par page, TTFB mesuré ~3 s | curl -w | confirmé |
| 10 | **Le domaine n'appartient pas au resto** : titulaire RDAP = « 1001 MENUS SAS » (Paris) — 1001Menus est l'ancien nom de Zenchef [probable, à recouper] ; transféré chez OVH le 14/01/2026, expire le 26/04/2027 | RDAP AFNIC | confirmé (titulaire) |
| 11 | `atmosphere-des-dunes.fr` et `atmospheredesdunes.com` sont **libres** — n'importe qui peut les prendre | RDAP AFNIC + Verisign | confirmé |

Le paradoxe à comprendre avant le pitch : ce site bâclé a probablement été fait par un prestataire pro (Overfull crédité en footer, webmaster `webmaster@overfull.fr`), avec des traces d'un passé Zenchef (page « Avis vérifiés » 4,7/5 sur 115 avis, aujourd'hui en 404 ; domaine au nom de 1001 Menus). Le resto a déjà payé pour du digital deux fois — et se retrouve invisible. C'est un argument de vente (« on te répare ça ») ET un risque (un prestataire en place qu'il faudra déloger ou contourner, voir §9).

## 4. La réservation : ce qui existe, et la contrainte Google

**Aujourd'hui** : 4 boutons « RÉSERVER » + un widget flottant sur toutes les pages → `app.overfull.fr/booking-v2` [confirmé]. Overfull (SAS IDFULL, Bordeaux, ~1 600 restos clients) : réservation sans commission, anti no-show avec empreinte bancaire, CRM, partenaire officiel « Reserve with Google » depuis mars 2024 — c'est très probablement lui qui alimente le bouton « Réserver une table » de la fiche Google [probable]. Pas de TheFork (absent du listing local), pas de module Wix natif.

**La contrainte qui borne ton projet** [confirmé, doctrine officielle Google] : le bouton « Réserver une table » de Google Maps ne peut être alimenté **que par un logiciel partenaire agréé** (Overfull, Zenchef, TheFork… ~800 partenaires listés). Un moteur de résa maison ne s'y branche pas — devenir partenaire est une démarche d'éditeur SaaS, pas de site individuel. Conséquence pratique : **le futur site garde le widget Overfull embarqué** (résa sur le site + bouton Google préservés), et le « fait maison » se concentre sur tout le reste. Retirer Overfull = perdre le canal de résa Google. À dire honnêtement au gérant.

**L'économie des solutions (prix publics 2026)** — pour situer la valeur de ce qui existe et de ce que tu offres :

| Solution | Prix | Commission | Note |
|---|---|---|---|
| Overfull (en place) | sur devis (introuvable publiquement) | 0 € | 3 formules, empreinte CB dès l'entrée de gamme |
| Zenchef | 129-249 € HT/mois (+options) | 0 € (mais 2-6 % sur encaissements CB) | a absorbé GuestOnline en 2025 |
| TheFork | ~139-149 €/mois estimé [probable] | **2-4 € HT/couvert** | le resto n'y est pas — pas de dépendance à déloger |
| Wix Table Reservations | inclus dans Wix Premium (16,80-178,80 €/mois) | 0 € | non utilisé ici |

## 5. Réputation : bon accueil, cuisine irrégulière, un 4,0 qui plafonne

- **Forces récurrentes** (toutes plateformes) : l'accueil d'Olivier et Lucie, la terrasse/jardin, les moules curry-piment, le préfou, le rapport qualité-prix. Clientèle fidèle (« presque tous les jours pendant les vacances »).
- **Plaintes récurrentes** (échantillon exploitable ~10-12 avis détaillés — petit, les plateformes bloquent le scraping) : **régularité de la cuisine** (pizza mal cuite, poisson cru, « visite complètement inégale » — ~3 mentions), **placement en salle** (relégué au fond, refus de changer de table — 3 mentions), écart carte/assiette (2 mentions).
- Aucune plainte trouvée du type « impossible de réserver/joindre » — le problème de résa n'existe pas dans les avis. Encore un clou dans le pitch « résa » ; le signal utile est ailleurs : une option « préférence terrasse/intérieur » dans la résa répondrait aux 3 plaintes de placement.
- Google est le canal qui compte : 639 avis contre ~100 sur TripAdvisor. Le 4,0 plafonne face aux 4,5-4,8 des concurrents mieux notés (§6) — et ça, ce n'est pas un problème de site, c'est un problème d'exploitation (régularité). Un site neuf n'y changera rien : à dire au gérant pour rester crédible.

## 6. La concurrence : la résa en ligne n'est PAS le standard — la note, si

15 établissements passés au crible à Bretignolles et Brem-sur-Mer :

- **Seuls 3 ont une vraie résa de table en ligne** : Atmosphère des Dunes (Overfull) et les deux gastronomiques — J.M. Pérochon (1★ Michelin, #1 TripAdvisor, site Webflow + TheFork) et La Grand'Roche (TheFork). **Tout le segment brasserie/pizzeria familial fonctionne au téléphone**, et près de la moitié n'a même pas de site (Facebook/annuaires seulement).
- Le resto est donc **déjà le mieux équipé digitalement de son segment** — et ça ne se voit pas dans les résultats : #14/~32 sur TripAdvisor, derrière des plus petits mieux notés : Bistrot des Halles (4,5), Les Osselins (4,8), **Chez Yoyo (4,8 — sur la même avenue)**.
- Concurrents directs : L'Escale des Dunes (même quartier, camping voisin), Chez Yoyo (même avenue), L'Oasis (institution du front de mer depuis 1958, « réservation sur place ou par téléphone » affiché).
- Lecture [[Théorie des contraintes|théorie des contraintes]] : le goulot de CE resto n'est pas l'outil de résa (déjà là) ni le trafic piéton (camping 5★ en face) — c'est **la visibilité en ligne (noindex !) et la réputation (4,0 vs 4,5-4,8)**. Le site que tu offres attaque la première ; la seconde est entre les mains du gérant.

## 7. Le marché : une station qui vit 2 mois par an

- Bretignolles-sur-Mer : **5 344 habitants** (INSEE 2023), **64,8 % de résidences secondaires**, ~**12 campings** sur la commune. La mairie revendique une population **×10 l'été** [probable] ; l'INSEE mesure 326 lits touristiques pour 100 habitants sur l'interco (×4,3 en capacité théorique) [confirmé].
- Pays de Saint-Gilles-Croix-de-Vie (l'interco) : **201 643 lits touristiques, 1er territoire d'accueil de Vendée** — elle-même 1er département de France en campings. 6,8 M de nuitées/an dont **50 % sur juillet-août** ; 5,6 M d'excursionnistes/an (la clientèle resto par excellence) [confirmé].
- Hiver = 12 % des nuitées vs 48 % l'été. Les voisins ferment 2 à 3,5 mois (Pérochon : deux coupures nov-déc + fév-mars) ; le marché couvert municipal ferme d'octobre à mars. **Estimation raisonnée : 45-60 % du CA annuel d'une brasserie de cet axe se fait sur juillet-août** [estimation, pas un chiffre publié]. Atmosphère des Dunes loue sa salle de septembre à mars [confirmé] — indice d'une ouverture à l'année à confirmer.
- **La tendance 2025 qui sert ton pitch** : 60-77 % des professionnels vendéens constatent l'explosion des **réservations de dernière minute** et des courts séjours [confirmé, Vendée Expansion]. Une résa en ligne 24/7 visible sur Google capte exactement ce flux — à condition d'être indexé, cf. §3.

## 8. Le business case du site offert

**L'offre recommandée** (une seule, pas un menu) : refonte complète — site rapide et indexé (le contraire trait pour trait du tableau §3), carte synchronisée (le JSON est déjà extrait), horaires/email/Maps/formulaire, schema.org Restaurant, fiche Google Business optimisée, widget Overfull conservé, et la récupération de la propriété du domaine au nom de la SARL. Offert. C'est une offre à la [[Grand Slam Offer]] : valeur perçue 1 500-5 000 € (prix agence d'une refonte vitrine [estimation]), coût marginal pour toi proche de zéro en argent (hébergement statique 0-20 €/mois) et **non nul en temps** — c'est le vrai prix, voir §9.

**Ce que le gratuit peut devenir** (à trancher AVANT le pitch, pas après) : ① un service rendu, point (famille/relation — statut de ta relation avec ce resto : inconnu de l'étude) ; ② un produit d'appel : 1 resto vitrine → démarcher les ~150 restaurateurs du Pays de Saint-Gilles dont la moitié n'a pas de site (§6) avec une offre payante ; ③ une maintenance récurrente (30-50 €/mois hébergement + mises à jour). Sans réponse à cette question, « gratuit » = juste un coût.

**Scénario réaliste vs optimiste** (ta tendance documentée à l'optimisme oblige) :
- *Optimiste* : pitch accepté sur démo noindex, site livré en 2 week-ends, le gérant signe une maintenance, 2 restos voisins suivent au printemps.
- *Réaliste* : le gérant dit oui au gratuit (qui refuse ?), mais la récupération du domaine chez le titulaire tiers + le contrat Overfull existant + les allers-retours contenu prennent **3-5× le temps prévu** ; valeur récurrente ≤ 30-50 €/mois ; aucun effet sur LTP. Un bon projet relationnel/portfolio, **pas un levier 500K**.

**Rentable ou intéressant « pour nous » ? Le chiffrage honnête** (ta question du 28/08, posée après le passage au resto le midi même) :

- **En business, non.** Marché atteignable si tu industrialises : ~75 restaurateurs sans site sur le Pays de Saint-Gilles (§6). Prix soutenable en local : 500-1 500 € la création + 30-60 €/mois de maintenance — obligé de rester sous Zenchef (129-249 €/mois), sinon aucun argument face à l'offre installée. An 1 réaliste après le pilote gratuit : 3-5 clients payants → **~2-4 k€ de one-shot + 150-300 €/mois de récurrent**, pour 20-40 h sur le pilote puis 10-20 h + prospection par client. **Taux horaire effectif : ~15-30 €/h** [estimation], dans un marché en contraction (UMIH : -15 à -20 % de fréquentation été 2025 ; la restauration est la 1re coupe budgétaire des vacanciers). Chaque heure sort du goulot clippers dont le rendement structurel est d'un autre ordre (LTP ≈ 65 k€/mois de CA) — le [[Coût d'opportunité|coût d'opportunité]] tue le business case. Ce serait un deuxième Agencity, en moins bon (plus saisonnier, clients plus pauvres).
- **En relationnel, oui — si borné.** UN site offert à CE resto : valeur perçue 1 500-5 000 €, coût cash ≈ 0, coût temps réel 2 week-ends si le scope est fermé (site + SEO + Overfull conservé, PAS de maintenance ouverte, PAS de « pendant que t'y es »). Le meilleur ratio valeur/coût du projet — à condition que la relation avec ce resto le justifie (donnée absente de l'étude).
- **Verdict : pas un business, une faveur bornée.** Ne pas en faire une offre commerciale ; le faire une fois, bien, si la relation le vaut — après le 30/09 ou en journalisant l'exception.
- **Le signal terrain du 28/08 midi (« ça marchait pas ») — RÉSOLU le soir même** : c'était la **borne de réservation Overfull en panne**, résa prise sur papier devant Gaëtan [confirmé, témoin direct]. Preuve de douleur idéale : le système payant du resto a lâché en production, un jour de service.

**La Grand Slam Offer (construite le 28/08 au soir, produit codé et testé)** — sur décision explicite de Gaëtan, le produit a été développé en session : `resa-dunes/` à la racine du repo (site public + résa anti-surbooking + CRM, Node/SQLite, ~26 fichiers, testé de bout en bout — README de déploiement Railway inclus). L'offre à pitcher, structure [[Grand Slam Offer]] :

| Élément | Contenu |
|---|---|
| **Nom** | « Plus jamais une résa sur papier » |
| **Ouverture (60 s)** | « Ce midi votre borne était en panne, on a réservé sur papier. En rentrant j'ai regardé : votre site demande à Google de ne pas l'indexer [démo 10 s]. Je vous ai déjà construit la solution — elle tourne, regardez. » |
| **Pile de valeur** | ① site neuf 94× plus léger que le Wix actuel (7,5 Ko vs 714 Ko mesurés), indexé, SEO complet (valeur agence 1 500-2 500 €) ; ② résa en ligne anti-surbooking avec préférence terrasse/salle (répond aux plaintes de placement des avis) ; ③ **CRM : le fichier clients leur APPARTIENT** (habitués, no-shows, notes, export CSV) — l'anti-SaaS ; ④ feuille de service imprimable (le papier en secours organisé) ; ⑤ conformité RGPD/CNIL/LCEN incluse, zéro cookie ; ⑥ mise en service + formation 1 h + récupération du domaine (détenu par un tiers, cf. §3). |
| **Garantie** | « En ligne sous 7 jours ou c'est gratuit — et si vous arrêtez un jour, vous partez avec votre fichier clients : vous n'êtes jamais prisonniers. » |
| **Prix recommandé** | **1 490 € de mise en service + 79 €/mois** (hébergement, sauvegardes, modifications de carte, support). Plancher de négo : 990 € + 49 €/mois. Ancrage : Zenchef 129-249 €/mois sans site inclus ; création de site agence seule 1 500-5 000 €. |
| **Urgence honnête** | « Je suis sur place cette semaine » + le référencement doit tourner des mois avant la saison 2027. |
| **Flags à dire soi-même** (crédibilité) | Le bouton Google « Réserver une table » reste réservé aux partenaires agréés — stratégie lien-sur-fiche + SEO ; v1 sans email de confirmation ni empreinte CB — vendues en options : ② confirmations email/SMS +15 €/mois, ③ anti no-show empreinte bancaire (Stripe + CGV) +29 €/mois. |

## 9. Ce qui ferait échouer ça (avocat du diable)

1. **La [[Kill-list (NON, pas maintenant)|Kill-list]], frontalement.** « Nouveau pôle/nouvelle verticale » est la ligne 13, gelée jusqu'au 30/09 ; la prédiction du 19/07 dit : une ligne exécutée pendant l'été = goulot Q3 raté ET la ligne ratée aussi. L'étude (ce doc) est du savoir, coût nul. L'exécution pendant le sprint exige la phrase écrite : « en disant oui à ça, je dis non à ___ sur le goulot clippers ». Ligne 16 ajoutée à la liste, relecture le 30/09 — dans 4 semaines.
2. **Le prestataire en place.** Overfull a construit le site actuel et tient la résa + le bouton Google. Le contrat du resto avec Overfull (durée, ce que couvre l'abonnement, qui administre le Wix) est inconnu — si le site est inclus dans leur abonnement, ta refonte les attaque de front et le gérant devra arbitrer. À clarifier AVANT de construire quoi que ce soit.
3. **Le domaine appartient à un tiers** (1001 MENUS SAS [confirmé] — probablement l'entité ex-Zenchef [probable]). Récupérer un domaine chez un prestataire qui n'a plus le client peut prendre des semaines ; règle ICANN : pas de transfert dans les 60 jours suivant le dernier transfert. Plan B : `atmosphere-des-dunes.fr` est libre — mais repartir d'un domaine neuf sacrifie l'historique (faible, vu le noindex…).
4. **Google Reserve verrouillé** : sans partenaire agréé, pas de bouton de résa sur Google. Garder Overfull embarqué est la seule option propre à court terme — ton « site de résa maison » est en réalité un « site maison + résa Overfull ». Si l'ambition était de remplacer la résa elle-même, elle est morte ici.
5. **Le goulot du resto n'est pas le site.** Sa note (4,0) plafonne pour des raisons de cuisine/régularité (§5) — un site neuf n'améliore ni les pizzas ni le placement en salle. Si le gérant attend du site une hausse de CA magique, la déception est programmée : cadrer la promesse (visibilité + capture de la demande existante, pas création de demande).
6. **Les photos.** Les images de la banque Wix/Shutterstock-via-Wix sont **inutilisables hors de Wix** [confirmé, licence Wix] ; les photos Google ajoutées par des clients appartiennent à leurs auteurs ; celles d'un éventuel photographe pro exigent une cession écrite. Sans audit photo, le nouveau site part sans visuels — prévoir un shooting (ou ses photos à lui).
7. **Signal marché défavorable en toile de fond** : l'UMIH relève -15 à -20 % de fréquentation resto au national été 2025, littoral en tête ; 1 vacancier sur 5 réduit son budget, la restauration en premier [confirmé]. Le resto est dans un marché qui se contracte en volume — le site ne renverse pas ça.

## 10. Check-list légale du lancement (France 2026 — condensé)

**Obligatoire** : mentions légales LCEN complètes avec **l'exploitant comme éditeur** (⚠️ les mentions actuelles disent « SARL ATMOSPHÈRE DES DUNES » alors que la dénomination légale est L.L.O.M. — même SIREN, à corriger au passage) ; registre RGPD (l'exemption < 250 salariés ne joue pas : traitement régulier) ; mention d'information art. 13 sur le formulaire de résa ; DPA art. 28 avec hébergeur/prestataire résa/SMS ; champ allergies jamais obligatoire (donnée de santé art. 9) ; si empreinte CB : CGV acceptées avant validation, qualification arrhes/acompte explicite (C. conso L214-1), PSP certifié (jamais de CB stockée) ; prix en ligne = prix en salle (L112-1) ; **origine des viandes sur le menu publié** (décret 2022-65, médium-agnostique) ; « fait maison » seulement si les critères sont remplis.
**Recommandé** : zéro traceur non exempté = zéro bandeau cookies ; pas de Google Analytics (position CNIL constante, contrôles annoncés 2026) → Matomo configuré CNIL si besoin ; pictos allergènes en ligne ; accessibilité de base (le resto est exempté EAA : < 10 salariés et < 2 M€).

## 11. À vérifier avant le pitch (to-verify)

- Le contrat Overfull du resto : que couvre l'abonnement (site ? résa seule ?), engagement, prix payé.
- Le lien exact 1001 MENUS SAS ↔ Zenchef ↔ Overfull, et qui administre réellement le compte Wix.
- La nature du `noindex` : volontaire (site en travaux ?) ou erreur — ça change le discours (erreur du prestataire = angle en or).
- Les horaires réels à l'année (ouvert l'hiver ?) — le site n'en affiche aucun ; Google dit « ferme à 23:00 » mis à jour il y a 6 semaines.
- Le bloc « CHEZ LE RESTO » sur la page « Nos établissements » : second établissement du gérant ou résidu de démo [spéculatif].
- Le dépôt de marque INPI (data.inpi.fr bloqué depuis l'environnement — probable absence).
- Ta relation avec ce resto (l'étude ne la connaît pas) — elle détermine le modèle du « gratuit » (§8).

## 12. Le second temps : construire

Quand la décision d'exécuter sera prise (voir [[Journal de coaching|journal]] du 28/08), l'ordre efficace : ① valider les to-verify ci-dessus (1 appel au resto + 1 échange domaine) → ② maquette sur la carte déjà extraite + shooting photos → ③ site statique rapide (l'inverse des 714 Ko Wix), schema.org, widget Overfull embarqué → ④ mentions légales/RGPD de la check-list §10 → ⑤ bascule DNS après récupération du domaine, redirections, demande d'indexation Search Console → ⑥ fiche Google Business nettoyée (et la coquille « Atsmosphere » sur Mappy signalée). Le registre de ce projet vit dans [[Projets]] ; le contexte business global reste [[LTP Models]] — ceci est un side-project, pas l'agence.

## Sources principales

- **Site et technique** : atmospheredesdunes.fr (HTML brut de 10 pages, robots.txt, sitemaps 404) ; rdap.nic.fr + rdap.verisign.com (domaines) ; dns.google (DNS/MX) ; RIPE RDAP (IP Wix/GCP).
- **Entreprise** : recherche-entreprises.api.gouv.fr (Sirene/RNE) ; bodacc-datadila.opendatasoft.com (création, dépôts de comptes) ; societe.com (recoupement). Pappers, Infogreffe, INPI : bloqués (403 anti-bot).
- **Réservation** : overfull.fr + blog.overfull.fr (partenariat Google, mars 2024) ; support.google.com/reserve/answer/9172607 (partenaires agréés) ; zenchef.com/fr/tarifs ; theforkmanager.com ; support.wix.com.
- **Avis** : restaurantguru.com et sluurpy.fr (fetch directs) ; TripAdvisor/Petit Futé/Facebook via extraits indexés (403 en direct).
- **Concurrence** : sites des restaurants (lesbrisants.com, bistrotdeshalles85.fr, oasis.webador.fr…), thefork.fr, guide.michelin.com.
- **Marché** : INSEE dossier 85035 + Insee Dossier Pays de la Loire n°15 (07/2025) ; Vendée Expansion (chiffres clés 2023, bilan saison 2025) ; chiffres clés OT Pays de Saint-Gilles 2025 ; vendee.fr.
- **Légal** : CNIL (cookies, Matomo, registre, art. 13) ; Légifrance (décrets 2022-65, 2015-447, 2014-797) ; economie.gouv.fr ; handicap.gouv.fr (EAA).
