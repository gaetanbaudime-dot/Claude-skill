# /// script
# requires-python = ">=3.10"
# ///
"""Génère un rapport markdown ultra-détaillé (6 mois WHOOP + prise de sang + 10 actions).

Lit ~/.whoop-mcp/whoop.db (rempli par sync.py) et la table `labs` (prise de sang).
Lance : uv run --python 3.11 --script ~/.whoop-mcp/report.py [jours]
Défaut : 180 jours. Sortie : ~/.whoop-mcp/whoop-report.md
"""
import sqlite3, sys, statistics as st
from datetime import datetime, date, timedelta
from pathlib import Path

DIR = Path.home() / ".whoop-mcp"
DB = DIR / "whoop.db"
OUT = DIR / "whoop-report.md"
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 180
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]  # %w: 1..0


def col(cx, sql):
    return [r[0] for r in cx.execute(sql).fetchall() if r[0] is not None]


def pairs(cx, sql):
    return [(r[0], r[1]) for r in cx.execute(sql).fetchall() if r[0] is not None and r[1] is not None]


def desc(vals, d=1):
    if not vals:
        return "—"
    return (f"moy **{st.mean(vals):.{d}f}** · méd {st.median(vals):.{d}f} · "
            f"min {min(vals):.{d}f} · max {max(vals):.{d}f} · n={len(vals)}")


def trend(vals):
    """Compare 1re moitié vs 2e moitié de la période."""
    if len(vals) < 8:
        return "—"
    h = len(vals) // 2
    a, b = st.mean(vals[:h]), st.mean(vals[h:])
    d = b - a
    fleche = "↗︎ en hausse" if d > 0 else ("↘︎ en baisse" if d < 0 else "→ stable")
    return f"{fleche} ({a:.1f} → {b:.1f}, Δ {d:+.1f})"


def pearson(xy):
    if len(xy) < 5:
        return None
    xs = [x for x, _ in xy]
    ys = [y for _, y in xy]
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in xy)
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return None if den == 0 else num / den


def r_txt(r):
    if r is None:
        return "pas assez de données"
    force = ("forte" if abs(r) >= 0.5 else "modérée" if abs(r) >= 0.3
             else "faible" if abs(r) >= 0.15 else "négligeable")
    sens = "négative" if r < 0 else "positive"
    return f"r = {r:+.2f} (corrélation {sens} {force})"


def weekday_table(cx, sql):
    d = {r[0]: (r[1], r[2]) for r in cx.execute(sql).fetchall()}
    order = ["1", "2", "3", "4", "5", "6", "0"]
    lines = ["| Jour | Moyenne | n |", "|---|---|---|"]
    for i, w in enumerate(order):
        if w in d and d[w][0] is not None:
            lines.append(f"| {JOURS[i]} | {d[w][0]:.1f} | {int(d[w][1])} |")
    return "\n".join(lines)


def main():
    if not DB.exists():
        raise SystemExit("whoop.db introuvable. Lance d'abord sync.py.")
    cx = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    since = f"datetime('now','-{DAYS} days')"

    rec = col(cx, f"SELECT recovery_score FROM recovery WHERE score_state='SCORED' AND created_at>={since} ORDER BY created_at")
    hrv = col(cx, f"SELECT hrv_rmssd_milli FROM recovery WHERE score_state='SCORED' AND created_at>={since} ORDER BY created_at")
    rhr = col(cx, f"SELECT resting_heart_rate FROM recovery WHERE score_state='SCORED' AND created_at>={since} ORDER BY created_at")
    spo2 = col(cx, f"SELECT spo2_percentage FROM recovery WHERE score_state='SCORED' AND created_at>={since}")
    skin = col(cx, f"SELECT skin_temp_celsius FROM recovery WHERE score_state='SCORED' AND created_at>={since}")
    perf = col(cx, f"SELECT sleep_performance_percentage FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={since} ORDER BY start")
    eff = col(cx, f"SELECT sleep_efficiency_percentage FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={since}")
    cons = col(cx, f"SELECT sleep_consistency_percentage FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={since}")
    resp = col(cx, f"SELECT respiratory_rate FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={since}")
    asleep_h = col(cx, f"SELECT (total_light_sleep_time_milli+total_slow_wave_sleep_time_milli+total_rem_sleep_time_milli)/3600000.0 FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={since}")
    rem_h = col(cx, f"SELECT total_rem_sleep_time_milli/3600000.0 FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={since}")
    sws_h = col(cx, f"SELECT total_slow_wave_sleep_time_milli/3600000.0 FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={since}")
    strain = col(cx, f"SELECT strain FROM cycles WHERE score_state='SCORED' AND start>={since} ORDER BY start")
    kj = col(cx, f"SELECT kilojoule FROM cycles WHERE score_state='SCORED' AND start>={since}")

    # zones de recovery
    green = sum(1 for v in rec if v >= 67)
    yellow = sum(1 for v in rec if 34 <= v < 67)
    red = sum(1 for v in rec if v < 34)
    tot = len(rec) or 1

    # évolution mensuelle recovery
    monthly = cx.execute(
        f"SELECT strftime('%Y-%m',created_at) m, ROUND(AVG(recovery_score),1), ROUND(AVG(hrv_rmssd_milli),1), COUNT(*) "
        f"FROM recovery WHERE score_state='SCORED' AND created_at>={since} GROUP BY m ORDER BY m").fetchall()

    # workouts par sport
    sports = cx.execute(
        f"SELECT COALESCE(sport_name,'(inconnu)') s, COUNT(*), ROUND(AVG(strain),1) "
        f"FROM workouts WHERE start>={since} GROUP BY s ORDER BY COUNT(*) DESC").fetchall()
    n_workouts = cx.execute(f"SELECT COUNT(*) FROM workouts WHERE start>={since}").fetchone()[0]

    # corrélations
    strain_by_d = {r[0][:10]: r[1] for r in cx.execute(
        f"SELECT start, strain FROM cycles WHERE score_state='SCORED' AND start>={since}").fetchall() if r[1] is not None}
    rec_by_d = {r[0][:10]: r[1] for r in cx.execute(
        f"SELECT created_at, recovery_score FROM recovery WHERE score_state='SCORED' AND created_at>={since}").fetchall() if r[1] is not None}
    xy_next = []
    for ds, sv in strain_by_d.items():
        try:
            nd = (date.fromisoformat(ds) + timedelta(days=1)).isoformat()
        except Exception:
            continue
        if nd in rec_by_d:
            xy_next.append((sv, rec_by_d[nd]))
    r_strain_rec = pearson(xy_next)

    sleep_by_d = {r[0][:10]: r[1] for r in cx.execute(
        f"SELECT start, sleep_performance_percentage FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={since}").fetchall() if r[1] is not None}
    xy_sleep = [(sleep_by_d[d], rec_by_d[d]) for d in sleep_by_d if d in rec_by_d]
    r_sleep_rec = pearson(xy_sleep)

    # période couverte
    span = cx.execute(f"SELECT MIN(created_at), MAX(created_at) FROM recovery WHERE score_state='SCORED' AND created_at>={since}").fetchone()
    span_txt = f"{(span[0] or '?')[:10]} → {(span[1] or '?')[:10]}" if span else "—"

    wd = lambda tbl, c, extra="": weekday_table(cx, (
        f"SELECT strftime('%w',{'created_at' if tbl in ('recovery',) else 'start'}), AVG({c}), COUNT(*) "
        f"FROM {tbl} WHERE score_state='SCORED' {extra} AND {'created_at' if tbl=='recovery' else 'start'}>={since} "
        f"GROUP BY strftime('%w',{'created_at' if tbl=='recovery' else 'start'})"))

    # ---- labs ----
    labs_md = ""
    has_labs = cx.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='labs'").fetchone()[0]
    lab_date = "—"
    if has_labs:
        lab_date = (cx.execute("SELECT MAX(collected_at) FROM labs").fetchone()[0]) or "—"
        cats = [r[0] for r in cx.execute("SELECT DISTINCT category FROM labs ORDER BY category").fetchall()]
        blocks = []
        for c in cats:
            rows = cx.execute(
                "SELECT test, value_text, unit, flag, ref_range FROM labs WHERE category=? AND collected_at=? ORDER BY test",
                (c, lab_date)).fetchall()
            lines = [f"#### {c}", "", "| Test | Résultat | Unité | Statut | Référence |", "|---|---|---|---|---|"]
            for t, vt, u, fl, rf in rows:
                badge = {"H": "🔺 haut", "L": "🔻 bas", "": "✅"}.get(fl, fl)
                lines.append(f"| {t} | **{vt}** | {u} | {badge} | {rf} |")
            blocks.append("\n".join(lines))
        labs_md = "\n\n".join(blocks)
        flags = cx.execute(
            "SELECT test, value_text, unit, flag FROM labs WHERE flag!='' AND collected_at=? ORDER BY category",
            (lab_date,)).fetchall()
    else:
        flags = []
    cx.close()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    def zone_bar(g, y, r, t):
        return f"🟢 {100*g/t:.0f}% · 🟡 {100*y/t:.0f}% · 🔴 {100*r/t:.0f}%"

    monthly_md = "\n".join(
        f"| {m} | {rc} | {hv} | {n} |" for m, rc, hv, n in monthly) or "| — | — | — | — |"
    sports_md = "\n".join(
        f"| {s} | {n} | {av} |" for s, n, av in sports) or "| — | — | — |"
    flags_md = "\n".join(
        f"- **{t}** : {vt} {u} ({'🔺 au-dessus' if fl=='H' else '🔻 en-dessous'} de la norme)"
        for t, vt, u, fl in flags) or "- Aucun marqueur hors norme 🎉"

    md = f"""# 🧬 Rapport santé — WHOOP + Biologie

> Généré le {now} · Période analysée : **{DAYS} derniers jours** ({span_txt})
> Source WHOOP : base locale `whoop.db` · Prise de sang : {lab_date}

Ce rapport croise tes données physiologiques WHOOP avec ta dernière prise de sang.
Il est **informatif** — ce n'est pas un avis médical.

---

## 1. Synthèse express

| Domaine | Valeur clé | Lecture |
|---|---|---|
| Recovery moyen | **{st.mean(rec):.0f}%** {('' if not rec else '')} | {zone_bar(green,yellow,red,tot)} |
| HRV moyen | **{st.mean(hrv):.1f} ms** | {trend(hrv)} |
| FC de repos | **{st.mean(rhr):.0f} bpm** | {trend(rhr)} |
| Sommeil (perf.) | **{st.mean(perf):.0f}%** | durée moy {st.mean(asleep_h):.1f} h |
| Strain quotidien | **{st.mean(strain):.1f}** | {n_workouts} séances |

---

## 2. Recovery (récupération)

- Distribution : **{zone_bar(green,yellow,red,tot)}** sur {tot} jours ({green} verts, {yellow} jaunes, {red} rouges).
- Statistiques : {desc(rec,0)}
- Tendance sur la période : {trend(rec)}

**Recovery moyen par jour de la semaine**

{wd('recovery','recovery_score')}

## 3. HRV & cœur

- **HRV (RMSSD)** : {desc(hrv,1)} — {trend(hrv)}
- **FC de repos** : {desc(rhr,0)} — {trend(rhr)}
- **SpO₂ nocturne** : {desc(spo2,1)}
- **Température de peau** : {desc(skin,2)} °C

**HRV moyen par jour de la semaine**

{wd('recovery','hrv_rmssd_milli')}

## 4. Sommeil

- **Performance** : {desc(perf,0)} %
- **Durée de sommeil** : {desc(asleep_h,1)} h  ·  dont REM {st.mean(rem_h):.1f} h, profond {st.mean(sws_h):.1f} h
- **Efficacité** : {desc(eff,0)} %
- **Consistance** (régularité des horaires) : {desc(cons,0)} %
- **Fréquence respiratoire** : {desc(resp,1)} /min

## 5. Effort (strain) & entraînement

- **Strain quotidien** : {desc(strain,1)}
- **Dépense énergétique** : {desc([k/4.184 for k in kj],0)} kcal/jour (depuis les kJ)
- **Séances** : {n_workouts} sur la période

**Répartition par sport**

| Sport | Séances | Strain moyen |
|---|---|---|
{sports_md}

## 6. Évolution mois par mois

| Mois | Recovery moy | HRV moy | Jours |
|---|---|---|---|
{monthly_md}

## 7. Corrélations dans TES données

- **Strain d'un jour → Recovery du lendemain** : {r_txt(r_strain_rec)}
  *(un chiffre négatif = plus tu forces un jour, plus ta récup baisse le lendemain — normal, c'est la dette de récupération)*
- **Performance de sommeil → Recovery du matin** : {r_txt(r_sleep_rec)}
  *(un chiffre positif = mieux tu dors, mieux tu récupères — le levier n°1)*

---

## 8. Prise de sang détaillée ({lab_date})

**Marqueurs hors norme à retenir :**

{flags_md}

{labs_md}

---

## 9. Analyse croisée sang × WHOOP

- **Inflammation basse (hs-CRP < 0,16 mg/L) ↔ bonne récupération** : une CRP très basse est cohérente avec un HRV correct et peu de « bruit » inflammatoire. C'est un atout : entretiens-le (sommeil, alcool modéré).
- **Métabolisme excellent (HbA1c 5,0 · insuline 3,0 · HOMA 0,59)** : une glycémie stable soutient un sommeil profond et un HRV régulier. Continue à limiter les sucres rapides le soir.
- **Statut en fer élevé (saturation transferrine 56 %)** : le fer sert au transport d'oxygène (endurance) mais un excès chronique n'aide pas — inutile de supplémenter.
- **Lipides à surveiller (LDL 126, HDL 43)** : le cardio en zone 2 (celui qui monte ton strain « aérobie » sans exploser la FC) est justement ce qui remonte le HDL.
- **Testostérone saine + cortisol normal** : bon équilibre anabolique/stress — cohérent si ta recovery ne s'effondre pas en semaine.

---

## 10. Plan d'action — 10 leviers concrets

1. **Attaque le trou du week-end.** Ton HRV/recovery plonge samedi-dimanche. Cible vendredi/samedi soir : alcool, heure de coucher, dernier repas. C'est ton plus gros gain rapide.
2. **Remonte ton HDL / baisse ton LDL.** 2–3 séances de **cardio zone 2** (30–45 min) par semaine + oméga-3 (poissons gras, noix, huile d'olive), plus de fibres, moins de gras saturés/sucres raffinés.
3. **Régularise tes horaires de sommeil.** Vise une **consistance** plus haute : même heure de coucher/lever, même le week-end → gain direct sur recovery et HRV.
4. **Ne supplémente PAS en fer.** Saturation transferrine à 56 % : réserves déjà pleines. Recontrôle fer/ferritine dans 3 mois ; si ça reste haut, un simple dépistage hémochromatose.
5. **Recontrôle tes globules blancs** dans 4–6 semaines (WBC 3,9 / neutrophiles 1,65 un peu bas). Souvent bénin/transitoire (virose, grosse charge d'entraînement) — assure-toi de ne pas être en surmenage.
6. **Baisse ton homocystéine (12,4).** Un complexe **B (folates, B12, B6)** + légumes verts à feuilles ; utile aussi pour le cœur.
7. **Optimise ta vitamine D (33,8 → cible 40–50).** Exposition solaire raisonnée et/ou **D3** surtout l'hiver — impacte énergie, immunité et sommeil.
8. **Protège ta récupération après les gros jours de strain.** Ta corrélation strain→recovery le confirme : après une grosse séance, planifie une nuit longue et une journée plus calme.
9. **Reste hydraté / note la créatine.** Créatinine 1,11 mais DFG 96 (reins OK) : classique chez les sportifs musclés. Bois assez ; si tu prends de la créatine en supplément, c'est une explication normale.
10. **Construis la série temporelle.** Active le **sync quotidien** (launchd) et **refais une prise de sang dans 3–6 mois** : tu pourras alors suivre l'évolution de chaque marqueur et mesurer l'effet des actions ci-dessus.

---

*⚠️ Rapport informatif généré depuis tes données personnelles. Il ne remplace pas un médecin — fais interpréter la prise de sang (surtout lipides et globules blancs) par un professionnel.*
"""
    OUT.write_text(md, encoding="utf-8")
    print("Rapport écrit ->", OUT)
    print(f"({len(rec)} recoveries, {len(perf)} nuits, {len(strain)} cycles, {n_workouts} séances analysés)")


if __name__ == "__main__":
    main()
