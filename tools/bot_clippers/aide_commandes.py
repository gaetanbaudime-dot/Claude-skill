"""Aide concise des commandes existantes ; aucun droit ni dispatch d'action ici."""

ADMIN = """🧰 **Aide admin**

**Voir**

• `!roster` — qui est actif, par créatrice.
• `!funnel` — leads, qualifiés, actifs par jour (`!funnel 30` pour un mois).
• `!pipeline` — candidatures et arrivées.
• `!tl liste` — équipes et primes.
• `!fiche Prénom` — le dossier d'un clipper.

**Agir**

• `!creatrice Prénom Chloé` — lui donner sa créatrice et lancer son parcours.
• `!remettre-compte1 Prénom` — renvoyer son compte 1 avec e-mail et mot de passe.
• `!reprise Prénom Sarah` — un ancien revient (ses 3 comptes à vie sont gardés).
• `!sortie Prénom raison` — le sortir et l'expulser (`garder` pour le laisser sur le serveur).
• `!tl Sarah Prénom` — nommer le TL d'une créatrice.

**Bien saisir**

Un prénom suffit quand un seul membre le porte ; sinon tape @ et choisis dans la liste. Une commande par message.

Le reste (diagnostics, exports, codes) : `!aide tout`."""

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


ADMIN_TOUT = """🧰 **Aide admin · tout le reste**

• `!audit` · `!secu` — qui voit quoi, sécurité.
• `!memoire @membre` · `!pilotage` — mémoire du bot, ton app.
• `!onboarding @membre` — reprendre son onboarding.
• `!pseudo @membre 1 vrai_pseudo` — renommer un compte.
• `!dashboard` — réécrire le suivi (`!dashboard scan` = scan payant).
• `!code [adresse]` — codes e-mail, réponse privée.
• `!sortie-auto` — qui serait sorti pour inactivité.
• `!organisation Prénom` — diagnostic rôles et salon (`appliquer` pour réparer).
• `!diagnostic-dossier UID Chloé UID_TL` — diagnostic d'un dossier.
• `!rapprocher-zero UID confirme-zero` — historique zéro, après diagnostic seulement.
• `!audit-discussions export` — archive des discussions."""


def aide_staff(est_admin, tout=False):
    if est_admin:
        return ADMIN_TOUT if tout else ADMIN
    return MANAGER
