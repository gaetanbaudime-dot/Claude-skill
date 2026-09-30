# Data G&M Créatrices v2 — classeur et rapport Telegram

**Pourquoi** (14/09/2026) : la Synthèse mélangeait OF et MYM et gardait sept créatrices ; Gaëtan veut six créatrices
(Chloé, Sophie, Maddy, Sarah, Jade, Clara) et la valeur d'un abonné **OF contre MYM**, dans le sheet et dans le rapport
Telegram quotidien. Le connecteur Drive ne sait pas écrire dans une cellule : le classeur a donc été **reconstruit** en v2
(fichier XLSX généré, à ouvrir avec Google Sheets) plutôt que modifié en place.

**Le classeur v2** : mêmes onglets créatrices (Amanda conservé mais hors Synthèse), mêmes cellules jaunes (B, C, E, F), totaux
H et I calculés, dates jusqu'au 31/12/2026, Synthèse en trois blocs (30 jours OF / MYM / total avec €/abonné et écart ;
CA par mois total, OF et MYM), Notice avec le taux $→€ (GoogleFinance, repli 0,92). Les formules sont écrites en syntaxe
Excel : Google Sheets les convertit à l'import, quelle que soit la locale.

**Le script** `rapport_telegram.gs` remplace le script « Pilotage G&M » (dont le code n'est pas dans ce dépôt) : même style,
avec OF et MYM séparés par créatrice, total OF / MYM, CA et profit de la veille (`MARGE` = 28 %, à ajuster).
Mise en place : Extensions → Apps Script du classeur v2 → coller → propriétés `TELEGRAM_TOKEN` et `TELEGRAM_CHAT_ID`
→ exécuter `installerDeclencheur` une fois.

Le fichier XLSX n'est pas versionné (chiffres de l'agence) : il est généré en session et envoyé à Gaëtan.

**v3 du rapport (30/09/2026, Gaëtan : « une ligne OF, une ligne MYM, une ligne Hier pour chaque créatrice, sauf celles qui
n'ont que MYM ; le €/sub n'est pas mesurable comme ça ; sans perturber le formatage, lisible sur téléphone »)** : même
présentation que le rapport « Pilotage G&M » en place (titre, date d'hier, blocs numérotés et copiables, CA et profit de la
veille), mais chaque créatrice a un titre avec son total sur 30 jours, puis `OF`, `MYM` (30 derniers jours) et `Hier`
(OF + MYM de la veille) en lignes de 28 caractères alignées ; pas de ligne pour une plateforme vide sur 30 jours. Plus de €
par abonné. Marge du profit à 30 % (celle du rapport actuel). Marche avec l'ancien classeur comme avec la v2 (onglet Notice
facultatif, onglets trouvés à l'accent et à la variante près : Maddy/Maddie). Mise en place : remplacer le code du script
du classeur par ce fichier, enregistrer, exécuter `installerDeclencheur` une fois.
