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

**v3.1 (03/10/2026, Gaëtan : « rétablir ce bot afin que Maxence voie tous les jours les LTV »)** : dernier rapport reçu le
29/09, la veille du collage de la v3, alors que le classeur est saisi jusqu'au 02/10. Cause probable : l'ancien
déclencheur appelle une fonction de l'ancien code qui n'existe plus — **confirmé le 03/10 par `diagnostic`** : seul
déclencheur en place, `envoyerRapportQuotidien` (orphelin) ; propriétés et saisie en ordre, rapport envoyé. La v3.1 garde la présentation de la v3 et ajoute :
`installerDeclencheur` retire les déclencheurs orphelins ; le jeton et le canal de l'ancien script sont reconnus même sous
un autre nom ; un refus de Telegram fait échouer l'exécution au lieu de passer en silence ; une erreur de calcul envoie
une alerte dans le canal ; le pied liste les créatrices dont la veille n'est pas saisie ; lecture dès la ligne 3
(« 1 juillet »). Remise en route : coller le code → exécuter `diagnostic` (journal + envoi test) → exécuter
`installerDeclencheur`.

**Commission & profit (03/10/2026, Gaëtan : « commission d'agence sur le CA : Chloé 40 %, Sarah, Sophie, Maddie, Clara
50 %, Jade 60 % ; ensuite tu retires 15 % de CA de dépenses et on a notre profit précisément »)** : la marge unique de 30 %
est supprimée. Profit = CA × (commission − 15 % de frais + chatting). `creerOngletCommission` (à lancer une fois) crée
l'onglet « Commission & profit » : taux en cases jaunes, puis 30 derniers jours (CA, commission, frais, profit, profit
par nouveau sub), hier, commission par mois et profit par mois. Formules écrites par le script en syntaxe anglaise, ce
qu'exige Apps Script : Google Sheets les affiche en français. Le rapport Telegram lit ses taux dans cet onglet (repli : les
constantes `COMMISSIONS` et `FRAIS`) et affiche en pied la commission et le profit d'hier, plus le profit sur 30 jours.

**Seuils 800 subs / 15 € (03/10/2026)** : sur les lignes OF et MYM du rapport, 🔴 devant les subs si moins de 800 sur 30
jours ; sinon 🔴 devant la LTV sous 8 €, 🟡 entre 8 et 15 € ; sinon 🟢 devant la plateforme. Réglables : `SEUIL_SUBS`,
`SEUIL_LTV_JAUNE`, `SEUIL_LTV`. Pas de légende dans le rapport (la règle est épinglée dans le groupe).

**Correctif du 03/10 (premier essai : `#ERROR!` dans tout l'onglet, mois décalés d'un jour)** : le classeur, réglé en
français, refusait les formules à virgules écrites par le script. `creerOngletCommission` teste maintenant le séparateur
accepté (`,` ou `;`) avant d'écrire, écrit les mois en `DATE()` (plus de décalage de fuseau), reconstruit l'onglet s'il
existe en gardant les taux saisis, et écrit dans le journal le nombre de cellules en erreur. `miseEnPlace` fait tout en
un clic : déclencheur de 8 h (orphelins retirés), onglet, rapport de test.

**Correctif du 03/10 (« ça dit hier 2 octobre et ça affiche les stats du 1 octobre »)** : le projet Apps Script et le
classeur n'avaient pas le même fuseau ; une date du classeur tombait la veille côté script, donc « Hier » et les 30 jours
étaient décalés d'un jour. Les jours se comparent maintenant au calendrier (lignes dans le fuseau du classeur, aujourd'hui
dans celui du script) ; `diagnostic` affiche les deux fuseaux. Régler le classeur sur Dubaï (Fichier → Paramètres) pour que
`AUJOURDHUI()` de l'onglet bascule à minuit Dubaï. Onglet Commission & profit : 30 jours complets, du J-30 à hier, comme le
rapport. « Profit 30 j » sans la commission.

**Envoi quotidien fiable et Synthèse alignée (03/10/2026)** : le projet Apps Script est à l'heure de Paris, le classeur à
celle de Dubaï ; l'ancien « 8 h » partait à 10 h Dubaï, parfois avant la saisie de la veille. Désormais un déclencheur
horaire appelle `envoiQuotidien`, qui envoie une seule fois par jour (propriété `DERNIER_ENVOI`) : dès 8 h Dubaï si la veille
est saisie pour toutes les créatrices actives, sinon il attend jusqu'à 12 h (`HEURE_LIMITE`) et envoie avec « ⚠️ Hier non
saisi ». Un envoi raté est retenté l'heure suivante. Heures et jours au fuseau du classeur. `alignerSynthese` réécrit le bloc
30 jours de la Synthèse (B, C, F, G, I, J des lignes 5 à 10) sur 30 jours complets jusqu'à hier, au séparateur du classeur.
`miseEnPlace` enchaîne déclencheur, Synthèse, onglet Commission & profit et rapport de test. Tout envoi réussi, manuel compris,
marque le jour : jamais deux rapports le même jour.

**Synthèse par créatrice, 30 et 90 jours (03/10/2026)** : `alignerSynthese` reconstruit le bloc du haut de la Synthèse —
pour chaque créatrice, trois lignes OF / MYM / Total (subs, CA, LTV sur 30 jours, une colonne vide, puis sur 90 jours), une
ligne vide, rangées par CA 30 jours décroissant au moment du lancement (comme le rapport), puis le groupe AGENCE. Fenêtres
complètes jusqu'à hier. Les blocs par mois sont décalés vers le bas (lignes insérées), leurs formules suivent. Relancer la
fonction refait le bloc à l'identique et le re-trie. Vérifié avant : aucune formule, aucun graphique ni aucune règle du
classeur ne lisait l'ancien bloc (colonne M comprise).

**Lisibilité de la Synthèse (03/10/2026, « un peu illisible »)** : prénom fusionné sur ses trois lignes, double en-tête
sombre « 30 DERNIERS JOURS » / « 90 DERNIERS JOURS », CA sans centimes, zéros affichés « — », trait sous chaque Total,
groupe AGENCE grisé ; mise en forme conditionnelle en fond clair, texte noir : subs sous 800 en rouge, LTV rouge < 8 €,
jaune 8-15 €, vert ≥ 15 €.
Correctif : la colonne F (espace entre 30 et 90 jours) avait été rétrécie, ce qui écrasait « novembre » dans les blocs par
mois ; elle est remise à 110 px.

**Seuils de la Synthèse (03/10/2026, « pour les 90 j, multiplie par 3 les subs »)** : même règle que le rapport sur chaque
période — subs sous le seuil en rouge ; au-dessus, LTV rouge < 8 €, jaune 8-15 €, vert ≥ 15 € ; pas de couleur de LTV sous
le seuil. Seuil de subs : 800 sur 30 jours, 2 400 sur 90 jours. Formules de mise en forme sans séparateur (`(a)*(b)`),
indépendantes de la langue du classeur.
