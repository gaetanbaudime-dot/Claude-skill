"""Aide concise des commandes existantes ; aucun droit ni dispatch d'action ici."""

ADMIN = """🧰 **Aide admin · essentiel**

**Lire**
• `!pipeline` · `!tableau` — avancement.
• `!fiche @membre` · `!memoire @membre` — dossier, en salon privé.
• `!audit` · `!secu` — accès et sécurité (sans appliquer).
• `!pilotage` — ton app, en MP.
• `!tl liste` — équipes.

**Agir — vérifier le résultat avant la suite**
• `!creatrice @membre Chloé` — affecter et lancer le parcours.
• `!onboarding @membre` — reprendre sa créatrice affectée ; peut réserver des accès et renvoyer une étape.
• `!pseudo @membre 1 vrai_pseudo` — renommer un compte, pas permuter les comptes.
• `!dashboard` — réécrire le suivi sans scan ; `!dashboard scan` lance un scan payant.
• `!code [adresse]` — connexion, création et confirmation e-mail ; accès contrôlé, réponse privée.
• `!reprise @membre Sarah` — un ancien clipper revient : historique de comptes repris (3 au total, jamais remis à zéro), puis parcours relancé.

**Propriétaire du serveur + admin, résultat en MP**
• `!organisation UID` — diagnostic rôles/TL/catégorie ; ajouter `appliquer` pour réparer, sans comptes.
• Lecture : `!diagnostic-dossier UID Chloé UID_TL` (Sarah aussi).
• Écriture : `!rapprocher-zero UID confirme-zero` — après diagnostic, seulement dossier autorisé et historique zéro vérifié.
• `!audit-discussions export nouveau` — démarrer UNE fois une nouvelle archive.
• `!audit-discussions export` — reprendre sa collecte.
• `!audit-discussions export livrer` — recevoir la suite des fichiers, sans recollecter.

**Bien saisir**
Pour `@membre`, tape @ et sélectionne la personne dans la liste Discord. Un prénom ou @Prénom tapé en texte ne suffit pas. UID = identifiant numérique.
Une commande par message, puis attends la réponse. Les rafales ne routent pas tout ; une erreur n'arrête pas les suivantes."""

MANAGER = """🧰 **Aide manager · essentiel**

**Lire**
• `!pipeline` · `!tableau` — avancement.
• `!fiche @membre` · `!memoire @membre` — dossier, en salon privé.
• `!comptes-libres Chloé` — stock disponible.
• `!clics` — relevé des visites.

**Agir — vérifier le résultat avant la suite**
• `!creatrice @membre Chloé` — affecter et lancer le parcours.
• `!onboarding @membre` — reprendre sa créatrice affectée ; peut réserver des accès et renvoyer une étape.
• `!pseudo @membre 1 vrai_pseudo` — renommer un compte, pas permuter les comptes.
• `!etape @membre` — renvoyer l'étape ; avec un numéro, la forcer.
• `!note @membre texte` — ajouter une note.
• `!paie-clics 5|20` — préparer ou recompter la liste de paie.
• `!dashboard` — réécrire le suivi sans scan ; `!dashboard scan` lance un scan payant.
• `!code [adresse]` — connexion, création et confirmation e-mail ; accès contrôlé, réponse privée.

Pour `@membre`, tape @ et sélectionne la personne dans la liste Discord. Un prénom ou @Prénom tapé en texte ne suffit pas.
Une commande par message, puis attends la réponse. Les rafales ne routent pas tout ; une erreur n'arrête pas les suivantes."""


def aide_staff(est_admin):
    return ADMIN if est_admin else MANAGER
