---
titre: "Continuité du bot et paie sacrée (plan anti-panne)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-19
tags: [ops/clippers, ops/paie, ops/outils, plan/richesse]
liens_forts: ["[[Machine de recrutement clippers (100 leads par mois)]]", "[[Manager 200 clippers par un système]]", "[[Plan richesse (100 actions triées par levier)]]", "[[Sprint été - croissance sans moi]]", "[[Journal de coaching]]"]
---

# Continuité du bot et paie sacrée — fondamental n°7 (avant le 26/07)

> [!tip] Verdict
> **Le risque de ruine n°1 de ton absence n'est ni un concurrent ni un ban — c'est un lundi sans paie.** Le bot Railway est un **point de défaillance unique** (l'incident Hugo l'a prouvé : un webhook perdu pendant un redéploiement = un candidat bloqué en silence), et les données du pipeline vivent sur un seul volume JSON. Un seul cycle de paie contesté en public dans un Discord qui grossit déclenche la spirale terminale : **les meilleurs partent, les fraudeurs restent** (réf. [[Manager 200 clippers par un système]] — condition ① : la paie est sacrée). Le plan anti-panne tient en 6 verrous, tous posables avant le départ, aucun ne demandant plus d'une heure.

## Les 6 verrous

1. **Moniteur de disponibilité externe** (ping HTTP toutes les 5 min type UptimeRobot, gratuit) + **alerte téléphone** — tu apprends que le bot est mort par une notification, jamais par un clipper mécontent 3 jours plus tard.
2. **Sauvegarde automatique hebdomadaire** : ✅ déjà codée (backup auto dimanche 20h + commande `!sauvegarde` à la demande) — vérifier UNE restauration réelle avant le départ (une sauvegarde jamais restaurée n'est pas une sauvegarde).
3. **La page « si le bot est mort »** (1 page, à remettre à Emma + Maxence) : comment vérifier que Railway tourne, comment redémarrer le service (2 clics), qui prévenir, et le message d'attente à poster dans le Discord — l'équipe doit pouvoir tenir 48 h sans toi ni le bot.
4. **Maxence payeur de secours** : accès aux montants dus (le bot prépare le batch, mais un export manuel doit exister) + méthode de virement documentée — la paie tombe MÊME si le bot est mort. Rails Madagascar/Bénin (les moins fiables) testés en premier.
5. **Le rythme sacré** : vues/subs vérifiés à J+7, virement à J+8, **jamais un retard, jamais une exception** — la fiabilité s'achète en fréquence, pas en montant. Première paie versée le matin du départ = le signal le plus fort possible à J-0.
6. **Plus AUCUN redéploiement non nécessaire** : la leçon Hugo est gravée — chaque redéploiement pendant l'absence est un risque de webhook perdu ; `rattraper_webhooks()` au démarrage limite la casse mais ne l'annule pas. Gel des déploiements sauf bug bloquant.

## Le plan anti-Goodhart (le 7e verrou, écrit AVANT le premier cas)

Toute métrique payée sera attaquée. La règle annoncée **avant** le premier cas est une politique ; annoncée après, c'est une injustice qui vide le Discord. À écrire noir sur blanc dans le kit : définition contractuelle du sub payable · consolidation J+7 · audits aléatoires (10 % des liens) · clawback (porté par le contrat v2) · **bannissement public documenté du premier fraudeur**. Réconciliation GetAllMyLinks ↔ dashboards hebdo : écart > 10 % = alerte, pas paiement.

## Ce que ça protège, chiffré

20 clippers actifs × ~550 €/mois de profit potentiel par clipper productif = la machine que la paie fiable retient. Le coût d'un cycle raté n'est pas le montant du cycle — c'est **la crédibilité du programme entier** au moment exact où tu n'es pas là pour la réparer. Dans le cadre du [[Pacte d'association LTP (partenariat 50-50 avec Maxence)|pacte]], c'est aussi ce qui rend vrai « mon pôle tourne via mes systèmes » (parade Art 10.2).

## Checklist départ (à cocher, [[Journal de coaching|journalisée]])

- [ ] Moniteur externe actif + alerte téléphone testée
- [ ] Une restauration de sauvegarde vérifiée en réel
- [ ] Page « si le bot est mort » remise à Emma + Maxence
- [ ] Export manuel des montants dus testé + Maxence a fait UN virement de test
- [ ] Plan anti-Goodhart publié dans le kit
- [ ] Gel des déploiements annoncé (sauf bug bloquant)
