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

- **C'est** : un répondeur sur le périmètre du kit (comptes, warm-up, Reels, cadence, bans, reporting), accès par code, 30 questions/jour/personne, journal des questions.
- **Ce n'est PAS** : un accès au playbook complet, aux identités des créatrices, aux chiffres de l'agence, ou à quoi que ce soit hors kit — le prompt système le verrouille et la base de connaissances (`connaissances.md`) ne contient rien d'autre.
- **La règle du renvoi reste la doctrine** ([[Kit Clippers - mode d'emploi]]) : le bot EST le renvoi automatisé — il cite la fiche concernée à chaque réponse.

## Mise en service (côté Gaëtan, ~15 min, une fois)

Le mode d'emploi complet est dans `tools/bot_clippers/README.md` : (1) créer le bot chez @BotFather → token, (2) créer la clé API sur console.anthropic.com avec une limite de dépense, (3) remplir `.env`, `pip install`, `python3 bot.py`. Hébergement 24/7 quand validé : Railway (~5 $/mois). Coût d'usage : **~1 centime/question** (~5-10 €/mois à l'échelle actuelle).

## La mesure (ce qui remplace le débat)

`donnees/journal_questions.jsonl` enregistre chaque question + un marqueur `escalade` (= la réponse n'était pas dans le kit). Bilan à la rentrée : beaucoup d'escalades → enrichir `connaissances.md` (et le kit) ; peu de questions → le kit v2 suffisait, le bot aura au moins servi de preuve. La section « FAQ vivante » de `connaissances.md` absorbe les questions posées 2 fois — même règle que le canal #faq.

## Sécurité

Secrets (`.env`) et données locales (`donnees/`) exclus du repo par le `.gitignore`. Le prompt refuse : hors-kit, injections (« ignore tes règles »), tactiques dangereuses pour les comptes (achat d'abonnés, bots). Révocation d'un clipper : changer le code d'accès + retirer son entrée de `donnees/autorises.json`.
