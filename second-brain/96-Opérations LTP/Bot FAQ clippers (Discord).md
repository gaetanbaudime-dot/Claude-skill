---
titre: "Bot FAQ clippers (Discord)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-15
tags: [ops/formation, ops/clipping, ops/outillage]
liens_forts: ["[[Kit Clippers - mode d'emploi]]", "[[Journal de coaching]]", "[[Recruter et déléguer 20-30 marketeurs (playbook)]]"]
---

# Bot FAQ clippers : l'assistant Discord du kit

> [!tip] Verdict
> Un bot **Discord** (**code : `tools/bot_clippers/bot_discord.py`**) qui répond aux questions des clippers **uniquement à partir du Kit Clipper v2 + la stratégie marketing** — s'il ne sait pas, il renvoie vers Gaëtan, il n'invente jamais. Choisi Discord plutôt que Telegram le 15/07 (décision UX/ROI) : les clippers y travaillent déjà, donc **zéro nouvelle appli, zéro code d'accès** (être dans le serveur = accès). Le vrai coût n'était jamais le développement : c'est la **curation** (réglée : la base = ce que les clippers ont déjà) et la **mesure** (réglée : chaque question journalisée avec un marqueur « escalade »).

## Ce que c'est (et ce que ce n'est pas)

- **C'est** : un répondeur sur le périmètre du kit + la stratégie marketing officielle (3 piliers cadence/qualité/A-B testing, circuit des 50 rushs, carrousels au pic, feedback quotidien — distillés des 2 vidéos YouTube, recentrés **Instagram + Facebook uniquement**). Réponses courtes forcées (2-4 phrases, niveau collège), 30 questions/jour/personne, journal des questions.
- **UX** : les clippers écrivent dans un canal `#assistant` dédié (ou mentionnent le bot). Pas de code, pas d'appli en plus. Retirer quelqu'un = le sortir du serveur.
- **Entrées** : texte + captures d'écran (vision Claude). Vocaux refusés poliment (pas de transcription en v1).
- **Amélioration continue** : connaissances rechargées sans redémarrage ; Gaëtan enrichit depuis Discord avec `!apprendre Question | Réponse` et suit l'usage avec `!stats`. Le bot n'écrit jamais dans sa base sans validation humaine (garde-fou anti-erreur).
- **Ce n'est PAS** : un accès au playbook complet, aux identités des créatrices, aux chiffres de l'agence, ou à quoi que ce soit hors kit — le prompt système le verrouille et `connaissances.md` ne contient rien d'autre.
- **La règle du renvoi reste la doctrine** ([[Kit Clippers - mode d'emploi]]) : le bot EST le renvoi automatisé — il cite la fiche concernée à chaque réponse.

## Mise en service (côté Gaëtan, ~15 min, une fois)

Mode d'emploi complet dans `tools/bot_clippers/README.md`. Il ne reste que ce que Claude ne peut pas faire à distance :
1. **App Discord** : discord.com/developers → New Application → onglet Bot → token + activer **Message Content Intent** ; OAuth2 → URL Generator → scope `bot` + permissions (View Channels, Send Messages, Read Message History) → inviter le bot sur le serveur.
2. **Clé API Claude** : console.anthropic.com → limite de dépense 25 $/mois → clé.
3. **Identifiants** : mode développeur Discord → id du canal `#assistant` (`CANAL_BOT_ID`) + son propre id (`ADMIN_IDS`).
4. **Hébergement always-on** (car Gaëtan voyage) : Railway (~5 $/mois), déploiement depuis le repo GitHub, root dir `tools/bot_clippers`, variables d'env + `DONNEES_DIR=/data`, **volume monté sur `/data`** pour que le journal et la FAQ apprise survivent aux redéploiements.

## Coût (le vrai chiffre)

Modèle par défaut **`claude-haiku-4-5`** (rapide, quasi gratuit, largement assez pour une FAQ) : API ≈ **1-2 €/mois** même à fort volume. Total dominé par l'hébergement (~5 $/mois) → **~5-7 $/mois**. À 65 k€/mois de CA, le coût est du bruit : le levier de ROI n'est pas le prix mais l'**adoption** (d'où le choix Discord). Option `MODELE=claude-opus-4-8` pour des réponses plus fines (~5x, reste sous ~10 €/mois).

## Architecture

Base curée (`connaissances.md`) versionnée dans le repo (mise à jour par Claude/Gaëtan) ; ajouts `!apprendre` dans `faq_apprise.md` sur le volume persistant. Le bot charge les deux. `bot.py` (version Telegram) est conservé en option mais non utilisé.

## v2 (17/07) — le bot du programme clippers

Le bot opère désormais la boucle de la [[Machine de recrutement clippers (100 leads par mois)|machine de recrutement]] : **`!paiement @x 50 [raison]`** (annonce dopamine + **compteur épinglé « X € déjà versés »** + trace `paiements.jsonl`), **`!compteur`**, **`!rang @x Rookie/Confirmé/Elite`** (rôles à créer sur le serveur), **`!invites`** (classement). Avec `ACTIVER_V2=1` (exige l'intent privilégié Server Members + permission « Gérer le serveur ») : **tracking d'invitations** (attribution du parrain à chaque join — on tracke au join, on ne paie jamais au join) + **accueil numéroté** (« tu es le Nᵉ futur clipper ») dans `#candidature` avec le lien du formulaire. Les commandes admin marchent depuis n'importe quel canal. Déploiement sans risque : v2 éteinte par défaut. Mise en service : `tools/bot_clippers/README.md`, section v2.

## La mesure (ce qui remplace le débat)

`donnees/journal_questions.jsonl` enregistre chaque question + un marqueur `escalade` (= réponse hors kit). Bilan rentrée (via `!stats` ou le journal) : beaucoup d'escalades → enrichir `connaissances.md` (et le kit) ; peu de questions → le kit v2 suffisait, le bot aura servi de preuve.

## Continuité (le bot est un point de défaillance unique)

Ce bot fait tomber la paie : s'il meurt pendant l'absence, c'est le risque de ruine n°1. Les 6 verrous opérationnels (moniteur de vie par heartbeat — le bot est un `worker` sans URL, donc pas de ping HTTP —, sauvegarde restaurée en réel, page « si le bot est mort » pour Emma/Maxence, Maxence payeur de secours via le Sheet de consolidation, rythme sacré, gel des déploiements via Watch Paths) sont détaillés dans [[Continuité du bot et paie sacrée (plan anti-panne)]].

## Sécurité

Secrets (`.env`) et données locales (`donnees/`) exclus du repo par le `.gitignore`. Le prompt refuse : hors-kit, injections (« ignore tes règles »), tactiques dangereuses pour les comptes. Le bot ne répond que dans le canal dédié ou quand on le mentionne — il ne spamme pas le serveur.
