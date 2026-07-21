---
titre: "Continuité du bot et paie sacrée (plan anti-panne)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-19
tags: [ops/clippers, ops/paie, ops/outils, plan/richesse]
liens_forts: ["[[Bot FAQ clippers (Discord)]]", "[[Machine de recrutement clippers (100 leads par mois)]]", "[[Manager 200 clippers par un système]]", "[[Reporting clippers]]", "[[Sprint été - croissance sans moi]]", "[[Journal de coaching]]"]
---

# Continuité du bot et paie sacrée — fondamental n°7 (avant le 26/07)

> [!tip] Verdict
> **Le risque de ruine n°1 de ton absence n'est ni un concurrent ni un ban — c'est un lundi sans paie.** Le [[Bot FAQ clippers (Discord)|bot Railway]] est un **point de défaillance unique** (l'incident Hugo l'a prouvé : un webhook perdu pendant un redéploiement = un candidat bloqué en silence), et les données du pipeline vivent sur un seul volume JSON. Un seul cycle de paie contesté en public dans un Discord qui grossit déclenche la spirale terminale : **les meilleurs partent, les fraudeurs restent** (réf. [[Manager 200 clippers par un système]], condition ① : la paie est sacrée). Le plan tient en **6 verrous + 1 politique**, tous posables avant le départ, aucun ne demandant plus d'une heure. **Deux corrections techniques ci-dessous invalident la version « 1 ligne » de la checklist** : le moniteur HTTP ne peut PAS marcher tel quel (le bot n'expose aucune URL), et l'« export des montants dus » n'existe pas comme fonction du bot — les deux ont un contournement chiffré.

---

## Verrou 1 — Savoir en premier, pas en dernier (moniteur de vie)

**Le geste.** Un moniteur externe qui alerte ton téléphone dès que le bot meurt. Objectif : tu l'apprends par une notification, jamais par un clipper mécontent 3 jours plus tard.

> [!warning] Correction technique (vérifiée dans le code, 21/07)
> Le bot est un **`worker` Discord** (`Procfile` : `worker: python3 bot_discord.py`) — il **n'ouvre aucun serveur HTTP**, donc **aucune URL à pinger**. Un moniteur type UptimeRobot en mode « ping HTTP » n'a rien à interroger : il rapportera « en ligne » même bot mort, ou « hors ligne » en permanence. La formule « ping HTTP toutes les 5 min » de la checklist est **inopérante telle quelle.**

**Ce qui marche à la place : un interrupteur d'homme mort (dead-man's switch).** On inverse la logique — c'est le bot qui appelle un service externe à intervalle régulier, et le service **hurle quand les appels s'arrêtent**. C'est exactement ce qu'on veut surveiller : « la boucle du bot tourne ET il a du réseau ».
- Créer un check gratuit sur **Healthchecks.io** (ou UptimeRobot type **Heartbeat**) → tu obtiens une URL de ping + une alerte push/SMS si silence > X min.
- Ajouter au bot une tâche de fond de ~8 lignes qui frappe cette URL toutes les 2-3 min (`requests` est déjà dans `requirements.txt`). Claude peut la coder en une passe — **à faire avant le gel des déploiements du verrou 6.**
- Réglage : période 5 min, grâce 5 min → alerte à ~10 min de silence. Bénéfice secondaire : un redémarrage Railway silencieux se voit aussi.

**Le test de validation.** Une fois posé, tue le bot depuis Railway (Stop) et **vérifie que l'alerte tombe bien sur ton téléphone** avant de le rallumer. Un moniteur jamais déclenché n'est pas un moniteur.

## Verrou 2 — Une sauvegarde restaurée, pas seulement écrite

**Le geste (déjà codé).** Backup auto le **dimanche à partir de 20h** (poste les JSON du volume dans le salon admin) + commande **`!sauvegarde`** à la demande (les mêmes fichiers en pièces jointes). Les données : `compteur_verse.json`, `paiements.jsonl`, `bump.json`, `faq_apprise.md`, le journal des questions.

> [!warning] Deux pièges qui rendent la sauvegarde fausse
> 1. **Elle vit dans le même Discord qu'elle est censée protéger.** Une sauvegarde postée dans le serveur n'est pas *hors-site* : serveur compromis ou salon purgé = sauvegarde perdue avec le reste. **Correctif : télécharge les pièces jointes `!sauvegarde` dans ton Drive** (hors Discord) au moins une fois avant le départ, et note où.
> 2. **L'auto-guérison ne restaure QUE le compteur public.** Au démarrage, si l'état local est vide, le bot relit le **total versé** depuis le message épinglé de `#dopamine` — mais **ni les montants par clipper, ni le tracking d'invitations, ni les bumps** ne sont restaurables ainsi (confirmé README : « les compteurs de bumps repartent du bump suivant »). Le compteur public survit ; la mémoire fine, non.

**Le test de validation (le vrai).** *« Une sauvegarde jamais restaurée n'est pas une sauvegarde. »* Fais le tour complet **une fois** avant de partir : `!sauvegarde` → télécharge les JSON → efface/renomme un fichier sur le volume `/data` → **remets le fichier sauvegardé en place** → redémarre → vérifie que `!compteur` et l'historique reviennent identiques. Tant que tu n'as pas fait ce cycle en réel, tu ne sais pas si tu peux restaurer.

## Verrou 3 — La page « si le bot est mort » (Emma + Maxence tiennent 48 h sans toi)

**Le geste.** Une page unique, remise à [[Les 5 Loom de passation|Emma et Maxence]], qui leur permet de survivre 48 h à un bot mort **sans toi et sans redéploiement risqué**. Le contenu est prêt, à copier tel quel :

> [!note] SI LE BOT NE RÉPOND PLUS — procédure 48 h (Emma / Maxence)
> **1. Est-il vraiment mort ?** Écris une question test dans `#assistant`. Pas de réponse en 2 min → il est probablement tombé.
> **2. Le relancer (2 clics, sans danger).** [railway.app](https://railway.app) → projet du bot → service → bouton **Restart** (ou Deployments → dernier déploiement → **Redeploy**). Attendre 1-2 min, les logs doivent afficher « Bot Discord démarré ». **Ne changer AUCUNE variable, ne pousser AUCUN code.**
> **3. Toujours mort ?** Regarder les logs Railway : si `DONNEES_DIR` a sauté ou le **Volume `/data`** s'est détaché (incident Railway connu), le réattacher suffit — sinon **ne rien bricoler.**
> **4. Message d'attente à poster dans `#assistant`** (copier-coller) : *« Petit souci technique sur l'assistant, on le relance — posez vos questions ici, on répond à la main en attendant. 🙏 »*
> **5. La paie ne dépend PAS du bot.** Le lundi tombe quand même via le verrou 4 (Maxence). Ne jamais dire aux clippers « pas de paie car le bot est cassé ».
> **6. Prévenir Gaëtan** (canal convenu), mais **sans attendre sa réponse pour faire 1-4.**

**Le test de validation.** Emma fait le Restart Railway **une fois devant toi** avant le départ. Une procédure jamais exécutée par la personne concernée n'est pas transférée.

## Verrou 4 — Maxence payeur de secours (la paie tombe même bot mort)

**Le geste.** La paie du lundi ne doit jamais dépendre d'un logiciel. Maxence doit pouvoir verser seul, à partir d'une source qu'il peut ouvrir sans toi.

> [!warning] Correction : « l'export des montants dus » n'existe pas dans le bot
> Le bot trace les montants **versés** (`paiements.jsonl`, compteur épinglé), pas les montants **dus.** `!paiement` est déclaratif : *toi* tu décides qui reçoit combien, le bot ne fait qu'annoncer et additionner. **Il n'y a aucune commande qui sorte « qui doit être payé cette semaine ».**
> **D'où vient réellement le batch dû :** de la consolidation du [[Reporting clippers|reporting du dimanche soir]] (Google Form → Sheet) croisée avec les subs vérifiés (GetAllMyLinks/Infloww, jamais déclarés par le clipper) → fixe + variable par personne. **C'est CE Sheet, pas le bot, qui est la source de vérité de la paie.**

**Donc le verrou 4 concret, c'est :**
1. **Donner à Maxence l'accès en lecture au Sheet de consolidation** du reporting (la ligne « à payer cette semaine » par clipper : fixe + subs × montant).
2. **Documenter la méthode de virement** — rails, ordre, et surtout **tester en premier les rails Madagascar/Bénin** (les moins fiables) : un virement de **test réel** avant le départ, pas au premier lundi critique.
3. **Le bot reste le mégaphone, pas le payeur** : une fois Maxence a viré, il tape `!paiement @x 50` → la preuve publique tombe dans `#dopamine`, le compteur monte. Si le bot est mort ce lundi-là, il **vire quand même** et rattrapera les annonces avec `!ajuster` au retour du bot.

**Le test de validation.** Maxence a fait **UN virement de test** sur le rail le plus fragile, et a ouvert le Sheet de consolidation **par lui-même**, avant le 26/07.

## Verrou 5 — Le rythme sacré (la fiabilité s'achète en fréquence)

**Le geste.** Vues/subs vérifiés à **J+7**, virement à **J+8**, **jamais un retard, jamais une exception.** La fiabilité perçue ne vient pas du montant mais de la régularité : un petit paiement toujours à l'heure bat un gros paiement parfois en retard. Le rituel complet (Form dimanche → lecture lundi → appel de groupe → paie) est dans [[Reporting clippers]] et le SLA dans le cadre d'[[Équipe marketing - structure et rémunération (FR × MG)|équipe]].

**Le geste de départ.** **Première paie du sprint versée le matin même du 26/07** — le signal de fiabilité le plus fort possible à J-0 : « je pars, et la machine paie pile à l'heure sans moi. »

**Le test de validation.** Le calendrier des paies d'août est déjà posé (dates fixes), connu de Maxence, et la première tombe avant/le jour du départ.

## Verrou 6 — Gel des déploiements (la leçon Hugo, gravée)

**Le geste.** Pendant l'absence : **plus AUCUN redéploiement non nécessaire.** Chaque redéploiement rouvre la fenêtre de webhook perdu qui a bloqué Hugo. `rattraper_webhooks()` au démarrage relit l'historique récent du salon admin et limite la casse — **mais ne l'annule pas** (un webhook hors fenêtre de rattrapage reste perdu).

**Les garde-fous concrets :**
- **Watch Paths Railway = `tools/bot_clippers/**`** (Settings) : sans ça, **chaque push du repo — même un commit du vault Obsidian — redéploie le bot.** C'est le correctif structurel du gel : le vault et le bot partagent le repo, donc sans Watch Paths, chaque session Claude sur le second cerveau redémarre le bot. **À vérifier posé avant le départ.**
- **Règle annoncée** : redéploiement autorisé uniquement sur bug bloquant, et jamais un lundi (jour de paie). Exception unique tolérée : poser la tâche de heartbeat du verrou 1 **avant** de geler.

**Le test de validation.** Un commit du vault poussé après réglage des Watch Paths **ne déclenche PAS** de redéploiement du bot (vérifiable dans l'onglet Deployments de Railway).

---

## Le 7e verrou (politique) — le plan anti-Goodhart, écrit AVANT le premier cas

Toute métrique payée sera attaquée. La règle annoncée **avant** le premier fraudeur est une politique ; annoncée après, c'est une injustice qui vide le Discord. À écrire noir sur blanc dans le kit, et à publier **avant** de scaler à 200 :
- **Définition contractuelle du sub payable** (portée par le contrat v2) et **consolidation à J+7** (rien n'est payé sur un chiffre non consolidé).
- **Audits aléatoires** : 10 % des liens recontrôlés chaque semaine.
- **Clawback** (récupération) : porté par le contrat, activable si fraude découverte après paiement.
- **Bannissement public documenté du premier fraudeur** : le signal qui protège les honnêtes.
- **Réconciliation GetAllMyLinks ↔ dashboards hebdo** : écart > 10 % = **alerte, pas paiement.**

## Ce que ça protège, chiffré

20 clippers actifs × ~550 €/mois de profit potentiel par clipper productif = la machine que la paie fiable retient. Le coût d'un cycle raté n'est pas le montant du cycle — c'est **la crédibilité du programme entier**, au moment exact où tu n'es pas là pour la réparer. Dans le cadre du [[Pacte d'association LTP (partenariat 50-50 avec Maxence)|pacte]], c'est aussi ce qui rend vrai « mon pôle tourne via mes systèmes » (parade Art 10.2), et c'est une pièce maîtresse du [[Sprint été - croissance sans moi|sprint « croissance sans moi »]].

## Checklist départ (à cocher, [[Journal de coaching|journalisée]])

- [ ] **Verrou 1** — Heartbeat codé dans le bot + check Healthchecks.io/UptimeRobot actif + **alerte reçue sur le téléphone lors d'un Stop test** *(⚠️ pas un simple ping HTTP — le bot n'a pas d'URL)*
- [ ] **Verrou 2** — Cycle `!sauvegarde` → **JSON téléchargés hors Discord (Drive)** → une restauration réelle vérifiée sur `/data`
- [ ] **Verrou 3** — Page « si le bot est mort » remise à Emma + Maxence, **Restart Railway fait une fois par Emma** devant toi
- [ ] **Verrou 4** — Maxence a l'**accès en lecture au Sheet de consolidation** + a fait **UN virement de test** sur le rail le plus fragile
- [ ] **Verrou 5** — Calendrier des paies d'août posé, **première paie versée le matin du 26/07**
- [ ] **Verrou 6** — **Watch Paths Railway = `tools/bot_clippers/**`** vérifiés (un commit du vault ne redéploie plus le bot) + gel annoncé
- [ ] **7e verrou** — Plan anti-Goodhart publié dans le kit avant de scaler
