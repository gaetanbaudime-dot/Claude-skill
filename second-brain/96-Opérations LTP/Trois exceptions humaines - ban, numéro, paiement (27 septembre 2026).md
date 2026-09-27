---
titre: "Trois exceptions humaines - ban, numéro, paiement (27 septembre 2026)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-09-27
tags: [ops/clipping, ops/support, ops/simplification, ops/bot]
liens_forts: ["[[Process clippers de bout en bout - 10 simplifications (27 septembre 2026)]]", "[[Bot FAQ clippers (Discord)]]", "[[Architecture Discord - simple au quotidien (14 septembre 2026)]]"]
---

# Trois exceptions humaines - ban, numéro, paiement (27 septembre 2026)

> [!tip] Verdict
> Un clipper n'a que **trois raisons** d'écrire à un humain : **un ban**, **un numéro refusé**, **une question de paiement**. Tout le reste est réglé par le bot ou n'a pas besoin de réponse. Cette règle est codée dans l'assistant depuis le 27/09 (règle 21) : il ne renvoie vers WhatsApp que pour ces trois cas, et pour tout le reste il donne la base, la fiche, ou « je ne sais pas » en une phrase. Ce que ça t'achète : un seul canal (WhatsApp), trois motifs, un message type par motif, et un temps de réponse que tu peux tenir seul. Ce qui le casse : répondre à un quatrième motif « pour dépanner ». Chaque exception que tu ajoutes revient le lendemain avec dix clippers.

## 1. Pourquoi trois, et pourquoi ces trois

Le bot a une base de connaissances, la mémoire de chaque clipper, le classeur des comptes, les visites et la paie. Il sait donc répondre à tout ce qui est **écrit quelque part**. Il ne sait pas répondre à ce qui demande **une décision ou un pouvoir** qu'il n'a pas :

| Exception | Pourquoi un humain | Ce que le bot ne peut pas faire |
|---|---|---|
| **Ban** (suspendu, désactivé, « nous examinons », restriction qui dure) | Décider entre faire appel et remplacer le compte ; c'est de l'argent (un compte chauffé) et du risque (un appel raté brûle le compte) | Faire appel à la place du clipper, lire l'écran Instagram, décider |
| **Numéro refusé** (Instagram refuse le numéro, ou le numéro est déjà lié à trop de comptes) | Vérifier si le numéro porte d'autres comptes, décider d'un autre numéro, ou stopper la création | Voir ce qu'Instagram sait du numéro, en fournir un autre |
| **Paiement** (montant, date, adresse, retard, désaccord) | C'est un virement, une promesse, un litige ; personne d'autre que toi ne peut payer ni trancher | Payer, corriger un montant, expliquer un retard |

Tout le reste tombe dans l'une de ces trois familles, déjà couvertes :
- **Ce qui est dans la base** (créer un compte, le warm-up, le lien, la cadence, le montage, les codes) : le bot répond, et renvoie à la fiche.
- **Ce qui est un état** (où j'en suis, mes visites, mon étape, mon code) : une commande ou un bouton.
- **Ce qui n'est nulle part** (« pourquoi Instagram me dit ça ? ») : le bot dit « je ne sais pas », donne la fiche la plus proche, et ne fait rien d'autre. Un « je ne sais pas » honnête coûte moins cher qu'une explication inventée (le 27/09, « sécurisé par l'agence, c'est normal » était une invention).

## 2. Le protocole, côté clipper

Le clipper voit toujours la même chose : **un bouton « Écrire à Gaëtan (WhatsApp) »** sous son salon perso et sous chaque étape, et une phrase du bot quand l'un des trois cas se présente. Le message WhatsApp attendu, dans cet ordre, sinon il repart :

1. Prénom et créatrice.
2. Le motif, un mot : **ban**, **numéro**, **paiement**.
3. Le problème en une phrase.
4. Une capture d'écran.

Ce que le bot dit, mot pour mot, pour chaque cas :

- **Ban** : « Ne clique sur rien. Ne crée rien. Fais une capture de l'écran. Écris à Gaëtan sur WhatsApp : ton prénom, ta créatrice, « ban », la capture. Continue sur tes autres comptes. »
- **Numéro** : « N'essaie pas un autre numéro. Fais une capture. Écris à Gaëtan sur WhatsApp : ton prénom, ta créatrice, « numéro », la capture. »
- **Paiement** : « Tes visites sont dans `!mesclics`. Pour un montant, une date ou une adresse, écris à Gaëtan sur WhatsApp : ton prénom, ta créatrice, « paiement », ta question en une phrase. »

## 3. Le protocole, côté Gaëtan

Un cas, une réponse type, un délai. Le délai est tenable parce que les motifs sont trois, et que le bot a déjà fait le tri.

| Cas | Première réponse (copier-coller) | Décision | Délai visé |
|---|---|---|---|
| **Ban** | « Reçu. Ne touche à rien. Je regarde et je te dis : appel ou nouveau compte. » | Appel si le compte a plus de 7 jours de publication et un motif contestable ; sinon `!liberer` et nouveau compte le lendemain. L'appel se fait **avec** le clipper, code de récupération via `!recup`. | 24 h |
| **Numéro** | « Reçu. Ce numéro sert à combien de comptes Instagram, en tout ? » | Un numéro = 3 comptes maximum. S'il en porte déjà, il ne sert plus : le clipper attend un autre moyen (compte déjà créé de l'agence, ou pause). Jamais de numéro jetable. | 24 h |
| **Paiement** | « Reçu. Je vérifie et je te réponds avant [date]. » | Le bot fait la liste le 5 et le 20 (`!paie-clics`). Une contestation se tranche sur `!mesclics` et la liste, pas de mémoire. | 48 h |

Trois règles pour toi :
1. **Une réponse par cas, pas une conversation.** La première réponse est un copier-coller ; la décision suit. Si la discussion dépasse trois messages, c'est que le cas n'était pas l'un des trois, ou que la fiche manque : on complète la fiche, pas la conversation.
2. **Le bot apprend chaque cas réglé.** `!apprendre Q | R` dans le salon admin après chaque cas : la prochaine fois, le bot répond seul.
3. **Pas de quatrième motif.** « Mon téléphone rame », « je n'ai pas compris la fiche », « je peux poster autre chose ? » : ce sont des questions pour le bot. Si le bot ne sait pas, la réponse à écrire est dans la base, pas sur WhatsApp.

## 4. Ce que ça donne en chiffres

| Mesure | Avant (salon de Daniella, 26-27/09) | Après |
|---|---|---|
| Motifs qui remontent à un humain | tout ce que le bot ne sait pas, plus ce qu'il inventait | 3 |
| Canaux vers Gaëtan | mentions Discord, salon perso, WhatsApp, Telegram | 1 (WhatsApp, bouton) |
| Messages du bot par message du clipper | ≈ 1,6 | < 1,2 (mesure au 04/10) |
| Cas réglés sans humain | non mesuré | à lire dans `!lacunes` (ce que le bot n'a pas su) |

## 5. Ce qui ferait échouer ça

- **Toi qui réponds dans le salon perso** à la place du bot : le bot se tait 30 minutes après toi (règle du 27/09), donc chaque intervention hors des trois cas éteint le bot pour tout le monde dans ce salon.
- **Un quatrième motif toléré une fois.** Il devient la norme en trois jours.
- **Une base qui ne bouge pas.** Chaque « je ne sais pas » du bot est une ligne à ajouter (`!lacunes` les liste) ; sans ça, les mêmes questions reviennent sur WhatsApp.

Cadre : [[Process clippers de bout en bout - 10 simplifications (27 septembre 2026)]] (simplification n° 7). Les réponses du bot et sa base : [[Bot FAQ clippers (Discord)]]. L'organisation des salons : [[Architecture Discord - simple au quotidien (14 septembre 2026)]].
