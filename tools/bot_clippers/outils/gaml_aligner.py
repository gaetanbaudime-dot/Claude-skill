"""Aligne les liens GAML des clippers sur la page de référence de leur créatrice (design, bio, fond, cartes), avec les codes de
tracking OnlyFans / MYM du classeur des logins (29/09/2026, Gaëtan : « je veux exactement les mêmes à chaque fois, on va
rediriger vers MYM et OF, images, textes, photos, widget ; fais gaffe à ce que les liens de tracking correspondent au sheets »).

Règles : la référence d'une créatrice est sa page principale (slug qui finit par « : ») ; un lien de clipper reçoit son design,
sa bio, son fond (téléversé, l'ancien retiré) et ses cartes dans le même ordre, avec SES codes : OnlyFans et MYM lus dans le bloc
du classeur qui porte ce lien, sinon ceux déjà sur la page, jamais ceux de la référence. Les cartes neuves sont créées avant
que les anciennes soient retirées (une limite d'API en plein milieu ne laisse jamais une page vide). Les liens « :fb », « :ytb »
et les références ne sont pas touchés.

Usage (depuis tools/bot_clippers, avec GAML_API_KEY, CLASSEUR_LOGINS_ID et GOOGLE_SERVICE_ACCOUNT_JSON dans l'environnement) :
    python3 outils/gaml_aligner.py DOSSIER_TRAVAIL [slug ...]
DOSSIER_TRAVAIL contient gaml_ref/ (fonds et cartes de référence téléchargés) et, si une référence n'est plus lisible par l'API,
gaml_liens.json (instantané des liens). Sans slug : tous les liens numérotés de Chloé, Sarah et Jade."""
import asyncio, json, os, re, subprocess, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paie_clics as pc, onboarding as ob, classeur_forme as cf  # noqa: E402
S = sys.argv[1] if len(sys.argv) > 1 else "."
REF = {"Chloé": "chloecallistafr:", "Sarah": "sarahivanovafr:", "Jade": "jadetorafr:"}
FICHIERS = {"Chloé": ("chloe_fond.png", {"Miam": "chloe_carte0_Miam.jpg", "0F": "chloe_carte1_0F.jpg"}),
            "Sarah": ("sarah_fond.jpg", {"Miam": "sarah_carte0_Miam.jpg", "0F": "sarah_carte1_0F.jpg"}),
            "Jade": ("jade_fond.mp4", {})}
DESIGN = ("template", "templateConfig", "contentStyle", "buttonStyle", "backgroundType", "textColor", "templateColor", "iconColor",
          "buttonColor", "buttonTextColor", "buttonIconColor", "hideContentIcons", "shield", "isDeeplinkEnabled", "isDeeplinkLongPress",
          "isDeeplinkHint", "geoip", "online", "replyTime", "bio")
def n(t): return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn")
cf.configurer({"normaliser": n})
def televerser(url, fichier):
    r = subprocess.run(["curl", "-sS", "-m", "120", "-X", "POST", url, "-H", f"X-Api-Key: {pc.GAML_API_KEY}", "-F", f"file=@{fichier}"], capture_output=True, text=True)
    import time; time.sleep(1.5)
    try: return json.loads(r.stdout)
    except ValueError: return {"erreur": r.stdout[:200] or r.stderr[:200]}
async def appel(methode, chemin, corps=None):
    for essai in range(4):
        try:
            r = await pc._requete(methode, chemin, corps=corps)
            await asyncio.sleep(1.3)                                        # 60 appels/min : on reste large
            return r
        except RuntimeError as e:
            if "trop de tentatives" in str(e) or "429" in str(e):
                await asyncio.sleep(65); continue
            raise
    raise RuntimeError(f"GAML : limite tenace sur {chemin}")
def code_of(v):  m = re.search(r"onlyfans\.com/[^/]+/(\w+)", v or ""); return m.group(1) if m else ""
def code_mym(v): m = re.search(r"mym\.fans/app/t/(\w+)", v or ""); return m.group(1) if m else ""
async def main(cibles):
    liens = await pc._requete("GET", "/links"); liens = liens.get("links", liens) if isinstance(liens, dict) else liens
    details = {}
    for l in liens:
        if (l.get("group") or {}).get("name") in REF:
            d = await pc.lien_detail(l["id"]); details[d["slug"]] = d
    instantane = json.load(open(f"{S}/gaml_liens.json"))                  # copie du 29/09 : sert quand une référence n'est plus lisible
    for slug_ref in REF.values():
        if slug_ref not in details:
            details[slug_ref] = next(v for v in instantane.values() if v.get("slug") == slug_ref)
            print("référence", slug_ref, "prise dans l'instantané")
    # Jade : sa référence n'a qu'un bouton OnlyFans ; on va « rediriger vers MYM et OF » → un bouton MYM en plus, sans image
    if not any("mym" in (c.get("value") or "") for c in details["jadetorafr:"].get("contents") or []):
        details["jadetorafr:"]["contents"] = list(details["jadetorafr:"].get("contents") or []) + [
            {"name": "Miam", "value": "https://mym.fans/", "effect": None, "cardType": "simple", "is18Plus": True, "image": ""}]
    comptes = await ob.lire_comptes()
    attendu = {}
    for t in REF:
        for g, lignes in cf.blocs([c for c in comptes if c["onglet"] == t]):
            a = lignes[0]; url = (a.get("lien_gaml") or "").strip().rstrip("/")
            if url and url not in attendu: attendu[url] = (g, a.get("lien_infloww", "").strip(), a.get("lien_mym", "").strip())
    rapport = []
    for slug, d in sorted(details.items()):
        crea = d["group"]["name"]
        if slug == REF[crea] or not re.search(r":\d+$", slug) or (cibles and slug not in cibles):
            continue
        ref = details[REF[crea]]
        g, of_s, mym_s = attendu.get((d.get("url") or "").rstrip("/"), ("", "", ""))
        of_page = next((c.get("value") for c in d.get("contents") or [] if "onlyfans" in (c.get("value") or "")), "")
        mym_page = next((c.get("value") for c in d.get("contents") or [] if "mym" in (c.get("value") or "")), "")
        ref_of = next((c.get("value") for c in ref.get("contents") or [] if "onlyfans" in (c.get("value") or "")), "")
        ref_mym = next((c.get("value") for c in ref.get("contents") or [] if "mym" in (c.get("value") or "")), "")
        if code_of(of_page) == code_of(ref_of): of_page = ""                # un clone porte le code de la référence : pas le sien
        if code_mym(mym_page) == code_mym(ref_mym): mym_page = ""
        of, mym = (of_s or of_page), (mym_s or mym_page)
        notes = []
        if of_s and of_page and code_of(of_s) != code_of(of_page): notes.append(f"OF page {code_of(of_page)} → classeur {code_of(of_s)}")
        if mym_s and mym_page and code_mym(mym_s) != code_mym(mym_page): notes.append(f"MYM page → classeur")
        if not of: notes.append("pas de code OF")
        if not mym: notes.append("pas de lien MYM")
        # 1. design + bio
        await appel("PATCH", f"/links/{d['id']}", corps={k: ref.get(k) for k in DESIGN if ref.get(k) is not None or k in ("templateColor", "replyTime")})
        # 2. fond : celui de la référence, les anciens retirés
        fond, cartes = FICHIERS[crea]
        anciens = [b["id"] for b in d.get("backgroundFiles") or []]
        rep = televerser(f"{pc.API}/links/{d['id']}/background-files", f"{S}/gaml_ref/{fond}")
        if rep.get("erreur") or "id" not in json.dumps(rep): notes.append(f"fond non téléversé : {str(rep)[:80]}")
        else:
            for b in anciens:
                try: await appel("DELETE", f"/background-files/{b}")
                except Exception as e: notes.append(f"ancien fond : {str(e)[:60]}")
        # 3. cartes : celles de la référence, valeurs du clipper — créées D'ABORD, les anciennes retirées ENSUITE
        anciennes_cartes = [c["id"] for c in d.get("contents") or []]
        for rc in ref.get("contents") or []:
            est_mym = "mym" in (rc.get("value") or ""); valeur = mym if est_mym else of
            if not valeur:
                continue
            attrs = {"name": rc["name"], "value": valeur, "effect": rc.get("effect"), "cardType": rc.get("cardType") or "simple", "is18Plus": bool(rc.get("is18Plus"))}
            nouveau = await appel("POST", f"/links/{d['id']}/contents", corps=attrs)
            nid = nouveau.get("id") or (nouveau.get("content") or {}).get("id")
            if rc.get("image") and nid and cartes.get(rc["name"]):
                r_img = televerser(f"{pc.API}/contents/{nid}/image", f"{S}/gaml_ref/{cartes[rc['name']]}")
                if r_img.get("erreur"): notes.append(f"image {rc['name']} : {str(r_img)[:60]}")
        for cid in anciennes_cartes:
            try: await appel("DELETE", f"/contents/{cid}")
            except Exception as e: notes.append(f"ancienne carte : {str(e)[:50]}")
        # 4. vérification
        apres = await appel("GET", f"/links/{d['id']}")
        boutons = [(c["name"], c.get("effect"), bool(c.get("image")), "MYM" if "mym" in (c.get("value") or "") else "OF") for c in apres.get("contents") or []]
        rapport.append((slug, g or "—", code_of(of), code_mym(mym)[-6:], len(apres.get("backgroundFiles") or []), boutons, notes))
        print("fait :", slug, flush=True)
    for slug, g, of, mym, nf, boutons, notes in rapport:
        print(f"{slug:<20} {g:<10} OF={of:<5} MYM={mym:<7} fonds={nf} boutons={boutons} {'· ' + ' ; '.join(notes) if notes else ''}")
asyncio.run(main(set(sys.argv[2:])))
