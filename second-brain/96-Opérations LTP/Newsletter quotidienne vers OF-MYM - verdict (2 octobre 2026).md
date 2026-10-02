---
titre: "Newsletter quotidienne vers OF-MYM - verdict (2 octobre 2026)"
type: décision
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-10-02
tags: [ops/trafic, ops/cgu, legal/rgpd, ofm/tunnel]
liens_forts: ["[[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]]", "[[Risques légaux et éthiques de l'OFM]]", "[[Tunnel de conversion]]", "[[Journal de coaching]]", "[[Stratégie trafic interne MYM]]"]
---

# Newsletter quotidienne vers OF-MYM - verdict (2 octobre 2026)

> [!tip] Verdict
> **Non au remplacement de tous les liens par une newsletter.** Sur Chloé, elle garde au mieux la moitié de la valeur du lien direct, et environ **7 %** en scénario réaliste (≈ 277 €/mois contre ≈ 4 100 €). Le coût n'est pas l'attente de 19 h : c'est le **formulaire**, qui fait passer de 83 % de clics à quelques pourcents d'inscrits.
>
> **Oui, plus tard, à une version réduite** : un bloc facultatif « Ma lettre du soir » sous les boutons OF/MYM de la page honnête, avec e-mail de bienvenue immédiat, et un test « lettre en premier » sur les seuls comptes de clippeurs de Chloé, **pas avant le 20/10** et seulement après l'avis de l'avocat (vote solennel de la proposition de loi le 13/10). Analyse multi-agents du 02/10, vérifiée sur sources, contexte dans [[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]].

## Ce qui est juste dans l'idée

L'e-mail est universel (89 % des 16-74 ans en France[^1]) et le lien ouvert depuis l'app mail part dans le **vrai navigateur**, où le fan est connecté à OnlyFans et garde le lien de tracking — c'est le problème du navigateur d'Instagram réglé sans artifice (probable). L'e-mail de bienvenue automatique fait environ **3 fois plus de clics** qu'un envoi classique (13,5 % contre 4,6 %[^2]). Et une liste survit à un bannissement : c'est l'actif possédé que la [[Veille réglementaire Meta (contrôles 2026-2027)|veille réglementaire]] recommandait déjà. Arrêter les renvois vers d'autres comptes Instagram privés retire en plus une dette CGU (contournement).

## Ce qui casse, chiffré

| Problème | Chiffre | Niveau |
|---|---|---|
| Formulaire | 83 % de clics aujourd'hui ; une page qui demande l'e-mail fait ≈ 2 % en moyenne, 11 % pour les meilleures | probable |
| Double confirmation | 1,28 % d'inscrits en simple, 0,33 % en double | confirmé |
| Outils d'envoi grand public | beehiiv nomme OnlyFans ; Mailchimp, Klaviyo, MailerLite, SendGrid interdisent l'adulte | confirmé |
| Plaintes pour spam | Gmail : ne jamais atteindre 0,3 % ; Amazon SES met le compte en revue dès 0,1 % | confirmé |
| « Instagram hyper safe » | non prouvé : le 02/10, c'est la présence d'un lien dans le profil qui a déclenché la vague ; un lien « propre » retire aussi la restriction 18+ que Meta applique aux liens adultes, donc fait entrer plus de mineurs dans l'entonnoir | probable |
| Charge d'écriture | ≈ 90 e-mails par mois pour 3 créatrices, 30 à 70 h | spéculatif |

**Point mort** : pour égaler le lien direct, il faut part d'inscrits × part qui confirme × valeur d'un inscrit ≥ 0,83. Même avec une valeur optimiste, il faudrait ≈ 45 % d'inscription en simple confirmation, 64 % en double. **Aucun repère publié n'en approche.**

| Chloé, newsletter à la place des liens | Inscription | Valeur gardée | €/mois |
|---|---|---|---|
| Pessimiste | 5 % | 0,7 % | ≈ 29 |
| Réaliste | 12 % | 6,8 % | ≈ 277 |
| Optimiste | 25 % | 47,7 % | ≈ 1 954 |
| Lien direct | — | 100 % | ≈ 4 100 |

Côté clippeurs (payés 0,041 € la visite), la marge par visite passe de −0,011 € aujourd'hui à −0,039 € en réaliste : la newsletter seule aggrave le problème identifié au [[Journal de coaching]] du 01/10. Le bloc facultatif seul rapporterait ≈ +30 à +230 €/mois (spéculatif) : **une assurance et une source de données, pas une source de cash**.

## La conception retenue pour le test

- **Page A (compte principal de Chloé)** : boutons OF/MYM en tête, avertissement 18+, bloc newsletter en dessous. Jamais d'inscription obligatoire pour voir les liens — un consentement couplé à l'accès rend toute la base contestable (RGPD art. 7.4).
- **Page B (comptes de clippeurs de Chloé, tirés au hasard)** : newsletter en tête, avec un lien visible « Accès direct (18+) ». Sans lui, risque de « redirection trompeuse » au sens de la politique anti-spam de Meta (probable).
- **Envoi** : Sendy sur un serveur dans l'UE + Amazon SES région UE, activité déclarée honnêtement (0,10 $ les 1 000 e-mails[^3]) ; plan B prêt avant lancement : YNOT Mail, qui « n'interdit pas le contenu adulte »[^4].
- **Séquence** : confirmation neutre sans lien OF/MYM → bienvenue immédiate avec les liens → **3 envois par semaine à 19 h, pas 7** → un seul appel à l'action par e-mail (l'entrée gratuite ; sur MYM, 96 % du CA vient du chat et des médias, cf. [[Stratégie trafic interne MYM]]).
- **Âge** : âge minimum 18 ans réglé sur les comptes Instagram du test, case 18+ non pré-cochée et année de naissance au formulaire, refus sous 18 ans.
- **Suivi par clippeur** : le lien d'inscription porte la source (`?src=c042`), qui remplit deux champs cachés (son lien OF et son lien MYM) repris dans chaque e-mail. MYM attribue la vente au dernier lien cliqué dans l'heure, plafond 100 liens actifs[^5] : ça tient pour ~50 clippeurs. Paie inchangée pendant le test.

## Obligations légales et flags

- **Mineurs, ligne rouge absolue** : zéro nu, zéro texte sexuel, zéro promotion de customs. La case « j'ai 18 ans » ne protège pas : art. 227-24 du Code pénal, 3 ans et 75 000 €[^6].
- **RGPD** : il s'applique malgré la société à Dubaï (art. 3.2). Une liste de fans d'une créatrice adulte révèle probablement la vie sexuelle (art. 9) : consentement explicite, représentant dans l'UE, registre, analyse d'impact. Détail du cadre dans [[Risques légaux et éthiques de l'OFM]].
- **Prospection** : consentement préalable et expéditeur identifié (art. L34-5 CPCE) ; désinscription appliquée immédiatement, sinon délit (art. 226-18-1 du Code pénal). Le suivi individuel des ouvertures et clics demande un consentement séparé (recommandation CNIL du 12/03/2026).
- **Signature** : « L'équipe de [nom de scène] ». Faire croire que la créatrice écrit elle-même = pratique commerciale trompeuse (art. L132-2, jusqu'à 5 ans et 750 000 € en ligne).
- **Article 25** : le texte de la commission vise l'aide apportée « par courrier électronique ». Vote solennel le 13/10 ; une newsletter crée une trace écrite quotidienne — **c'est l'avocat qui tranche**, avec Maxence.
- **Interdit** : outil d'envoi grand public, rotation de domaines, se servir de la liste pour pousser les fans vers un nouveau compte après un ban.

## Le test (si GO après l'avocat)

Lancement vers le **20/10**, Chloé seule ; Sarah et Sophie ne bougent pas. Indicateurs : € par visite lien par lien, inscrits confirmés, clics OF/MYM, passages à l'orange par page, plaintes. **Arrêt immédiat** si plaintes ≥ 0,08 %, signal de mineur non traité, compte d'envoi fermé, ou clics de la page A en baisse de plus d'un point. Bascule de la page B en lien de secours seulement si elle rapporte ≥ 60 % des € par visite de la page A **et** passe moins souvent à l'orange (lisible avec ≈ 36 comptes par page).

**Prédictions (02/10, revue le 20/11)** : le bloc de la page A recueille 2 à 6 % d'inscrits confirmés (70 %) ; la page B rapporte moins de 60 % des € par visite de la page A (70 %).

## Prochaines actions

1. Ne rien changer à la destination des liens : page honnête, revue des canaris le 12/10, liens MYM par clippeur avant le 15/10.
2. Ajouter la newsletter à la question posée à l'avocat pénaliste (avec Maxence) + demander un avis RGPD.
3. Demande d'accès en production à Amazon SES et demande écrite à YNOT Mail.
4. Accord écrit de Chloé ; rédacteur désigné (Loris, via l'avenant du 31/10, sans accès à la liste) ; accord écrit de Maxence si le coût dépasse 2 000 AED/mois.

La logique générale du tunnel (chaque étape ajoutée fait fuir des gens) est dans [[Tunnel de conversion]] ; la valeur d'un fan sur la durée dans [[Rétention et LTV]].

## Sources

[^1]: Eurostat, usage de l'e-mail par les 16-74 ans (tin00094) — https://ec.europa.eu/eurostat/databrowser/product/view/tin00094
[^2]: beehiiv, *2025 State of Email Newsletters* — https://www.beehiiv.com/blog/2025-state-of-email-newsletters-by-beehiiv
[^3]: Amazon SES, tarifs — https://aws.amazon.com/ses/pricing/ ; application des règles de plainte — https://docs.aws.amazon.com/ses/latest/dg/faqs-enforcement.html
[^4]: YNOT Mail, FAQ — https://www.ynotmail.com/faq/
[^5]: MYM, *Liens de suivi* — https://support.mym.fans/hc/fr/articles/25453926981532-Liens-de-suivi
[^6]: Légifrance, art. 227-24 du Code pénal — https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000044394218 ; art. L34-5 CPCE — https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042155961/ ; art. L132-2 Code de la consommation — https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000049532070
