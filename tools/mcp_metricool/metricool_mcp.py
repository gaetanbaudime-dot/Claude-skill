#!/usr/bin/env python3
"""Serveur MCP Metricool — les comptes de l'agence lus par Claude.

RÔLE : exposer les données Metricool (18 marques : « Créatrice N - R/J », R = Rianah,
J = Julien) sous forme d'outils utilisables en conversation. Complète GAML (clics sur
les landings) et Infloww (abonnés + revenus) : Metricool couvre l'étage AMONT —
combien de posts, combien de vues, sur quel réseau, par qui.

AUTHENTIFICATION : jeton dans la variable d'environnement METRICOOL_TOKEN (jamais
en dur, jamais commité). userId optionnel via METRICOOL_USER_ID (déduit sinon).

LANCEMENT
  Local (stdio, pour Claude Code)   : python metricool_mcp.py
  Distant (Railway, pour claude.ai) : MCP_TRANSPORT=http python metricool_mcp.py
  Vérification rapide sans MCP      : python metricool_mcp.py --selftest

PÉRIMÈTRE (précisé par Gaëtan le 12/08/2026) : l'agence a DEUX machines de distribution.
Les clippers travaillent Facebook + Instagram, suivis par GAML, Infloww et le bot.
Metricool couvre **l'autre machine** — Facebook/TikTok/YouTube, comptes tenus par Rianah
(suffixe « - R ») et Julien (« - J »). Qu'Instagram soit quasi absent d'ici est donc
NORMAL : ce n'est pas un défaut de configuration, c'est la frontière entre les deux outils.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

# Le SDK n'est requis qu'en mode serveur (--selftest tourne sans). Il a renommé sa classe
# entre la 1.x (FastMCP) et la 2.x (MCPServer) : on gère les deux, sinon un `pip install`
# qui résout en 2.x fait planter le démarrage sur Railway.
_SDK = 0
try:
    from mcp.server.mcpserver import MCPServer as _Serveur   # SDK 2.x
    _SDK = 2
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as _Serveur   # SDK 1.x
        _SDK = 1
    except ImportError:
        _Serveur = None                         # type: ignore[assignment]

API_BASE = "https://app.metricool.com/api"
TIMEOUT = 40.0
DATE_FMT = "%Y-%m-%dT%H:%M:%S"                  # format exigé par l'API (validé le 12/08)
RESEAUX = ("instagram", "facebook", "tiktok", "youtube")

mcp = _Serveur("metricool_mcp") if _Serveur else None


# ------------------------------------------------------------------ socle HTTP
def _token() -> str:
    jeton = os.environ.get("METRICOOL_TOKEN", "").strip()
    if not jeton:
        raise RuntimeError(
            "METRICOOL_TOKEN absent. Pose la variable d'environnement "
            "(Railway → Variables, ou `export METRICOOL_TOKEN=...` en local)."
        )
    return jeton


async def _get(chemin: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Appel GET authentifié. Renvoie le corps JSON (déballé de `data` si présent)."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        reponse = await client.get(
            f"{API_BASE}/{chemin.lstrip('/')}",
            params=params or {},
            headers={"X-Mc-Auth": _token(), "Accept": "application/json"},
        )
        reponse.raise_for_status()
        corps = reponse.json()
    return corps.get("data", corps) if isinstance(corps, dict) else corps


def _erreur(e: Exception) -> str:
    """Message d'erreur actionnable (le but : que l'agent sache quoi faire ensuite)."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 401:
            return "Erreur : jeton Metricool invalide ou expiré → régénère-le dans Metricool et mets à jour METRICOOL_TOKEN."
        if code == 403:
            return ("Erreur : accès refusé pour cette marque/ce réseau — le réseau n'est probablement "
                    "PAS connecté sur cette marque. Lance `metricool_brands` pour voir les réseaux réellement branchés.")
        if code == 400:
            return f"Erreur : paramètres invalides ({e.response.text[:200]}). Les dates doivent être au format AAAA-MM-JJ."
        if code == 429:
            return "Erreur : trop d'appels d'affilée (429). Attends une minute puis réessaie."
        return f"Erreur : l'API Metricool a répondu {code}."
    if isinstance(e, httpx.TimeoutException):
        return "Erreur : Metricool n'a pas répondu à temps. Réessaie, ou réduis la période demandée."
    if isinstance(e, RuntimeError):
        return f"Erreur : {e}"
    return f"Erreur inattendue : {type(e).__name__}."


def _bornes(depuis: Optional[str], jusqu_a: Optional[str], jours: int) -> tuple[str, str]:
    """Convertit AAAA-MM-JJ (ou rien = N derniers jours) au format attendu par l'API."""
    fin = datetime.strptime(jusqu_a, "%Y-%m-%d") if jusqu_a else datetime.utcnow()
    debut = datetime.strptime(depuis, "%Y-%m-%d") if depuis else fin - timedelta(days=jours)
    return debut.strftime(DATE_FMT), fin.strftime(DATE_FMT)


async def _marques() -> List[Dict[str, Any]]:
    """Marques + réseaux réellement connectés (simpleProfiles porte les identifiants)."""
    profils = await _get("admin/simpleProfiles")
    marques = []
    for p in profils:
        connectes = [r for r in RESEAUX
                     if p.get(r) or (r == "facebook" and p.get("facebookPageId"))]
        marques.append({
            "id": p["id"],
            "nom": p.get("label"),
            "reseaux_connectes": connectes,
            "instagram": p.get("instagram"),
            "facebook_page_id": p.get("facebookPageId"),
            "tiktok": p.get("tiktok"),
            "youtube": p.get("youtube"),
            # Identifiant du COMPTE derrière chaque réseau. Indispensable : plusieurs marques
            # Metricool pointent souvent vers la MÊME chaîne YouTube / le même TikTok (cas
            # constaté le 12/08 : les 7 marques « Chloé » partagent une seule chaîne YouTube).
            # Sans cette clé, un résumé multi-comptes compte 7 fois les mêmes vues.
            "identifiants": {r: (p.get("facebookPageId") if r == "facebook" else p.get(r))
                             for r in connectes},
        })
    return sorted(marques, key=lambda m: str(m["nom"]))


def _user_id(marques: List[Dict[str, Any]]) -> str:
    """userId de l'espace de travail — facultatif : le jeton suffit à identifier le compte.

    Vérifié le 12/08 : `userId=` vide renvoie bien 200. La variable METRICOOL_USER_ID
    reste une porte de sortie si l'API se met un jour à l'exiger (valeur connue : 2302746).
    """
    return os.environ.get("METRICOOL_USER_ID", "").strip()


# ---- normalisation des métriques : chaque réseau nomme ses champs différemment ----
def _metriques(reseau: str, post: Dict[str, Any]) -> Dict[str, Any]:
    """Ramène un post de n'importe quel réseau à un socle commun (vues/likes/…)."""
    if reseau == "tiktok":
        return {"date": post.get("createTime"), "vues": post.get("viewCount", 0),
                "likes": post.get("likeCount", 0), "commentaires": post.get("commentCount", 0),
                "partages": post.get("shareCount", 0), "engagement": post.get("engagement", 0),
                "titre": (post.get("videoDescription") or "")[:90], "url": post.get("shareUrl")}
    if reseau == "youtube":
        return {"date": post.get("publishedAt"), "vues": post.get("views", 0),
                "likes": post.get("likes", 0), "commentaires": post.get("comments", 0),
                "partages": post.get("shares", 0), "engagement": 0,
                "titre": (post.get("title") or "")[:90], "url": post.get("watchUrl")}
    if reseau == "facebook":
        return {"date": post.get("created") or post.get("timestamp"),
                "vues": post.get("videoViews", 0) or post.get("impressions", 0),
                "likes": post.get("reactions", 0), "commentaires": post.get("comments", 0),
                "partages": post.get("shares", 0), "engagement": post.get("engagement", 0),
                "titre": (post.get("text") or "")[:90], "url": post.get("link")}
    return {"date": post.get("created") or post.get("timestamp") or post.get("publishedAt"),
            "vues": post.get("impressions", 0) or post.get("views", 0) or post.get("reach", 0),
            "likes": post.get("likes", 0) or post.get("reactions", 0),
            "commentaires": post.get("comments", 0), "partages": post.get("shares", 0),
            "engagement": post.get("engagement", 0),
            "titre": (post.get("text") or post.get("caption") or "")[:90], "url": post.get("link")}


async def _posts(blog_id: int, reseau: str, debut: str, fin: str,
                 user_id: str) -> List[Dict[str, Any]]:
    brut = await _get(f"v2/analytics/posts/{reseau}",
                      {"blogId": blog_id, "userId": user_id, "from": debut, "to": fin})
    return [_metriques(reseau, p) for p in (brut or [])]


def _cumul(posts: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "posts": len(posts),
        "vues": int(sum(p["vues"] or 0 for p in posts)),
        "likes": int(sum(p["likes"] or 0 for p in posts)),
        "commentaires": int(sum(p["commentaires"] or 0 for p in posts)),
    }


# ------------------------------------------------------------------ modèles d'entrée
class Format(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class EntreeMarques(BaseModel):
    """Aucun paramètre : renvoie toutes les marques de l'espace de travail."""
    model_config = ConfigDict(extra="forbid")
    format: Format = Field(default=Format.MARKDOWN, description="markdown (lisible) ou json (brut)")


class EntreePosts(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    marque_id: int = Field(..., description="Identifiant de la marque (colonne id de metricool_brands), ex. 6314104")
    reseau: str = Field(..., description="instagram · facebook · tiktok · youtube")
    depuis: Optional[str] = Field(default=None, description="Date de début AAAA-MM-JJ (défaut : il y a `jours` jours)")
    jusqu_a: Optional[str] = Field(default=None, description="Date de fin AAAA-MM-JJ (défaut : aujourd'hui)")
    jours: int = Field(default=30, description="Fenêtre en jours si aucune date n'est donnée", ge=1, le=365)
    limite: int = Field(default=25, description="Nombre de posts détaillés à retourner (les plus vus d'abord)", ge=1, le=200)
    format: Format = Field(default=Format.MARKDOWN, description="markdown (lisible) ou json (brut)")


class EntreeResume(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    jours: int = Field(default=7, description="Fenêtre en jours (défaut 7)", ge=1, le=90)
    depuis: Optional[str] = Field(default=None, description="Date de début AAAA-MM-JJ (prioritaire sur `jours`)")
    jusqu_a: Optional[str] = Field(default=None, description="Date de fin AAAA-MM-JJ")
    filtre_nom: Optional[str] = Field(default=None, description="Ne garder que les marques dont le nom contient ce texte (ex. 'Chloé', '- R')")
    format: Format = Field(default=Format.MARKDOWN, description="markdown (lisible) ou json (brut)")


# ------------------------------------------------------------------ implémentations
# La logique vit hors des décorateurs @mcp.tool : elle reste testable sans le SDK MCP
# (--selftest) et les outils déclarés plus bas ne sont que des enveloppes.
async def _impl_marques(params: EntreeMarques) -> str:
    try:
        marques = await _marques()
        if params.format == Format.JSON:
            return json.dumps(marques, indent=2, ensure_ascii=False)
        lignes = [f"# Comptes Metricool ({len(marques)})", "",
                  "| id | nom | réseaux connectés |", "|---|---|---|"]
        for m in marques:
            res = ", ".join(m["reseaux_connectes"]) or "**aucun**"
            lignes.append(f"| {m['id']} | {m['nom']} | {res} |")
        sans_ig = [m["nom"] for m in marques if "instagram" not in m["reseaux_connectes"]]
        if sans_ig:
            lignes += ["", f"ℹ️ {len(sans_ig)} compte(s) sans Instagram : **c'est attendu**. "
                           "Instagram et Facebook côté clippers se suivent dans GAML / Infloww / "
                           "le bot. Metricool couvre l'autre machine (Facebook, TikTok, YouTube). "
                           "Ne pas conclure à un problème de configuration."]
        return "\n".join(lignes)
    except Exception as e:                                      # noqa: BLE001
        return _erreur(e)


async def _impl_posts(params: EntreePosts) -> str:
    if params.reseau not in RESEAUX:
        return f"Erreur : réseau « {params.reseau} » inconnu. Valeurs acceptées : {', '.join(RESEAUX)}."
    try:
        debut, fin = _bornes(params.depuis, params.jusqu_a, params.jours)
        marques = await _marques()
        posts = await _posts(params.marque_id, params.reseau, debut, fin, _user_id(marques))
        posts.sort(key=lambda p: p["vues"] or 0, reverse=True)
        cumul = _cumul(posts)
        if params.format == Format.JSON:
            return json.dumps({"marque_id": params.marque_id, "reseau": params.reseau,
                               "periode": {"depuis": debut, "jusqu_a": fin},
                               "cumul": cumul, "posts": posts[:params.limite]},
                              indent=2, ensure_ascii=False)
        nom = next((m["nom"] for m in marques if m["id"] == params.marque_id), params.marque_id)
        lignes = [f"# {nom} — {params.reseau} ({debut[:10]} → {fin[:10]})", "",
                  f"**{cumul['posts']} posts · {cumul['vues']:,} vues · "
                  f"{cumul['likes']:,} likes · {cumul['commentaires']:,} commentaires**".replace(",", " "), ""]
        if not posts:
            lignes.append("_Aucune publication sur la période._")
        else:
            lignes += ["| vues | likes | date | contenu |", "|---|---|---|---|"]
            for p in posts[:params.limite]:
                lignes.append(f"| {p['vues']} | {p['likes']} | {str(p['date'])[:10]} | {p['titre']} |")
        return "\n".join(lignes)
    except Exception as e:                                      # noqa: BLE001
        return _erreur(e)


def _creatrice(nom: str) -> str:
    """« Chloé 3 - J » → « Chloé » (le suffixe est le numéro de compte + le manager)."""
    return str(nom).split(" - ")[0].rsplit(" ", 1)[0].strip() or str(nom)


async def _impl_resume(params: EntreeResume) -> str:
    try:
        debut, fin = _bornes(params.depuis, params.jusqu_a, params.jours)
        marques = await _marques()
        if params.filtre_nom:
            besoin = params.filtre_nom.lower()
            marques = [m for m in marques if besoin in str(m["nom"]).lower()]
        if not marques:
            return f"Aucune marque ne correspond au filtre « {params.filtre_nom} »."
        uid = _user_id(marques)

        # Un appel par COMPTE RÉEL (réseau + identifiant), pas par marque : sinon les
        # marques qui partagent une chaîne YouTube gonflent le total (× 7 chez Chloé).
        uniques: Dict[tuple, tuple] = {}
        for m in marques:
            for r in m["reseaux_connectes"]:
                cle = (r, str(m["identifiants"].get(r) or m["id"]))
                uniques.setdefault(cle, (m["id"], r))
        resultats = await asyncio.gather(
            *(_posts(bid, r, debut, fin, uid) for bid, r in uniques.values()),
            return_exceptions=True)
        cumuls: Dict[tuple, Any] = {}
        for cle, res in zip(uniques.keys(), resultats):
            cumuls[cle] = {"erreur": _erreur(res)} if isinstance(res, Exception) else _cumul(res)

        par_marque: Dict[int, Dict[str, Any]] = {
            m["id"]: {"marque_id": m["id"], "nom": m["nom"], "posts": 0, "vues": 0,
                      "likes": 0, "commentaires": 0, "par_reseau": {}} for m in marques}
        partages: Dict[tuple, List[str]] = {}
        for m in marques:
            for r in m["reseaux_connectes"]:
                cle = (r, str(m["identifiants"].get(r) or m["id"]))
                c = cumuls.get(cle, {})
                par_marque[m["id"]]["par_reseau"][r] = c
                partages.setdefault(cle, []).append(str(m["nom"]))
                if "erreur" in c:
                    continue
                for k in ("posts", "vues", "likes", "commentaires"):
                    par_marque[m["id"]][k] += c[k]

        lignes_marques = sorted(par_marque.values(), key=lambda x: -x["vues"])
        # Total dédupliqué : chaque compte réel compté UNE fois.
        total = {k: int(sum(c[k] for c in cumuls.values() if "erreur" not in c))
                 for k in ("posts", "vues", "likes", "commentaires")}
        comptes_partages = [f"{r} « {ident} » partagé par {len(noms)} marques : {', '.join(noms)}"
                            for (r, ident), noms in partages.items() if len(noms) > 1]

        # Par créatrice, sur les comptes dédupliqués. Un compte partagé est attribué à la
        # créatrice de la 1re marque qui le porte : correct tant qu'un compte n'est pas
        # partagé ENTRE créatrices (jamais vu le 12/08 — les partages sont intra-créatrice).
        par_creatrice: Dict[str, Dict[str, int]] = {}
        for cle, noms in partages.items():
            c = cumuls.get(cle, {})
            if "erreur" in c:
                continue
            agg = par_creatrice.setdefault(_creatrice(noms[0]), {"posts": 0, "vues": 0})
            agg["posts"] += c["posts"]
            agg["vues"] += c["vues"]
        for m in marques:                                 # créatrices sans aucun compte actif
            par_creatrice.setdefault(_creatrice(m["nom"]), {"posts": 0, "vues": 0})
        muets = [m["nom"] for m in lignes_marques if m["posts"] == 0]

        if params.format == Format.JSON:
            return json.dumps({"periode": {"depuis": debut, "jusqu_a": fin}, "total": total,
                               "par_marque": lignes_marques, "par_creatrice": par_creatrice,
                               "comptes_muets": muets,
                               "comptes_partages": comptes_partages}, indent=2, ensure_ascii=False)

        esp = lambda n: f"{n:,}".replace(",", " ")         # noqa: E731
        out = [f"# Production Metricool — {debut[:10]} → {fin[:10]}", "",
               f"**{total['posts']} posts · {esp(total['vues'])} vues · "
               f"{esp(total['likes'])} likes**", "",
               "## Par créatrice", "", "| créatrice | posts | vues |", "|---|---|---|"]
        for nom, agg in sorted(par_creatrice.items(), key=lambda kv: -kv[1]["vues"]):
            out.append(f"| {nom} | {agg['posts']} | {esp(agg['vues'])} |")
        out += ["", "## Par compte", "", "| compte | posts | vues | détail |", "|---|---|---|---|"]
        for m in lignes_marques:
            detail = " · ".join(f"{r} {d.get('posts', 0)}p/{esp(d.get('vues', 0))}v"
                                for r, d in m["par_reseau"].items() if "erreur" not in d)
            out.append(f"| {m['nom']} | {m['posts']} | {esp(m['vues'])} | {detail or '—'} |")
        if muets:
            out += ["", f"🔴 **{len(muets)} compte(s) sans AUCUNE publication** sur la période : "
                        + ", ".join(muets)]
        if comptes_partages:
            out += ["", "ℹ️ **Comptes partagés entre plusieurs marques** (comptés une seule fois "
                        "dans le total, mais affichés sur chaque ligne) :"]
            out += [f"· {c}" for c in comptes_partages]
        return "\n".join(out)
    except Exception as e:                                      # noqa: BLE001
        return _erreur(e)


# ------------------------------------------------------------------ outils MCP
def _enregistrer_outils() -> None:
    """Déclare les outils. Séparé pour que --selftest tourne sans le SDK MCP."""

    @mcp.tool(
        name="metricool_brands",
        annotations={"title": "Lister les comptes Metricool", "readOnlyHint": True,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def metricool_brands(params: EntreeMarques) -> str:
        """Liste toutes les marques Metricool de l'agence et les réseaux réellement connectés.

        À appeler EN PREMIER : les autres outils ont besoin d'un `marque_id`, et cet outil
        révèle aussi les comptes où un réseau n'est PAS branché (cause n°1 des erreurs 403).

        Args:
            params (EntreeMarques) : format d'affichage.

        Returns:
            str : tableau markdown (id · nom · réseaux connectés) ou JSON :
            [{"id": int, "nom": str, "reseaux_connectes": [str],
              "instagram": str|None, "facebook_page_id": str|None,
              "tiktok": str|None, "youtube": str|None}]
        """
        return await _impl_marques(params)

    @mcp.tool(
        name="metricool_posts",
        annotations={"title": "Posts et performances d'un compte", "readOnlyHint": True,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def metricool_posts(params: EntreePosts) -> str:
        """Récupère les publications d'UNE marque sur UN réseau, avec leurs métriques.

        Utiliser pour : « qu'est-ce qui a marché sur le TikTok de Chloé 1 ce mois-ci ? ».
        Les posts sont triés par vues décroissantes (les meilleurs d'abord).

        Args:
            params (EntreePosts) : marque_id, reseau, période (depuis/jusqu_a ou jours),
                limite, format.

        Returns:
            str : markdown (cumul + top posts) ou JSON :
            {"marque_id": int, "reseau": str, "periode": {"depuis": str, "jusqu_a": str},
             "cumul": {"posts": int, "vues": int, "likes": int, "commentaires": int},
             "posts": [{"date": str, "vues": int, "likes": int, "commentaires": int,
                        "partages": int, "titre": str, "url": str}]}

        Erreurs :
            - réseau non connecté sur cette marque → message explicite (voir metricool_brands)
            - dates mal formées → rappel du format AAAA-MM-JJ
        """
        return await _impl_posts(params)

    @mcp.tool(
        name="metricool_summary",
        annotations={"title": "Résumé de production tous comptes", "readOnlyHint": True,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def metricool_summary(params: EntreeResume) -> str:
        """Résumé de production sur TOUS les comptes : qui a posté, combien, pour quelles vues.

        C'est l'outil de pilotage quotidien : il répond à « est-ce que l'équipe publie ? »
        en une seule question, agrégé par marque puis par créatrice. Interroge chaque
        réseau connecté de chaque marque en parallèle.

        Args:
            params (EntreeResume) : jours (ou depuis/jusqu_a), filtre_nom, format.

        Returns:
            str : markdown (total, tableau par marque, total par créatrice, comptes muets)
            ou JSON :
            {"periode": {"depuis": str, "jusqu_a": str},
             "total": {"posts": int, "vues": int, "likes": int, "commentaires": int},
             "par_marque": [{"marque_id": int, "nom": str, "posts": int, "vues": int,
                             "par_reseau": {"tiktok": {...}, ...}}],
             "par_creatrice": {"Chloé": {"posts": int, "vues": int}, ...},
             "comptes_muets": [str]}
        """
        return await _impl_resume(params)


# ------------------------------------------------------------------ vérification hors MCP
async def _selftest(complet: bool = False) -> int:
    """Teste la clé et les 3 outils sans passer par le protocole MCP.

    `complet` ajoute le résumé 7 jours sur tous les comptes (une trentaine d'appels).
    """
    try:
        marques = await _marques()
    except Exception as e:                                      # noqa: BLE001
        print(_erreur(e))
        return 1
    print(f"✅ Connexion OK — {len(marques)} marques")
    sans_ig = [m["nom"] for m in marques if "instagram" not in m["reseaux_connectes"]]
    print(f"   {len(marques) - len(sans_ig)}/{len(marques)} marques ont Instagram connecté")
    uid = _user_id(marques)
    debut, fin = _bornes(None, None, 7)
    cible = next((m for m in marques if m["reseaux_connectes"]), None)
    if cible:
        reseau = cible["reseaux_connectes"][0]
        posts = await _posts(cible["id"], reseau, debut, fin, uid)
        print(f"✅ Posts OK — {cible['nom']} / {reseau} : {_cumul(posts)}")
    # Contrôle de non-régression de la déduplication : le nombre de comptes RÉELS doit
    # être < au nombre de couples (marque × réseau) dès qu'un compte est partagé.
    couples = sum(len(m["reseaux_connectes"]) for m in marques)
    reels = len({(r, str(m["identifiants"].get(r) or m["id"]))
                 for m in marques for r in m["reseaux_connectes"]})
    print(f"✅ Déduplication — {couples} couples marque×réseau → {reels} comptes réels")
    if complet:
        print()
        print(await _impl_resume(EntreeResume(jours=7)))
    print("✅ Serveur prêt.")
    return 0


def _dire(message: str) -> None:
    """Trace de démarrage forcée sur stderr, non tamponnée.

    Sur un hébergeur, la sortie standard de Python est tamponnée par blocs quand elle
    n'est pas un terminal : un service qui démarre puis se tait est alors indiscernable
    d'un service mort. On écrit donc sur stderr avec flush explicite, pour que les
    Deploy Logs disent toujours QUEL mode a été pris et sur quel port on écoute.
    """
    print(message, file=sys.stderr, flush=True)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(asyncio.run(_selftest("--complet" in sys.argv)))
    if mcp is None:
        raise SystemExit("Le SDK MCP manque : pip install -r requirements.txt")
    _dire(f"[metricool_mcp] démarrage · SDK MCP {_SDK}.x · python {sys.version.split()[0]}")
    _enregistrer_outils()
    _transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    _dire(f"[metricool_mcp] MCP_TRANSPORT={_transport!r} · jeton "
          f"{'présent' if os.environ.get('METRICOOL_TOKEN') else 'ABSENT'}")
    if _transport not in ("http", "streamable_http"):
        _dire("[metricool_mcp] mode stdio — si c'est un déploiement distant, "
              "MCP_TRANSPORT doit valoir 'http'.")
        mcp.run()                                           # stdio (Claude Code en local)
        raise SystemExit(0)

    # HTTP distant. MCP_PATH sert de mot de passe : claude.ai ne propose pas de champ
    # « en-tête personnalisé » pour un connecteur, donc c'est l'URL elle-même qui protège
    # l'accès. La mettre longue et aléatoire (voir README), et ne jamais la publier.
    # L'URL finale est /<secret>/mcp : le segment secret protège l'accès, le suffixe /mcp
    # reste la convention attendue par les clients. Sans MCP_PATH, on retombe sur /mcp nu.
    secret = os.environ.get("MCP_PATH", "").strip().strip("/")
    chemin = f"/{secret}/mcp" if secret else "/mcp"
    port = int(os.environ.get("PORT", "8000"))
    _token()                                                # échoue tout de suite si la clé manque
    _dire(f"[metricool_mcp] écoute sur 0.0.0.0:{port}{chemin}")
    if _SDK == 2:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port,
                streamable_http_path=chemin, stateless_http=True, json_response=True)
    else:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = port
        mcp.settings.streamable_http_path = chemin
        mcp.settings.stateless_http = True
        mcp.settings.json_response = True
        mcp.run(transport="streamable-http")
