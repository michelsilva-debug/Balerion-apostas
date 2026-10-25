"""Testes das regras de aposta: liquidação, value, stake, placar 90', backtest, relatório."""
import importlib.util, os, sys, tempfile, builtins
from datetime import datetime, timedelta, timezone

CAMINHO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "predictor.py")
os.environ.update(TELEGRAM_TOKEN="x", TELEGRAM_CHAT="y", APIFOOTBALL_KEY="z", DATA_DIR=tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location("p", CAMINHO)
p = importlib.util.module_from_spec(spec)
_pr = builtins.print; builtins.print = lambda *a, **k: None
spec.loader.exec_module(p)
builtins.print = _pr
falhas = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        falhas.append(msg)


print("\n### 1. Liquidação (odd 2.00, lucro por R$1) — tabela conferida à mão")
# (mercado, linha, placar casa, placar fora, lucro esperado, explicação)
TABELA = [
    ("vitoria_casa", None, 2, 1, 1.0, "casa vence"),
    ("vitoria_casa", None, 1, 1, -1.0, "empate"),
    ("empate", None, 0, 0, 1.0, "0x0"),
    ("vitoria_fora", None, 0, 1, 1.0, "fora vence"),
    ("over25", None, 2, 1, 1.0, "3 gols"),
    ("over25", None, 1, 1, -1.0, "2 gols"),
    ("under25", None, 1, 1, 1.0, "2 gols"),
    ("under25", None, 3, 0, -1.0, "3 gols"),
    ("over15", None, 1, 1, 1.0, "2 gols"),
    ("over15", None, 1, 0, -1.0, "1 gol"),
    ("btts", None, 1, 1, 1.0, "os dois marcam"),
    ("btts", None, 2, 0, -1.0, "fora não marca"),
    ("ah_casa", -0.5, 1, 0, 1.0, "casa -0.5 vence por 1"),
    ("ah_casa", -0.5, 0, 0, -1.0, "casa -0.5 empata"),
    ("ah_casa", 0.0, 0, 0, 0.0, "linha 0 empate = devolve"),
    ("ah_casa", -1.0, 1, 0, 0.0, "casa -1 vence por 1 = devolve"),
    ("ah_casa", -1.0, 2, 0, 1.0, "casa -1 vence por 2"),
    ("ah_casa", -0.75, 1, 0, 0.5, "casa -0.75 vence por 1 = meia vitória"),
    ("ah_casa", -0.75, 2, 0, 1.0, "casa -0.75 vence por 2"),
    ("ah_casa", -0.75, 0, 0, -1.0, "casa -0.75 empata"),
    ("ah_casa", -0.25, 0, 0, -0.5, "casa -0.25 empata = meia derrota"),
    ("ah_casa", 0.25, 0, 0, 0.5, "casa +0.25 empata = meia vitória"),
    ("ah_casa", 0.25, 0, 1, -1.0, "casa +0.25 perde"),
    ("ah_casa", -1.75, 2, 0, 0.5, "casa -1.75 vence por 2 = meia vitória"),
    ("ah_casa", -1.25, 1, 0, -0.5, "casa -1.25 vence por 1 = meia derrota"),
    ("ah_casa", 1.5, 0, 1, 1.0, "casa +1.5 perde por 1"),
    ("ah_casa", 1.5, 0, 2, -1.0, "casa +1.5 perde por 2"),
    ("ah_fora", 0.5, 0, 0, 1.0, "fora +0.5 empata"),
    ("ah_fora", 0.5, 1, 0, -1.0, "fora +0.5 perde"),
    ("ah_fora", -1.25, 0, 1, -0.5, "fora -1.25 vence por 1 = meia derrota"),
    ("ah_fora", -1.25, 0, 2, 1.0, "fora -1.25 vence por 2"),
    ("ah_fora", 0.75, 1, 0, -0.5, "fora +0.75 perde por 1 = meia derrota"),
    ("ah_fora", 0.75, 0, 0, 1.0, "fora +0.75 empata"),
]
for m, l, gc, gf, esp, txt in TABELA:
    got = p.lucro_aposta(m, gc, gf, 2.0, l)
    check(abs(got - esp) < 1e-9, f"{m} {'' if l is None else f'{l:+.2f}'} {gc}x{gf}: {got:+.2f} ({txt})")

print("\n### 2. Probabilidade do handicap = soma dos placares (consistência com a liquidação)")
pl = p.matriz_placares(1.7, 1.0)
for lado, linha in (("ah_casa", -0.75), ("ah_casa", 0.25), ("ah_fora", 0.75), ("ah_fora", -0.25), ("ah_casa", -1.0)):
    # EV exato pela liquidação x EV pela probabilidade média que o alerta mostra
    ev_exato = sum(x * p.lucro_aposta(lado, a, b, 1.9, linha) for a, b, x in pl)
    h = p.calcular_handicap_asiatico(pl, linha if lado == "ah_casa" else -linha)
    win = h["prob_casa"] if lado == "ah_casa" else h["prob_fora"]
    perda = 100 - win - h["prob_push"]
    ev_alerta = (win * 0.9 - perda) / 100
    check(abs(ev_exato - ev_alerta) < 0.002, f"{lado} {linha:+.2f}: EV exato {ev_exato:+.4f} = EV do alerta {ev_alerta:+.4f}")
    odd_justa = p._odd_minima_ha(win, h["prob_push"])
    ev_justo = sum(x * p.lucro_aposta(lado, a, b, odd_justa, linha) for a, b, x in pl)
    check(abs(ev_justo) < 0.01, f"   odd justa {odd_justa} dá EV ≈ 0 ({ev_justo:+.4f})")

print("\n### 3. Value: melhor odd por mercado, sem duplicar casas")
vb = p.calcular_value_bets({"vitoria_casa": 55.0, "over25": 50.0, "empate": 20.0},
                           {"vitoria_casa": {"Bet365": 2.0, "Betano": 2.1}, "over25": {"Bet365": 1.9},
                            "empate": {"Bet365": 3.5}})
check([v["mercado"] for v in vb] == ["vitoria_casa"], f"só vitória casa tem value: {[(v['mercado'], v['casa'], v['odd']) for v in vb]}")
check(vb and vb[0]["casa"] == "Betano" and vb[0]["odd"] == 2.1, "usou a melhor odd (Betano 2.10)")
check(abs(vb[0]["value"] - 0.155) < 1e-9, f"value = 0.55*2.1-1 = {vb[0]['value']}")
check(p.calcular_value_bets({"over25": 51.0}, {"over25": {"Bet365": 2.0}}) == [], "value 2% (< 3%) não entra")

print("\n### 4. Stake (Kelly fracionado) com teto")
check(p.kelly_stake(50, 2.0) == 0.0, "sem vantagem = R$0")
check(p.kelly_stake(55, 2.0) == round(0.10 * 0.20 * 1000, 2), f"55% @2.0 → {p.kelly_stake(55, 2.0)} (Kelly 10% x fração 20%)")
check(p.kelly_stake(90, 3.0) == 20.0, f"teto de 2% da banca: {p.kelly_stake(90, 3.0)}")

print("\n### 5. Placar de 90 min em jogo com prorrogação")
j = {"fixture": {"id": 1}, "goals": {"home": 2, "away": 1},
     "score": {"fulltime": {"home": 1, "away": 1}, "extratime": {"home": 1, "away": 0}}}
check(p.placar_90min(j)["goals"] == {"home": 1, "away": 1}, "usa 1x1 dos 90 min, não 2x1 com prorrogação")
check(p.placar_90min({"goals": {"home": 3, "away": 0}})["goals"]["home"] == 3, "sem 'score' mantém goals")

print("\n### 6. Backtest do log: acerto por mercado e ROI só das apostas simuladas")
log = [{"fixture_id": "10", "probs_calibradas": {"vitoria_casa": 70, "over25": 40, "over15": 80},
        "apostas_simuladas": [{"mercado": "empate", "casa": "Bet365", "odd": 3.4},
                              {"mercado": "ah_fora", "casa": "Bet365", "odd": 1.9, "linha": 0.75}],
        "resultado": None, "placar_real": None}]
fin = [{"fixture": {"id": 10}, "goals": {"home": 2, "away": 1},
        "score": {"fulltime": {"home": 1, "away": 1}}}]   # 1x1 nos 90, 2x1 na prorrogação
bt = p.processar_backtest(log, fin)
check(log[0]["placar_real"] == "1-1", "liquidou pelo 1x1 dos 90 min")
check(bt["total_mercado"] == {"vitoria_casa": 1, "over15": 1} and bt["acertos_mercado"].get("over15") == 1
      and bt["acertos_mercado"].get("vitoria_casa", 0) == 0, f"acertos {bt['acertos_mercado']} de {bt['total_mercado']}")
check(bt["roi_mercado"] == {"empate": 24.0, "ah_fora": 9.0},
      f"simulação: empate @3.4 = +R$24, fora +0.75 empate @1.9 = +R$9 → {bt['roi_mercado']}")
rel = p.montar_relatorio_backtest(bt)
check("+R$33.00" in rel, "relatório soma +R$33.00")
check(p.processar_backtest(log, fin)["atualizados"] == 0, "não liquida o mesmo jogo duas vezes")

print("\n### 7. Relatório semanal usa só as apostas simuladas")
log[0]["data"] = datetime.now().isoformat()
sem = p.gerar_relatorio_semanal(log, [])
check("2 apostas" in sem and "+R$33.00" in sem and "ROI +165.0%" in sem, "semanal: 2 apostas, +R$33, ROI +165%")

print("\n### 8. Texto do alerta não manda apostar")
jogo = {"fixture": {"id": 5, "date": "2026-10-26T20:00:00+00:00"}, "league": {"id": 71, "round": "Regular Season - 30"},
        "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 2, "name": "B"}}}
pl = p.matriz_placares(2.0, 0.8)
probs = p.ensemble(p.derivar_mercados_poisson(pl), p.derivar_mercados_poisson(pl), {}, "fase_grupos")
txt = p.montar_alerta(jogo, probs, {}, {}, {}, "fase_grupos", 2.0, 0.8, {"alpha": 1, "beta": 1},
                      {"alpha": 1, "beta": 1}, {}, 5, 5, None, None, False, p.selecionar_melhor_handicap(pl, 2.0, 0.8))
txt += p.montar_bloco_value_bets(p.calcular_value_bets(probs, {"vitoria_casa": {"Bet365": 2.5}}))
check("Modo observação" in txt, "aviso de modo observação no topo")
check("Stake" not in txt and "R$" not in txt, "nenhum valor em R$ para apostar")
check("NÃO é dica de aposta" in txt, "divergências marcadas como simulação")

print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)"))
sys.exit(1 if falhas else 0)
