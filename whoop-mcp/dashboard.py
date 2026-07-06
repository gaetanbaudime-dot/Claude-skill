# /// script
# requires-python = ">=3.10"
# ///
"""Génère un dashboard HTML autonome depuis whoop.db et l'ouvre dans le navigateur.

Graphiques SVG inline (aucune dépendance, aucun CDN, tout offline).
Lance : uv run --python 3.11 --script ~/.whoop-mcp/dashboard.py [jours]
Défaut : 90 derniers jours. Sortie : ~/.whoop-mcp/whoop-dashboard.html
"""
import sqlite3, sys, webbrowser
from datetime import datetime
from pathlib import Path

DIR = Path.home() / ".whoop-mcp"
DB = DIR / "whoop.db"
OUT = DIR / "whoop-dashboard.html"
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 90

PALETTE = {
    "recovery": "#34d399", "hrv": "#22d3ee", "rhr": "#fbbf24",
    "sleep": "#a78bfa", "strain": "#60a5fa",
}


def _series(cx, sql):
    rows = cx.execute(sql).fetchall()
    return [(r[0][:10], r[1]) for r in rows if r[1] is not None]


def spark(series, color, w=560, h=130, pad=20):
    if len(series) < 2:
        return '<div class="empty">Pas assez de données</div>'
    ys = [v for _, v in series]
    lo, hi = min(ys), max(ys)
    rng = (hi - lo) or 1
    n = len(ys)
    X = lambda i: pad + i * (w - 2 * pad) / (n - 1)
    Y = lambda v: h - pad - (v - lo) * (h - 2 * pad) / rng
    line = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(ys))
    area = f"{X(0):.1f},{h - pad:.1f} {line} {X(n - 1):.1f},{h - pad:.1f}"
    gid = "grad" + color.strip("#")
    dot_x, dot_y = X(n - 1), Y(ys[-1])
    return f'''<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="spark" role="img">
  <defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{color}" stop-opacity="0.30"/>
    <stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>
  <polygon points="{area}" fill="url(#{gid})"/>
  <polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.2"
    stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="{dot_x:.1f}" cy="{dot_y:.1f}" r="3.5" fill="{color}"/>
</svg>'''


def card(title, unit, series, color, digits=0):
    vals = [v for _, v in series]
    if not vals:
        body = '<div class="empty">Aucune donnée sur la période</div>'
        big, delta = "—", ""
    else:
        latest = vals[-1]
        avg = sum(vals) / len(vals)
        big = f"{latest:.{digits}f}"
        d = latest - avg
        arrow = "▲" if d >= 0 else "▼"
        cls = "up" if d >= 0 else "down"
        delta = (f'<span class="delta {cls}">{arrow} {abs(d):.{digits}f} vs moy. '
                 f'{avg:.{digits}f}</span>')
        body = spark(series, color)
    return f'''<article class="card">
  <header><h2>{title}</h2><span class="unit">{unit}</span></header>
  <div class="value" style="color:{color}">{big}<small>{unit}</small></div>
  {delta}
  <div class="chart">{body}</div>
  <footer>{len(vals)} points · {DAYS} derniers jours</footer>
</article>'''


def main():
    if not DB.exists():
        raise SystemExit("whoop.db introuvable. Lance d'abord sync.py.")
    cx = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    since = f"-{DAYS} days"
    rec = card("Recovery", "%", _series(cx,
        f"SELECT created_at, recovery_score FROM recovery WHERE score_state='SCORED' "
        f"AND created_at >= datetime('now','{since}') ORDER BY created_at"),
        PALETTE["recovery"])
    hrv = card("HRV (RMSSD)", "ms", _series(cx,
        f"SELECT created_at, hrv_rmssd_milli FROM recovery WHERE score_state='SCORED' "
        f"AND created_at >= datetime('now','{since}') ORDER BY created_at"),
        PALETTE["hrv"], 1)
    rhr = card("FC de repos", "bpm", _series(cx,
        f"SELECT created_at, resting_heart_rate FROM recovery WHERE score_state='SCORED' "
        f"AND created_at >= datetime('now','{since}') ORDER BY created_at"),
        PALETTE["rhr"])
    slp = card("Perf. sommeil", "%", _series(cx,
        f"SELECT start, sleep_performance_percentage FROM sleep WHERE score_state='SCORED' "
        f"AND nap=0 AND start >= datetime('now','{since}') ORDER BY start"),
        PALETTE["sleep"])
    strain = card("Strain", "", _series(cx,
        f"SELECT start, strain FROM cycles WHERE score_state='SCORED' "
        f"AND start >= datetime('now','{since}') ORDER BY start"),
        PALETTE["strain"], 1)

    counts = {t: cx.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
              for t in ("cycles", "recovery", "sleep", "workouts")}
    cx.close()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    totals = " · ".join(f"{v} {k}" for k, v in counts.items())

    html = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard WHOOP</title><style>
:root{{--bg:#0d0f14;--card:#161a22;--line:#232936;--txt:#e6e9ef;--mut:#8b93a7;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--txt);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:32px;max-width:1200px;margin:0 auto}}
.head{{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:24px}}
.head h1{{font-size:24px;letter-spacing:-.02em}}
.head .meta{{color:var(--mut);font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 18px 12px}}
.card header{{display:flex;justify-content:space-between;align-items:center}}
.card h2{{font-size:14px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}}
.card .unit{{color:var(--mut);font-size:12px}}
.value{{font-size:40px;font-weight:700;letter-spacing:-.03em;margin:6px 0 2px}}
.value small{{font-size:15px;font-weight:500;color:var(--mut);margin-left:4px}}
.delta{{font-size:12.5px;font-weight:600}}
.delta.up{{color:#34d399}} .delta.down{{color:#f87171}}
.chart{{margin:10px 0 6px}} .spark{{width:100%;height:130px;display:block}}
.empty{{color:var(--mut);font-size:13px;padding:40px 0;text-align:center}}
.card footer{{color:var(--mut);font-size:11.5px;border-top:1px solid var(--line);padding-top:8px}}
</style></head><body>
<div class="head"><h1>🩺 Dashboard WHOOP</h1>
<div class="meta">Généré le {now} · {totals}</div></div>
<div class="grid">{rec}{hrv}{rhr}{slp}{strain}</div>
</body></html>'''

    OUT.write_text(html, encoding="utf-8")
    print("Dashboard écrit ->", OUT)
    try:
        webbrowser.open(f"file://{OUT}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
