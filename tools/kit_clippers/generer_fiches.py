# Génère le Kit Clipper v3 dans second-brain/96-Opérations LTP/Kit Clippers/ :
#   - Kit Clipper LTP (v3).pdf      = le PDF complet (bienvenue + 6 fiches)
#   - Fiches séparées/*.pdf          = chaque fiche en fichier séparé (étape par étape)
# Usage : python3 tools/kit_clippers/generer_fiches.py
# Source de vérité unique : tools/bot_clippers/connaissances.md (base du bot, v6.2 du 14/09/2026).
# Le kit doit dire mot pour mot ce que dit la base ; si les deux divergent, c'est la base qui gagne.
# Historique :
#   v2 (14/07/2026) : setup 3 IG + 3 FB par téléphone, jamais de numéro, lien J+7 sur le privé,
#     plus de renommage des rushs, reporting du dimanche lié à la rémunération, langage collégien.
#   15/07/2026 : fiches séparées (une par fichier) en plus du PDF complet.
#   v3 (14/09/2026) : mission 100 % Instagram seul (les pages Meta hors Instagram sortent du kit) : structure 2 comptes de
#     croissance + 1 compte privé, cadence 2 Reels par jour par compte de croissance (4 publications
#     par jour), journée validée comptée par le bot, warm-up = toute la semaine 1, comptes créés au
#     créneau AVEC le manager (lundi/mercredi/vendredi 17 h, mails de l'agence, codes en direct),
#     lien posé par le manager sur le privé à J+7, « ton manager » partout (Gaëtan = contrat,
#     paiement, facture, parrainage, arnaque), règles de sortie, évolutions sans dates.

from weasyprint import HTML
import os

SORTIE = os.path.join(os.path.dirname(__file__), "..", "..",
                      "second-brain", "96-Opérations LTP", "Kit Clippers")

CSS = """
@page {
  size: A4; margin: 9mm 12mm 12mm 12mm;
  @bottom-center { content: "Kit Clipper · LTP · septembre 2026 · v3 — document interne, ne pas diffuser"; font-size: 7.5pt; color: #8a8a8a; }
  @bottom-right { content: "page " counter(page) " / " counter(pages); font-size: 7.5pt; color: #8a8a8a; }
}
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.3pt; color: #1c1c1c; line-height: 1.36; margin: 0; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
.bandeau { background: #1d3d2f; color: #fff; padding: 9px 14px; border-radius: 8px;
  display: flex; justify-content: space-between; align-items: baseline; }
.bandeau .num { font-size: 9pt; letter-spacing: 1px; text-transform: uppercase; color: #bcd9c9; }
.bandeau .titre { font-size: 16pt; font-weight: bold; }
.sous { color: #4a4a4a; font-size: 9.1pt; margin: 7px 2px 11px; }
h2 { font-size: 10.8pt; color: #1d3d2f; margin: 10px 0 5px; letter-spacing: .3px;
  border-bottom: 1.5px solid #1d3d2f; padding-bottom: 3px; }
.box { background: #eff5f1; border-left: 4px solid #1d3d2f; padding: 7px 11px; border-radius: 5px; margin: 8px 0; }
.rouge { background: #fdf0ef; border-left-color: #a33025; }
.rouge b.t { color: #a33025; }
ul.check { list-style: none; padding-left: 2px; margin: 6px 0; }
ul.check li { padding-left: 22px; text-indent: -22px; margin: 3.5px 0; }
ul.check li::before { content: "\\2610\\00a0\\00a0"; font-size: 11pt; color: #1d3d2f; }
ul.puces { margin: 6px 0 6px 18px; padding: 0; }
ul.puces li { margin: 3.5px 0; }
ol.etapes { margin: 6px 0 6px 20px; padding: 0; }
ol.etapes li { margin: 4px 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th { background: #1d3d2f; color: #fff; font-size: 8.4pt; padding: 4px 7px; text-align: left; }
td { border: 1px solid #c9d6cd; padding: 4px 7px; font-size: 8.8pt; vertical-align: top; }
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
.objectif { font-size: 10.5pt; margin: 6px 0; }
"""

IG = ('<svg width="15" height="15" viewBox="0 0 24 24" style="vertical-align:-2px">'
      '<rect x="2" y="2" width="20" height="20" rx="5.5" fill="none" stroke="#E4405F" stroke-width="2.2"/>'
      '<circle cx="12" cy="12" r="4.6" fill="none" stroke="#E4405F" stroke-width="2.2"/>'
      '<circle cx="17.4" cy="6.6" r="1.5" fill="#E4405F"/></svg>')

IG_GRAND = IG.replace('width="15" height="15"', 'width="34" height="34"')

PAGES = []

# ---------------------------------------------------------------- PAGE 1 — BIENVENUE
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Bienvenue dans l&#8217;équipe clipping</span><span class="num">LTP</span></div>'}
<p class="sous">Ta feuille de route : une page = une étape. Garde-la sous la main, presque toutes les réponses sont dedans.</p>

<h2>★ Ton objectif (dans l&#8217;ordre)</h2>
<ol class="etapes objectif">
<li>Avoir des comptes Instagram <b>propres qui durent</b></li>
<li><b>Publier tous les jours</b>, à la cadence</li>
<li>Tester <b>beaucoup</b> de formats</li>
<li><b>Refaire ce qui marche</b></li>
<li>Ramener des abonnés OnlyFans avec <b>ton lien</b> — c&#8217;est ça qui te paie</li>
</ol>

<h2><svg width="14" height="14" viewBox="0 0 24 24" style="vertical-align:-2px"><rect x="6" y="1.5" width="12" height="21" rx="2.5" fill="none" stroke="#1d3d2f" stroke-width="2"/><circle cx="12" cy="19" r="1.3" fill="#1d3d2f"/></svg> Ton matériel de travail : 3 comptes Instagram (pour 1 téléphone)</h2>
<div class="schema">
<span class="carte">{IG} Compte de croissance 1</span>
<span class="carte">{IG} Compte de croissance 2</span><br/>
<span class="fleche">↓ leur bio contient juste l&#8217;arobase @ du compte privé ↓</span><br/>
<span class="carte privee">{IG} Compte privé — <b>c&#8217;est LUI qui a le lien</b></span>
</div>
<div class="box">Les <b>2 comptes de croissance</b> publient et font des vues ; leur bio contient <b>uniquement l&#8217;arobase @ du compte privé</b>, jamais de lien.
Le <b>compte privé</b> ne publie pas, n&#8217;accepte personne et <b>porte le lien</b> : les curieux cliquent sur l&#8217;@, arrivent sur le privé, voient le lien.<br/>
<b>La cadence de croisière : 2 Reels par jour sur chaque compte de croissance = 4 publications par jour.</b> On la tient, on ne monte pas plus haut sans l&#8217;accord de ton manager (le détail est à la fiche 4).</div>
<div class="box rouge"><b class="t">La vidéo de formation parle encore de pages Facebook : saute ces passages, la mission est 100 % Instagram depuis le 14 septembre 2026.</b></div>

<h2>⚠ La règle la plus importante de toutes</h2>
<div class="box rouge"><b class="t">Tu ne postes JAMAIS une vidéo brute du Google Drive.</b> Chaque vidéo est <b>modifiée</b> avant publication : début changé, coupes, zoom, texte, sous-titres, musique, miniature.
Pourquoi ? Instagram repère les copies (le « contenu dupliqué ») et coupe les vues. Le détail est à la fiche 3.</div>

<h2>Qui contacter (à lire avant tout)</h2>
<div class="box"><b class="t">Ton manager</b> (rôle « Manager »), dans le salon de ta créatrice : tes comptes, ta créatrice, tes Reels, tes créneaux, un ban, un compte à zéro. C&#8217;est lui, pas Gaëtan.<br/>
<b class="t">Le bot</b>, dans #assistant-ia, 24 h/24 : la méthode, le kit, le parcours, la facture.<br/>
<b class="t">Gaëtan</b> (@Gaëtan dans #assistant-ia), et rien d&#8217;autre : contrat, paiement, facture bloquée, parrainage, arnaque à signaler.</div>

<h2>Ton parcours en 6 fiches</h2>
<table>
<tr><th style="width:38%">Fiche</th><th>Quand</th></tr>
<tr><td><b>1 — Créer tes comptes</b></td><td>Au créneau avec ton manager (lundi, mercredi, vendredi, 17 h Paris), 1 compte par jour</td></tr>
<tr><td><b>2 — Le warm-up</b></td><td>Toute la semaine 1, zéro publication</td></tr>
<tr><td><b>3 — Monter et poster un Reel</b></td><td>Dès la semaine 2, quand le test de l&#8217;Explorer est bon</td></tr>
<tr><td><b>4 — Ta routine et ta semaine</b></td><td>Tous les jours + le formulaire du dimanche</td></tr>
<tr><td><b>5 — Reels d&#8217;essai et évolutions</b></td><td>Vers 200 abonnés</td></tr>
<tr><td><b>6 — Quand ça coince</b></td><td>À lire dès le début, à ressortir en cas de pépin</td></tr>
</table>
</div>
""")

# ---------------------------------------------------------------- PAGE 2 — FICHE 1
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Créer tes comptes (au créneau, avec ton manager)</span><span class="num">Fiche 1 / 6</span></div>'}
<p class="sous">Avant de commencer : quiz validé + test de montage validé + (équipe France) contrat signé + ta créatrice attribuée par ton manager. Ses rushs et ses modèles sont dans son salon.</p>

<h2>Les créneaux de création (jamais seul)</h2>
<ul class="check">
<li>Tes comptes Instagram se créent <b>en direct avec ton manager</b>, aux créneaux fixes : <b>lundi, mercredi et vendredi à 17 h</b> (heure de Paris). Tu viens avec ton téléphone chargé et une bonne connexion.</li>
<li><b>Les adresses mail sont fournies par l&#8217;agence.</b> Tu ne crées pas de Gmail, tu n&#8217;inventes rien. Les <b>codes de vérification</b> arrivent sur la boîte de l&#8217;agence et te sont <b>donnés en direct pendant le créneau</b>.</li>
<li><b>1 seul compte créé par jour.</b> Jamais 2 ou 3 le même jour.</li>
<li>Pas dispo à un créneau ? <b>Préviens ton manager avant</b>, il te met sur le suivant. Ne crée <b>jamais</b> un compte seul pour « rattraper » : il sera banni et ne comptera pas.</li>
<li>Un compte, ça se remplace, ça ne se répare pas : <b>un compte banni se recrée au créneau suivant, avec lui.</b></li>
</ul>

<h2>{IG} Instagram — les règles d&#8217;or</h2>
<ul class="check">
<li>Pour chaque compte : <b>1 adresse mail + 1 mot de passe rien qu&#8217;à lui</b>, fournis par l&#8217;agence et posés au créneau. Les identifiants restent à l&#8217;agence : tu utilises les comptes, tu ne les possèdes pas.</li>
<li><b>Photo, bio et arobase @ uniques</b> pour chaque compte. Bio hyper soft, en rapport avec ta créatrice, <b>jamais de localisation</b> (ni ville, ni région).</li>
<li>✘ <b>JAMAIS ton numéro de téléphone</b> — et jamais un numéro « jetable » ou temporaire non plus. Instagram en réclame un ? Tu le dis à ton manager pendant le créneau, il gère.
Tu vois un numéro dans Profil → Paramètres → <b>Informations personnelles</b> ? Ne touche à rien, préviens ton manager.</li>
<li><b>Jamais associer les comptes entre eux</b> (ni dans le Centre de comptes Meta). Jamais de VPN.</li>
<li><b>Date de naissance clairement adulte</b>, identité cohérente : un compte qui « fait ado » est restreint.</li>
</ul>
<div class="box rouge"><b class="t">⚠ Le piège de l&#8217;association :</b> si Instagram crée ton nouveau compte <b>sans</b> demander une adresse mail et un mot de passe,
c&#8217;est qu&#8217;il est <b>associé à l&#8217;ancien</b>. Dis-le au créneau, on dissocie. Sinon, un seul ban peut emporter <b>tous</b> tes comptes d&#8217;un coup.</div>

<h2>€ Le lien (celui qui te fait gagner de l&#8217;argent)</h2>
<ul class="check">
<li>Ton lien de tracking (GetAllMyLinks) est <b>posé par ton manager</b>, jamais par toi : <b>uniquement sur le compte Instagram privé, à J+7</b>. Avant, aucun lien nulle part. Personne ne te l&#8217;envoie en MP, tu ne le colles nulle part.</li>
<li>Les 2 comptes de croissance n&#8217;ont <b>jamais</b> de lien : seulement <b>l&#8217;arobase @ du compte privé</b> dans la bio.</li>
</ul>

<h2>Si tu travailles sur ton propre téléphone</h2>
<ul class="puces">
<li><b>Un seul appareil</b> pour tes 3 comptes, toujours le même. Jamais sur un autre téléphone ni sur un ordinateur.</li>
<li><b>Tes comptes perso sont déconnectés</b> de ce téléphone : un compte perso sur le même appareil relie tout, un ban en entraîne un autre. Téléphone et Instagram <b>en français</b>.</li>
</ul>

<div class="box rouge"><b class="t">Rappel :</b> contenu 100 % propre, toujours (le détail est à la fiche 3). Et si un compte saute, ce n&#8217;est pas un drame :
tu préviens ton manager avec une capture, il le recrée avec toi au créneau suivant — voir fiche 6.</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 3 — FICHE 2
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Le warm-up (toute la semaine 1) <svg width="16" height="16" viewBox="0 0 24 24" style="vertical-align:-2px"><path d="M12 2 C13.5 7 7.5 9.5 7.5 14.5 a4.5 4.5 0 0 0 9 0 c0-1.8-.8-3.2-1.8-4.3 0 1.8-.8 2.6-1.7 3.1 .6-2.2-.3-4.6-1-11.3z" fill="#f0813c"/></svg></span><span class="num">Fiche 2 / 6</span></div>'}
<p class="sous">Le but : montrer à Instagram que ton compte est celui d&#8217;une vraie personne, une vraie utilisatrice française qui vit sa vie sur l&#8217;application.
De la création du compte au premier Reel de la semaine 2, <b>tu ne publies rien</b>.</p>

<h2>Toute la semaine 1 (aucune publication)</h2>
<ul class="check">
<li><b>Zéro publication pendant toute la semaine 1.</b> Le premier Reel, c&#8217;est en semaine 2 (1 par jour par compte de croissance).</li>
<li>Chaque jour, un peu, comme une vraie utilisatrice — jamais en rafale.</li>
<li>Regarde <b>uniquement des Reels de créatrices françaises</b> (la liste est dans #ressources).</li>
<li><b>Abonne-toi</b> aux créatrices de la liste + <b>active les notifications</b> Reels.</li>
<li>Like, regarde les Reels <b>en entier</b>, commente un peu — bien écrit, en français.</li>
<li><b>Enregistre les meilleurs Reels</b> : tu les reproduiras plus tard.</li>
</ul>
<div class="box">Tout le warm-up et toutes les interactions se font <b>en français, avec des créatrices françaises</b> : c&#8217;est ce qui apprend à Instagram à qui montrer tes Reels.
La semaine 1 (warm-up) et la semaine 2 (montée) <b>ne comptent pas contre toi</b> pour les journées validées.</div>

<div class="espace"></div>
<h2>Pourquoi activer les notifications ?</h2>
<div class="box">Un commentaire <b>bien écrit</b> sous un Reel tout frais d&#8217;une grosse créatrice = vu par <b>des milliers de gens</b>.
C&#8217;est de la visibilité gratuite — mais seulement si le commentaire est drôle ou utile. Les commentaires de robot font bloquer le compte.</div>

<div class="espace"></div>
<h2>✔ LE test de fin de warm-up (à partir du 2ᵉ jour)</h2>
<div class="box"><b class="t">Ouvre ton onglet Explorer :</b><br/><br/>
→ Il te montre des <b>créatrices françaises</b> ? Ton compte est chaud ✔ Mais on attend quand même la <b>semaine 2</b> pour publier (fiche 3).<br/><br/>
→ Il montre autre chose ? Le warm-up n&#8217;est <b>pas</b> fini : continue les interactions naturelles. Ce n&#8217;est pas une question de durée,
c&#8217;est une question de signal. Si ça ne vient pas après plusieurs jours, tu as fait trop d&#8217;actions trop vite : <b>dis-le à ton manager</b>.</div>

<div class="espace"></div>
<h2>✘ Les erreurs qui cassent un warm-up</h2>
<ul class="puces">
<li>Publier en semaine 1</li>
<li>Regarder du contenu hors sujet (ton fil doit rester 100 % créatrices françaises)</li>
<li>Les rafales : 50 likes en 5 minutes = comportement de robot</li>
<li>Un lien posé trop tôt (il arrive à J+7, sur le compte privé seulement, posé par ton manager — fiche 1)</li>
<li>Te connecter au même compte depuis plusieurs appareils</li>
</ul>

<div class="logo-bas">{IG_GRAND}</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 4 — FICHE 3
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Monter et poster un Reel</span><span class="num">Fiche 3 / 6</span></div>'}
<p class="sous">L&#8217;application : <b>Edits</b> (le monteur vidéo d&#8217;Instagram, gratuit, sous-titres automatiques inclus). La routine : <b>les brouillons le matin</b>, la publication étalée dans la journée.</p>

<h2>La préparation (une seule fois)</h2>
<ul class="check">
<li>Télécharge les <b>bases</b> (= le top 10 des Reels de TA créatrice, dans son salon : ce qui a déjà marché).</li>
<li>Importe-les <b>en template</b> dans Edits : extraire le son · dupliquer la caption.</li>
</ul>

<div class="espace"></div>
<h2>La boucle par Reel (10-15 min au début, 5 min avec l&#8217;habitude)</h2>
<ol class="etapes">
<li>Télécharge <b>un rush</b> depuis le Drive de ta créatrice (tu ne renommes jamais rien dedans : il est partagé avec toute l&#8217;équipe).</li>
<li>Dans Edits : <b>« Remplacer le rush »</b> du template par celui que tu viens de prendre.</li>
<li>Modifie : <b>filtre</b> · <b>début et fin coupés</b> · <b>zoom ou cadrage</b> · <b>son</b> (celui de la base ou un son populaire) ·
<b>caption</b> (celle de la base ou une variante — 100 idées dans #ressources) · <b>sous-titres</b> si elle parle · <b>miniature</b>.</li>
<li>Mets en <b>brouillon</b> le matin → publie étalé dans la journée (pas de programmation automatique).</li>
<li>Publie sur <b>Instagram</b>.</li>
</ol>

<div class="box rouge"><b class="t">⚠ Avant de publier, pose-toi UNE question : est-ce que ma vidéo ressemble encore au rush du Drive ?</b><br/>
Si oui → tu ne postes pas, tu modifies encore. Chaque vidéo publiée doit avoir : un début changé, des coupes, une caption,
un hook fort dès la première seconde, et un son ou un filtre différent.</div>

<div class="espace"></div>
<h2>Ce qui fait performer un Reel (tout le reste compte moins)</h2>
<ul class="puces">
<li><b>Le hook</b> — la première seconde donne envie de rester : le début du rush est coupé, on entre direct dans l&#8217;action.</li>
<li><b>Le partage</b> — une vidéo qu&#8217;on a envie d&#8217;envoyer à un ami.</li>
<li><b>Un montage propre</b> — coupes nettes, zoom, sous-titres lisibles, une durée proche de la trend d&#8217;origine (elle dure 8 secondes ? la tienne aussi, pas 13).
Si elle parle, on garde <b>SA voix</b>. La <b>miniature</b> est obligatoire : claire, contrastée, le visage ou l&#8217;action principale. Hashtags : 3 à 5 simples, ils comptent peu.</li>
</ul>
<div class="box"><b class="t">Le même rush sur tes 2 comptes de croissance ?</b> Oui, mais <b>jamais le même montage</b> : hook, caption, sous-titres différents (3 minutes avec ton template).
Deux comptes qui postent la même vidéo = vues coupées + comptes reliés.</div>

<div class="espace"></div>
<h2>✔ Autorisé / ✘ Interdit</h2>
<table>
<tr><th>✔ Ce qu&#8217;on poste</th><th>✘ Ce qu&#8217;on ne poste jamais</th></tr>
<tr><td>Tenues couvertes · street, décontracté, sport · tenue de soirée habillée</td><td>Bikinis · sous-vêtements · poses provocantes</td></tr>
<tr><td>Hooks sur la personnalité · humour · une histoire · une situation où on se reconnaît</td><td>Les textes « écris-moi en privé », « lien en bio », « contenu exclusif »</td></tr>
<tr><td>Des vidéos qui donnent envie de commenter</td><td>Toute mention d&#8217;argent, de drogue ou d&#8217;OnlyFans · les sous-entendus sexuels et les émojis trop chauds</td></tr>
</table>
<div class="box"><b class="t">Objectif : des comptes propres qui durent.</b> La qualité vient en publiant beaucoup et en corrigeant un détail à chaque fois.</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 5 — FICHE 4
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Ta routine et ta semaine</span><span class="num">Fiche 4 / 6</span></div>'}
<p class="sous">Le but n&#8217;est pas d&#8217;être parfait. Le but est de <b>publier tous les jours, à la cadence</b>, et de s&#8217;améliorer un peu chaque semaine.</p>

<h2>Ta routine du jour</h2>
<ol class="etapes">
<li>Je prends un rush sur le Drive de ma créatrice et je fais mon montage sur Edits (fiche 3)</li>
<li>Je publie <b>2 Reels sur chaque compte de croissance</b> (jamais le même montage sur les deux)</li>
<li>Je fais quelques commentaires naturels, et je réponds aux commentaires sous mes Reels (court, soft, sans lien)</li>
<li>Je regarde mes statistiques et <b>je refais les formats qui marchent</b></li>
</ol>

<h2>Ta montée en puissance, semaine par semaine</h2>
<p class="petit">Sur chacun de tes 2 comptes Instagram de croissance :</p>
<table>
<tr><th>Semaine</th><th>Ce qu&#8217;on attend de toi</th></tr>
<tr><td><b>Semaine 1</b></td><td>Création des comptes aux créneaux + warm-up (fiche 2) — <b>zéro publication</b></td></tr>
<tr><td><b>Semaine 2</b></td><td><b>1 Reel par jour</b> et par compte de croissance</td></tr>
<tr><td><b>Semaine 3 et après</b></td><td><b>2 Reels par jour</b> et par compte de croissance = <b>4 publications par jour</b>, la croisière. On ne monte pas plus haut sans l&#8217;accord de ton manager. Et le formulaire <b>chaque dimanche</b>.</td></tr>
<tr><td><b>Vers 200 abonnés</b></td><td>Les Reels d&#8217;essai de la fiche 5 se débloquent ★</td></tr>
</table>
<div class="box"><b class="t">Une journée validée</b> = tes <b>3 comptes sont vivants</b> ET tu as publié <b>2 Reels sur chaque compte de croissance</b> ce jour-là (de minuit à minuit, heure de Paris).
C&#8217;est le bot qui compte : ton rapport du matin te dit si la veille est validée, et pourquoi. Les semaines 1 et 2 ne comptent pas contre toi.</div>
<div class="box">Autour des Reels : <b>2-3 carrousels par semaine</b> (dès qu&#8217;un Reel pète → un carrousel dans la foulée, c&#8217;est là qu&#8217;ils explosent) ·
<b>1-3 stories par jour</b> (sondages, quiz, lifestyle ; celles du Drive jamais brutes) · <b>1-10 commentaires par jour</b> chez les créatrices suivies.</div>

<h2>☑ Le reporting du dimanche (non négociable)</h2>
<div class="box rouge"><b class="t">Chaque dimanche, tu remplis LE formulaire</b> (épinglé dans #reporting), avec <b>les liens de tes Reels qui ont le mieux marché</b> :
c&#8217;est comme ça qu&#8217;un concept gagnant repart en tournage chez ta créatrice.<br/>
En semaine, ton manager relit au moins 2 de tes Reels et te donne un conseil simple. Tu veux plus de retours ? Poste tes Reels dans <b>le salon de ta créatrice</b>.<br/>
<b class="t">Pas de formulaire = pas de suivi = pas de fixe.</b></div>

<h2>Les règles du jeu (annoncées dès le départ)</h2>
<ul class="puces">
<li><b>Cadence non tenue 2 jours de suite = sortie le lundi suivant.</b> Ton manager te prévient dès le 2ᵉ jour.</li>
<li><b>Moins de 50 abonnés OnlyFans venus de ton lien sur ton premier mois de publication = sortie.</b> On garde les meilleurs, on en ajoute chaque semaine.</li>
<li>Absent (maladie, examens, vacances) ? <b>Préviens ton manager AVANT, en MP, avec les dates</b> : une absence prévenue n&#8217;est pas une sortie.
Les journées non publiées ne sont pas validées : ton fixe et ta prime suivent tes journées validées.</li>
</ul>

<h2>La traversée du désert (à lire les jours difficiles)</h2>
<div class="box">Les 2-3 premières semaines, les vues seront basses. <b>C&#8217;est normal, c&#8217;est prévu, et c&#8217;est là que tout le monde abandonne.</b>
La courbe est plate — puis un Reel pète et fait boule de neige. Tu ne peux pas échouer si tu publies tous les jours et que tu t&#8217;améliores chaque semaine.</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 6 — FICHE 5
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Reels d&#8217;essai &amp; évolutions ★</span><span class="num">Fiche 5 / 6</span></div>'}
<p class="sous">Débloqués vers <b>200 abonnés Instagram</b> (environ J+15 si ta cadence est bonne). C&#8217;est l&#8217;arme secrète : presque personne n&#8217;a la discipline de les utiliser.</p>

<h2>Les Reels d&#8217;essai (Instagram uniquement)</h2>
<ul class="check">
<li>Ce sont des <b>variantes d&#8217;un Reel existant</b>, montrées à des gens <b>qui ne suivent pas le compte</b> → zéro risque pour ton audience, et de la portée gratuite en plus.</li>
<li>Dès qu&#8217;un Reel marche, <b>duplique-le TOI-MÊME</b> : change surtout le <b>montage</b> et le <b>hook</b>, puis la <b>caption</b>, les <b>sous-titres</b>, le <b>filtre</b>, le <b>son</b>.</li>
<li>Même rush, plusieurs angles = beaucoup plus de chances qu&#8217;un pète.</li>
<li>Chaque dimanche, regarde tes Reels qui ont le mieux marché et refais-les en variantes. Le lien du Reel gagnant va aussi dans ton formulaire : le concept repart en tournage chez ta créatrice.</li>
</ul>

<div class="grand-espace"></div>
<h2>Les évolutions (décidées par ton manager, selon tes résultats — pas de date)</h2>
<table>
<tr><th>Palier</th><th>Ce qui se débloque</th></tr>
<tr><td><b>500-1 000 abonnés</b>, compte stable qui fait des vues</td><td>Passage en <b>compte professionnel</b> (statistiques détaillées). Tu ne le fais <b>jamais seul</b> :
jusqu&#8217;à sa décision, la règle reste « jamais de comptes reliés ».</td></tr>
<tr><td><b>Ton installation tourne bien</b></td><td>Migration des comptes sur <b>Metricool</b> (gestion sur ordinateur), quand ton manager le décide, sans date fixe
→ on recrée des comptes neufs sur ton téléphone → <b>tu gères plus, tu gagnes plus</b></td></tr>
<tr><td><b>Tu veux passer à la vitesse supérieure</b></td><td><b>Un 2ᵉ téléphone = un 2ᵉ setup de 3 comptes</b> = deux fois plus de revenus</td></tr>
<tr><td><b>Meilleur clipper de la promo</b></td><td><b>Clipper Manager</b> : tu accompagnes les autres — la méritocratie est réelle</td></tr>
</table>

<div class="grand-espace"></div>
<h2>Le rappel</h2>
<div class="box"><b class="t">Instagram, et rien d&#8217;autre.</b> Pas de TikTok, pas de YouTube : ça ne fait ni clics ni abonnés OnlyFans.
Mieux vaut tenir la cadence sur tes 3 comptes que créer trop de comptes ou monter à 6 Reels par jour sans l&#8217;accord de ton manager.</div>
</div>
""")

# ---------------------------------------------------------------- PAGE 7 — FICHE 6
PAGES.append(f"""
<div class="page">
{'<div class="bandeau"><span class="titre">Quand ça coince ⚑</span><span class="num">Fiche 6 / 6</span></div>'}
<p class="sous">Les pannes sont prévues. Ce qui compte, c&#8217;est le réflexe : <b>ton manager</b>, dans le salon de ta créatrice, avec une capture.</p>

<h2>Compte restreint ou banni</h2>
<ol class="etapes">
<li><b>Pas de panique</b> : ce n&#8217;est pas une faute, c&#8217;est le métier. <b>Ne tente rien seul</b> : pas d&#8217;appel, pas de nouveau compte, pas de numéro.</li>
<li><b>Écris tout de suite à ton manager, dans le salon de ta créatrice</b> : quel compte, depuis quand, <b>une capture</b>.</li>
<li>Il le <b>recrée avec toi au créneau suivant</b> (lundi, mercredi ou vendredi à 17 h).</li>
<li>En attendant, tu continues sur tes autres comptes : plus vite il est recréé, moins tu perds de journées validées (il faut 3 comptes vivants).</li>
</ol>
<div class="box">Les bans s&#8217;enchaînent ? C&#8217;est ton manager qui cherche la cause : des comptes <b>reliés entre eux</b> (même mail, même numéro, même appareil) ou un compte qui « fait ado ».
« Pas recommandé aux moins de 18 ans » ? Pas grave, c&#8217;est attendu sur notre niche. Grave : une restriction générale <b>sans</b> mention d&#8217;âge, ou des suppressions de Reels répétées → capture à ton manager.</div>

<h2>Les autres pépins</h2>
<table>
<tr><th>Ça coince</th><th>Le réflexe</th></tr>
<tr><td><b>Mes Reels font 0 vue depuis 2-3 jours</b></td><td>200 vues = le contenu ne plaît pas, on le change. <b>0 vue plusieurs jours de suite</b> = signal de restriction : ne change rien seul, envoie à ton manager une capture de tes stats et de l&#8217;écran « Statut du compte ».</td></tr>
<tr><td><b>Des MP arrivent sur mes comptes</b></td><td>On ne répond <b>pas en MP</b> et on n&#8217;en envoie jamais en masse (cause n°1 des bans). Réponds en story (capture du MP) ou en commentaire. Jamais de lien OnlyFans en MP : les clics passent par le lien en bio.</td></tr>
<tr><td><b>Un inconnu m&#8217;envoie une « offre » en MP</b></td><td>Arnaque ou débauchage : l&#8217;agence ne te contacte jamais en MP pour un autre job. Ne réponds pas, bloque, signale à Gaëtan avec une capture.</td></tr>
</table>

<h2>Tu as une question ? Le circuit (dans CET ordre)</h2>
<table>
<tr><th>Étape</th><th>Réflexe</th></tr>
<tr><td><b>1. Le chapitre de la vidéo</b></td><td>La formation (le Loom, dans le forum formation), chapitre par chapitre : 90 % des réponses y sont. Cherche avant de demander.</td></tr>
<tr><td><b>2. Le bot dans #assistant-ia</b></td><td>24 h/24 : la méthode, le kit, le parcours, la facture. S&#8217;il ne sait pas, il te dit vers qui aller.</td></tr>
<tr><td><b>3. Ton manager</b></td><td>Tes comptes, ta créatrice, tes Reels, tes créneaux — dans le salon de ta créatrice.
Contrat, paiement, facture bloquée, parrainage, arnaque : @Gaëtan dans #assistant-ia, et rien d&#8217;autre.</td></tr>
<tr><td><b>4. Le formulaire du dimanche</b></td><td>Pour les retours de fond, <b>avec une capture d&#8217;écran</b>.</td></tr>
</table>
<div class="box rouge"><b class="t">La règle (assumée) :</b> si la réponse est dans la formation, on te renvoie <b>au chapitre</b>, pas une réponse personnalisée. Le temps gagné sert à relire tes Reels et à te faire des retours.</div>

<h2>Les 3 chiffres à ne jamais oublier</h2>
<ul class="puces">
<li><b>1</b> compte créé par jour, maximum — au créneau, avec ton manager</li>
<li><b>Semaine 1</b> sans publier — et le test de l&#8217;Explorer avant de poster</li>
<li><b>2</b> Reels par jour sur chaque compte de croissance — la régularité bat l&#8217;intensité</li>
</ul>

<div class="box"><b class="t">Et le mindset ?</b> À la fin du Loom, à écouter les jours difficiles : <b>tu ne peux pas échouer si tu n&#8217;abandonnes jamais</b> — et le meilleur clipper devient manager.</div>
</div>
""")

# Noms des fichiers séparés, dans le même ordre que PAGES ci-dessus (une entrée = une page/fiche).
NOMS_FICHES = [
    "00 - Bienvenue.pdf",
    "Fiche 1 - Creer tes comptes (au creneau).pdf",
    "Fiche 2 - Le warm-up (semaine 1).pdf",
    "Fiche 3 - Monter et poster un Reel.pdf",
    "Fiche 4 - Ta routine et ta semaine.pdf",
    "Fiche 5 - Reels d essai et evolutions.pdf",
    "Fiche 6 - Quand ca coince.pdf",
]

def enrober(corps_html):
    return f"<html><head><style>{CSS}</style></head><body>{corps_html}</body></html>"

def main():
    os.makedirs(SORTIE, exist_ok=True)

    # 1. Le PDF complet (toutes les fiches à la suite).
    complet = os.path.join(SORTIE, "Kit Clipper LTP (v3).pdf")
    HTML(string=enrober("".join(PAGES))).write_pdf(complet)
    print("OK (complet)", complet)

    # 2. Chaque fiche en fichier séparé, dans un sous-dossier.
    dossier_fiches = os.path.join(SORTIE, "Fiches séparées")
    os.makedirs(dossier_fiches, exist_ok=True)
    assert len(NOMS_FICHES) == len(PAGES), "NOMS_FICHES et PAGES doivent avoir la même longueur"
    for nom, page in zip(NOMS_FICHES, PAGES):
        chemin = os.path.join(dossier_fiches, nom)
        HTML(string=enrober(page)).write_pdf(chemin)
        print("OK (fiche) ", chemin)

if __name__ == "__main__":
    main()
