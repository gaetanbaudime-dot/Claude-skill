"""Reels uniques par clipper (26/09, Gaëtan : « mets les TOP 20 Reels de la créatrice dans le Drive de chaque clipper, avec quelques
modifications pour faire du contenu unique à chaque fois »).

Source : le dossier « TOP 20 Reels » dans « 📁 Reels » de l'Instagram Drive de la créatrice (trouvé par le parent « 🎬 Clippers » de
DRIVE_SOURCES). Pour chaque clipper de la créatrice, chaque Reel est décliné en une version qui lui est propre, déterministe (même
clipper + même vidéo = même recette) : miroir ou non, zoom léger avec recadrage, vitesse ±3 %, saturation, contraste, luminosité,
teinte, coupe d'attaque, ré-encodage 1080×1920 30 i/s. Rien n'est identique d'un clipper à l'autre, ni au fichier d'origine. Les
variantes sont déposées dans « Reels uniques » du dossier Drive du clipper (script de l'agence, le compte de service ne peut pas
téléverser). Une variante n'est faite qu'une fois (état dans DONNEES/reels_uniques.json). Option OPUSCLIP_API_KEY : passage
OpusClip (sous-titres du template) avant la déclinaison — voir `passage_opusclip`.

Dépendances (`configurer`) : lire_json, ecrire_json, FICHIER, google_api, drive_agence, sources (DRIVE_SOURCES parsé), roster,
normaliser, canal_admin, est_staff, dossier_clipper(prenom, creatrice) -> id."""
import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time

import aiohttp

journal = logging.getLogger("bot.reels_uniques")
_deps: dict = {}
MAX_VIDEOS = int(os.environ.get("REELS_UNIQUES_MAX", "20") or 20)
NOM_SOUS_DOSSIER = "Reels uniques"
OPUSCLIP_API_KEY = os.environ.get("OPUSCLIP_API_KEY", "").strip()            # clé API du tableau de bord OpusClip (Pro/Max)
OPUSCLIP_TEMPLATE = os.environ.get("OPUSCLIP_TEMPLATE_ID", "cmcaokhia041t7ypf070b4wmu").strip()   # « Créatrices OFM »
OPUSCLIP_ATTENTE_MAX = int(os.environ.get("OPUSCLIP_ATTENTE_MAX", "900") or 900)


def configurer(deps: dict):
    global _deps
    _deps = deps


def actif() -> bool:
    return bool(_deps) and bool(shutil.which("ffmpeg")) and _deps["google_api"].actif()


def _n(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _etat() -> dict:
    d = _deps["lire_json"](_deps["FICHIER"], {})
    d.setdefault("faits", {})
    return d


# ------------------------------------------------------------------ Drive : la source
async def dossier_top20(creatrice: str):
    """(id du dossier TOP 20, nom) ou (None, raison)."""
    g = _deps["google_api"]
    cfg = _deps["sources"]().get(creatrice) or _deps["sources"]().get(creatrice.split()[0]) or {}
    parent = cfg.get("parent")
    if not parent:
        return None, f"DRIVE_SOURCES sans entrée pour {creatrice}"
    infos = await g.drive_infos(parent)
    instagram = (infos.get("parents") or [None])[0]
    if not instagram:
        return None, "dossier Instagram introuvable au-dessus de « 🎬 Clippers »"
    reels = next((f for f in await g.drive_lister(instagram) if "reels" in _n(f.get("name")) and "folder" in f.get("mimeType", "")), None)
    if not reels:
        return None, "pas de dossier « 📁 Reels » dans l'Instagram de la créatrice"
    top = next((f for f in await g.drive_lister(reels["id"]) if "top" in _n(f.get("name")) and "folder" in f.get("mimeType", "")), None)
    if not top:
        return None, "pas de dossier « TOP 20 Reels » dans « 📁 Reels »"
    return top["id"], top["name"].strip()


async def videos_top20(top_id: str) -> list:
    g = _deps["google_api"]
    vids = [f for f in await g.drive_lister(top_id) if (f.get("mimeType") or "").startswith("video/")]
    vids.sort(key=lambda f: f.get("name", ""))
    return vids[:MAX_VIDEOS]


# ------------------------------------------------------------------ la recette d'un clipper
def recette(prenom: str, video_id: str) -> dict:
    h = hashlib.sha256(f"{_n(prenom)}|{video_id}".encode()).digest()
    u = lambda i, a, b: a + (h[i] / 255) * (b - a)                     # nombre entre a et b, stable
    return {"miroir": h[0] % 2 == 0, "zoom": round(u(1, 1.02, 1.07), 3), "vitesse": round(u(2, 0.97, 1.04), 3),
            "saturation": round(u(3, 0.92, 1.10), 3), "contraste": round(u(4, 0.97, 1.05), 3),
            "luminosite": round(u(5, -0.03, 0.03), 3), "teinte": round(u(6, -4, 4), 1), "coupe": round(u(7, 0.0, 0.5), 2),
            "dx": round(u(8, -0.5, 0.5), 2), "dy": round(u(9, -0.5, 0.5), 2)}


def commande_ffmpeg(src: str, dst: str, r: dict, prenom: str) -> list:
    z = r["zoom"]
    vf = (("hflip," if r["miroir"] else "")
          + f"scale=trunc(iw*{z}/2)*2:trunc(ih*{z}/2)*2,"
          + f"crop=trunc(iw/{z}/2)*2:trunc(ih/{z}/2)*2:(iw-iw/{z})/2*{1 + r['dx']}:(ih-ih/{z})/2*{1 + r['dy']},"
          + "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          + f"eq=saturation={r['saturation']}:contrast={r['contraste']}:brightness={r['luminosite']},"
          + f"hue=h={r['teinte']},setpts=PTS/{r['vitesse']},format=yuv420p")
    return ["ffmpeg", "-v", "error", "-y", "-ss", f"{r['coupe']:.2f}", "-i", src, "-vf", vf, "-af", f"atempo={r['vitesse']}",
            "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "-metadata", f"comment=variante {prenom}", dst]


def _variante_sync(src: str, dst: str, r: dict, prenom: str) -> bool:
    p = subprocess.run(commande_ffmpeg(src, dst, r, prenom), capture_output=True, text=True, timeout=600)
    if p.returncode != 0 or not os.path.exists(dst):
        journal.warning("ffmpeg variante %s : %s", prenom, (p.stderr or "")[-300:])
        return False
    return True


# ------------------------------------------------------------------ OpusClip par API (optionnel, OPUSCLIP_API_KEY)
async def passage_opusclip(video: dict):
    """Repasse un Reel dans OpusClip sans le découper (skipSlicing) avec le template « Créatrices OFM » : sous-titres et
    recadrage du template, puis renvoie le MP4 exporté (octets), ou None si quoi que ce soit échoue (on repart de l'original).
    ≈ 1 crédit par minute de vidéo. API : POST /api/clip-projects, GET /api/exportable-clips (help.opus.pro/api-reference)."""
    g = _deps["google_api"]
    if not await g.drive_partager_public(video["id"]):
        return None
    entetes = {"Authorization": f"Bearer {OPUSCLIP_API_KEY}", "Content-Type": "application/json"}
    corps = {"videoUrl": f"https://drive.google.com/file/d/{video['id']}/view", "brandTemplateId": OPUSCLIP_TEMPLATE,
             "uploadedVideoAttr": {"title": f"Reel unique · {video.get('name', '')[:60]}"},
             "curationPref": {"skipSlicing": True}, "renderPref": {"layoutAspectRatio": "portrait"},
             "importPreference": {"sourceLang": "fr"}}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
            async with session.post("https://api.opus.pro/api/clip-projects", json=corps, headers=entetes) as r:
                rep = await r.json(content_type=None)
                if r.status >= 400:
                    journal.warning("OpusClip %s : %s", r.status, str(rep)[:200])
                    return None
            projet = rep.get("id") or rep.get("projectId") or (rep.get("project") or {}).get("id")
            if not projet:
                return None
            debut = time.time()
            while time.time() - debut < OPUSCLIP_ATTENTE_MAX:
                await asyncio.sleep(30)
                async with session.get("https://api.opus.pro/api/exportable-clips", params={"q": "findByProjectId", "projectId": projet},
                                       headers={"Authorization": f"Bearer {OPUSCLIP_API_KEY}"}) as r:
                    clips = await r.json(content_type=None)
                lst = clips if isinstance(clips, list) else (clips.get("data") or clips.get("clips") or [])
                url = next((c.get("uriForExport") for c in lst if c.get("uriForExport")), None)
                if url:
                    async with session.get(url) as r:
                        if r.status < 400:
                            return await r.read()
                    return None
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("OpusClip pour %s : %s", video.get("name"), erreur)
    return None


# ------------------------------------------------------------------ exécution
async def executer(creatrice: str, prenoms=None, progression=None) -> list:
    """Décline les TOP 20 de `creatrice` pour `prenoms` (défaut : tout le roster de la créatrice). Renvoie une ligne de bilan par
    clipper. `progression(texte)` (coroutine) reçoit les étapes pour le salon admin."""
    if not actif():
        return ["Reels uniques inactifs : ffmpeg ou Google manquant."]
    top_id, nom_top = await dossier_top20(creatrice)
    if not top_id:
        return [f"❌ {creatrice} : {nom_top}"]
    vids = await videos_top20(top_id)
    if not vids:
        return [f"❌ {creatrice} : « {nom_top} » est vide"]
    noms = list(prenoms or (_deps["roster"].groupes().get(creatrice) or _deps["roster"].groupes().get(creatrice.capitalize()) or []))
    if not noms:
        return [f"❌ {creatrice} : aucun clipper au roster"]
    d = _etat()
    bilan = []
    with tempfile.TemporaryDirectory() as tmp:
        originaux = {}
        for prenom in noms:
            faits = d["faits"].setdefault(creatrice, {}).setdefault(_n(prenom), [])
            a_faire = [v for v in vids if v["id"] not in faits]
            if not a_faire:
                bilan.append(f"✅ {prenom} : déjà à jour ({len(faits)} Reels)")
                continue
            dossier = await _deps["dossier_clipper"](prenom, creatrice)
            if not dossier:
                bilan.append(f"⏭️ {prenom} : pas de dossier Drive (onboarding d'abord)")
                continue
            g = _deps["google_api"]
            sous = await g.drive_trouver_dossier(NOM_SOUS_DOSSIER, dossier) or await g.drive_creer_dossier(NOM_SOUS_DOSSIER, dossier)
            deja_la = {f.get("name") for f in await g.drive_lister(sous)}
            ok, rates = 0, 0
            for i, v in enumerate(a_faire, start=1):
                if v["id"] not in originaux:
                    try:
                        chemin = os.path.join(tmp, v["id"] + ".mp4")
                        contenu_src = await passage_opusclip(v) if OPUSCLIP_API_KEY else None
                        with open(chemin, "wb") as f:
                            f.write(contenu_src or await g.drive_telecharger(v["id"]))
                        originaux[v["id"]] = chemin
                    except Exception as erreur:                             # noqa: BLE001
                        journal.warning("Téléchargement %s : %s", v.get("name"), erreur)
                        rates += 1
                        continue
                dst = os.path.join(tmp, f"{_n(prenom)}_{v['id']}.mp4")
                if not await asyncio.to_thread(_variante_sync, originaux[v["id"]], dst, recette(prenom, v["id"]), prenom):
                    rates += 1
                    continue
                numero = vids.index(v) + 1
                nom_fichier = f"{creatrice.split()[0]} · Reel {numero:02d} · {prenom}.mp4"
                try:
                    if nom_fichier in deja_la:                              # idempotent par nom (déclinaison faite ailleurs, ex. hors ligne)
                        faits.append(v["id"]); ok += 1
                        _deps["ecrire_json"](_deps["FICHIER"], d)
                        continue
                    with open(dst, "rb") as f:
                        contenu = f.read()
                    if len(contenu) > 45_000_000:
                        raise RuntimeError("variante de plus de 45 Mo")
                    await _deps["drive_agence"].televerser(sous, nom_fichier, contenu, "video/mp4")
                    faits.append(v["id"]); ok += 1
                    _deps["ecrire_json"](_deps["FICHIER"], d)
                except Exception as erreur:                                 # noqa: BLE001
                    journal.warning("Dépôt %s pour %s : %s", nom_fichier, prenom, erreur)
                    rates += 1
                finally:
                    if os.path.exists(dst):
                        os.remove(dst)
                if progression and i % 5 == 0:
                    try:
                        await progression(f"⏳ {creatrice} · {prenom} : {ok} Reel(s) déposé(s) sur {len(a_faire)}…")
                    except Exception:                                       # noqa: BLE001
                        pass
            bilan.append(f"{'✅' if not rates else '⚠️'} {prenom} : {ok} Reel(s) unique(s) déposé(s)" + (f", {rates} raté(s)" if rates else "")
                         + f" → « {NOM_SOUS_DOSSIER} » de son Drive")
    journal.info("Reels uniques %s : %s", creatrice, bilan)
    return bilan


async def commande_staff(message, texte: str) -> bool:
    """`!reels-uniques Créatrice [Prénom …]` : décline les TOP 20 de la créatrice pour ses clippers (tous, ou ceux nommés)."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!reels-uniques", "!reels-unique"):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Commande réservée aux managers et aux admins.")
        return True
    if len(mots) < 2:
        await message.reply("Format : `!reels-uniques Chloé` (tous ses clippers du roster) ou `!reels-uniques Chloé Ricado Lucas`. "
                            "Source : le dossier « TOP 20 Reels » dans « 📁 Reels » de son Instagram Drive.")
        return True
    if not actif():
        await message.reply("Reels uniques inactifs : ffmpeg ou Google manquant sur le serveur.")
        return True
    creatrice, prenoms = mots[1].strip().capitalize(), [m for m in mots[2:] if not m.isdigit()]
    await message.reply(f"⏳ Déclinaison des TOP 20 de {creatrice} pour {', '.join(prenoms) if prenoms else 'tout son roster'}… "
                        "Je poste le bilan ici quand c'est fini (quelques minutes par clipper).")

    async def _progression(t):
        await message.channel.send(t)

    async def _tache():
        try:
            bilan = await executer(creatrice, prenoms or None, _progression)
        except Exception as erreur:                                         # noqa: BLE001
            journal.exception("Reels uniques : %s", erreur)
            bilan = [f"❌ erreur : {type(erreur).__name__} {str(erreur)[:120]}"]
        await message.channel.send(("🎬 **Reels uniques · " + creatrice + "**\n" + "\n".join(bilan))[:1990])
    asyncio.create_task(_tache())
    return True


async def pour_nouveau(prenom: str, creatrice: str) -> None:
    """À l'onboarding d'un nouveau clipper : ses Reels uniques partent en tâche de fond, bilan au salon admin."""
    if not actif():
        return
    try:
        bilan = await executer(creatrice, [prenom])
        canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
        if canal is not None and bilan:
            await canal.send(("🎬 **Reels uniques de " + prenom + "** (" + creatrice + ")\n" + "\n".join(bilan))[:1990])
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Reels uniques pour %s : %s", prenom, erreur)
