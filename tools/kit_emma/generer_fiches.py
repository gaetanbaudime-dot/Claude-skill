# Génère les fiches A4 du Kit Emma (PDF) dans second-brain/96-Opérations LTP/Kit Emma/
# Usage : python3 tools/kit_emma/generer_fiches.py
# Sources de vérité : Scorecard Emma, SOP Machine à contenu, Checklist tournage,
# Méthode de délégation Emma (96-Opérations LTP/).
# v2 (18/07/2026, brief dicté par Gaëtan) : ton chaleureux et encourageant, aération,
# zéro anglicisme (batch → lot / séance), cadence 2 lots complets par mois,
# ordre de priorité Maddy → Chloé → Sophie → Sarah → Jade, point du dimanche en
# Google Form, autonomie élargie (Emma décide seule de tout sauf le safe plateforme),
# aucune mention d'absence. Profils créatrices = version provisoire, à ajuster
# avec Gaëtan après le premier call.

from weasyprint import HTML
import os

SORTIE = os.path.join(os.path.dirname(__file__), "..", "..",
                      "second-brain", "96-Opérations LTP", "Kit Emma")

CSS = """
@page {
  size: A4; margin: 12mm 14mm 14mm 14mm;
  @bottom-center { content: "Kit Emma · LTP · juillet 2026 · v2"; font-size: 7.5pt; color: #8a8a8a; }
}
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.6pt; color: #1c1c1c; line-height: 1.46; margin: 0; }
.bandeau { background: #17324f; color: #fff; padding: 7px 12px; border-radius: 6px;
  display: flex; justify-content: space-between; align-items: baseline; }
.bandeau .num { font-size: 8.5pt; letter-spacing: 1px; text-transform: uppercase; color: #b8cbe0; }
.bandeau .titre { font-size: 15pt; font-weight: bold; }
.sous { color: #4a4a4a; font-size: 9.1pt; margin: 6px 2px 10px; }
h2 { font-size: 10.3pt; color: #17324f; margin: 12px 0 5px; text-transform: uppercase; letter-spacing: .5px;
  border-bottom: 1.5px solid #17324f; padding-bottom: 2px; }
.box { background: #f1f4f8; border-left: 3.5px solid #17324f; padding: 8px 11px; border-radius: 4px;
  margin: 7px 0; page-break-inside: avoid; }
.rouge { background: #fdf0ef; border-left-color: #a33025; }
.rouge h2, .rouge b.t { color: #a33025; }
ul.check { list-style: none; padding-left: 2px; margin: 5px 0; }
ul.check li { padding-left: 20px; text-indent: -20px; margin: 4px 0; }
ul.check li::before { content: "\\2610\\00a0\\00a0"; font-size: 11pt; color: #17324f; }
ul.puces { margin: 5px 0 5px 16px; padding: 0; }
ul.puces li { margin: 4px 0; }
table { border-collapse: collapse; width: 100%; margin: 6px 0; }
th { background: #17324f; color: #fff; font-size: 8.3pt; padding: 4px 6px; text-align: left; }
td { border: 1px solid #c9d2dc; padding: 4px 6px; font-size: 8.7pt; vertical-align: top; }
tr { page-break-inside: avoid; }
.ligne { border-bottom: 1px dotted #9aa7b5; height: 16px; }
b.t { color: #17324f; }
.petit { font-size: 8.5pt; color: #555; line-height: 1.5; }
"""

def bandeau(num, titre):
    return f'<div class="bandeau"><span class="titre">{titre}</span><span class="num">{num}</span></div>'

FICHES = {}

FICHES["Fiche 1 - Ta mission (Emma).pdf"] = bandeau("Fiche 1 / 4", "Ta mission") + """
<p class="sous">Ton rôle en une page — écrit pour toi, Emma. Bienvenue dans la machine.</p>

<div class="box"><b class="t">Ta mission :</b> faire que chaque créatrice prioritaire dépose régulièrement
un <b>lot de contenu frais</b> — un lot complet <b>au moins 2 fois par mois</b>.<br/>
Pourquoi c'est important : plus de contenu → plus de clips → plus d'abonnés → plus de revenus
pour les créatrices (et pour l'agence). <b>Tu es la personne qui fait tourner cette chaîne.</b></div>

<h2>Tes 4 résultats (on regarde ça, pas les heures)</h2>
<ul class="check">
<li>Un <b>lot complet</b> (~40-50 clips) déposé par créatrice prioritaire, <b>2 fois par mois</b></li>
<li><b>Zéro mois à vide</b> sur les créatrices prioritaires</li>
<li>Le <b>dossier Drive de la semaine envoyé chaque lundi</b> sur Telegram (note courte ou vocal)</li>
<li>Le <b>formulaire du dimanche soir</b> rempli chaque semaine (10 min)</li>
</ul>

<h2>Ton ordre de priorité</h2>
<ul class="puces">
<li><b>1. Maddy</b> — moteur n°1 du CA MYM, la confiance est son carburant</li>
<li><b>2. Chloé</b> — n°1 toutes plateformes, son volume doit suivre</li>
<li><b>3. Sophie</b> — machine en pleine explosion, à nourrir</li>
<li><b>4. Sarah</b> — en pleine accélération</li>
<li><b>5. Jade</b> — cadence à maintenir</li>
</ul>
<p class="petit">Quand tu dois choisir où mettre ton énergie, tu suis cet ordre. Maddy d'abord, toujours.</p>

<h2>Tu décides seule</h2>
<ul class="puces">
<li>Le choix des trends et le contenu des briefs</li>
<li>Tes relances : le ton, le moment, le canal</li>
<li>L'organisation de ta semaine</li>
<li>La façon d'accompagner une créatrice qui ralentit</li>
<li>Les ajustements de la méthode (note-les, ils m'intéressent)</li>
</ul>
<p class="petit">On te fait confiance : décide, essaie, ajuste. C'est ton terrain.</p>

<h2>La règle 1-3-1 (pour remonter un sujet)</h2>
<div class="box">
<b class="t">1</b> — le problème, posé en deux phrases.<br/>
<b class="t">3</b> — trois solutions possibles.<br/>
<b class="t">1</b> — ta recommandation.<br/>
<span class="petit">Par écrit, quand tu veux. Je suis toujours disponible pour te répondre.</span></div>

<h2 style="color:#a33025;border-color:#a33025;">Le non-négociable</h2>
<div class="box rouge"><b class="t">100 % safe plateforme.</b> Aucune nudité, aucune sollicitation, aucune référence
explicite à OF/MYM dans le contenu Instagram/Facebook. C'est ce qui garde les comptes en vie.<br/>
<b>Dans le doute → tu m'envoies la capture et ta question AVANT, je réponds vite.</b>
C'est le seul sujet où on décide toujours à deux.</div>

<p class="petit"><b>Droit à l'erreur :</b> une trend qui ne prend pas, un lot imparfait — c'est un coût
d'apprentissage, jamais une faute. La seule vraie erreur serait de laisser une créatrice tourner du contenu
trop osé pour les plateformes. Tout le reste s'apprend.</p>
"""

FICHES["Fiche 2 - Ta semaine type (Emma).pdf"] = bandeau("Fiche 2 / 4", "Ta semaine type") + """
<p class="sous">Ton rituel de la semaine — simple, régulier, sans pression.</p>

<div class="box"><b class="t">Le principe :</b> chaque lundi, tu envoies à chaque créatrice ses idées et son
dossier Drive de la semaine. Objectif : un <b>lot complet</b> (5 tenues × 10 trends = <b>~50 clips</b>)
par créatrice prioritaire, <b>2 fois par mois</b>.</div>

<h2>Lundi — lancement (ton gros bloc)</h2>
<ul class="check">
<li>Commencer par <b>ce qui a déjà marché</b> : les trends déjà validées par la créatrice
et les idées des canaux Telegram d'idées</li>
<li>Compléter avec des <b>nouvelles trends</b> reproductibles en France et safe plateforme</li>
<li>Préparer le <b>dossier Drive de la semaine</b> — ex. : Marketing &gt; Instagram Reels &gt; Juillet &gt; Semaine 3</li>
<li><b>Envoyer le dossier à chaque créatrice sur Telegram</b>, avec une note courte ou un vocal qui explique ce qu'elle reproduit</li>
<li>Confirmer son <b>créneau de tournage</b></li>
</ul>

<h2>Mercredi — point en douceur</h2>
<ul class="check">
<li>Elle a planifié ou commencé ? Si non : comprendre ce qui bloque
(agenda ? consigne pas claire ? motivation ?) et <b>l'aider aujourd'hui</b></li>
</ul>

<h2>Vendredi — point livraison</h2>
<ul class="check">
<li>Les rushs sont déposés sur le Drive ? Si non : identifier le frein —
<b>technique</b> (réglages, lumière) · <b>créatif</b> (ne sait pas quoi filmer) · <b>motivation</b> —
et aider concrètement, pas juste relancer</li>
</ul>

<h2>Week-end — rattrapage</h2>
<ul class="check">
<li>Pour les retardataires : relance douce + <b>aide concrète</b> (réexpliquer une trend, décaler le créneau).
Objectif : aucune prioritaire laissée de côté</li>
</ul>

<h2>Dimanche soir — le formulaire (10 min)</h2>
<div class="box">Tu remplis le <b>formulaire Google du dimanche</b> (Gaëtan te donne le lien). Pour chaque créatrice :
les <b>rushs déposés</b> cette semaine · le <b>lot est-il complet ?</b> · le <b>blocage</b> éventuel ·
ton <b>action pour la semaine suivante</b>.</div>

<h2>Pourquoi ça marche</h2>
<div class="box">
<b class="t">La relation</b> — une créatrice suivie de près produit deux à trois fois plus.<br/>
<b class="t">La méthode</b> — une séance structurée sort 50 clips, trois séances improvisées en sortent 15.<br/>
<b class="t">L'itération</b> — note ce qui a marché, ajuste les idées de la semaine suivante.</div>
"""

FICHES["Fiche 3 - Checklist tournage (creatrice).pdf"] = bandeau("Fiche 3 / 4", "Checklist tournage") + """
<p class="sous"><b>À transmettre à la créatrice</b> avec son dossier Drive de la semaine.
Objectif : <b>50 clips en une séance</b>.</p>

<h2>1. Réglages téléphone (à vérifier à chaque séance)</h2>
<ul class="check">
<li>Caméra en <b>4K, 60 images/seconde</b> (Réglages → Appareil photo → Enregistrement vidéo)</li>
<li><b>Caméra arrière</b> — jamais la caméra selfie (qualité deux fois meilleure)</li>
<li><b>Objectif nettoyé</b> (un coup de chiffon change tout)</li>
<li><b>Lumière face à toi</b> : fenêtre en journée ou ring light — jamais dans le dos</li>
<li>Batterie chargée + stockage suffisant</li>
</ul>

<h2>2. Avant de filmer</h2>
<ul class="check">
<li><b>5 tenues</b> préparées et accessibles</li>
<li>Les <b>10 trends de la semaine</b> ouvertes sur un deuxième écran (envoyées par Emma, dossier Drive)</li>
<li>Fond propre, lieu rangé</li>
</ul>

<h2>3. Le tournage : la méthode matrice</h2>
<div class="box">Tu filmes <b>toutes les trends dans une tenue, puis tu changes de tenue</b> —
jamais l'inverse (changer de tenue à chaque trend fait perdre un temps fou).</div>
<ul class="check">
<li><b>Tenue 1</b> → filme les 10 trends</li>
<li><b>Tenue 2</b> → filme les 10 trends</li>
<li><b>Tenue 3</b> → filme les 10 trends</li>
<li><b>Tenue 4</b> → filme les 10 trends</li>
<li><b>Tenue 5</b> → filme les 10 trends &nbsp;&nbsp;→&nbsp; <b>= 50 clips prêts, en une séance</b></li>
<li><b>Dépose tout</b> dans ton dossier Drive de la semaine</li>
<li>Nomme simplement : <b>Tenue X – Trend Y</b></li>
<li><b>Préviens Emma</b> que c'est déposé</li>
</ul>

<div class="box rouge"><b class="t">Règle d'or :</b> tout le contenu reste <b>100 % safe</b> pour Instagram/Facebook —
pas de nudité, pas de sollicitation, pas de référence explicite. Un doute sur une trend →
<b>demande à Emma AVANT de filmer</b>.</div>

<p class="petit"><b>Pourquoi ce système :</b> plus tu produis, plus on peut poster sur les réseaux,
plus tu gagnes d'abonnés OnlyFans ou MYM — et donc d'argent. Une séance par semaine =
des semaines de contenu d'avance pour nos clippeurs.</p>
"""

FICHES["Fiche 4 - Quand ca coince (Emma).pdf"] = bandeau("Fiche 4 / 4", "Quand ça coince") + """
<p class="sous">Toutes les pannes possibles : ce que tu règles toi-même, et quand tu m'écris (toujours en 1-3-1).
Je suis toujours joignable — un doute ne reste jamais bloqué.</p>

<table>
<tr><th style="width:26%">La panne</th><th style="width:44%">Ce que tu fais toi-même</th><th style="width:30%">Tu m'écris si…</th></tr>
<tr><td><b>1. La créatrice ne répond pas</b></td>
<td>Relance douce à J+1 sur un autre canal ; propose un créneau précis plutôt qu'un « quand tu peux »</td>
<td>Silence total <b>&gt; 5 jours</b></td></tr>
<tr><td><b>2. Le lot n'est pas déposé / plus de rushs</b></td>
<td>Identifier le frein : technique / créatif / motivation. Aide concrète : réexpliquer une trend, refaire un réglage, décaler le créneau</td>
<td><b>Un mois sans lot</b> sur une prioritaire</td></tr>
<tr><td><b>3. Une trend ne prend pas, doute créatif</b></td>
<td>Coût d'apprentissage, pas une faute : remplace la trend, note-le au formulaire, ajuste les idées suivantes</td>
<td>(rien à remonter)</td></tr>
<tr><td><b>4. Doute « safe plateforme »</b></td>
<td><b>Rien — c'est le seul sujet qu'on tranche à deux.</b></td>
<td><b>Tout de suite</b> : capture/lien + ta question</td></tr>
<tr><td><b>5. Rushs inutilisables (flous, sombres, mal cadrés)</b></td>
<td>Renvoyer la checklist réglages (fiche 3), refaire les clips concernés à la séance suivante</td>
<td>Si ça se répète deux séances de suite</td></tr>
<tr><td><b>6. La créatrice n'est pas disponible (examens, vacances, imprévu)</b></td>
<td>Décaler le créneau, alléger le lot, planifier le rattrapage avec elle</td>
<td>Indisponibilité qui dure <b>&gt; 3 semaines</b></td></tr>
<tr><td><b>7. Problème d'outil (Drive, Telegram, envoi qui échoue)</b></td>
<td>Renvoyer le lien, vérifier les accès, tester un autre moyen d'envoi</td>
<td>Si rien ne fonctionne après tes essais</td></tr>
<tr><td><b>8. Elle refuse une trend ou veut changer de format</b></td>
<td>Écouter, proposer une variante qui garde ce qui marche déjà pour elle</td>
<td>Si elle veut abandonner son format principal</td></tr>
<tr><td><b>9. Conflit, démotivation profonde</b></td>
<td>Écouter, ne rien promettre, noter les faits</td>
<td>Dès que c'est plus qu'un coup de mou (avec le contexte)</td></tr>
</table>

<h2>Le format pour m'écrire (toujours le même)</h2>
<div class="box">
<b class="t">1</b> — le problème, posé en deux phrases.<br/>
<b class="t">3</b> — trois options possibles.<br/>
<b class="t">1</b> — ta recommandation.<br/><br/>
<span class="petit">Exemple : « Maddy n'a rien déposé depuis dix jours et ne confirme pas son créneau (1).
Options : je l'accompagne pour filmer ensemble / on décale d'une semaine et je renvoie les idées lundi /
Gaëtan l'appelle (3). Je recommande la séance ensemble jeudi, elle produit toujours mieux accompagnée (1). »</span></div>

<div class="box"><b class="t">Rappel :</b> tu as le droit de décider, de te tromper et d'ajuster
la semaine suivante — <b>sans pression</b>. C'est comme ça qu'on avance.</div>
"""

FICHES["Fiche 5 - Profil creatrice (modele).pdf"] = bandeau("Modèle × 5", "Profil créatrice") + """
<p class="sous">Une fiche par créatrice : <b>Maddy · Chloé · Sophie · Sarah · Jade</b>. Le système commun (fiches 1-4)
tient la cadence ; cette fiche tient <b>l'adaptation</b>. À remplir avec Gaëtan, puis mise à jour par Emma chaque mois.</p>

<table>
<tr><td style="width:33%"><b>Créatrice :</b></td><td style="width:34%"><b>Plateformes :</b></td><td><b>Priorité contenu :</b> P1 ☐ &nbsp; P2 ☐</td></tr>
</table>

<h2>Sa persona en 1 phrase</h2>
<div class="ligne"></div><div class="ligne"></div>

<h2>Les types de trends qui marchent pour ELLE</h2>
<div class="ligne"></div><div class="ligne"></div><div class="ligne"></div><div class="ligne"></div>

<h2>Ce qu'elle ne fait pas</h2>
<div class="ligne"></div><div class="ligne"></div><div class="ligne"></div>

<h2>Tournage</h2>
<ul class="puces">
<li>Créneau habituel : ____________________________________</li>
<li>Durée de séance : ____________________________________</li>
<li>Matériel (téléphone, ring light, lieu) : ________________</li>
<li>Niveau technique : débutante ☐ · correcte ☐ · autonome ☐</li>
</ul>

<h2>Relation</h2>
<ul class="puces">
<li>Canal de contact : ____________________________________</li>
<li>Ton qui marche (encourager, cadrer…) : ________________</li>
<li>Fréquence de relance idéale : __________________________</li>
<li>Ce qui la motive : ____________________________________</li>
</ul>

<h2>Particularités</h2>
<p class="petit">Ex. : ne fait pas de TikTok · a besoin de félicitations · matière via YouTube plutôt que tournage en lot · deux comptes à alimenter…</p>
<div class="ligne"></div><div class="ligne"></div><div class="ligne"></div>

<h2>Ce qui a le mieux marché ce mois-ci (à jour le : ______ )</h2>
<div class="ligne"></div><div class="ligne"></div><div class="ligne"></div>
"""

# ---------------------------------------------------------------------------
# Fiches par créatrice — VERSION PROVISOIRE (specs dictées le 13/07/2026 +
# données 30 j). À ajuster avec Gaëtan après le premier call avec Emma.
# ---------------------------------------------------------------------------

def fiche_crea(nom, priorite, apercu, manager, trends, limites, chiffres, a_completer=True):
    compl = ('<h2>À compléter avec Gaëtan / au fil des semaines</h2>'
             '<ul class="puces"><li>Créneau de tournage habituel : ______________ · durée : ______</li>'
             '<li>Matériel (téléphone, ring light, lieu) : ____________________</li>'
             '<li>Ce qui a le mieux marché ce mois-ci : ____________________</li></ul>') if a_completer else ''
    return bandeau("Profil créatrice", nom) + f"""
<p class="sous">{apercu} &nbsp;·&nbsp; <b>Priorité contenu : {priorite}</b></p>

<h2>Comment l'accompagner (le levier n°1)</h2>
<div class="box">{manager}</div>

<h2>Quoi lui envoyer (ses trends)</h2>
{trends}

<h2>Ce qu'elle ne fait pas</h2>
{limites}

<h2>Ce que disent les chiffres (au 13/07/2026)</h2>
<p class="petit">{chiffres}</p>
{compl}
<p class="petit">Profil provisoire — on l'ajuste ensemble (Emma + Gaëtan) après les premiers échanges.</p>
"""

FICHES["Profil - Maddy.pdf"] = fiche_crea(
    "Maddy", "P1 — priorité n°1, moteur du CA MYM",
    "Son levier n'est pas technique : c'est la CONFIANCE.",
    "<b>Félicite-la explicitement, à chaque livraison.</b> Elle doute d'elle sur tout ce qui touche au marketing — "
    "ton rôle est de lui dire, avec des mots clairs : <b>« ton contenu nous aide énormément, c'est exactement ce qu'il "
    "nous faut, c'est très bien »</b>. Une Maddy en confiance produit deux fois plus. Ensuite : consignes simples, "
    "pas de sur-réflexion, optimiser son temps.",
    '<ul class="puces"><li>Briefs <b>simples et rassurants</b> : l\'exemple + « tu fais pareil, c\'est parfait »</li>'
    '<li>Éviter tout ce qui la fait douter (formats compliqués, choix multiples ouverts)</li>'
    '<li>Banque d\'idées Reels + ce qui a déjà marché pour elle</li></ul>',
    '<ul class="puces"><li>Jamais de critique sèche sur un clip : toujours « super, et la prochaine fois essaie aussi… »</li>'
    '<li>Ne pas la surcharger : mieux vaut un lot terminé qu\'un plan ambitieux abandonné</li></ul>',
    "N°1 du CA MYM sur 30 j : <b>8 098 € (37 % du MYM)</b>, monétisation en explosion (31,77 €/nouvel abonné en juillet). "
    "MYM uniquement pour l'instant — sa production est le moteur du chiffre, sa confiance est le carburant.")

FICHES["Profil - Chloe.pdf"] = fiche_crea(
    "Chloé", "P1 — n°2 de la priorité, n°1 toutes plateformes",
    "Un seul format, décliné à l'infini — et il est n°1 de l'agence.",
    "Son contenu tourne sur <b>UN format unique : « J'adore les hommes qui font X / Y / Z »</b>. "
    "Ton rôle n'est pas d'inventer autre chose : c'est de <b>faire tourner les variantes</b> et de t'assurer "
    "qu'elle ne soit jamais à court d'idées <b>faisables chez elle, dans son appartement</b>.",
    '<ul class="puces"><li>Les <b>variantes sont déjà préparées</b> dans la banque d\'idées Reels : par métiers, personnalité, '
    'physique, relations, actions, habitudes, routine, dormir, jouer…</li>'
    '<li>Filtre à appliquer avant d\'envoyer : <b>réalisable en intérieur, seule, sans accessoire compliqué</b></li>'
    '<li>10 variantes par semaine, prêtes à tourner en une séance</li></ul>',
    '<ul class="puces"><li>Pas de scénarios extérieurs ou à accessoires : tout doit être tournable dans son appartement</li>'
    '<li>On reste sur SON format — pas d\'expérimentations qui diluent ce qui marche</li></ul>',
    "N°1 toutes plateformes : <b>~13 100 €/30 j</b> (OF 7 429 $ + MYM 6 301 €). Son MYM est passé en <b>gratuit le 14/07</b> : "
    "le volume d'abonnés explose, le contenu doit suivre — pas de mois à vide.")

FICHES["Profil - Sophie.pdf"] = fiche_crea(
    "Sophie", "P1 — n°3 de la priorité, machine en pleine explosion",
    "Tourne en duo avec son mari. Leur logique : rentabiliser chaque minute.",
    "<b>Sois directive (c'est ce qu'ils préfèrent).</b> Pas de brainstorming, pas de « qu'est-ce que tu en penses ? » : "
    "tu envoies des <b>exemples précis</b> et tu dis <b>« fais exactement ça »</b>. Ils tournent énormément de clips très vite "
    "quand la consigne est claire — leur contrainte c'est le temps, pas l'envie. Une consigne floue = une séance perdue.",
    '<ul class="puces"><li>Pioche dans la <b>banque d\'idées Reels</b> : les idées déjà repérées pour eux sont bonnes à reprendre</li>'
    '<li>Privilégie ce qui est <b>faisable dans leur quotidien</b> : avec le camion, en course, en déplacement</li>'
    '<li>Toujours joindre l\'exemple vidéo + la consigne en une phrase</li></ul>',
    '<ul class="puces"><li>Pas de créativité libre — ils veulent exécuter vite</li>'
    '<li>Respecter leur organisation de couple (créneaux groupés, grosses séances)</li></ul>',
    "OF en explosion : <b>+27 % sur 30 j</b> (~9 800 $/30 j, ×11 depuis avril), 85 % du CA en messages. "
    "Sa machine est une priorité à nourrir : chaque lot se transforme directement en revenus.")

FICHES["Profil - Sarah.pdf"] = fiche_crea(
    "Sarah", "P1 — n°4 de la priorité, en pleine accélération",
    "La plus flexible du groupe : tout type de contenu passe.",
    "Avec elle, <b>le frein n'est ni la créativité ni les limites : c'est juste l'organisation</b>. "
    "Cadence claire, briefs réguliers, et elle délivre. Relation simple et détendue — pas de précautions particulières.",
    '<ul class="puces"><li><b>Reproduis d\'abord ce qui a déjà marché pour elle</b> (ses meilleurs Reels : les repérer et les décliner)</li>'
    '<li>Ensuite, pioche large dans la banque d\'idées Reels — tout est jouable</li>'
    '<li>Bon terrain d\'essai : une trend nouvelle se teste sur elle avant les autres</li></ul>',
    '<ul class="puces"><li>Aucune limite particulière connue — garder le filtre safe plateforme, comme pour toutes</li></ul>',
    "En pleine accélération : abonnés MYM <b>×8 en un mois</b> (~4 900 €/30 j) et son OnlyFans (Lila Doré) vient de "
    "démarrer (42 abonnés via les liens, les premiers payeurs arrivent). Plus elle a de contenu, plus la fusée monte.")

FICHES["Profil - Jade (a completer).pdf"] = fiche_crea(
    "Jade", "P1 cadence — n°5 de la priorité, diagnostic en cours",
    "Grosse base d'abonnés, monétisation faible : le contenu entretient, le diagnostic décidera.",
    "Maintenir la <b>cadence normale</b> (ses lots de contenu) sans investissement particulier : sa situation est en "
    "diagnostic côté Gaëtan (trafic et monétisation). Ton rôle : que la machine ne s'arrête pas pendant qu'on décide.",
    '<ul class="puces"><li>Ses préférences de contenu : <b>à compléter avec Gaëtan</b> ______________________</li>'
    '<li>En attendant : reproduire ce qui a déjà marché pour elle</li></ul>',
    '<ul class="puces"><li><b>Pas de TikTok</b> — c\'est son choix, on ne pousse pas</li></ul>',
    "La plus grosse base MYM (4 949 abonnés actifs) mais LTV faible (5,33 €/nouveau) et OF en repli "
    "(<b>-40 % sur 30 j</b>). Le sujet n'est pas « plus de volume », c'est « pourquoi ça convertit moins » — "
    "décision chez Gaëtan, cadence chez toi.")

FICHES["Profil - Alice (a confirmer).pdf"] = fiche_crea(
    "Alice", "P2 — lancement prévu en septembre",
    "Positionnement : jeune étudiante, ultra soft. (Nom à confirmer avec Gaëtan.)",
    "<b>Accompagne-la pas à pas dans la création</b> : elle a besoin d'exemples et d'un cadre très simple, "
    "pas d'autonomie créative. Trends <b>très douces, très simples</b>, ambiance « vie d'étudiante » — "
    "l'aider à prendre le rythme avant de penser volume.",
    '<ul class="puces"><li>Trends « étudiante » : quotidien, humour léger, routine, études — le plus simple possible</li>'
    '<li>Toujours envoyer l\'exemple + la consigne pas à pas</li>'
    '<li>Tenues simples uniquement</li></ul>',
    '<ul class="puces"><li><b>Pas de ventre visible · pas de maillot de bain · rien de trop sexy · pas de gestes suggestifs</b></li>'
    '<li>Le positionnement soft EST la stratégie : un clip trop suggestif casse la cohérence du personnage</li></ul>',
    "Lancement à zéro prévu en septembre. Objectif de la période : constituer sa bibliothèque de contenu "
    "et son rythme de tournage, sans pression de chiffre.")

def main():
    os.makedirs(SORTIE, exist_ok=True)
    for nom, corps in FICHES.items():
        html = f"<html><head><style>{CSS}</style></head><body>{corps}</body></html>"
        chemin = os.path.join(SORTIE, nom)
        HTML(string=html).write_pdf(chemin)
        print("OK", nom)

if __name__ == "__main__":
    main()
