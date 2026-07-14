# Génère le Kit Clipper v2 : UN SEUL PDF de 7 pages (bienvenue + 6 fiches)
# dans second-brain/96-Opérations LTP/Kit Clippers/
# Usage : python3 tools/kit_clippers/generer_fiches.py
# Sources de vérité : formation Loom (13/07) + consignes Discord de Gaëtan (09/07) + corrections du 14/07.
# v2 (14/07/2026) : setup 3 IG + 3 FB par téléphone, jamais de numéro de téléphone,
# lien GetAllMyLinks J+7 sur le compte privé uniquement, plus de renommage des rushs,
# reporting hebdomadaire du dimanche (formulaire) lié à la rémunération, langage collégien.

from weasyprint import HTML
import os

SORTIE = os.path.join(os.path.dirname(__file__), "..", "..",
                      "second-brain", "96-Opérations LTP", "Kit Clippers")

CSS = """
@page {
  size: A4; margin: 11mm 13mm 14mm 13mm;
  @bottom-center { content: "Kit Clipper · LTP · juillet 2026 · v2 — document interne, ne pas diffuser"; font-size: 7.5pt; color: #8a8a8a; }
  @bottom-right { content: "page " counter(page) " / " counter(pages); font-size: 7.5pt; color: #8a8a8a; }
}
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.8pt; color: #1c1c1c; line-height: 1.42; margin: 0; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
.bandeau { background: #1d3d2f; color: #fff; padding: 9px 14px; border-radius: 8px;
  display: flex; justify-content: space-between; align-items: baseline; }
.bandeau .num { font-size: 9pt; letter-spacing: 1px; text-transform: uppercase; color: #bcd9c9; }
.bandeau .titre { font-size: 16pt; font-weight: bold; }
.sous { color: #4a4a4a; font-size: 9.5pt; margin: 8px 2px 14px; }
h2 { font-size: 11.2pt; color: #1d3d2f; margin: 13px 0 6px; letter-spacing: .3px;
  border-bottom: 1.5px solid #1d3d2f; padding-bottom: 3px; }
.box { background: #eff5f1; border-left: 4px solid #1d3d2f; padding: 8px 12px; border-radius: 5px; margin: 10px 0; }
.rouge { background: #fdf0ef; border-left-color: #a33025; }
.rouge b.t { color: #a33025; }
ul.check { list-style: none; padding-left: 2px; margin: 6px 0; }
ul.check li { padding-left: 22px; text-indent: -22px; margin: 4.5px 0; }
ul.check li::before { content: "\\2610\\00a0\\00a0"; font-size: 11pt; color: #1d3d2f; }
ul.puces { margin: 6px 0 6px 18px; padding: 0; }
ul.puces li { margin: 4.5px 0; }
ol.etapes { margin: 6px 0 6px 20px; padding: 0; }
ol.etapes li { margin: 5px 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th { background: #1d3d2f; color: #fff; font-size: 8.6pt; padding: 5px 7px; text-align: left; }
td { border: 1px solid #c9d6cd; padding: 5px 7px; font-size: 9.2pt; vertical-align: top; }
b.t { color: #1d3d2f; }
.petit { font-size: 8.6pt; color: #555; }
.espace { height: 8px; }
.grand-espace { height: 14px; }
.logo-bas { text-align: center; margin-top: 22px; }
.schema { text-align: center; margin: 12px 0; }
.carte { display: inline-block; border: 2px solid #1d3d2f; border-radius: 8px; padding: 5px 10px;
  margin: 3px 5px; font-size: 9.2pt; background: #eff5f1; }
.carte.privee { border-color: #a33025; background: #fdf0ef; }
.fleche { font-size: 13pt; color: #1d3d2f; margin: 0 4px; }
.objectif { font-size: 11pt; margin: 8px 0; }
"""

IG = ('<svg width="15" height="15" viewBox="0 0 24 24" style="vertical-align:-2px">'
      '<rect x="2" y="2" width="20" height="20" rx="5.5" fill="none" stroke="#E4405F" stroke-width="2.2"/>'
      '<circle cx="12" cy="12" r="4.6" fill="none" stroke="#E4405F" stroke-width="2.2"/>'
      '<circle cx="17.4" cy="6.6" r="1.5" fill="#E4405F"/></svg>')

IG_GRAND = IG.replace('width="15" height="15"', 'width="34" height="34"')

FB = ('<svg width="15" height="15" viewBox="0 0 24 24" style="vertical-align:-2px">'
      '<circle cx="12" cy="12" r="11" fill="#1877F2"/>'
      '<path d="M13.4 21.5v-7.2h2.5l.4-2.9h-2.9V9.5c0-.85.3-1.45 1.55-1.45h1.45V5.4c-.3 0-1.15-.1-2.1-.1-2.1 0-3.55 1.3-3.55 3.7v2.4H8.2v2.9h2.55v7.2z" fill="#fff"/></svg>')

PAGES = []

# ---------------------------------------------------------------- PAGE 1 — BIENVENUE
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Bienvenue dans l&#8217;équipe clipping</span><span class="num">LTP</span></div>'}
<p class="sous">Ce document, c&#8217;est ta feuille de route. Une page = une étape. Garde-le sous la main : presque toutes les réponses sont dedans.</p>

<h2>★ Ton objectif (dans l&#8217;ordre)</h2>
<ol class="etapes objectif">
<li>Créer des comptes Instagram <b>propres</b></li>
<li><b>Poster tous les jours</b></li>
<li>Tester <b>beaucoup</b> de formats</li>
<li><b>Refaire ce qui marche</b></li>
<li>Ramener des abonnés OnlyFans avec <b>ton lien</b> — c&#8217;est ça qui te paie €</li>
</ol>

<h2><svg width="14" height="14" viewBox="0 0 24 24" style="vertical-align:-2px"><rect x="6" y="1.5" width="12" height="21" rx="2.5" fill="none" stroke="#1d3d2f" stroke-width="2"/><circle cx="12" cy="19" r="1.3" fill="#1d3d2f"/></svg> Ton matériel de travail (pour 1 téléphone)</h2>
<div class="schema">
<span class="carte">{IG} Compte de croissance 1</span>
<span class="carte">{IG} Compte de croissance 2</span><br/>
<span class="fleche">↓ leur bio contient juste l&#8217;arobase @ du compte privé ↓</span><br/>
<span class="carte privee">{IG} Compte privé — <b>c&#8217;est LUI qui a le lien</b></span><br/>
<span class="fleche">+</span><br/>
<span class="carte">{FB} Page Facebook 1</span>
<span class="carte">{FB} Page Facebook 2</span>
<span class="carte">{FB} Page Facebook 3</span>
</div>
<div class="box">Les <b>2 comptes de croissance</b> font des vues. Ils envoient les curieux vers le <b>compte privé</b> grâce à l&#8217;arobase.
Le compte privé reçoit le monde : c&#8217;est lui qui porte le lien. Les <b>3 pages Facebook</b> republient tes Reels et font des vues en plus
— et en ce moment, Facebook marche très fort.</div>

<h2>⚠ La règle la plus importante de toutes</h2>
<div class="box rouge"><b class="t">Tu ne postes JAMAIS une vidéo brute du Google Drive.</b><br/>
Chaque vidéo doit être <b>modifiée</b> avant d&#8217;être publiée : début changé, coupes, zoom, texte, sous-titres, musique, miniature.
Pourquoi ? Instagram repère les copies (le « contenu dupliqué ») et coupe les vues. Le détail est à la fiche 3.</div>

<h2>Ton parcours en 6 fiches</h2>
<table>
<tr><th>Fiche</th><th>Quand</th></tr>
<tr><td><b>1 — Créer tes comptes</b></td><td>Jour 0, après le quiz validé</td></tr>
<tr><td><b>2 — Le warm-up</b></td><td>Les 48 premières heures de chaque compte</td></tr>
<tr><td><b>3 — Monter et poster un Reel</b></td><td>Quand le test de l&#8217;Explorer est bon</td></tr>
<tr><td><b>4 — Ta routine et ta semaine</b></td><td>Tous les jours + le formulaire du dimanche</td></tr>
<tr><td><b>5 — Reels d&#8217;essai et évolutions</b></td><td>Vers 200 abonnés</td></tr>
<tr><td><b>6 — Quand ça coince</b></td><td>À lire dès le début, à ressortir en cas de pépin</td></tr>
</table>
</div>
""")

# ---------------------------------------------------------------- PAGE 2 — FICHE 1
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Créer tes comptes (Jour 0)</span><span class="num">Fiche 1 / 6</span></div>'}
<p class="sous">Avant de commencer : quiz validé (8/10 minimum) + ton adresse Gmail envoyée à Gaëtan (pour l&#8217;accès au Drive de ta créatrice).</p>

<h2>{IG} Instagram — les règles d&#8217;or</h2>
<ul class="check">
<li><b>1 seul compte Instagram créé par jour.</b> Jamais 2 ou 3 le même jour.</li>
<li>Pour chaque compte : <b>1 adresse mail + 1 mot de passe rien qu&#8217;à lui</b> (créés avec Gaëtan).</li>
<li><b>Photo, bio et arobase @ uniques</b> pour chaque compte → tu notes tout dans ton canal Discord.</li>
<li>✘ <b>JAMAIS ton numéro de téléphone sur un compte Instagram.</b> Pour vérifier : Profil → Paramètres →
<b>Informations personnelles</b>. S&#8217;il y a un numéro, tu l&#8217;enlèves.</li>
<li><b>Jamais associer les comptes entre eux</b> (et jamais dans le Meta Center).</li>
</ul>
<div class="box rouge"><b class="t">⚠ Le piège de l&#8217;association :</b> si Instagram crée ton nouveau compte <b>sans</b> te demander
une adresse mail et un mot de passe, c&#8217;est qu&#8217;il est <b>associé à l&#8217;ancien</b>. Va dans les paramètres et <b>dissocie-le</b>.
Sinon, un seul ban peut emporter <b>tous</b> tes comptes d&#8217;un coup.</div>

<div class="espace"></div>
<h2>€ Le lien (celui qui te fait gagner de l&#8217;argent)</h2>
<ul class="check">
<li>Ton lien <b>GetAllMyLinks</b> va <b>UNIQUEMENT sur le compte Instagram privé</b> — et seulement à <b>J+7</b> (demande ton lien à Gaëtan).</li>
<li>Les 2 comptes de croissance n&#8217;ont <b>jamais</b> de lien : seulement <b>l&#8217;arobase @ du compte privé</b> dans la bio.</li>
</ul>

<div class="espace"></div>
<h2>{FB} Facebook — les pages</h2>
<ul class="check">
<li>Ton compte Facebook <b>personnel</b> = le compte « mère ». Il sert <b>uniquement</b> à créer et gérer les pages.
Tes amis et ta famille <b>ne voient pas</b> les pages que tu gères.</li>
<li>1 compte mère peut gérer <b>jusqu&#8217;à 10 pages</b>. Toi, tu en gères <b>3 par créatrice</b>.</li>
<li>Sur Facebook, c&#8217;est plus simple : <b>le lien dès le premier jour</b> (bio + profil) et tu peux <b>publier dès le premier jour</b>.</li>
</ul>

<div class="espace"></div>
<div class="box rouge"><b class="t">Rappel :</b> contenu 100 % propre, toujours (le détail est à la fiche 3). Et si un compte saute,
ce n&#8217;est pas un drame : on le note, on recrée (1 par jour) et on continue — voir fiche 6.</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 3 — FICHE 2
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Le warm-up (48 heures) <svg width="16" height="16" viewBox="0 0 24 24" style="vertical-align:-2px"><path d="M12 2 C13.5 7 7.5 9.5 7.5 14.5 a4.5 4.5 0 0 0 9 0 c0-1.8-.8-3.2-1.8-4.3 0 1.8-.8 2.6-1.7 3.1 .6-2.2-.3-4.6-1-11.3z" fill="#f0813c"/></svg></span><span class="num">Fiche 2 / 6</span></div>'}
<p class="sous">Le but : montrer à Instagram que ton compte est celui d&#8217;une vraie créatrice française qui vit sa vie sur l&#8217;application.
Facebook n&#8217;a <b>pas</b> besoin de warm-up : là-bas tu publies dès le premier jour.</p>

<h2>Les 48 premières heures (aucune publication)</h2>
<ul class="check">
<li><b>Zéro publication pendant 48 heures.</b></li>
<li>Regarde <b>uniquement du contenu de créatrices françaises</b> (la liste est dans le Discord).</li>
<li><b>Abonne-toi</b> aux créatrices de la liste + <b>active les notifications</b> Reels et carrousels.</li>
<li>Like, regarde les Reels <b>en entier</b>, commente un peu — comme une vraie utilisatrice.</li>
<li><b>Enregistre les meilleurs Reels</b> : tu les reproduiras plus tard.</li>
</ul>

<div class="espace"></div>
<h2>Pourquoi activer les notifications ?</h2>
<div class="box">Commenter un Reel <b>dans les minutes après sa publication</b> chez une grosse créatrice = ton commentaire est vu par
10 000 à 200 000 personnes. C&#8217;est de la visibilité gratuite — mais seulement si le commentaire est <b>bien écrit, drôle ou utile</b>.
Les commentaires de robot font bloquer le compte. Le guide des bons commentaires est dans le Discord.</div>

<div class="espace"></div>
<h2>✔ LE test de fin de warm-up (le seul qui compte)</h2>
<div class="box"><b class="t">Ouvre ton onglet Explorer :</b><br/><br/>
→ Il te montre des <b>créatrices françaises</b> ? Ton warm-up est terminé. Passe à la fiche 3 ✔<br/><br/>
→ Il montre autre chose ? Le warm-up n&#8217;est <b>pas</b> fini : continue les interactions naturelles. Ce n&#8217;est pas une question de durée,
c&#8217;est une question de signal. Si ça ne vient pas après plusieurs jours, tu as fait trop d&#8217;actions trop vite : demande conseil.</div>

<div class="espace"></div>
<h2>✘ Les erreurs qui cassent un warm-up</h2>
<ul class="puces">
<li>Publier avant la fin des 48 heures</li>
<li>Regarder du contenu hors sujet (ton fil doit rester 100 % créatrices françaises)</li>
<li>Les rafales : 50 likes en 5 minutes = comportement de robot</li>
<li>Mettre le lien trop tôt (il arrive à J+7, sur le compte privé seulement — fiche 1)</li>
<li>Te connecter au même compte depuis plusieurs appareils</li>
</ul>

<div class="logo-bas">{IG_GRAND}</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 4 — FICHE 3
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Monter et poster un Reel</span><span class="num">Fiche 3 / 6</span></div>'}
<p class="sous">L&#8217;application : <b>Edits</b> (le monteur vidéo d&#8217;Instagram). La routine : <b>1 heure le matin en brouillons</b>, publication étalée dans la journée.</p>

<h2>La préparation (une seule fois)</h2>
<ul class="check">
<li>Télécharge les <b>bases</b> depuis le Discord (= le top 10 des Reels de TA créatrice, ce qui a déjà marché).</li>
<li>Importe-les <b>en template</b> dans Edits : extraire le son · dupliquer la caption.</li>
</ul>

<div class="espace"></div>
<h2>La boucle par Reel (10-15 min au début, 5 min avec l&#8217;habitude)</h2>
<ol class="etapes">
<li>Télécharge <b>un rush</b> depuis le Google Drive de ta créatrice.</li>
<li>Dans Edits : <b>« Remplacer le rush »</b> du template par celui que tu viens de prendre.</li>
<li>Modifie : <b>filtre</b> · <b>début et fin coupés</b> · <b>zoom ou cadrage</b> · <b>son</b> (celui de la base ou un son populaire) ·
<b>caption</b> (celle de la base ou une variante — 100 idées dans le Discord) · <b>sous-titres</b> si elle parle (varie les couleurs) · <b>miniature</b>.</li>
<li>Mets en <b>brouillon</b> le matin → publie étalé dans la journée (pas de programmation automatique : moins de vues).</li>
<li>Publie sur <b>Instagram ET sur une page Facebook</b>.</li>
</ol>

<div class="box rouge"><b class="t">⚠ Avant de publier, pose-toi UNE question : est-ce que ma vidéo ressemble encore au rush du Drive ?</b><br/>
Si oui → tu ne postes pas, tu modifies encore. Chaque vidéo publiée doit avoir : un début changé, des coupes, une caption,
un hook fort dès la première seconde, et un son ou un filtre différent.</div>

<div class="espace"></div>
<h2>Ce qui fait performer un Reel (tout le reste compte moins)</h2>
<ul class="puces">
<li><b>Le hook</b> — la première seconde doit donner envie de rester.</li>
<li><b>Le partage</b> — une vidéo qu&#8217;on a envie d&#8217;envoyer à un ami.</li>
</ul>

<div class="espace"></div>
<h2>✔ Autorisé / ✘ Interdit</h2>
<table>
<tr><th>✔ Ce qu&#8217;on poste</th><th>✘ Ce qu&#8217;on ne poste jamais</th></tr>
<tr><td>Tenues couvertes · street, décontracté, sport · tenue de soirée habillée</td><td>Bikinis trop sexy · sous-vêtements · poses trop provocantes</td></tr>
<tr><td>Hooks sur la personnalité · humour · une histoire · une situation où on se reconnaît</td><td>Les textes « écris-moi en privé », « lien en bio », « contenu exclusif »</td></tr>
<tr><td>Des vidéos qui donnent envie de commenter</td><td>Toute mention d&#8217;argent, de drogue ou d&#8217;OnlyFans · les émojis trop chauds (fruits, flammes, gouttes…)</td></tr>
</table>
<div class="box"><b class="t">Objectif : des comptes propres qui durent le plus longtemps possible.</b></div>
</div>
""")

# ---------------------------------------------------------------- PAGE 5 — FICHE 4
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Ta routine et ta semaine</span><span class="num">Fiche 4 / 6</span></div>'}
<p class="sous">Le but n&#8217;est pas d&#8217;être parfait. Le but est de <b>poster tous les jours</b> et de s&#8217;améliorer un peu chaque semaine.</p>

<h2>Ta routine du jour</h2>
<ol class="etapes">
<li>Je prends un rush sur le Google Drive et je fais mon montage sur Edits (fiche 3)</li>
<li>Je publie sur mes comptes Instagram</li>
<li>Je republie sur mes pages Facebook</li>
<li>Je fais quelques commentaires naturels</li>
<li>Je regarde mes statistiques et <b>je refais les formats qui marchent</b></li>
</ol>

<div class="espace"></div>
<h2>Ta montée en puissance, semaine par semaine</h2>
<p class="petit">Sur chacun de tes 2 comptes Instagram de croissance :</p>
<table>
<tr><th>Semaine</th><th>Ce qu&#8217;on attend de toi</th></tr>
<tr><td><b>Semaine 1</b></td><td><b>1 Reel par jour</b> et par compte</td></tr>
<tr><td><b>Semaine 2</b></td><td><b>2 Reels par jour</b> et par compte</td></tr>
<tr><td><b>Semaine 3</b></td><td><b>3 Reels par jour</b> et par compte</td></tr>
<tr><td><b>Semaine 4</b></td><td>Tu tiens le rythme (+1 par semaine ensuite, si ça tient) + le formulaire <b>chaque dimanche</b>, comme toutes les semaines</td></tr>
<tr><td><b>Vers J+30</b></td><td>Un compte bien tenu peut viser <b>~500 abonnés</b> → les évolutions de la fiche 5 se débloquent ★</td></tr>
</table>
<div class="box">Autour des Reels : <b>2-3 carrousels par semaine</b> (dès qu&#8217;un Reel pète → poste un carrousel, c&#8217;est là qu&#8217;ils explosent) ·
<b>1-10 commentaires par jour</b> chez les créatrices suivies · <b>1-3 stories par jour</b> (sondages, quiz, lifestyle).</div>

<div class="espace"></div>
<h2>☑ Le reporting du dimanche (non négociable)</h2>
<div class="box rouge"><b class="t">1 fois par semaine, chaque dimanche : tu remplis LE formulaire</b> (le lien est dans le Discord).<br/>
En semaine, tu peux aussi poster un petit retour dans <b>ton canal Discord privé</b> quand tu veux : on regarde tes Reels et on te fait
des retours pour que tu fasses plus de vues — et donc <b>plus de revenus</b>.<br/>
<b class="t">Sans le formulaire du dimanche : pas de suivi, pas d&#8217;évolution, pas de revenus → pas de rémunération.</b></div>

<h2>La traversée du désert (à lire les jours difficiles)</h2>
<div class="box">Les 2-3 premières semaines, les vues seront basses. <b>C&#8217;est normal, c&#8217;est prévu, et c&#8217;est là que tout le monde abandonne.</b>
La courbe est plate — puis un Reel pète et fait boule de neige. Tu ne peux pas échouer si tu publies tous les jours
et que tu t&#8217;améliores chaque semaine. Ceux qui gagnent sont ceux qui n&#8217;ont pas arrêté.</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 6 — FICHE 5
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Reels d&#8217;essai &amp; évolutions ★</span><span class="num">Fiche 5 / 6</span></div>'}
<p class="sous">Débloqués vers <b>200 abonnés</b> (environ J+10 / J+15 si ta cadence est bonne). C&#8217;est l&#8217;arme secrète : presque personne n&#8217;a la discipline de les utiliser.</p>

<h2>Les Reels d&#8217;essai (Instagram uniquement)</h2>
<ul class="check">
<li>Ce sont des <b>variantes d&#8217;un Reel existant</b>, montrées <b>uniquement à des gens qui ne te suivent pas</b> → zéro risque pour ton audience.</li>
<li>Tu varies : le <b>hook</b>, la <b>description</b>, les <b>sous-titres</b> (couleurs), le <b>filtre</b>, le <b>son</b>, la <b>caption</b>.</li>
<li>Un même contenu = plusieurs variantes = beaucoup plus de chances d&#8217;en avoir une qui pète.</li>
<li>Monte en volume : <b>+1 Reel d&#8217;essai par jour, chaque semaine</b> (comme la cadence normale).</li>
<li>Le Loom « Comment dupliquer un Reel viral en Reels d&#8217;essai » est dans le Discord.</li>
</ul>

<div class="grand-espace"></div>
<h2>Les évolutions (vers J+30 / J+60, selon tes résultats)</h2>
<table>
<tr><th>Palier</th><th>Ce qui se débloque</th></tr>
<tr><td><b>500-1 000 abonnés</b>, compte stable qui fait des vues</td><td>Passage en <b>compte professionnel</b> + association de la page Facebook
→ <b>republication automatique</b> depuis Edits (Reels, stories, carrousels publiés en double : gros gain de temps)</td></tr>
<tr><td><b>Ton installation tourne bien</b></td><td>Migration des comptes sur <b>Metricool</b> (gestion sur ordinateur) → on recrée des comptes
neufs sur ton téléphone → <b>tu gères plus, tu gagnes plus</b></td></tr>
<tr><td><b>Tu veux passer à la vitesse supérieure</b></td><td><b>2e ou 3e téléphone fourni</b> = deux ou trois fois plus de comptes, donc deux ou trois fois plus de revenus</td></tr>
<tr><td><b>Meilleur clipper de la promo</b></td><td><b>Clipper Manager</b> : tu accompagnes les autres et tu touches une commission sur leur part — la méritocratie est réelle</td></tr>
</table>

<div class="grand-espace"></div>
<h2>Le rappel</h2>
<div class="box"><b class="t">Pas de Reels d&#8217;essai sur Facebook</b> — là-bas tu publies tout, directement, dès le premier jour.
Et pas de TikTok : ça ne fait ni clics ni abonnés OnlyFans.</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 7 — FICHE 6
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Quand ça coince ⚑</span><span class="num">Fiche 6 / 6</span></div>'}
<p class="sous">Les pannes sont prévues. Ce qui compte, c&#8217;est le réflexe.</p>

<h2>Compte restreint ou banni</h2>
<ol class="etapes">
<li><b>Pas de panique</b> : ça fait partie du métier, ce n&#8217;est pas une faute. Les pages Facebook, elles, ne sautent presque jamais.</li>
<li><b>Note-le dans ton canal Discord et mentionne Gaëtan</b> (quel compte, depuis quand, ce que tu faisais) → prévoyez un créneau ensemble.</li>
<li><b>Si les bans s&#8217;enchaînent</b> : recrée un compte propre (fiche 1) <b>et demande un diagnostic à Gaëtan</b>. La cause, presque à chaque fois :
des comptes <b>connectés entre eux</b> — même adresse mail, même numéro de téléphone, ou même appareil.</li>
</ol>

<div class="espace"></div>
<h2>Tu as une question ? Le circuit (dans CET ordre)</h2>
<table>
<tr><th>Étape</th><th>Réflexe</th></tr>
<tr><td><b>1. Le chapitre du Loom</b></td><td>La formation est découpée en chapitres : Mindset · Stratégie · Création des comptes · Warm-up ·
Publication · Cadence · Essais · Évolutions. 90 % des réponses y sont.</td></tr>
<tr><td><b>2. Le canal #faq</b></td><td>Toutes les questions déjà posées 2 fois y sont écrites. Cherche avant de demander.</td></tr>
<tr><td><b>3. Le formulaire du dimanche soir</b></td><td>Toujours pas de réponse ? Pose ta question <b>avec une capture d&#8217;écran</b> dans le reporting du dimanche soir.</td></tr>
</table>

<div class="grand-espace"></div>
<div class="box rouge"><b class="t">La règle (assumée) :</b> si la réponse à ta question est dans la formation ou la FAQ, on te renverra
<b>le lien du chapitre</b>, pas une réponse personnalisée. Ce n&#8217;est pas de la mauvaise volonté : le temps gagné sert à regarder
tes Reels et à te faire des retours — ce qui te fait réellement gagner de l&#8217;argent.</div>

<div class="grand-espace"></div>
<h2>Les 3 chiffres à ne jamais oublier</h2>
<ul class="puces">
<li><b>1</b> compte créé par jour, maximum</li>
<li><b>48 h</b> sans publier au début du warm-up — et le test de l&#8217;Explorer avant de poster</li>
<li><b>+1</b> Reel par jour chaque semaine — la régularité bat l&#8217;intensité</li>
</ul>

<div class="grand-espace"></div>
<div class="box"><b class="t">Et le mindset ?</b> Il est à la fin du Loom, à écouter les jours où la traversée du désert pèse.
Résumé en une phrase : <b>tu ne peux pas échouer si tu n&#8217;abandonnes jamais</b> — et le meilleur clipper devient manager.</div>
</div>
""")

def main():
    os.makedirs(SORTIE, exist_ok=True)
    html = f"<html><head><style>{CSS}</style></head><body>{''.join(PAGES)}</body></html>"
    chemin = os.path.join(SORTIE, "Kit Clipper LTP (v2).pdf")
    HTML(string=html).write_pdf(chemin)
    print("OK", chemin)

if __name__ == "__main__":
    main()
