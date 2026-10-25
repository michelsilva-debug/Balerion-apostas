"""Backtest do CÓDIGO DO BOT (calcular_probabilidades + calcular_value_bets) com
chutes no alvo, escanteios e odds REAIS de handicap asiático da Bet365.

Dados: git clone --depth 1 https://github.com/xgabora/Club-Football-Match-Data-2000-2025
Uso:   python3 testes/backtest_handicap.py [predictor.py] [Matches.csv]
"""
import csv, importlib.util, math, os, sys, tempfile, builtins
from collections import defaultdict
from datetime import datetime, timedelta

os.environ.update(TELEGRAM_TOKEN="x", TELEGRAM_CHAT="y", APIFOOTBALL_KEY="z", DATA_DIR=tempfile.mkdtemp())
CAMINHO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "predictor.py")
CSV = sys.argv[2] if len(sys.argv) > 2 else os.getenv("MATCHES_CSV", "Club-Football-Match-Data-2000-2025/data/Matches.csv")
spec = importlib.util.spec_from_file_location("p", CAMINHO)
p = importlib.util.module_from_spec(spec)
_pr = builtins.print; builtins.print = lambda *a, **k: None
spec.loader.exec_module(p)
builtins.print = _pr
p.MONTE_CARLO_N = 2000

DIVS = ("E0", "SP1", "I1", "D1", "F1", "P1", "N1")


def fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


por_div = defaultdict(list)
for r in csv.DictReader(open(CSV)):
    if r["Division"] in DIVS and r["MatchDate"] >= "2021-07-01" and r["FTHome"] not in ("", None):
        por_div[r["Division"]].append(r)

ah, esc = [], []
for div, rows in por_div.items():
    rows.sort(key=lambda r: r["MatchDate"])
    ids = {}
    for r in rows:
        for t in (r["HomeTeam"], r["AwayTeam"]):
            ids.setdefault(t, len(ids) + 1)
    jogos = []
    for i, r in enumerate(rows):
        sh, sa, ch, ca = fl(r["HomeTarget"]), fl(r["AwayTarget"]), fl(r["HomeCorners"]), fl(r["AwayCorners"])
        j = {"fixture": {"id": i, "date": r["MatchDate"] + "T15:00:00+00:00"},
             "teams": {"home": {"id": ids[r["HomeTeam"]], "name": r["HomeTeam"]},
                       "away": {"id": ids[r["AwayTeam"]], "name": r["AwayTeam"]}},
             "goals": {"home": int(float(r["FTHome"])), "away": int(float(r["FTAway"]))},
             "league": {"id": 0, "round": ""}}
        if None not in (sh, sa, ch, ca):
            j["estat"] = {"h": {"sot": int(sh), "esc": int(ch)}, "a": {"sot": int(sa), "esc": int(ca)}}
        jogos.append(j)
    hist = defaultdict(list)
    for i, r in enumerate(rows):
        jogo = jogos[i]
        a, b = jogo["teams"]["home"]["id"], jogo["teams"]["away"]["id"]
        if r["MatchDate"] >= "2022-07-01" and len(hist[a]) >= 6 and len(hist[b]) >= 6:
            ref = datetime.fromisoformat(r["MatchDate"] + "T15:00:00")
            p.dias_atras = (lambda rf: (lambda s: max(0.0, (rf - datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)).total_seconds() / 86400)))(ref)
            jc = [jogos[k] for k in hist[a][-p.JOGOS_HISTORICO:]]
            jf = [jogos[k] for k in hist[b][-p.JOGOS_HISTORICO:]]
            jh = [jogos[k] for k in hist[a] if b in (jogos[k]["teams"]["home"]["id"], jogos[k]["teams"]["away"]["id"])][-6:]
            fin = [jogos[k] for k in range(max(0, i - 200), i) if (ref - datetime.fromisoformat(jogos[k]["fixture"]["date"][:19])).days <= 60]
            res = p.calcular_probabilidades(jogo, jc, jf, jh, fin)
            gc, gf = jogo["goals"]["home"], jogo["goals"]["away"]
            parte = "treino" if r["MatchDate"] < "2024-07" else "prova"
            L, oh, oa = fl(r["HandiSize"]), fl(r["HandiHome"]), fl(r["HandiAway"])
            if L is not None and oh and oa and oh > 1 and oa > 1:
                odds = {f"ah_casa@{L:+.2f}": {"Bet365": oh}, f"ah_fora@{-L:+.2f}": {"Bet365": oa}}
                for v in p.calcular_value_bets(res["probs_cal"], odds, res["placares"]):
                    ah.append({"parte": parte, "div": div, "estrategia": v["estrategia"], "lado": v["mercado"],
                               "lucro": p.lucro_aposta(v["mercado"], gc, gf, v["odd"], v["linha"])})
                ah.append({"parte": parte, "div": div, "estrategia": None, "lado": "base_fora",
                           "lucro": p.lucro_aposta("ah_fora", gc, gf, oa, -L)})
            if res["lam_esc"] is not None and "estat" in jogo:
                tot = jogo["estat"]["h"]["esc"] + jogo["estat"]["a"]["esc"]
                esc.append({"parte": parte, "probs": {k: v for k, v in res["probs_cal"].items() if k.startswith("esc_")}, "tot": tot})
        hist[a].append(i); hist[b].append(i)


def roi(sel):
    if not sel:
        return "   -"
    v = [x["lucro"] for x in sel]; m = sum(v) / len(v); sd = (sum((x - m) ** 2 for x in v) / len(v)) ** .5
    return f"{len(v):>5} apostas | ROI {m * 100:+5.1f}% ± {1.96 * sd / math.sqrt(len(v)) * 100:.1f}"


print(f"\n=== Código do bot: {CAMINHO} ===")
print("\nHANDICAP ASIÁTICO x odds reais da Bet365")
for parte in ("treino", "prova"):
    print(f"  [{parte}]")
    print(f"    todo AH visitante (sem modelo)  {roi([x for x in ah if x['parte'] == parte and x['lado'] == 'base_fora'])}")
    print(f"    ⭐ estratégia AH visitante EV>8% {roi([x for x in ah if x['parte'] == parte and x['estrategia']])}")
    print(f"    AH mandante (divergência)       {roi([x for x in ah if x['parte'] == parte and x['lado'] == 'ah_casa'])}")
print("\n  Estratégia por liga (treino + prova):")
for d in DIVS:
    print(f"    {d:<4} {roi([x for x in ah if x['div'] == d and x['estrategia']])}")

print("\nESCANTEIOS — calibração (prova): o modelo promete X%, aconteceu Y%")
for linha in p.LINHAS_ESC:
    faixas = defaultdict(list)
    for e in esc:
        if e["parte"] != "prova":
            continue
        pr = e["probs"][f"esc_over_{linha}"]
        faixas[min(9, int(pr // 10))].append((pr, e["tot"] > linha))
    txt = "  ".join(f"{sum(a for a, _ in v) / len(v):.0f}→{sum(b for _, b in v) / len(v) * 100:.0f}%"
                    for f, v in sorted(faixas.items()) if len(v) >= 50)
    print(f"  +{linha}: {txt}")
print(f"  jogos com escanteios avaliados: {len(esc)}")
