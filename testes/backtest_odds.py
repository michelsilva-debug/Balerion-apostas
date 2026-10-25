"""Backtest das REGRAS DE APOSTA contra odds reais da Bet365 (2022-2026).

Dados: github.com/xgabora/Club-Football-Match-Data-2000-2025 (Matches.csv)
Para cada jogo: modelo vê só o passado -> probabilidades -> regra de value bet
-> liquida com o placar real e a odd real. Mede ROI com stake fixo e com Kelly.
"""
import csv, importlib.util, os, sys, tempfile, builtins, math
from collections import defaultdict
from datetime import datetime, timedelta

os.environ.update(TELEGRAM_TOKEN="x", TELEGRAM_CHAT="y", APIFOOTBALL_KEY="z", DATA_DIR=tempfile.mkdtemp())
CAMINHO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "predictor.py")
# Dados: git clone --depth 1 https://github.com/xgabora/Club-Football-Match-Data-2000-2025
CSV = sys.argv[2] if len(sys.argv) > 2 else os.getenv("MATCHES_CSV", "Club-Football-Match-Data-2000-2025/data/Matches.csv")
spec = importlib.util.spec_from_file_location("p", CAMINHO)
p = importlib.util.module_from_spec(spec)
_pr = builtins.print; builtins.print = lambda *a, **k: None
spec.loader.exec_module(p)
builtins.print = _pr
p.MONTE_CARLO_N = 20_000

DIVS = {"E0": "Premier", "SP1": "La Liga", "I1": "Serie A", "D1": "Bundesliga", "BRA": "Brasileirão"}
INICIO_HIST, INICIO_TESTE = "2021-07-01", "2022-07-01"


def f(x):
    try:
        v = float(x)
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None


def lucro(mercado, gc, gf, odd, linha=None):
    if mercado.startswith("ah_"):
        dif = gc - gf if mercado == "ah_casa" else gf - gc
        partes = [linha - 0.25, linha + 0.25] if abs(round(linha * 4)) % 2 == 1 else [linha]
        return sum((odd - 1) if dif + l > 0 else (-1 if dif + l < 0 else 0) for l in partes) / len(partes)
    ganhou = {"vitoria_casa": gc > gf, "empate": gc == gf, "vitoria_fora": gc < gf,
              "over25": gc + gf > 2, "under25": gc + gf <= 2}[mercado]
    return odd - 1 if ganhou else -1.0


# ── carrega ──
por_div = defaultdict(list)
for r in csv.DictReader(open(CSV)):
    if r["Division"] in DIVS and r["MatchDate"] >= INICIO_HIST and r["FTHome"] not in ("", None):
        por_div[r["Division"]].append(r)

apostas = []   # dicts
for div, rows in por_div.items():
    rows.sort(key=lambda r: (r["MatchDate"], r["MatchTime"] or "15:00"))
    ids = {}
    for r in rows:
        for t in (r["HomeTeam"], r["AwayTeam"]):
            ids.setdefault(t, len(ids) + 1)

    def api(r, i):
        dt = r["MatchDate"] + "T" + ((r["MatchTime"] or "15:00")[:5]) + ":00+00:00"
        return {"fixture": {"id": i, "date": dt},
                "teams": {"home": {"id": ids[r["HomeTeam"]], "name": r["HomeTeam"]},
                          "away": {"id": ids[r["AwayTeam"]], "name": r["AwayTeam"]}},
                "goals": {"home": int(float(r["FTHome"])), "away": int(float(r["FTAway"]))},
                "league": {"id": 0, "round": ""}}

    convertidos = [api(r, i) for i, r in enumerate(rows)]
    hist = defaultdict(list)
    for i, r in enumerate(rows):
        a, b = r["HomeTeam"], r["AwayTeam"]
        jogo = convertidos[i]
        if r["MatchDate"] >= INICIO_TESTE and len(hist[a]) >= 6 and len(hist[b]) >= 6:
            ref = datetime.fromisoformat(jogo["fixture"]["date"]).replace(tzinfo=None)
            p.dias_atras = (lambda rf: (lambda s: max(0.0, (rf - datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)).total_seconds() / 86400)))(ref)
            jc = [convertidos[k] for k in hist[a][-10:]]
            jf = [convertidos[k] for k in hist[b][-10:]]
            jh = [convertidos[k] for k in hist[a] if {rows[k]["HomeTeam"], rows[k]["AwayTeam"]} == {a, b}][-6:]
            ini = ref - timedelta(days=2)
            fin = [convertidos[k] for k in range(max(0, i - 40), i)
                   if ini <= datetime.fromisoformat(convertidos[k]["fixture"]["date"]).replace(tzinfo=None) < ref]
            res = p.calcular_probabilidades(jogo, jc, jf, jh, fin)
            pr, pl = res["probs_cal"], p.matriz_placares(res["lc"], res["lf"])
            gc, gf = jogo["goals"]["home"], jogo["goals"]["away"]
            odds_b365 = {"vitoria_casa": f(r["OddHome"]), "empate": f(r["OddDraw"]), "vitoria_fora": f(r["OddAway"]),
                         "over25": f(r["Over25"]), "under25": f(r["Under25"])}
            odds_max = {"vitoria_casa": f(r["MaxHome"]), "empate": f(r["MaxDraw"]), "vitoria_fora": f(r["MaxAway"]),
                        "over25": f(r["MaxOver25"]), "under25": f(r["MaxUnder25"])}
            for m in odds_b365:
                for fonte, od in (("b365", odds_b365[m]), ("max", odds_max[m])):
                    if od:
                        ev = pr[m] / 100 * od - 1
                        apostas.append({"div": div, "data": r["MatchDate"], "m": m, "fonte": fonte, "odd": od,
                                        "prob": pr[m], "ev": ev, "lucro": lucro(m, gc, gf, od)})
            # handicap asiático (linha do mandante + odds Bet365)
            try:
                L = float(r["HandiSize"]); oh, oa = f(r["HandiHome"]), f(r["HandiAway"])
            except ValueError:
                L = None
            if L is not None and oh and oa:
                for lado, linha, od in (("ah_casa", L, oh), ("ah_fora", -L, oa)):
                    ev = sum(x * lucro(lado, i2, j2, od, linha) for i2, j2, x in pl)
                    apostas.append({"div": div, "data": r["MatchDate"], "m": lado, "fonte": "b365", "odd": od,
                                    "prob": None, "ev": ev, "lucro": lucro(lado, gc, gf, od, linha)})
        hist[a].append(i); hist[b].append(i)


def resumo(sel, titulo):
    n = len(sel)
    if not n:
        print(f"  {titulo:<44} sem apostas"); return
    tot = sum(a["lucro"] for a in sel)
    gan = sum(1 for a in sel if a["lucro"] > 0)
    print(f"  {titulo:<44} {n:>6} apostas | acerto {gan/n*100:5.1f}% | ROI {tot/n*100:+6.2f}%")


todas_b365 = [a for a in apostas if a["fonte"] == "b365"]
jogos = len({(a["div"], a["data"], a["odd"]) for a in todas_b365 if a["m"] == "vitoria_casa"})
print(f"\n=== {os.path.basename(os.path.dirname(os.path.abspath(CAMINHO)))} | jogos com odds: ~{jogos} | 2022-07 → 2026 ===")
print("\nReferência: apostar em TUDO na Bet365 (sem modelo)")
resumo(todas_b365, "todas as apostas possíveis")

for fonte, nome in (("b365", "Bet365"), ("max", "melhor odd de ~17 casas")):
    print(f"\nREGRA DO BOT: value > 3%  — odds {nome}")
    sel = [a for a in apostas if a["fonte"] == fonte and a["ev"] > 0.03]
    resumo(sel, "TOTAL")
    for m in ("vitoria_casa", "empate", "vitoria_fora", "over25", "under25", "ah_casa", "ah_fora"):
        resumo([a for a in sel if a["m"] == m], m)

print("\nPor faixa de value (Bet365, 1X2 + O/U + AH):")
b = [a for a in apostas if a["fonte"] == "b365"]
for lo, hi in ((0.03, 0.06), (0.06, 0.10), (0.10, 0.15), (0.15, 0.25), (0.25, 9)):
    resumo([a for a in b if lo < a["ev"] <= hi], f"value {lo*100:.0f}%–{min(hi,9.99)*100:.0f}%")
print("\nPor faixa de odd (Bet365, value > 3%):")
for lo, hi in ((1.0, 1.6), (1.6, 2.2), (2.2, 3.2), (3.2, 5.0), (5.0, 99)):
    resumo([a for a in b if a["ev"] > 0.03 and lo < a["odd"] <= hi], f"odd {lo}–{hi}")
print("\nPor liga (Bet365, value > 3%):")
for d, nome in DIVS.items():
    resumo([a for a in b if a["ev"] > 0.03 and a["div"] == d], nome)
print("\nPor temporada (Bet365, value > 3%):")
for ini, fim in (("2022-07", "2023-07"), ("2023-07", "2024-07"), ("2024-07", "2025-07"), ("2025-07", "2026-12")):
    resumo([a for a in b if a["ev"] > 0.03 and ini <= a["data"][:7] < fim], f"{ini} a {fim}")

# Kelly com as regras do código (fração e teto) — banca 1000, ordem cronológica
print("\nSimulação de banca R$1.000 (Bet365, value > 3%, ordem cronológica):")
sel = sorted([a for a in b if a["ev"] > 0.03], key=lambda a: a["data"])
for nome, frac, teto in (("Kelly do código (20%, teto 15%)", p.KELLY_FRACAO, 0.15),
                         ("Kelly 10%, teto 2%", 0.10, 0.02), ("Stake fixo 1% da banca inicial", None, None)):
    banca, pico, dd = 1000.0, 1000.0, 0.0
    for a in sel:
        if frac is None:
            st = 10.0
        else:
            bb = a["odd"] - 1
            pwin = (a["ev"] + 1) / a["odd"]
            fk = (pwin * a["odd"] - 1) / bb if bb > 0 else 0
            st = max(0.0, min(fk * frac, teto)) * banca
        banca += st * a["lucro"]
        pico = max(pico, banca); dd = max(dd, (pico - banca) / pico if pico > 0 else 0)
        if banca <= 1:
            break
    print(f"  {nome:<36} banca final R${banca:9.2f} | maior queda {dd*100:5.1f}%")

import json as _j
if os.getenv("DUMP"):
    _j.dump(apostas, open(os.getenv("DUMP"), "w"))
