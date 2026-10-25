"""Backtest do modelo em resultados REAIS (openfootball), sem olhar o futuro.

Uso: python3 backtest_real.py <caminho_predictor.py>
Para cada jogo, monta o histórico dos dois times (últimos 10 jogos ANTES da data),
roda o mesmo pipeline do analisar_jogo e compara a probabilidade com o resultado.
"""
import importlib.util, json, os, sys, tempfile
from collections import defaultdict
from datetime import datetime, timedelta

os.environ.update(TELEGRAM_TOKEN="x", TELEGRAM_CHAT="y", APIFOOTBALL_KEY="z", DATA_DIR=tempfile.mkdtemp())
CAMINHO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "predictor.py")
spec = importlib.util.spec_from_file_location("p", CAMINHO)
p = importlib.util.module_from_spec(spec)
_print = print
import builtins
builtins.print = lambda *a, **k: None          # silencia prints do módulo
spec.loader.exec_module(p)
builtins.print = _print
p.MONTE_CARLO_N = 20_000

# Dados: git clone --depth 1 https://github.com/openfootball/football.json
BASE = os.getenv("OPENFOOTBALL_DIR", "football.json")
ARQS = [f"{s}/{l}.json" for s in ("2022-23", "2023-24", "2024-25") for l in ("en.1", "es.1", "it.1", "de.1")]
ARQS += ["2025/br.1.json"]

MERC = ["vitoria_casa", "empate", "vitoria_fora", "over25", "under25", "btts", "over15"]


def real(gc, gf):
    return {"vitoria_casa": gc > gf, "empate": gc == gf, "vitoria_fora": gc < gf,
            "over25": gc + gf > 2, "under25": gc + gf <= 2, "btts": gc > 0 and gf > 0, "over15": gc + gf > 1}


def to_api(m, ids):
    return {"fixture": {"id": m["_id"], "date": m["_dt"].isoformat() + "+00:00"},
            "teams": {"home": {"id": ids[m["team1"]], "name": m["team1"]},
                      "away": {"id": ids[m["team2"]], "name": m["team2"]}},
            "goals": {"home": m["score"]["ft"][0], "away": m["score"]["ft"][1]},
            "league": {"id": 39, "round": m.get("round", "")}}


def probs_pipeline(jogo, jc, jf, jh, fin, idc, idf):
    if hasattr(p, "calcular_probabilidades"):
        return p.calcular_probabilidades(jogo, jc, jf, jh, fin)["probs_cal"]
    mc, mf = p.extrair_metricas(jc, idc), p.extrair_metricas(jf, idf)
    h2h = p.extrair_metricas_h2h(jh, idc)
    dc, df = p.calcular_dias_descanso(jc, jogo["fixture"]["date"]), p.calcular_dias_descanso(jf, jogo["fixture"]["date"])
    forcas = p.calcular_forca_times(fin + jc + jf)
    fc, ff = forcas.get(idc, {"alpha": 1, "beta": 1}), forcas.get(idf, {"alpha": 1, "beta": 1})
    lc, lf = p.calcular_lambdas(mc, mf, fc, ff, "x", dc, df)
    pl = p.matriz_placares(lc, lf)
    pp = p.derivar_mercados_poisson(pl)
    pm = p.monte_carlo(lc, lf, p.MONTE_CARLO_N)
    ens = p.ensemble(pp, pm, h2h, "fase_grupos", {})
    return p.aplicar_platt_todos(ens, p.PLATT_PARAMS)


reg = []   # (liga, probs, reais)
for arq in ARQS:
    caminho = os.path.join(BASE, arq)
    if not os.path.exists(caminho):
        continue
    ms = []
    for m in json.load(open(caminho))["matches"]:
        sc = m.get("score")
        if isinstance(sc, list) and len(sc) == 2:
            m["score"] = {"ft": sc}
        elif not (isinstance(sc, dict) and sc.get("ft")):
            continue
        ms.append(m)
    for i, m in enumerate(ms):
        m["_id"] = i
        m["_dt"] = datetime.fromisoformat(m["date"] + "T" + (m.get("time") or "16:00")[:5])
    ms.sort(key=lambda m: m["_dt"])
    ids = {}
    for m in ms:
        for t in (m["team1"], m["team2"]):
            ids.setdefault(t, len(ids) + 1)
    hist = defaultdict(list)
    for m in ms:
        a, b = m["team1"], m["team2"]
        if len(hist[a]) >= 6 and len(hist[b]) >= 6:
            jogo = to_api(m, ids)
            jc = [to_api(x, ids) for x in hist[a][-10:]]
            jf = [to_api(x, ids) for x in hist[b][-10:]]
            jh = [to_api(x, ids) for x in hist[a] if {x["team1"], x["team2"]} == {a, b}][-6:]
            fin = [to_api(x, ids) for x in ms if m["_dt"] - timedelta(days=2) <= x["_dt"] < m["_dt"]]
            # o modelo "vive" na data do jogo: recência medida a partir dela
            p.dias_atras = (lambda ref: (lambda s: max(0.0, (ref - datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)).total_seconds() / 86400)))(m["_dt"])
            pr = probs_pipeline(jogo, jc, jf, jh, fin, ids[a], ids[b])
            reg.append((arq, pr, real(*m["score"]["ft"])))
        hist[a].append(m); hist[b].append(m)

print(f"\n=== {os.path.basename(os.path.dirname(CAMINHO)) or CAMINHO} | {len(reg)} jogos reais avaliados ===\n")
print(f"{'mercado':<14}{'prob média':>11}{'real':>8}{'Brier':>8}{'Brier base':>12}{'  melhora':>9}")
for k in MERC:
    ps = [r[1][k] / 100 for r in reg if k in r[1]]
    ys = [1.0 if r[2][k] else 0.0 for r in reg if k in r[1]]
    if not ps:
        continue
    base = sum(ys) / len(ys)
    brier = sum((a - b) ** 2 for a, b in zip(ps, ys)) / len(ps)
    brier0 = sum((base - b) ** 2 for b in ys) / len(ys)
    print(f"{k:<14}{sum(ps)/len(ps)*100:>10.1f}%{base*100:>7.1f}%{brier:>8.4f}{brier0:>12.4f}{(1-brier/brier0)*100:>8.1f}%")

print("\nIndicações (prob ≥ PROB_MINIMA): o modelo promete X%, quanto acertou de verdade?")
lim = p.PROB_MINIMA
tot_i = tot_a = 0
for k in MERC:
    sel = [(r[1][k], r[2][k]) for r in reg if k in r[1] and r[1][k] >= lim]
    if not sel:
        continue
    tot_i += len(sel); tot_a += sum(y for _, y in sel)
    print(f"  {k:<14} {len(sel):>5} indicações | prometido {sum(s for s,_ in sel)/len(sel):5.1f}% | real {sum(y for _,y in sel)/len(sel)*100:5.1f}%")
print(f"  TOTAL          {tot_i:>5} indicações | acerto real {tot_a/max(tot_i,1)*100:.1f}%  ({tot_i/len(reg):.2f} por jogo)")

print("\nCalibração (todas as probabilidades de todos os mercados, por faixa):")
faixas = defaultdict(lambda: [0, 0.0, 0])
for _, pr, y in reg:
    for k in MERC:
        if k in pr:
            f = min(9, int(pr[k] // 10))
            faixas[f][0] += 1; faixas[f][1] += pr[k]; faixas[f][2] += y[k]
for f in sorted(faixas):
    n, sp, sy = faixas[f]
    print(f"  {f*10:>3}-{f*10+9}%: {n:>6} previsões | prometido {sp/n:5.1f}% | aconteceu {sy/n*100:5.1f}%")
