# Génère les fiches A4 du Kit Clippers (PDF) dans second-brain/96-Opérations LTP/Kit Clippers/
# Usage : python3 tools/kit_clippers/generer_fiches.py
# Source de vérité : la formation Loom clipping de Gaëtan (transcript 13/07/2026).
# Une fiche = une page A4 = l'étape où le clipper en est. Le Loom reste la bibliothèque.

from weasyprint import HTML
import os

SORTIE = os.path.join(os.path.dirname(__file__), "..", "..",
                      "second-brain", "96-Opérations LTP", "Kit Clippers")

CSS = """
@page {
  size: A4; margin: 12mm 14mm 14mm 14mm;
  @bottom-center { content: "Kit Clippers · LTP · juillet 2026 · v1 — document interne, ne pas diffuser"; font-size: 7.5pt; color: #8a8a8a; }
}
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.6pt; color: #1c1c1c; line-height: 1.42; margin: 0; }
.bandeau { background: #1d3d2f; color: #fff; padding: 7px 12px; border-radius: 6px;
  display: flex; justify-content: space-between; align-items: baseline; }
.bandeau .num { font-size: 8.5pt; letter-spacing: 1px; text-transform: uppercase; color: #bcd9c9; }
.bandeau .titre { font-size: 15pt; font-weight: bold; }
.sous { color: #4a4a4a; font-size: 9pt; margin: 5px 2px 10px; }
h2 { font-size: 10.5pt; color: #1d3d2f; margin: 10px 0 4px; text-transform: uppercase; letter-spacing: .5px;
  border-bottom: 1.5px solid #1d3d2f; padding-bottom: 2px; }
.box { background: #eff5f1; border-left: 3.5px solid #1d3d2f; padding: 7px 10px; border-radius: 4px; margin: 6px 0; }
.rouge { background: #fdf0ef; border-left-color: #a33025; }
.rouge b.t { color: #a33025; }
ul.check { list-style: none; padding-left: 2px; margin: 4px 0; }
ul.check li { padding-left: 20px; text-indent: -20px; margin: 2.5px 0; }
ul.check li::before { content: "\\2610\\00a0\\00a0"; font-size: 11pt; color: #1d3d2f; }
ul.puces { margin: 4px 0 4px 16px; padding: 0; }
ul.puces li { margin: 2.5px 0; }
table { border-collapse: collapse; width: 100%; margin: 5px 0; }
th { background: #1d3d2f; color: #fff; font-size: 8.3pt; padding: 4px 6px; text-align: left; }
td { border: 1px solid #c9d6cd; padding: 4px 6px; font-size: 8.8pt; vertical-align: top; }
b.t { color: #1d3d2f; }
.petit { font-size: 8.3pt; color: #555; }
"""

def bandeau(num, titre):
    return f'<div class="bandeau"><span class="titre">{titre}</span><span class="num">{num}</span></div>'

FICHES = {}

FICHES["Fiche 1 - J0 creation des comptes.pdf"] = bandeau("Fiche 1 / 6", "J0 — Création des comptes") + """
<p class="sous">Avant de commencer : quiz de formation validé (8/10 minimum) + Gmail envoyé à Gaëtan (accès au Drive de ta créatrice).</p>
<h2>Instagram — les règles d'or</h2>
<ul class="check">
<li><b>1 seul compte Instagram créé par jour</b> — jamais les 4 d'un coup</li>
<li>Photo, bio, nom et username <b>UNIQUES pour chaque compte</b> (photo depuis le Drive de la créatrice)</li>
<li><b>1 adresse mail + 1 mot de passe par compte</b> (créés avec Gaëtan) + 2FA activé</li>
<li><b>JAMAIS associer les comptes dans le Meta Center</b> — sinon bans en chaîne</li>
<li>Pas trop d'actions le premier jour : agis comme un humain normal</li>
<li><b>Lien GAML : à J+7 seulement</b> sur Instagram (demande ton lien à Gaëtan) — jamais à la création</li>
</ul>
<h2>Facebook — la page associée</h2>
<ul class="check">
<li>App Facebook, connexion avec <b>ton compte perso</b> (tes amis ne voient PAS tes pages)</li>
<li>La page reprend <b>la même identité</b> que le compte Instagram associé (photo, bio, nom, username)</li>
<li><b>Lien dès J0</b> sur Facebook : dans la bio ET sur le profil</li>
<li>Léger warm-up puis tu peux <b>publier dès le premier jour</b> sur Facebook</li>
</ul>
<h2>Ton setup cible (1 téléphone)</h2>
<div class="box"><b class="t">4 paires</b> = 4 comptes Instagram + 4 pages Facebook jumelles (ex. « LaPetiteLucie » IG + FB).
Sur Instagram : <b>3 comptes actifs + 1 compte privé</b>. Les 3 façons de rediriger, une par compte :</div>
<table>
<tr><th>Méthode</th><th>Conversion</th><th>Risque</th></tr>
<tr><td><b>Lien en bio</b></td><td>La meilleure</td><td>Le plus dangereux</td></tr>
<tr><td><b>Arobase en bio → compte IG privé</b> (lien dans le privé)</td><td>Moyenne</td><td>Moyen</td></tr>
<tr><td><b>Lien en story à la une</b></td><td>La moins bonne</td><td>Le plus safe</td></tr>
</table>
<div class="box rouge"><b class="t">Rappel :</b> contenu 100 % safe plateforme, toujours. Et si un compte saute, ce n'est pas un drame —
c'est un coût d'exploitation : on le note au reporting et on recrée (1 par jour). Voir Fiche 6.</div>
"""

FICHES["Fiche 2 - Warm-up Instagram.pdf"] = bandeau("Fiche 2 / 6", "Warm-up Instagram (J0 → J+2/4)") + """
<p class="sous">Le but : montrer à Instagram que tu es une créatrice française qui interagit naturellement avec ses copines créatrices. Facebook n'a PAS besoin de warm-up : publie dès J0.</p>
<h2>Les 48 premières heures</h2>
<ul class="check">
<li><b>Zéro publication pendant 48 h</b></li>
<li>Consommer <b>uniquement du contenu de créatrices OF françaises</b> (la liste est dans le Discord)</li>
<li><b>Follow</b> les créatrices de la liste + <b>activer les notifications</b> Reels et carrousels</li>
<li>Liker, regarder les Reels en entier, <b>commenter légèrement</b> — comme une vraie utilisatrice</li>
<li><b>Enregistrer les meilleurs Reels</b> de ces créatrices (tu les reproduiras plus tard)</li>
</ul>
<h2>Pourquoi les notifications ?</h2>
<div class="box">Commenter un Reel <b>dans les minutes qui suivent sa publication</b> sur une grosse créatrice = ton commentaire vu par
10 000-200 000 personnes. C'est de la visibilité gratuite — mais uniquement si le commentaire est <b>bien écrit, drôle ou utile</b>
(les commentaires de bot font bloquer ton compte). Le guide des bons commentaires est dans le Discord.</div>
<h2>✅ LE test de fin de warm-up (le seul qui compte)</h2>
<div class="box"><b class="t">Ouvre ton onglet Explorer :</b><br/>
→ Il montre des <b>créatrices OF françaises</b> ? Ton warm-up est terminé, passe à la Fiche 3.<br/>
→ Il montre autre chose ? Le warm-up n'est <b>pas</b> fini — continue les interactions naturelles (ce n'est pas une question de durée,
c'est une question de signal). Si ça ne vient pas après plusieurs jours : tu as fait trop d'actions trop vite, demande conseil.</div>
<h2>Les erreurs qui cassent un warm-up</h2>
<ul class="puces">
<li>Publier avant la fin des 48 h</li>
<li>Interagir avec du contenu hors niche (ton feed doit rester 100 % créatrices FR)</li>
<li>Rafales d'actions (50 likes en 5 minutes = comportement de bot)</li>
<li>Mettre le lien en bio pendant le warm-up (il arrive à J+7, Fiche 1)</li>
</ul>
"""

FICHES["Fiche 3 - Posting quotidien (checklist Edit).pdf"] = bandeau("Fiche 3 / 6", "Posting quotidien — checklist Edit") + """
<p class="sous">L'app : <b>Edit</b> (le videomaker d'Instagram — captions, sons populaires et publication IG + FB intégrés). La routine : <b>1 h le matin en brouillons, publication étalée dans la journée</b>.</p>
<h2>La préparation (une fois)</h2>
<ul class="check">
<li>Télécharger les <b>bases</b> depuis le Discord (= le top 10 des Reels de TA créatrice — ce qui a déjà marché)</li>
<li>Les importer <b>en template</b> dans Edit : extraire l'audio · dupliquer la caption · renommer le template</li>
</ul>
<h2>La boucle par Reel (10-15 min au début, 5 min avec l'habitude)</h2>
<ul class="check">
<li>Télécharger <b>un rush brut</b> depuis le Google Drive de la créatrice</li>
<li><b>Le renommer avec un 👍</b> immédiatement (3 petits points → renommer) — évite que deux clippers utilisent le même rush</li>
<li>Dans Edit : <b>« Remplacer le rush »</b> du template par celui que tu viens de prendre</li>
<li>Ajuster le <b>filtre</b> (cinématique ou classique marchent bien)</li>
<li>Ajuster la <b>durée</b> : crop le début et la fin (surtout si gestes trop suggestifs — safe plateforme !)</li>
<li>Le <b>son</b> : audio de la trend de base OU un son populaire Instagram</li>
<li>La <b>caption</b> (texte à l'écran) : celle de la base, ou une variante (100 idées de captions dans le Discord)</li>
<li><b>Sous-titres automatiques</b> si la créatrice parle (et varie les templates de couleurs : rose, noir, blanc…)</li>
<li>Mettre en <b>brouillon</b> le matin → publier étalé dans la journée (pas de programmation : moins de reach)</li>
<li>Publier sur <b>Instagram ET la page Facebook</b> (à la main au début, 1 et 1 depuis Edit)</li>
</ul>
<div class="box"><b class="t">Plus tu modifies (filtre + durée + son + caption), plus ton Reel est unique aux yeux d'Instagram — et meilleur il performe.</b></div>
<h2>Ce qui fait performer un Reel (tout le reste est du bruit)</h2>
<div class="box"><b class="t">1. Le hook</b> (la première seconde) = 90 % du problème résolu. <b class="t">2. Le taux de partage</b> (un Reel qu'on envoie à un pote) = les 10 % restants.
Concentre chaque choix (caption, son, crop) sur ces deux critères. Le Loom « Comment je crée des Reels performants » est dans le Discord.</div>
"""

FICHES["Fiche 4 - Cadence hebdomadaire.pdf"] = bandeau("Fiche 4 / 6", "La cadence (par compte actif)") + """
<p class="sous">C'est la cadence qui nous fait tester plus vite que la concurrence. Un Reel qui pète fait péter les autres — le plus dur, c'est le premier.</p>
<h2>Par ordre d'importance</h2>
<table>
<tr><th>Quoi</th><th>Combien</th><th>Pourquoi</th></tr>
<tr><td><b>1. Reels</b></td><td><b>1 → 10 par jour</b> : semaine 1 = 1/jour, semaine 2 = 2/jour, semaine 3 = 3/jour… (+1 par semaine)</td><td>C'est ça qui fait la différence — la montée progressive fait « vrai humain »</td></tr>
<tr><td><b>2. Carrousels</b></td><td><b>2-3 par semaine</b></td><td>Followers + crédibilité + conversion. Lifestyle habillé (resto, salle de sport, Pinterest), musiques tendance. <b>Dès qu'un Reel pète → poste un carrousel</b> (c'est là qu'ils explosent)</td></tr>
<tr><td><b>3. Commentaires</b></td><td><b>1-10 par jour</b> sur les créatrices suivies (notifications activées)</td><td>Bien écrits, drôles, utiles, ou des questions — jamais des commentaires de bot</td></tr>
<tr><td><b>4. Stories</b></td><td><b>1-3 par jour</b></td><td>Lifestyle, sondages, quiz — l'engagement envoie de très bons signaux à Instagram et construit la communauté qui clique</td></tr>
</table>
<h2>Le reporting (non négociable)</h2>
<div class="box"><b class="t">1 fois par jour, dans ton salon Discord :</b> ce que tu as publié, les vues, les comptes actifs/restreints.
C'est ce qui permet d'avoir des retours sur tes Reels et de t'améliorer — <b>plus de retours = plus de vues = plus de revenus</b>.
Pas de reporting = pas de suivi = pas d'évolution.</div>
<h2>La traversée du désert (lis ça les jours difficiles)</h2>
<div class="box">Les 2-3 premières semaines, les vues seront basses. <b>C'est normal, c'est prévu, et c'est là que tous les concurrents abandonnent.</b>
La courbe est plate, plate, plate — puis un Reel pète et fait boule de neige (profil → autres Reels → autre Reel qui pète).
Tu ne peux pas échouer si tu publies tous les jours et que tu t'améliores chaque semaine. Ceux qui gagnent sont juste ceux qui n'ont pas arrêté.</div>
"""

FICHES["Fiche 5 - Reels d essai et evolutions.pdf"] = bandeau("Fiche 5 / 6", "Reels d'essai & évolutions") + """
<p class="sous">Débloqués vers <b>200 followers</b> (≈ J+10 / J+15 si ta cadence est bonne). C'est l'arme secrète : personne n'a la discipline de les utiliser.</p>
<h2>Les Reels d'essai (Instagram uniquement)</h2>
<ul class="check">
<li>Ce sont des <b>variantes d'un Reel existant</b> montrées <b>uniquement à des non-followers</b> → zéro risque pour ton audience</li>
<li>Varier : le <b>hook</b>, la <b>description</b>, les <b>sous-titres</b> (templates de couleurs), le <b>filtre</b>, le <b>son</b>, la <b>caption</b></li>
<li>Un même contenu = plusieurs variantes = beaucoup plus de chances d'en avoir une qui pète</li>
<li>Monter en volume : <b>+1 Reel d'essai par jour, par semaine</b> (comme la cadence normale)</li>
<li>Le Loom « Comment dupliquer un Reel viral en Reels d'essai » est dans le Discord</li>
</ul>
<h2>Les évolutions (à J+30 / J+60 selon tes résultats)</h2>
<table>
<tr><th>Palier</th><th>Ce qui se débloque</th></tr>
<tr><td><b>IG à 500-1 000 followers</b>, stable et qui fait des vues</td><td>Passage en <b>compte professionnel</b> + association de la page Facebook → <b>repost automatique</b> depuis Edit (Reels, stories, carrousels publiés en double, gros gain de temps)</td></tr>
<tr><td><b>Setup qui tourne bien</b></td><td>Migration des comptes sur <b>Metricool</b> (gestion sur ordinateur) → on recrée des comptes neufs sur ton téléphone → <b>tu gères plus, tu gagnes plus</b></td></tr>
<tr><td><b>Tu veux scaler</b></td><td><b>2e ou 3e téléphone fourni</b> = ×2 / ×3 comptes, donc ×2 / ×3 revenus</td></tr>
<tr><td><b>Meilleur clipper de la promo</b></td><td><b>Clipper Manager</b> : tu manages les autres, commission sur leur part — la méritocratie est réelle</td></tr>
</table>
<div class="box"><b class="t">Rappel :</b> pas de Reels d'essai sur Facebook — là-bas tu publies tout, directement, dès J0. Et pas de TikTok : ça ne fait ni clics ni subs.</div>
"""

FICHES["Fiche 6 - Quand ca coince.pdf"] = bandeau("Fiche 6 / 6", "Quand ça coince") + """
<p class="sous">Les pannes sont prévues. Ce qui compte, c'est le réflexe.</p>
<h2>Compte restreint ou banni</h2>
<ul class="check">
<li><b>Pas de panique</b> : c'est un coût d'exploitation du métier, pas une faute — les pages Facebook, elles, ne sautent quasiment jamais</li>
<li>Le <b>noter dans ton reporting du jour</b> (quel compte, depuis quand, ce que tu faisais)</li>
<li><b>Recréer</b> (1 compte par jour, Fiche 1) et continuer la cadence sur les autres comptes</li>
<li>Si les bans s'enchaînent → demande un diagnostic : c'est presque toujours Meta Center, des actions trop rapides, ou le lien trop tôt</li>
</ul>
<h2>Tu as une question ? Le circuit (dans CET ordre)</h2>
<table>
<tr><th>Étape</th><th>Réflexe</th></tr>
<tr><td><b>1. Le chapitre du Loom</b></td><td>La formation est chapitrée : Mindset · Stratégie · Création des comptes · Warm-up · Posting · Cadence · Essais · Évolutions. 90 % des réponses y sont.</td></tr>
<tr><td><b>2. Le canal #faq</b></td><td>Toutes les questions déjà posées 2 fois y sont écrites. Cherche avant de demander.</td></tr>
<tr><td><b>3. Ton reporting</b></td><td>Toujours pas de réponse ? Pose la question <b>avec une capture d'écran</b> dans ton reporting du jour.</td></tr>
</table>
<div class="box rouge"><b class="t">La règle (assumée) :</b> si la réponse à ta question est dans la formation ou la FAQ, on te renverra
<b>le lien du chapitre</b>, pas une réponse personnalisée. Ce n'est pas de la mauvaise volonté : le temps gagné sert à faire
des retours sur tes Reels — ce qui te fait réellement gagner de l'argent.</div>
<h2>Les 3 chiffres à ne jamais oublier</h2>
<ul class="puces">
<li><b>1</b> compte créé par jour, maximum</li>
<li><b>48 h</b> sans publier au début du warm-up Instagram — et le test de l'Explorer avant de poster</li>
<li><b>+1</b> Reel/jour par semaine — la régularité bat l'intensité</li>
</ul>
<div class="box"><b class="t">Et le mindset ?</b> Il est à la fin du Loom, à écouter les jours où la traversée du désert pèse.
Résumé en une phrase : tu ne peux pas échouer si tu n'abandonnes jamais — et le meilleur clipper devient manager.</div>
"""

def main():
    os.makedirs(SORTIE, exist_ok=True)
    for nom, corps in FICHES.items():
        html = f"<html><head><style>{CSS}</style></head><body>{corps}</body></html>"
        HTML(string=html).write_pdf(os.path.join(SORTIE, nom))
        print("OK", nom)

if __name__ == "__main__":
    main()
