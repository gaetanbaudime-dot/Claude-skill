# Génère les fiches du Kit Clipper v2 en JPEG haute résolution pour Discord :
#   second-brain/96-Opérations LTP/Kit Clippers/Fiches JPEG (Discord)/*.jpg
# Le contenu vient de generer_fiches.py (source de vérité unique) — ici on ne fait
# que le rendu écran : largeur 1200 px, device scale ×2 (= 2400 px de large), JPEG q92.
# Les noms de fichiers reprennent EXACTEMENT les titres des posts du forum #checklist.
# Usage : python3 tools/kit_clippers/generer_jpegs.py
# Prérequis : pip install playwright + chromium préinstallé (/opt/pw-browsers/chromium).

import importlib.util
import os
import sys
import types

DOSSIER = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(DOSSIER, "..", "..", "second-brain",
                      "96-Opérations LTP", "Kit Clippers", "Fiches JPEG (Discord)")
CHROMIUM = os.environ.get("CHROMIUM_BIN", "/opt/pw-browsers/chromium")

# ---- charger PAGES depuis generer_fiches.py sans exiger weasyprint (inutile ici)
sys.modules.setdefault("weasyprint", types.SimpleNamespace(HTML=None))
spec = importlib.util.spec_from_file_location("generer_fiches",
                                              os.path.join(DOSSIER, "generer_fiches.py"))
fiches = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fiches)

# Titres des posts Discord (forum #checklist) = noms de fichiers, dans l'ordre de PAGES.
NOMS_DISCORD = [
    "Bienvenue.jpg",
    "Fiche 1 - Création des Comptes.jpg",
    "Fiche 2 - Le Warmup.jpg",
    "Fiche 3 - Monter et Poster un Reel.jpg",
    "Fiche 4 - Ta routine.jpg",
    "Fiche 5 - Reel d'essai et Évolution.jpg",
    "Fiche 6 - Quand ça coince.jpg",
]

# CSS écran : la maquette du PDF (vert LTP, encadrés, tableaux) re-calibrée pour une
# image de 1200 px de large, lisible dans l'aperçu Discord sans zoomer.
CSS_ECRAN = """
* { box-sizing: border-box; }
body { margin: 0; background: #fff; font-family: "DejaVu Sans", Arial, sans-serif;
  font-size: 20px; color: #1c1c1c; line-height: 1.45; }
.page { width: 1200px; padding: 40px 48px 28px; background: #fff; }
.bandeau { background: #1d3d2f; color: #fff; padding: 18px 28px; border-radius: 14px;
  display: flex; justify-content: space-between; align-items: baseline; }
.bandeau .num { font-size: 18px; letter-spacing: 2px; text-transform: uppercase; color: #bcd9c9; white-space: nowrap; margin-left: 24px; }
.bandeau .titre { font-size: 34px; font-weight: bold; }
.sous { color: #4a4a4a; font-size: 20px; margin: 16px 4px 26px; }
h2 { font-size: 24px; color: #1d3d2f; margin: 26px 0 12px; letter-spacing: .4px;
  border-bottom: 3px solid #1d3d2f; padding-bottom: 6px; }
.box { background: #eff5f1; border-left: 8px solid #1d3d2f; padding: 16px 24px; border-radius: 10px; margin: 18px 0; }
.rouge { background: #fdf0ef; border-left-color: #a33025; }
.rouge b.t { color: #a33025; }
ul.check { list-style: none; padding-left: 4px; margin: 12px 0; }
ul.check li { padding-left: 44px; text-indent: -44px; margin: 10px 0; }
ul.check li::before { content: "\\2610\\00a0\\00a0"; font-size: 22px; color: #1d3d2f; }
ul.puces { margin: 12px 0 12px 36px; padding: 0; }
ul.puces li { margin: 9px 0; }
ol.etapes { margin: 12px 0 12px 40px; padding: 0; }
ol.etapes li { margin: 10px 0; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; }
th { background: #1d3d2f; color: #fff; font-size: 18px; padding: 10px 14px; text-align: left; }
td { border: 1px solid #c9d6cd; padding: 10px 14px; font-size: 19px; vertical-align: top; }
b.t { color: #1d3d2f; }
.petit { font-size: 17px; color: #555; }
.espace { height: 16px; }
.grand-espace { height: 28px; }
.logo-bas { text-align: center; margin-top: 40px; }
.schema { text-align: center; margin: 22px 0; }
.carte { display: inline-block; border: 3px solid #1d3d2f; border-radius: 12px; padding: 10px 18px;
  margin: 6px 8px; font-size: 19px; background: #eff5f1; }
.carte.privee { border-color: #a33025; background: #fdf0ef; }
.fleche { font-size: 26px; color: #1d3d2f; margin: 0 8px; }
.objectif { font-size: 22px; margin: 14px 0; }
svg { transform: scale(1.6); transform-origin: center; margin: 0 6px; }
.logo-bas svg, .bandeau svg { transform: none; margin: 0; }
.pied { margin-top: 34px; padding-top: 14px; border-top: 1px solid #d9d9d9;
  font-size: 15px; color: #8a8a8a; text-align: center; }
"""

PIED = '<div class="pied">Kit Clipper · LTP · juillet 2026 · v2 — document interne, ne pas diffuser</div>'


def enrober(corps: str) -> str:
    """Insère le pied de page à la fin de la fiche (remplace le footer @page du PDF)."""
    corps = corps.rstrip()
    if corps.endswith("</div>"):
        corps = corps[: -len("</div>")] + PIED + "</div>"
    return f'<html><head><meta charset="utf-8"><style>{CSS_ECRAN}</style></head><body>{corps}</body></html>'


def main():
    from playwright.sync_api import sync_playwright

    os.makedirs(SORTIE, exist_ok=True)
    assert len(NOMS_DISCORD) == len(fiches.PAGES), "NOMS_DISCORD et PAGES doivent avoir la même longueur"

    with sync_playwright() as p:
        navigateur = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        contexte = navigateur.new_context(viewport={"width": 1200, "height": 900},
                                          device_scale_factor=2)
        page = contexte.new_page()
        for nom, corps in zip(NOMS_DISCORD, fiches.PAGES):
            page.set_content(enrober(corps), wait_until="load")
            chemin = os.path.join(SORTIE, nom)
            page.screenshot(path=chemin, full_page=True, type="jpeg", quality=92)
            print("OK", chemin)
        navigateur.close()


if __name__ == "__main__":
    main()
