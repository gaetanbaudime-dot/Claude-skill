# /// script
# requires-python = ">=3.10"
# ///
"""Export markdown BRUT et complet des données WHOOP + prise de sang (aucune analyse).

Sort toutes les métriques disponibles sur N jours : tableaux quotidiens complets,
tendances mensuelles, moyennes par jour de semaine, et la prise de sang intégrale.
Lance : uv run --python 3.11 --script ~/.whoop-mcp/export.py [jours]
Défaut : 365 jours. Sortie : ~/.whoop-mcp/whoop-export.md
"""
import sqlite3, sys, statistics as st
from datetime import datetime
from pathlib import Path

DIR = Path.home() / ".whoop-mcp"
DB = DIR / "whoop.db"
OUT = DIR / "whoop-export.md"
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 365
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def f(v, d=1):
    return "" if v is None else f"{v:.{d}f}"


def stats_line(cx, sql, d=1):
    vals = [r[0] for r in cx.execute(sql).fetchall() if r[0] is not None]
    if not vals:
        return "aucune donnée"
    return (f"n={len(vals)} · moy {st.mean(vals):.{d}f} · méd {st.median(vals):.{d}f} · "
            f"min {min(vals):.{d}f} · max {max(vals):.{d}f} · "
            f"écart-type {st.pstdev(vals):.{d}f}")


def wd_table(cx, table, tcol, metric):
    d = {r[0]: (r[1], r[2]) for r in cx.execute(
        f"SELECT strftime('%w',{tcol}), AVG({metric}), COUNT(*) FROM {table} "
        f"WHERE score_state='SCORED' AND {tcol}>=datetime('now','-{DAYS} days') "
        f"GROUP BY strftime('%w',{tcol})").fetchall()}
    out = ["| Jour | Moyenne | n |", "|---|---|---|"]
    for i, w in enumerate(["1", "2", "3", "4", "5", "6", "0"]):
        if w in d and d[w][0] is not None:
            out.append(f"| {JOURS[i]} | {d[w][0]:.1f} | {int(d[w][1])} |")
    return "\n".join(out)


def main():
    if not DB.exists():
        raise SystemExit("whoop.db introuvable. Lance d'abord sync.py.")
    cx = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    S = f"datetime('now','-{DAYS} days')"
    P = []  # morceaux du markdown
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    counts = {t: cx.execute(f'SELECT COUNT(*) FROM "{t}" WHERE ' +
              ("created_at" if t == "recovery" else "start") + f">={S}").fetchone()[0]
              for t in ("recovery", "sleep", "cycles", "workouts")}

    P.append(f"""# 📦 Export santé complet — WHOOP + Biologie

> Généré le {now} · Période : **{DAYS} derniers jours**
> Données brutes, sans interprétation. Source : `whoop.db` (API WHOOP v2).

**Volumétrie sur la période** : {counts['recovery']} recoveries · {counts['sleep']} nuits · {counts['cycles']} cycles · {counts['workouts']} séances.

> ℹ️ **Non disponible via l'API WHOOP** (donc absent de cet export) : le **Journal** (alcool,
> caféine, suppléments, comportements), les données de stress en continu et les événements
> temps réel. L'API publique n'expose que : recovery, sommeil, cycles/strain, workouts,
> profil et mensurations.
""")

    # ---- Statistiques globales ----
    P.append("## 1. Statistiques globales\n")
    P.append("| Métrique | Résumé |\n|---|---|")
    rows = [
        ("Recovery (%)", "SELECT recovery_score FROM recovery WHERE score_state='SCORED' AND created_at>=" + S, 0),
        ("HRV RMSSD (ms)", "SELECT hrv_rmssd_milli FROM recovery WHERE score_state='SCORED' AND created_at>=" + S, 1),
        ("FC de repos (bpm)", "SELECT resting_heart_rate FROM recovery WHERE score_state='SCORED' AND created_at>=" + S, 0),
        ("SpO2 (%)", "SELECT spo2_percentage FROM recovery WHERE score_state='SCORED' AND created_at>=" + S, 1),
        ("Temp. peau (°C)", "SELECT skin_temp_celsius FROM recovery WHERE score_state='SCORED' AND created_at>=" + S, 2),
        ("Perf. sommeil (%)", "SELECT sleep_performance_percentage FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>=" + S, 0),
        ("Efficacité sommeil (%)", "SELECT sleep_efficiency_percentage FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>=" + S, 0),
        ("Consistance sommeil (%)", "SELECT sleep_consistency_percentage FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>=" + S, 0),
        ("Fréq. respiratoire (/min)", "SELECT respiratory_rate FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>=" + S, 1),
        ("Durée sommeil (h)", "SELECT (total_light_sleep_time_milli+total_slow_wave_sleep_time_milli+total_rem_sleep_time_milli)/3600000.0 FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>=" + S, 1),
        ("Strain quotidien", "SELECT strain FROM cycles WHERE score_state='SCORED' AND start>=" + S, 1),
        ("Dépense (kJ)", "SELECT kilojoule FROM cycles WHERE score_state='SCORED' AND start>=" + S, 0),
        ("FC moy cycle (bpm)", "SELECT average_heart_rate FROM cycles WHERE score_state='SCORED' AND start>=" + S, 0),
        ("FC max cycle (bpm)", "SELECT max_heart_rate FROM cycles WHERE score_state='SCORED' AND start>=" + S, 0),
    ]
    for name, sql, d in rows:
        P.append(f"| {name} | {stats_line(cx, sql, d)} |")

    # ---- Tendances mensuelles ----
    P.append("\n## 2. Tendances mensuelles\n")
    P.append("| Mois | Recovery | HRV | FC repos | Perf. sommeil | Strain | Jours |\n|---|---|---|---|---|---|---|")
    m_rec = {r[0]: r[1:] for r in cx.execute(
        f"SELECT strftime('%Y-%m',created_at), ROUND(AVG(recovery_score),1), ROUND(AVG(hrv_rmssd_milli),1), ROUND(AVG(resting_heart_rate),1), COUNT(*) FROM recovery WHERE score_state='SCORED' AND created_at>={S} GROUP BY 1").fetchall()}
    m_sl = {r[0]: r[1] for r in cx.execute(
        f"SELECT strftime('%Y-%m',start), ROUND(AVG(sleep_performance_percentage),1) FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={S} GROUP BY 1").fetchall()}
    m_st = {r[0]: r[1] for r in cx.execute(
        f"SELECT strftime('%Y-%m',start), ROUND(AVG(strain),1) FROM cycles WHERE score_state='SCORED' AND start>={S} GROUP BY 1").fetchall()}
    for mo in sorted(set(m_rec) | set(m_sl) | set(m_st)):
        rc = m_rec.get(mo, (None, None, None, None))
        P.append(f"| {mo} | {f(rc[0])} | {f(rc[1])} | {f(rc[2])} | {f(m_sl.get(mo))} | {f(m_st.get(mo))} | {rc[3] or ''} |")

    # ---- Moyennes par jour de semaine ----
    P.append("\n## 3. Moyennes par jour de la semaine\n")
    P.append("### Recovery\n" + wd_table(cx, "recovery", "created_at", "recovery_score"))
    P.append("\n### HRV (ms)\n" + wd_table(cx, "recovery", "created_at", "hrv_rmssd_milli"))
    P.append("\n### FC de repos (bpm)\n" + wd_table(cx, "recovery", "created_at", "resting_heart_rate"))
    P.append("\n### Performance de sommeil (%)\n" + wd_table(cx, "sleep", "start", "sleep_performance_percentage"))
    P.append("\n### Strain\n" + wd_table(cx, "cycles", "start", "strain"))

    # ---- Détail quotidien : Recovery ----
    P.append("\n## 4. Détail quotidien — Recovery\n")
    P.append("| Date | Recovery % | HRV ms | FC repos | SpO2 % | Temp. peau °C |\n|---|---|---|---|---|---|")
    for r in cx.execute(f"SELECT substr(created_at,1,10), recovery_score, hrv_rmssd_milli, resting_heart_rate, spo2_percentage, skin_temp_celsius FROM recovery WHERE score_state='SCORED' AND created_at>={S} ORDER BY created_at DESC").fetchall():
        P.append(f"| {r[0]} | {f(r[1],0)} | {f(r[2],1)} | {f(r[3],0)} | {f(r[4],1)} | {f(r[5],2)} |")

    # ---- Détail quotidien : Sommeil ----
    P.append("\n## 5. Détail quotidien — Sommeil\n")
    P.append("| Date | Perf % | Effic. % | Consist. % | Resp. /min | Au lit h | Endormi h | Léger h | Profond h | REM h | Éveil h | Perturb. |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in cx.execute(f"""SELECT substr(start,1,10), sleep_performance_percentage, sleep_efficiency_percentage, sleep_consistency_percentage, respiratory_rate,
        total_in_bed_time_milli/3600000.0, (total_light_sleep_time_milli+total_slow_wave_sleep_time_milli+total_rem_sleep_time_milli)/3600000.0,
        total_light_sleep_time_milli/3600000.0, total_slow_wave_sleep_time_milli/3600000.0, total_rem_sleep_time_milli/3600000.0,
        total_awake_time_milli/3600000.0, disturbance_count
        FROM sleep WHERE score_state='SCORED' AND nap=0 AND start>={S} ORDER BY start DESC""").fetchall():
        P.append("| " + " | ".join([r[0], f(r[1],0), f(r[2],0), f(r[3],0), f(r[4],1), f(r[5],2), f(r[6],2), f(r[7],2), f(r[8],2), f(r[9],2), f(r[10],2), str(r[11] if r[11] is not None else "")]) + " |")

    # ---- Détail quotidien : Cycles / Strain ----
    P.append("\n## 6. Détail quotidien — Cycles (strain)\n")
    P.append("| Date | Strain | Dépense kJ | FC moy | FC max |\n|---|---|---|---|---|")
    for r in cx.execute(f"SELECT substr(start,1,10), strain, kilojoule, average_heart_rate, max_heart_rate FROM cycles WHERE score_state='SCORED' AND start>={S} ORDER BY start DESC").fetchall():
        P.append(f"| {r[0]} | {f(r[1],1)} | {f(r[2],0)} | {f(r[3],0)} | {f(r[4],0)} |")

    # ---- Séances ----
    P.append("\n## 7. Séances (workouts)\n")
    P.append("| Date | Sport | Strain | FC moy | FC max | kJ | Distance m |\n|---|---|---|---|---|---|---|")
    for r in cx.execute(f"SELECT substr(start,1,10), sport_name, strain, average_heart_rate, max_heart_rate, kilojoule, distance_meter FROM workouts WHERE start>={S} ORDER BY start DESC").fetchall():
        P.append(f"| {r[0]} | {r[1] or ''} | {f(r[2],1)} | {f(r[3],0)} | {f(r[4],0)} | {f(r[5],0)} | {f(r[6],0)} |")

    # ---- Prise de sang ----
    P.append("\n## 8. Prise de sang (complète)\n")
    has = cx.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='labs'").fetchone()[0]
    if not has:
        P.append("_Table `labs` absente — importe ta prise de sang pour la voir ici._")
    else:
        for (ld,) in cx.execute("SELECT DISTINCT collected_at FROM labs ORDER BY collected_at DESC").fetchall():
            P.append(f"\n### Prélèvement du {ld}\n")
            for (cat,) in cx.execute("SELECT DISTINCT category FROM labs WHERE collected_at=? ORDER BY category", (ld,)).fetchall():
                P.append(f"#### {cat}\n")
                P.append("| Test | Résultat | Unité | Statut | Référence | Source |\n|---|---|---|---|---|---|")
                for t, vt, u, fl, rf, src in cx.execute(
                        "SELECT test, value_text, unit, flag, ref_range, source FROM labs WHERE collected_at=? AND category=? ORDER BY test", (ld, cat)).fetchall():
                    badge = {"H": "🔺", "L": "🔻", "": "✅"}.get(fl, fl)
                    P.append(f"| {t} | {vt} | {u} | {badge} | {rf} | {src} |")
                P.append("")

    cx.close()
    OUT.write_text("\n".join(P) + "\n", encoding="utf-8")
    print("Export écrit ->", OUT)
    print(f"({counts['recovery']} recoveries, {counts['sleep']} nuits, {counts['cycles']} cycles, {counts['workouts']} séances)")


if __name__ == "__main__":
    main()
