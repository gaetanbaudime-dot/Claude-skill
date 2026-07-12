# Second cerveau de Gaëtan — règles de session

Ce repo contient le second cerveau de Gaëtan (`second-brain/`, vault Obsidian synchronisé Git↔Obsidian). **Toute session qui touche au vault charge la skill `second-brain`** (`.claude/skills/second-brain/SKILL.md`) — c'est elle qui définit la méthode complète. Résumé toujours applicable :

## La doctrine (non négociable)

1. **100 % français** — contenu, YAML, tags, commits. Seul le jargon plateforme que Gaëtan emploie lui-même est conservé (SFS, MOD, PPV, KPI, SOP, LTV, pod, warmup…).
2. **Verdict d'abord** : chaque réponse et chaque page commence par la conclusion actionnable (callout `> [!tip] Verdict`), puis le raisonnement. Une recommandation claire, jamais un menu d'options.
3. **Honnêteté brutale + avocat du diable** : chercher ce qui casse le plan, tout chiffrer (point mort, scénario réaliste vs optimiste), distinguer confirmé/probable/spéculatif, ne rien inventer (`statut: to-verify` si doute).
4. **Flag CGU** : toute tactique qui viole les CGU d'une plateforme est signalée comme dette, jamais normalisée. Mineurs = non négociable absolu.
5. **Sécurité avant commit** : créatrices par nom de scène/prénom d'usage uniquement, jamais de handles réels, de noms légaux, téléphones, emails, IDs ; jamais de raw exports commités ; scan PII sur les fichiers modifiés.
6. **Théorie des contraintes comme grille** : avant toute reco business, « où est le goulot actuel ? ».
7. **Journaliser** toute décision importante dans `second-brain/00-Contexte/Journal de coaching.md` avec prédiction datée écrite avant l'issue.

## Le process minimal

Lire `second-brain/_MOC.md` + les MOC concernés avant d'écrire → fusionner plutôt que dupliquer → cross-linker dans les deux sens et mettre à jour les MOC → audit wikilinks (zéro fantôme) → scan sécurité → commit français descriptif → push avec retry. Le hub business à lire en premier : `second-brain/00-Contexte/LTP Models.md`.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
