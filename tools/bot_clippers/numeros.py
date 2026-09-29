"""Vérification du numéro WhatsApp du formulaire (30/09, Gaëtan : « assure-toi qu'ils ne mettent pas des numéros erronés »).

Le 29/09, la liste des clippeurs du Discord a sorti des numéros inutilisables : un « +220 » (Gambie) pour un candidat du
Bénin, des numéros malgaches à 8 chiffres au lieu de 9, un numéro béninois sans le « 01 » ajouté en 2024. Chaque numéro
faux, c'est une relance WhatsApp impossible — et WhatsApp est le canal où ils répondent le plus vite.

`verifier(brut, pays)` → (numéro +E164 ou "", joli format « +229 01 90 90 21 87 », erreur, alerte) :
- erreur : le numéro n'existe pas (trop court, trop long, indicatif impossible) → le formulaire est réaffiché, rien n'est
  enregistré ;
- alerte : le numéro existe mais surprend (un autre pays que celui choisi, un fixe) → réaffiché une fois ; s'il renvoie le
  même numéro, on l'accepte (un Français qui vit à Madagascar garde son +33).
Corrigé sans rien demander : le numéro béninois à 8 chiffres (on ajoute le « 01 »), le numéro local sans indicatif (lu
avec le pays choisi), l'indicatif sans « + », le « 0 » qui traîne après l'indicatif (+33 06…).

Sans la bibliothèque phonenumbers (requirements.txt), on retombe sur l'ancienne lecture du bot : aucun blocage."""

import re

try:
    import phonenumbers
    from phonenumbers import PhoneNumberType, geocoder
except ImportError:                                                     # pragma: no cover
    phonenumbers = None

REGIONS = {"madagascar": "MG", "benin": "BJ", "cameroun": "CM", "nigeria": "NG", "cote d'ivoire": "CI",
           "france": "FR", "belgique": "BE", "maurice": "MU", "suisse": "CH", "togo": "TG", "senegal": "SN"}
NOMS = {"MG": "Madagascar", "BJ": "Bénin", "CM": "Cameroun", "NG": "Nigeria", "CI": "Côte d'Ivoire", "FR": "France",
        "BE": "Belgique", "MU": "Maurice", "CH": "Suisse", "TG": "Togo", "SN": "Sénégal", "GM": "Gambie"}
EXEMPLES = {"MG": "+261 34 12 345 67", "BJ": "+229 01 90 12 34 56", "CM": "+237 6 12 34 56 78",
            "NG": "+234 803 123 4567", "CI": "+225 07 12 34 56 78", "FR": "+33 6 12 34 56 78",
            "BE": "+32 470 12 34 56", "MU": "+230 5 123 4567"}


def _sans_accents(texte: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte or "") if unicodedata.category(c) != "Mn").lower().strip()


def region_du_pays(pays: str) -> str:
    p = _sans_accents(pays)
    return next((r for nom, r in REGIONS.items() if nom in p), "")


def nom_pays(region: str, numero=None) -> str:
    if region in NOMS:
        return NOMS[region]
    if numero is not None and phonenumbers:
        return geocoder.country_name_for_number(numero, "fr") or region
    return region


def _lectures(brut: str, region: str, secours: str):
    """Les lectures possibles, la plus probable d'abord (objets phonenumbers)."""
    t = re.sub(r"[^\d+]", "", brut or "")
    if t.startswith("00"):
        t = "+" + t[2:]
    essais = [(t, region or None)]
    if t and not t.startswith("+"):
        essais.append(("+" + t, None))                                  # « 261341234567 » : l'indicatif sans le +
    if secours:
        essais.append((secours, None))                                  # la lecture historique du bot (+33 06…, 03x…)
    vus = set()
    for texte, reg in essais:
        if not texte or (texte, reg) in vus:
            continue
        vus.add((texte, reg))
        try:
            yield phonenumbers.parse(texte, reg)
        except phonenumbers.NumberParseException:
            continue


def _benin_01(numero):
    """Bénin : depuis le 30/11/2024 les mobiles ont 10 chiffres (« 01 » devant l'ancien numéro à 8 chiffres)."""
    nsn = str(numero.national_number)
    if numero.country_code == 229 and len(nsn) == 8:
        try:
            return phonenumbers.parse("+22901" + nsn)
        except phonenumbers.NumberParseException:
            return None
    return None


def verifier(brut: str, pays: str = "", secours: str = "") -> tuple:
    """(e164, joli, erreur, alerte). `secours` : la lecture de tel_selon_pays du bot, essayée si la nôtre échoue."""
    region = region_du_pays(pays)
    exemple = EXEMPLES.get(region, "+261 34 12 345 67")
    if phonenumbers is None:
        return (secours, secours, "" if secours else f"Le numéro WhatsApp n'est pas lisible. Exemple : {exemple}", "")
    if len(re.sub(r"\D", "", brut or "")) < 6:
        return ("", "", f"Ton numéro WhatsApp est trop court. Écris-le en entier avec l'indicatif. Exemple : {exemple}", "")
    trouve, premier = None, None
    for numero in _lectures(brut, region, secours):
        premier = premier or numero
        corrige = _benin_01(numero)
        if corrige is not None and phonenumbers.is_valid_number(corrige):
            numero = corrige
        if phonenumbers.is_valid_number(numero):
            trouve = numero
            break
    if trouve is None:
        if premier is not None and region and phonenumbers.region_code_for_number(premier) not in ("", None, region):
            autre = phonenumbers.region_code_for_number(premier)
            return ("", "", f"Ton numéro commence par +{premier.country_code} ({nom_pays(autre, premier)}) et il n'est pas "
                            f"complet. Pour le pays choisi ({nom_pays(region)}), l'indicatif est +{phonenumbers.country_code_for_region(region)}. "
                            f"Exemple : {exemple}", "")
        return ("", "", f"Ce numéro WhatsApp n'existe pas : il manque ou il y a un chiffre en trop. Vérifie-le. "
                        f"Exemple : {exemple}", "")
    e164 = phonenumbers.format_number(trouve, phonenumbers.PhoneNumberFormat.E164)
    joli = phonenumbers.format_number(trouve, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    reg_num = phonenumbers.region_code_for_number(trouve)
    if region and reg_num != region:
        return (e164, joli, "", f"Ton numéro {joli} commence par +{trouve.country_code} ({nom_pays(reg_num, trouve)}), mais "
                                f"tu as choisi {nom_pays(region)}. Si c'est bien ton WhatsApp, appuie de nouveau sur le bouton. "
                                f"Sinon, corrige-le.")
    if phonenumbers.number_type(trouve) == PhoneNumberType.FIXED_LINE:
        return (e164, joli, "", f"{joli} est un numéro de fixe, pas de portable. Si c'est bien ton WhatsApp, appuie de "
                                f"nouveau sur le bouton. Sinon, mets ton numéro de portable.")
    return (e164, joli, "", "")
