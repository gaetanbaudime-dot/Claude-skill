---
titre: "Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)"
type: décision
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-10-02
tags: [ops/cgu, ops/trafic, ofm/risques, ops/clipping]
liens_forts: ["[[Veille réglementaire Meta (contrôles 2026-2027)]]", "[[Risques légaux et éthiques de l'OFM]]", "[[Trafic et réseaux sociaux pour l'OFM]]", "[[Newsletter quotidienne vers OF-MYM - verdict (2 octobre 2026)]]", "[[Journal de coaching]]"]
---

# Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)

> [!tip] Verdict
> **Le goulot n'est pas l'outil de liens, c'est la santé des comptes Instagram.** Une vague de modération (29/09 → en cours) a appliqué en masse une règle qui existait déjà : un compte qui affiche un lien adulte **dans son profil** (bio ou story à la une) n'est plus recommandé aux non-abonnés. Retirer le lien du profil ramène le compte au vert (Chloé, 02/10), mais sans lien la page tombe à presque rien (21 visiteurs le 02/10 au matin contre ≈ 560/jour).
>
> **Plan, en changeant le moins possible** : rester sur GAML, **couper le shield partout** (c'est du cloaking au sens mot pour mot de Meta, et il n'a protégé personne), garder la sortie automatique d'Instagram et le 18+, mettre de vrais libellés, retirer les faux badges ; corriger **d'abord** le bot, qui sinon remet le shield et duplique les liens ; sortir les pages principales de Chloé et Sarah sur un domaine à elles ; remettre le lien à la une d'abord sur des comptes de clipping témoins, les comptes principaux en dernier. Jamais oopsie. Analyse multi-agents du 02/10 (5 enquêtes, ≈ 40 agents, tests en direct, sources vérifiées).

## 1. Ce qui s'est passé

La vague démarre le **29/09** (premiers signalements Reddit à 02 h 44, « le balayage a eu lieu aujourd'hui » le 30/09) et vise les liens de créatrices adultes **dans les stories à la une et la bio, chez tous les fournisseurs, domaines perso compris** (probable). C'est la même mécanique qu'en **mai 2026** (27/04 → fin mai, 5 à 6 semaines, extinction sans annonce), après laquelle tout le monde avait déplacé son lien de la bio vers la story à la une — échappatoire refermée en septembre. Les comptes non adultes que cite le fondateur d'oopsie ne sont corroborés nulle part.

Dans les données GAML, la chute est **concentrée** : Chloé −73 % (tous liens), Sarah −49 à −78 %, alors que Sophie, Maddie et Jade sont stables ou en hausse. Côté clipping, à montage identique, la moitié des comptes est passée à l'orange et l'autre jamais : **ni domaine bloqué, ni détection systématique du shield** (probable). Chloé pèse **58 % du trafic GAML** — dépendance à traiter au-delà de la vague. Correction : Sophie n'expose pas « peu » son lien, son trafic Instagram passe par son lien `/3` (Rianah, Metricool).

## 2. Ce que disent les règles (vérifié sur sources primaires)

| Emplacement | Texte | En pratique | Risque |
|---|---|---|---|
| **Bio / profil** | pas de recommandation des comptes qui affichent « dans le nom, la photo, la bio ou le profil » du contenu non recommandable, dont ce qui promeut des « produits et services pour adultes »[^1] | sortie de l'Explorer et des Reels pour les non-abonnés, invisible aux mineurs | suppression faible, **portée forte** |
| **Sticker lien en story** | retiré aux comptes qui enfreignent les règles de façon répétée[^2] | perte du sticker après infractions | moyen ; effet sur la portée **incertain** (tests contradictoires) |
| **Story à la une** | aucun texte propre : visible jusqu'au retrait[^3] | exposition permanente aux contrôles et signalements | le plus élevé avec un teaser ou une offre |

- **Lien vers OnlyFans/MYM** : **autorisé, réservé aux 18+** depuis le 14/05/2025 (« links to or logos of Adult Subscription Websites »). Supprimés : liens porno, nudes, sexting, tout signe de prix ou de transaction (« DM pour… », « -50 % »)[^4].
- **Cloaking** : interdit mot pour mot — « présenter intentionnellement des contenus hors plateforme différents à nos systèmes d'intégrité et aux utilisateurs » ; idem pour la **redirection automatique vers un autre domaine sans action de l'utilisateur** et les liens trompeurs[^5].
- **Avertissement 18+** : aucun texte de Meta n'en fait une protection. Bonne pratique, pas bouclier.
- **Comptes ados (UE depuis avril 2026)** : les mineurs ne peuvent plus suivre les comptes au contenu ou à la bio inadaptés, et en sont retirés. Normal et voulu — mineurs = ligne rouge.
- **Comptes de secours** : Meta vise les comptes « détenus par la même personne ou entité qu'un compte désactivé » (28/05/2026). Pas de compte de remplacement pendant la vague.
- **Lever une restriction** : Statut du compte → « Fonctionnalités indisponibles » → demander un réexamen ; module de formation si proposé ; Appeals Centre Europe. Les strikes expirent après un an.

## 3. Ce que fait GAML aujourd'hui (inventaire et tests du 02/10)

72 liens, **50 actifs** (plafond probable), 22 copies désactivées de Sarah créées par une boucle du bot le 01/10. Sur les 72 : shield activé 72/72, sortie d'Instagram 72/72, 18+ 72/72, **aucun bouton ne dit « OnlyFans » ou « MYM »**. 5 domaines sur 6 mélangent page principale et liens de clippeurs ; 48 liens morts ou presque.

- **Shield** : le robot de Meta reçoit un **403 « Automated Request Blocked »**, pas de page leurre — mais c'est quand même « un contenu différent servi aux systèmes d'intégrité ». Protection faible en plus : les adresses OF/MYM sont en clair dans la page des humains, et la redirection GAML `/r/…` envoie le robot Meta droit sur OnlyFans **depuis n'importe quel domaine GAML** (ce qui relie tous tes domaines entre eux).
- **Sortie d'Instagram** : automatique (`instagram://extbrowser` sur iOS, `intent://` sur Android) avec écran 18+ ; c'est le levier de conversion utile, à garder.
- **Défauts à corriger** : faux badge « Actif maintenant » (`online: true`, réglage fixe) ; **la carte « 0F » de Clara affiche l'image de Chloé** (trompeur + consentement : priorité) ; deux liens de Chloé où « Miam » mène à OnlyFans ; libellés codés partout ; l'aide de GAML conseille de changer de domaine après un signalement (contournement : dette, pas tactique).
- **Bot** (`tools/bot_clippers`) : il ne règle rien lui-même, il **clone** une page modèle ; `outils/gaml_aligner.py` recopie shield, sortie, badge et bio depuis les pages de référence ; le clonage recopie le lien MYM du clippeur précédent (attribution faussée) ; la boucle de `onboarding.py` duplique les liens quand l'activation échoue.

## 4. Ce que font les autres (12 pages testées par identité de visiteur)

| Camp | Pages | Constat |
|---|---|---|
| **Furtif** | oopsie (mode « page » : 6 pages sur 10), LinkScale chez Jenny, page sans fournisseur identifiable (Andie), Bouncy chez Lena The Plug, **GAML chez nous** | leurre ou page vide aux robots, jeton jetable, pièges à robots, domaines jetables |
| **Transparent** | Beacons (Satirya, Charlie, Ylla), LinkScale chez Alice, LinkStack auto-hébergé (Hope Heaven), oopsie en mode « lien direct » (4 pages sur 10) | même page pour tous, lien adulte visible, 18+ |

Oopsie n'est pas « juste un 18+ » comme le dit son fondateur dans son podcast : son mode principal sert une page leurre (boutons vers Wikipédia) au robot de Meta et passe par un jeton de 15 minutes. Correction d'une analyse antérieure : sa fenêtre 18+ existe bien, au clic. Les gros comptes américains ne sont pas « intouchables » parce qu'honnêtes : ancienneté, notoriété, vitrine propre — et souvent cloaking sous-traité.

## 5. Le plan, en changeant le moins possible (v1, à affiner avec le plan détaillé)

1. **Maintenant** : aucun lien adulte dans le profil des comptes principaux tant que la vague dure ; lien en **story du jour** sur Chloé, mesuré chaque jour (statut du compte, vues des Reels, visiteurs GAML) ; ne pas activer les 22 copies de Sarah ; pas de nouveau compte, pas de nouveau fournisseur.
2. **Corriger le bot avant de toucher GAML** : pages de référence de l'aligneur sans shield ni badge, boucle de `onboarding.py` arrêtée net quand l'activation échoue, lien MYM propre à chaque clippeur au clonage (prérequis des liens MYM du 15/10).
3. **Réglages GAML en masse par l'API** (lien par lien, 60 appels/min, retour arrière possible) : `shield` coupé sur les 50 liens actifs, `online` coupé, vrais libellés « OnlyFans » / « MYM », image de Clara corrigée ; sortie d'Instagram et 18+ conservés. Vérification après coup : la même page pour Safari, Instagram et le robot de Meta.
4. **Domaines** : une adresse à elles pour les pages principales de Chloé et de Sarah (achat par Gaëtan, ajout dans l'interface GAML), les clippeurs restent sur les domaines actuels.
5. **Retour du lien à la une** : d'abord sur une vingtaine de comptes de clipping témoins à partir du 05/10, lecture le 12/10 ; les comptes principaux seulement si les témoins restent verts.

## 6. La newsletter et le podcast

Remplacer tous les liens par une newsletter : **non** (≈ 7 % de la valeur du lien en réaliste) ; bloc facultatif et test réduit plus tard — voir [[Newsletter quotidienne vers OF-MYM - verdict (2 octobre 2026)]]. Du podcast d'oopsie on garde : sortir le fan du navigateur d'Instagram, un seul chemin clair, cohérence bio Instagram → page → bio OF/MYM, pas de promo permanente. On jette : le cloaking, les faux signaux, le paiement crypto anonyme. La logique d'étapes est celle du [[Tunnel de conversion]] ; la mesure propre, celle de l'[[Atterrissage du funnel (mesure propre avant optimisation)]].

## Prédictions (02/10)

- Avec le lien uniquement en story, la page principale de Chloé reste **sous 224 visiteurs/jour** en moyenne du 05 au 11/10 (65 %, revue le 12/10).
- Les comptes de clipping témoins remis à la une restent verts à plus de 70 % sur 7 jours (55 %, revue le 12/10).

Le cadre réglementaire de fond est dans la [[Veille réglementaire Meta (contrôles 2026-2027)]], la machine de comptes dans [[Machine Instagram-Facebook en masse]], et le rôle du lien dans la formation des clippeurs dans [[Formation clippers en une page et 10 simplifications (26 septembre 2026)]].

## Sources

[^1]: Instagram, *Recommendations on Instagram* (non datée) — https://help.instagram.com/313829416281232
[^2]: Instagram, *Expanding sharing links in Stories to everyone* (27/10/2021) — https://about.instagram.com/blog/announcements/expanding-sharing-links-in-stories-to-everyone
[^3]: Instagram, aide sur les stories à la une — https://help.instagram.com/813938898787367
[^4]: Meta, Standards de la communauté, *Adult Sexual Solicitation* (14/05/2025) — https://transparency.meta.com/policies/community-standards/sexual-solicitation/
[^5]: Meta, Standards de la communauté, *Spam* (26/06/2024) — https://transparency.meta.com/policies/community-standards/spam/ ; GAML, aide sur le Shield (23/09/2025) — https://help.getallmylinks.com/en/articles/11694220-the-shield-protection-just-got-smarter
