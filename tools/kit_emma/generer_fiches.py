# Génère les fiches A4 du Kit Emma (PDF) dans second-brain/96-Opérations LTP/Kit Emma/
# Usage : python3 tools/kit_emma/generer_fiches.py
# Sources de vérité : Scorecard Emma, SOP Machine à contenu, Checklist tournage,
# Méthode de délégation Emma (96-Opérations LTP/). Une fiche = une page A4.

from weasyprint import HTML
import os

SORTIE = os.path.join(os.path.dirname(__file__), "..", "..",
                      "second-brain", "96-Opérations LTP", "Kit Emma")

CSS = """
@page {
  size: A4; margin: 12mm 14mm 14mm 14mm;
  @bottom-center { content: "Kit Emma · LTP · juillet 2026 · v1"; font-size: 7.5pt; color: #8a8a8a; }
}
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.6pt; color: #1c1c1c; line-height: 1.42; margin: 0; }
.bandeau { background: #17324f; color: #fff; padding: 7px 12px; border-radius: 6px;
  display: flex; justify-content: space-between; align-items: baseline; }
.bandeau .num { font-size: 8.5pt; letter-spacing: 1px; text-transform: uppercase; color: #b8cbe0; }
.bandeau .titre { font-size: 15pt; font-weight: bold; }
.sous { color: #4a4a4a; font-size: 9pt; margin: 5px 2px 10px; }
h2 { font-size: 10.5pt; color: #17324f; margin: 10px 0 4px; text-transform: uppercase; letter-spacing: .5px;
  border-bottom: 1.5px solid #17324f; padding-bottom: 2px; }
.box { background: #f1f4f8; border-left: 3.5px solid #17324f; padding: 7px 10px; border-radius: 4px; margin: 6px 0; }
.rouge { background: #fdf0ef; border-left-color: #a33025; }
.rouge h2, .rouge b.t { color: #a33025; }
ul.check { list-style: none; padding-left: 2px; margin: 4px 0; }
ul.check li { padding-left: 20px; text-indent: -20px; margin: 2.5px 0; }
ul.check li::before { content: "\\2610\\00a0\\00a0"; font-size: 11pt; color: #17324f; }
ul.puces { margin: 4px 0 4px 16px; padding: 0; }
ul.puces li { margin: 2.5px 0; }
table { border-collapse: collapse; width: 100%; margin: 5px 0; }
th { background: #17324f; color: #fff; font-size: 8.3pt; padding: 4px 6px; text-align: left; }
td { border: 1px solid #c9d2dc; padding: 4px 6px; font-size: 8.8pt; vertical-align: top; }
.ligne { border-bottom: 1px dotted #9aa7b5; height: 15px; }
.deux { display: flex; gap: 10px; } .deux > div { flex: 1; }
b.t { color: #17324f; }
.petit { font-size: 8.3pt; color: #555; }
"""

def bandeau(num, titre):
    return f'<div class="bandeau"><span class="titre">{titre}</span><span class="num">{num}</span></div>'

FICHES = {}

FICHES["Fiche 1 - Ta mission (Emma).pdf"] = bandeau("Fiche 1 / 4", "Ta mission") + """
<p class="sous">Le rôle en une page : ce qu'on attend, ce que tu décides, ce qui ne se négocie pas.</p>
<div class="box"><b class="t">Ta mission :</b> faire que chaque créatrice prioritaire dépose un <b>batch de contenu
frais chaque semaine</b>. Pourquoi : plus de contenu → plus de clips → plus d'abonnés → plus de revenus
pour les créatrices (et pour l'agence). Tu es la personne qui fait tourner cette chaîne.</div>
<h2>Tes 4 résultats (on se juge là-dessus, pas sur les heures)</h2>
<ul class="check">
<li>Batch complet (~40-50 clips) déposé <b>9 semaines sur 10</b> par créatrice prioritaire</li>
<li><b>Zéro semaine à vide</b> sur Maddy, Sarah et Jade</li>
<li>Délai entre ton brief du lundi et le dépôt Drive : <b>moins de 4 jours</b></li>
<li>Tableau de contenu <b>rempli chaque dimanche soir</b> (15 min)</li>
</ul>
<div class="deux">
<div><h2>Tu décides SEULE</h2>
<ul class="puces"><li>Le choix des trends et le contenu des briefs</li>
<li>Tes relances : ton, timing, canal</li>
<li>L'organisation de ta semaine</li>
<li>Les ajustements du process (note-les)</li></ul></div>
<div><h2>Tu ne décides JAMAIS seule</h2>
<ul class="puces"><li>Un doute « safe plateforme » → Gaëtan tranche</li>
<li>Ajouter / retirer une créatrice du périmètre</li>
<li>Tout ce qui touche à l'argent ou aux contrats</li>
<li>Une créatrice qui décroche durablement</li></ul></div>
</div>
<h2>La règle 1-3-1 (comment on remonte un problème)</h2>
<div class="box">Jamais un problème « nu ». Toujours : <b>1</b> problème posé en deux phrases ·
<b>3</b> solutions possibles · <b>1</b> recommandation (la tienne). Par écrit.</div>
<h2 style="color:#a33025;border-color:#a33025;">Le non-négociable</h2>
<div class="box rouge"><b class="t">100 % safe plateforme.</b> Aucune nudité, aucune sollicitation, aucune référence
explicite à OF/MYM dans le contenu Instagram/Facebook. C'est ce qui garde les comptes en vie.
<b>Dans le doute → tu demandes AVANT.</b></div>
<p class="petit"><b>Droit à l'erreur :</b> une trend qui flop ou un batch imparfait = un coût d'apprentissage, pas une faute.
Mieux vaut rater petit et vite que d'attendre une validation pour tout.</p>
"""

FICHES["Fiche 2 - Ta semaine type (Emma).pdf"] = bandeau("Fiche 2 / 4", "Ta semaine type") + """
<p class="sous">Le rituel : les cases se font par défaut, pas « quand on y pense ».</p>
<div class="box"><b class="t">Le principe :</b> 1 session de tournage batch par créatrice et par semaine =
<b>5 tenues × 10 trends = ~50 clips</b>. Toute ta semaine sert à faire arriver ce batch.</div>
<h2>Lundi — lancement (ton gros bloc)</h2>
<ul class="check">
<li>Curer <b>20-30 trends US</b> reproductibles en France et safe plateforme</li>
<li>Taguer par créatrice : <b>10 trends chacune</b> (une trend peut servir plusieurs personas)</li>
<li>Remplir le <b>dossier Drive de la semaine</b> : lien + capture + note courte « ce qu'elle reproduit »</li>
<li>Envoyer le <b>brief</b> à chaque créatrice + <b>confirmer son créneau de tournage</b></li>
</ul>
<h2>Mercredi — relance planning</h2>
<ul class="check"><li>Chacune a planifié ou commencé ? Si non : identifier le blocage
(agenda ? brief pas clair ? motivation ?) et <b>le lever aujourd'hui</b></li></ul>
<h2>Vendredi — relance livraison</h2>
<ul class="check"><li>Les rushs sont déposés sur le Drive ? Si non : diagnostiquer —
<b>technique</b> (réglages, lumière) / <b>créatif</b> (ne sait pas quoi filmer) / <b>motivation</b> —
et résoudre concrètement, pas juste relancer</li></ul>
<h2>Week-end — rattrapage</h2>
<ul class="check"><li>Retardataires : relance douce + <b>aide concrète</b> (réexpliquer une trend, décaler le créneau).
Objectif : zéro prioritaire à vide</li></ul>
<h2>Dimanche soir — reporting (15 min)</h2>
<table>
<tr><th>Créatrice</th><th>Rushs déposés</th><th>Batch complet ?</th><th>Blocage</th><th>Action S+1</th></tr>
<tr><td><b>Maddy</b> (P1)</td><td></td><td></td><td></td><td></td></tr>
<tr><td><b>Sarah</b> (P1)</td><td></td><td></td><td></td><td></td></tr>
<tr><td><b>Jade</b> (P1)</td><td></td><td></td><td></td><td></td></tr>
<tr><td><b>Sophie</b> (suivi léger)</td><td></td><td></td><td></td><td></td></tr>
<tr><td><b>Chloé</b> (flux YouTube)</td><td></td><td></td><td></td><td></td></tr>
</table>
<div class="box"><b class="t">La boucle ×2/×3 :</b> ① la <b>relation</b> (une créatrice suivie de près produit 2-3× plus) ·
② la <b>méthode batch</b> (une session structurée sort 50 clips, trois sessions improvisées en sortent 15) ·
③ l'<b>itération</b> (note ce qui a marché, ajuste le brief de la semaine suivante).</div>
"""

FICHES["Fiche 3 - Checklist tournage batch (creatrice).pdf"] = bandeau("Fiche 3 / 4", "Checklist tournage batch") + """
<p class="sous"><b>À transférer à la créatrice</b> avec son dossier Drive de la semaine (copier-coller ou PDF).
Objectif : <b>50 clips en une session</b>.</p>
<h2>1. Réglages téléphone (à vérifier à chaque session)</h2>
<ul class="check">
<li>Caméra en <b>4K, 60 fps</b> (Réglages → Appareil photo → Enregistrement vidéo)</li>
<li><b>Caméra arrière</b> — jamais la caméra selfie (qualité 2× meilleure)</li>
<li><b>Objectif nettoyé</b> (un coup de chiffon change tout)</li>
<li><b>Lumière face à toi</b> : fenêtre en journée ou ring light — jamais dans le dos</li>
<li>Batterie chargée + stockage suffisant</li>
</ul>
<h2>2. Avant de filmer</h2>
<ul class="check">
<li><b>5 tenues</b> préparées et accessibles</li>
<li>Les <b>10 trends de la semaine</b> ouvertes sur un 2e écran (envoyées par Emma, dossier Drive)</li>
<li>Fond propre / lieu rangé</li>
</ul>
<h2>3. Le tournage : la méthode matrice</h2>
<div class="box">Tu filmes <b>toutes les trends dans une tenue, puis tu changes de tenue</b> —
jamais l'inverse (changer de tenue à chaque trend fait perdre un temps fou).</div>
<ul class="check">
<li><b>Tenue 1</b> → filme les 10 trends</li>
<li><b>Tenue 2</b> → filme les 10 trends</li>
<li><b>Tenue 3</b> → filme les 10 trends</li>
<li><b>Tenue 4</b> → filme les 10 trends</li>
<li><b>Tenue 5</b> → filme les 10 trends &nbsp;&nbsp;→&nbsp; <b>= 50 clips prêts, en une session</b></li>
</ul>
<h2>4. Après le tournage</h2>
<ul class="check">
<li><b>Dépose tout</b> dans ton dossier Drive de la semaine</li>
<li>Nomme simplement : <b>Tenue[X]_Trend[Y]</b></li>
<li><b>Préviens Emma</b> que c'est déposé</li>
</ul>
<div class="box rouge"><b class="t">Règle d'or :</b> tout le contenu reste <b>100 % safe</b> pour Instagram/Facebook —
pas de nudité, pas de sollicitation, pas de référence explicite. Doute sur une trend → <b>demande à Emma AVANT de filmer</b>.</div>
<p class="petit"><b>Pourquoi ce système :</b> plus tu produis, plus on peut te booster, plus tu gagnes d'abonnés et d'argent.
Une session batch par semaine = des semaines de contenu pour te faire grandir.</p>
"""

FICHES["Fiche 4 - Quand ca coince (Emma).pdf"] = bandeau("Fiche 4 / 4", "Quand ça coince") + """
<p class="sous">Les 5 pannes classiques : ce que tu règles seule, et quand tu escalades (toujours en 1-3-1).</p>
<table>
<tr><th style="width:26%">La panne</th><th style="width:44%">Ce que tu fais seule</th><th style="width:30%">Tu escalades si…</th></tr>
<tr><td><b>1. La créatrice ne répond pas</b></td>
<td>Relance douce à J+1 sur un autre canal ; propose un créneau précis plutôt qu'un « quand tu peux »</td>
<td>Silence total <b>&gt; 5 jours</b></td></tr>
<tr><td><b>2. Batch pas déposé / plus de rushs</b></td>
<td>Diagnostique : technique / créatif / motivation. Aide concrète : réexpliquer une trend, refaire un réglage, décaler le créneau</td>
<td><b>2 semaines à vide</b> sur une prioritaire</td></tr>
<tr><td><b>3. Trend qui flop, doute créatif</b></td>
<td>Coût d'apprentissage, pas une faute : remplace la trend, note-le au tableau, ajuste le brief suivant</td>
<td>(pas d'escalade)</td></tr>
<tr><td><b>4. Doute « safe plateforme »</b></td>
<td><b>Rien — tu ne tranches jamais seule.</b></td>
<td><b>Immédiatement</b> : capture/lien + ta question</td></tr>
<tr><td><b>5. Conflit, démotivation profonde</b></td>
<td>Écoute, ne promets rien, note les faits</td>
<td>Dès que c'est plus qu'un coup de mou (avec le contexte)</td></tr>
</table>
<h2>Le format d'escalade (toujours le même)</h2>
<div class="box"><b class="t">1</b> problème posé en deux phrases · <b class="t">3</b> options possibles ·
<b class="t">1</b> recommandation (la tienne). <b>Par écrit</b> — pas d'appel surprise.
<br/><span class="petit">Exemple : « Maddy n'a rien déposé depuis 10 jours et ne confirme pas son créneau (1).
Options : je passe chez elle filmer ensemble / on saute une semaine et je re-brief lundi / Gaëtan l'appelle (3).
Je recommande la session ensemble jeudi, elle produit toujours mieux accompagnée (1). »</span></div>
<h2>Pendant l'absence de Gaëtan (21 juillet → 21 septembre)</h2>
<ul class="puces">
<li>Le canal par défaut = <b>le tableau du dimanche soir</b> — il est lu chaque lundi matin.</li>
<li>L'escalade écrite = pour ce qui ne peut <b>pas</b> attendre le lundi.</li>
<li>Réponse type que tu recevras : « qu'est-ce que tu proposes ? » — c'est normal, c'est la méthode : ta proposition compte.</li>
</ul>
<div class="box"><b class="t">Rappel :</b> Emma à 80 % en autonomie vaut mieux que personne à 100 %.
Tu as le droit de décider, de te tromper petit, et d'ajuster la semaine suivante.</div>
"""

FICHES["Fiche 5 - Profil creatrice (modele).pdf"] = bandeau("Modèle × 5", "Profil créatrice") + """
<p class="sous">Une fiche par créatrice : <b>Chloé · Sophie · Maddy · Sarah · Jade</b>. Le système commun (fiches 1-4)
tient la cadence ; cette fiche tient <b>l'adaptation</b>. À remplir avec Gaëtan, puis mise à jour par Emma chaque mois.</p>
<table>
<tr><td style="width:33%"><b>Créatrice :</b></td><td style="width:34%"><b>Plateformes :</b></td><td><b>Priorité contenu :</b> P1 ☐ &nbsp; P2 ☐</td></tr>
</table>
<h2>Sa persona en 1 phrase</h2>
<div class="ligne"></div><div class="ligne"></div>
<h2>Les types de trends qui marchent pour ELLE</h2>
<div class="ligne"></div><div class="ligne"></div><div class="ligne"></div><div class="ligne"></div>
<h2>Ses limites — ce qu'elle ne fait PAS</h2>
<div class="ligne"></div><div class="ligne"></div><div class="ligne"></div>
<div class="deux">
<div><h2>Tournage</h2>
<ul class="puces">
<li>Créneau habituel : ______________________</li>
<li>Durée de session : ______________________</li>
<li>Matériel (tél, ring light, lieu) : __________</li>
<li>Niveau technique : débutante ☐ · correcte ☐ · autonome ☐</li>
</ul></div>
<div><h2>Relation</h2>
<ul class="puces">
<li>Canal de contact : ______________________</li>
<li>Ton qui marche (encourager, cadrer…) : __________</li>
<li>Fréquence de relance idéale : ____________</li>
<li>Ce qui la motive : ______________________</li>
</ul></div>
</div>
<h2>Particularités / garde-fous</h2>
<p class="petit">Ex. : refuse TikTok · a besoin de félicitations · matière via YouTube plutôt que tournage batch · deux comptes à alimenter…</p>
<div class="ligne"></div><div class="ligne"></div><div class="ligne"></div>
<h2>Ce qui a le mieux marché ce mois-ci (à jour le : ______ )</h2>
<div class="ligne"></div><div class="ligne"></div><div class="ligne"></div>
"""

# ---------------------------------------------------------------------------
# Fiches par créatrice (specs dictées par Gaëtan le 13/07/2026 + données 30 j)
# ---------------------------------------------------------------------------

def fiche_crea(nom, priorite, apercu, manager, trends, limites, chiffres, a_completer=True):
    compl = ('<h2>À compléter avec Gaëtan / au fil des semaines</h2>'
             '<ul class="puces"><li>Créneau de tournage habituel : ______________ · durée : ______</li>'
             '<li>Matériel (tél, ring light, lieu) : ____________________</li>'
             '<li>Ce qui a le mieux marché ce mois-ci : ____________________</li></ul>') if a_completer else ''
    return bandeau("Profil créatrice", nom) + f"""
<p class="sous">{apercu} &nbsp;·&nbsp; <b>Priorité contenu : {priorite}</b></p>
<h2>Comment la manager (le levier n°1)</h2>
<div class="box">{manager}</div>
<h2>Quoi lui envoyer (ses trends)</h2>
{trends}
<h2>Ses limites — à respecter sans exception</h2>
{limites}
<h2>Ce que disent les chiffres (13/07/2026)</h2>
<p class="petit">{chiffres}</p>
{compl}
"""

FICHES["Profil - Sophie.pdf"] = fiche_crea(
    "Sophie", "P1 — machine en pleine explosion, zéro semaine à vide",
    "Tourne en duo avec son mari. Leur logique : rentabiliser chaque minute.",
    "<b>Sois directive.</b> Pas de brainstorming, pas de « qu'est-ce que tu en penses ? » : tu envoies des "
    "<b>exemples précis</b> et tu dis <b>« fais exactement ça »</b>. Ils tournent énormément de clips très vite "
    "quand la consigne est claire — leur contrainte c'est le temps, pas l'envie. Un brief flou = un batch perdu.",
    '<ul class="puces"><li>Pioche dans la <b>banque d\'idées Reels</b> : les idées déjà repérées pour eux sont bonnes à reprendre</li>'
    '<li>Privilégie ce qui est <b>faisable dans leur quotidien</b> : avec le camion, en course / en déplacement</li>'
    '<li>Toujours joindre l\'exemple vidéo + la consigne en une phrase</li></ul>',
    '<ul class="puces"><li>Ne pas leur demander de créativité libre — ils veulent exécuter vite</li>'
    '<li>Respecter leur organisation de couple (créneaux groupés, batchs XXL)</li></ul>',
    "OF en explosion : <b>+27 % sur 30 j</b> (~9 800 $/30 j, ×11 depuis avril), 85 % du CA en messages. "
    "Sa machine est LA priorité à nourrir : chaque batch se transforme directement en revenus.")

FICHES["Profil - Chloe.pdf"] = fiche_crea(
    "Chloé", "P1 — n°1 toutes plateformes, volume à soutenir",
    "Un seul format, décliné à l'infini — et il est n°1 de l'agence.",
    "Son contenu tourne sur <b>UN format unique : « J'adore les hommes qui font X / Y / Z »</b>. "
    "Ton job n'est pas d'inventer autre chose : c'est de <b>faire tourner les variantes</b> et de t'assurer "
    "qu'elle ne soit jamais à court d'idées <b>faisables chez elle, dans son appartement</b>.",
    '<ul class="puces"><li>Les <b>variantes sont déjà préparées</b> dans la banque d\'idées Reels : par métiers, personnalité, '
    'physique, relations, actions, habitudes, routine, dormir, jouer…</li>'
    '<li>Filtre à appliquer avant d\'envoyer : <b>réalisable en intérieur, seule, sans accessoire compliqué</b></li>'
    '<li>10 variantes par semaine, prêtes à tourner en batch</li></ul>',
    '<ul class="puces"><li>Pas de scénarios extérieurs ou à accessoires : tout doit être tournable dans son appartement</li>'
    '<li>On reste sur SON format — pas d\'expérimentations qui diluent ce qui marche</li></ul>',
    "N°1 toutes plateformes : <b>~13 100 €/30 j</b> (OF 7 429 $ + MYM 6 301 €). ⚠️ Son MYM passe en <b>gratuit le 14/07</b> : "
    "le volume d'abonnés va exploser, le contenu doit suivre — semaine à vide interdite.")

FICHES["Profil - Sarah.pdf"] = fiche_crea(
    "Sarah", "P1 — en pleine accélération, montée en volume",
    "La plus flexible du roster : tout type de contenu passe.",
    "Avec elle, <b>le frein n'est ni la créativité ni les limites : c'est juste l'organisation</b>. "
    "Cadence claire, briefs réguliers, et elle délivre. Relation simple et cool — pas de précautions particulières.",
    '<ul class="puces"><li><b>Reproduis d\'abord ce qui a déjà marché pour elle</b> (ses meilleurs Reels : les repérer et les décliner)</li>'
    '<li>Ensuite, pioche large dans la banque d\'idées Reels — tout est jouable</li>'
    '<li>Bon terrain de test : une trend nouvelle se teste sur elle avant les autres</li></ul>',
    '<ul class="puces"><li>Aucune limite particulière connue — garder le filtre safe plateforme, comme pour toutes</li></ul>',
    "En pleine accélération : abonnés MYM <b>×8 en un mois</b> (~4 900 €/30 j) et son OnlyFans (Lila Doré) vient de "
    "démarrer (42 subs via les liens, les premiers payeurs arrivent). Plus elle a de contenu, plus la fusée monte.")

FICHES["Profil - Maddy.pdf"] = fiche_crea(
    "Maddy", "P1 — moteur n°1 du CA MYM",
    "Son levier n'est pas technique : c'est la CONFIANCE.",
    "<b>Félicite-la explicitement, à chaque livraison.</b> Elle doute d'elle sur tout ce qui touche au marketing — "
    "ton job est de lui dire, avec des mots clairs : <b>« ton contenu nous aide énormément, c'est exactement ce qu'il "
    "nous faut, c'est très bien »</b>. Une Maddy en confiance produit deux fois plus. Ensuite : consignes simples, "
    "pas de sur-réflexion, optimiser son temps.",
    '<ul class="puces"><li>Briefs <b>simples et rassurants</b> : l\'exemple + « tu fais pareil, c\'est parfait »</li>'
    '<li>Éviter tout ce qui la fait douter (formats compliqués, choix multiples ouverts)</li>'
    '<li>Banque d\'idées Reels + ce qui a déjà marché pour elle</li></ul>',
    '<ul class="puces"><li>Jamais de critique sèche sur un clip : toujours « super, et la prochaine fois essaie aussi… »</li>'
    '<li>Ne pas la surcharger : mieux vaut un batch fini qu\'un plan ambitieux abandonné</li></ul>',
    "N°1 du CA MYM sur 30 j : <b>8 098 € (37 % du MYM)</b>, monétisation en explosion (31,77 €/nouvel abonné en juillet). "
    "MYM uniquement pour l'instant — sa production est le moteur du chiffre, sa confiance est le carburant.")

FICHES["Profil - Alice (a confirmer).pdf"] = fiche_crea(
    "Alice", "P2 — lancement en préparation (septembre)",
    "Positionnement : jeune étudiante, ultra soft. (Nom à confirmer avec Gaëtan.)",
    "<b>Accompagne-la pas à pas dans la création</b> : elle a besoin d'exemples et d'un cadre très simple, "
    "pas d'autonomie créative. Trends <b>hyper softs, hyper simples</b>, ambiance « vie d'étudiante » — "
    "l'aider à prendre le rythme avant de penser volume.",
    '<ul class="puces"><li>Trends « étudiante » : quotidien, humour léger, routine, études — le plus simple possible</li>'
    '<li>Toujours envoyer l\'exemple + la consigne pas à pas</li>'
    '<li>Tenues simples uniquement</li></ul>',
    '<ul class="puces"><li><b>Pas de ventre visible · pas de maillot de bain · rien de trop sexy · pas de gestes suggestifs</b></li>'
    '<li>Le positionnement soft EST la stratégie : un clip trop suggestif casse la cohérence du personnage</li></ul>',
    "Lancement à zéro prévu après l'été (les lancements attendent le retour de Gaëtan). "
    "Objectif de la période : constituer sa bibliothèque de contenu et son rythme de tournage, sans pression de chiffre.")

FICHES["Profil - Jade (a completer).pdf"] = fiche_crea(
    "Jade", "P1 cadence — mais diagnostic en cours, pas d'investissement lourd",
    "Grosse base d'abonnés, monétisation faible : le contenu entretient, le diagnostic décidera.",
    "Maintenir la <b>cadence normale</b> (batch hebdo) sans investissement particulier : sa situation est en "
    "diagnostic côté Gaëtan (trafic et monétisation). Ton rôle : que la machine ne s'arrête pas pendant qu'on décide.",
    '<ul class="puces"><li>Ses préférences de contenu : <b>à compléter avec Gaëtan</b> ______________________</li>'
    '<li>En attendant : reproduire ce qui a déjà marché pour elle</li></ul>',
    '<ul class="puces"><li><b>Pas de TikTok</b> — c\'est son choix, on ne pousse pas</li></ul>',
    "La plus grosse base MYM (4 949 abonnés actifs) mais LTV faible (5,33 €/nouveau) et OF en repli "
    "(<b>-40 % sur 30 j</b>). Le sujet n'est pas « plus de volume », c'est « pourquoi ça convertit moins » — "
    "décision chez Gaëtan, cadence chez toi.")

def main():
    os.makedirs(SORTIE, exist_ok=True)
    for nom, corps in FICHES.items():
        html = f"<html><head><style>{CSS}</style></head><body>{corps}</body></html>"
        chemin = os.path.join(SORTIE, nom)
        HTML(string=html).write_pdf(chemin)
        print("OK", nom)

if __name__ == "__main__":
    main()
