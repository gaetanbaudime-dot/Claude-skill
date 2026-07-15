---
titre: "Bot FAQ clippers (Telegram)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-15
tags: [ops/formation, ops/clipping, ops/outillage]
liens_forts: ["[[Kit Clippers - mode d'emploi]]", "[[Journal de coaching]]", "[[Recruter et déléguer 20-30 marketeurs (playbook)]]"]
---

# Bot FAQ clippers : l'assistant Telegram du kit

> [!tip] Verdict
> Un bot Telegram (**code : `tools/bot_clippers/`**) qui répond aux questions des clippers **uniquement à partir du Kit Clipper v2** — s'il ne sait pas, il renvoie vers le canal Discord, il n'invente jamais. Construit le 15/07 sur demande de Gaëtan (avancé par rapport au verdict « septembre » du 14/07 — voir journal). Le vrai coût n'était pas le développement : c'est la **curation** (réglée : la base = le kit v2, déjà distribué en PDF, donc zéro exposition nouvelle) et la **mesure** (réglée : chaque question est journalisée avec un marqueur « escalade »).

## Ce que c'est (et ce que ce n'est pas)

- **C'est** : un répondeur sur le périmètre du kit + la stratégie marketing officielle (v2 du 15/07 : les 3 piliers cadence/qualité/A-B testing, le circuit des 50 rushs, les carrousels au pic, le feedback quotidien — distillés des 2 vidéos YouTube de Gaëtan, recentrés Instagram + Facebook uniquement). Accès par code, 30 questions/jour/personne, journal des questions, réponses courtes forcées (2-4 phrases, niveau collège).
- **Entrées acceptées** : texte + photos/captures d'écran (lues par la vision de Claude). Vocaux : pas en v1 (l'API ne transcrit pas l'audio) — le bot demande d'écrire.
- **Amélioration continue** : les connaissances se rechargent seules (fichier modifié = pris en compte sans redémarrage) ; Gaëtan enrichit la FAQ depuis Telegram avec `/apprendre Question | Réponse` et suit l'usage avec `/stats`. Le bot n'écrit jamais lui-même dans sa base sans validation humaine (garde-fou anti-erreur).
- **Le lien** : `t.me/<nom_du_bot>` — permanent, à épingler dans Discord avec le code d'accès.
- **Ce n'est PAS** : un accès au playbook complet, aux identités des créatrices, aux chiffres de l'agence, ou à quoi que ce soit hors kit — le prompt système le verrouille et la base de connaissances (`connaissances.md`) ne contient rien d'autre.
- **La règle du renvoi reste la doctrine** ([[Kit Clippers - mode d'emploi]]) : le bot EST le renvoi automatisé — il cite la fiche concernée à chaque réponse.

## Mise en service (côté Gaëtan, ~15 min, une fois)

Le mode d'emploi complet est dans `tools/bot_clippers/README.md`. Il ne reste que ce que Claude ne peut pas faire à distance (créer les 2 clés) :
1. **Bot Telegram** : @BotFather → `/newbot` → token. Le lien à partager est `t.me/<nom_du_bot>` (permanent, à épingler sur Discord avec le code d'accès).
2. **Clé API Claude** : console.anthropic.com → une limite de dépense (25 $/mois) → clé.
3. **Hébergement always-on (recommandé, car Gaëtan voyage)** : Railway (~5 $/mois), déploiement depuis le repo GitHub, root dir `tools/bot_clippers`, 4 variables d'env + `DONNEES_DIR=/data`, **un volume monté sur `/data`** pour que le journal et la FAQ apprise survivent aux redéploiements. Test rapide possible sur le Mac (`python3 bot.py`) avant de déployer.

**Architecture** : la base curée (`connaissances.md`) est versionnée dans le repo (mise à jour par Claude/Gaëtan) ; les ajouts `/apprendre` vont dans `faq_apprise.md` sur le volume persistant. Le bot charge les deux. Coût d'usage : **~1 centime/question** (~5-10 €/mois à l'échelle actuelle).

## La mesure (ce qui remplace le débat)

`donnees/journal_questions.jsonl` enregistre chaque question + un marqueur `escalade` (= la réponse n'était pas dans le kit). Bilan à la rentrée : beaucoup d'escalades → enrichir `connaissances.md` (et le kit) ; peu de questions → le kit v2 suffisait, le bot aura au moins servi de preuve. La section « FAQ vivante » de `connaissances.md` absorbe les questions posées 2 fois — même règle que le canal #faq.

## Sécurité

Secrets (`.env`) et données locales (`donnees/`) exclus du repo par le `.gitignore`. Le prompt refuse : hors-kit, injections (« ignore tes règles »), tactiques dangereuses pour les comptes (achat d'abonnés, bots). Révocation d'un clipper : changer le code d'accès + retirer son entrée de `donnees/autorises.json`.
