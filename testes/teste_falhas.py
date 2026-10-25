"""Cenários de falha e operação real, com a API-Football simulada."""
import importlib.util, json, os, sys, tempfile
from datetime import datetime, timedelta, timezone

CAMINHO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "predictor.py")
DATA = tempfile.mkdtemp()
os.environ.update(TELEGRAM_TOKEN="x", TELEGRAM_CHAT="y", APIFOOTBALL_KEY="z",
                  DATA_DIR=DATA, API_INTERVALO_SEG="0", CASAS="Bet365,Betano", NOTIFY_BOOT="0")
import requests

agora = datetime.now(timezone.utc)
HOJE, ONTEM = agora.date().isoformat(), (agora.date() - timedelta(days=1)).isoformat()
chamadas, telegramas = [], []
MODO = {"falha": None, "n_jogos": 3, "remaining": 95}


def fx(fid, lid, c, f, dt, st="NS", g=(None, None)):
    return {"fixture": {"id": fid, "date": dt.isoformat().replace("+00:00", "Z"), "status": {"short": st}},
            "league": {"id": lid, "name": f"L{lid}", "round": "Regular Season - 9", "season": 2026},
            "teams": {"home": {"id": c, "name": f"T{c}"}, "away": {"id": f, "name": f"T{f}"}},
            "goals": {"home": g[0], "away": g[1]}}


class R:
    def __init__(self, resp, errors=None, status=200):
        self.status_code = status
        MODO["remaining"] -= 1
        self.headers = {"x-ratelimit-requests-limit": "100",
                        "x-ratelimit-requests-remaining": str(max(0, MODO["remaining"]))}
        self._j = {"errors": errors or [], "response": resp}

    def json(self):
        return self._j


def fake_get(url, headers=None, params=None, timeout=None):
    ep = url.split("api-sports.io/")[-1]
    p = dict(params or {})
    chamadas.append((ep, p))
    if MODO["falha"] == "timeout":
        raise requests.exceptions.Timeout()
    if MODO["falha"] == "500":
        return R([], status=500)
    if MODO["falha"] == "plano":
        return R([], errors={"plan": "Free plans do not have access to this season, try from 2022 to 2024."})
    if ep == "fixtures" and "ids" in p:
        if MODO.get("ids_falha"):
            return R([])
        if MODO.get("plano_gratis"):
            return R([], errors={"plan": "Free plans do not have access to the Ids parameter."})
        out = []
        for f in str(p["ids"]).split("-"):
            out.append({"fixture": {"id": int(f)}, "teams": {"home": {"id": 1}, "away": {"id": 2}},
                        "statistics": [{"team": {"id": 1}, "statistics": [{"type": "Shots on Goal", "value": 5}, {"type": "Corner Kicks", "value": 6}]},
                                       {"team": {"id": 2}, "statistics": [{"type": "Shots on Goal", "value": 3}, {"type": "Corner Kicks", "value": 4}]}]})
        return R(out)
    if ep == "fixtures" and "date" in p:
        if p["date"] == HOJE:
            js = [fx(100 + i, [71, 2, 39, 13][i % 4], 10 + 2 * i, 11 + 2 * i,
                     agora + timedelta(minutes=60 + 10 * i)) for i in range(MODO["n_jogos"])]
            js.append(fx(999, 71, 500, 501, agora + timedelta(hours=2)))     # time sem histórico
            js.append(fx(998, 71, 600, 601, agora + timedelta(hours=2)))     # dado quebrado
            return R(js + [fx(5, 4000, 1, 2, agora + timedelta(hours=1))])   # liga ignorada
        if p["date"] == ONTEM:
            return R([fx(100, 71, 10, 11, agora - timedelta(hours=20), "FT", (1, 1))])
        return R([fx(7, 4000, 1, 2, agora + timedelta(days=1))])
    if ep == "fixtures" and "team" in p:
        if "last" in p:
            return R([], errors={"plan": "Free plans do not have access to the Last parameter."})
        assert "season" in p, "histórico deve vir por temporada"
        t = p["team"]
        if t in (500, 501):
            return R([])
        jogos = [fx(9000 + t * 30 + i, 71, t, 800 + i, agora - timedelta(days=5 * (i + 1)), "FT",
                    ((t + i) % 3, (t * i) % 2)) for i in range(10)]
        if t == 600:
            jogos[0]["goals"] = {"home": "x", "away": 1}   # força ValueError
        return R(jogos)
    if ep == "fixtures/statistics":
        fid = int(p["fixture"])                     # times do jogo, como a API real devolve
        casa, fora = ((fid - 9000) // 30, 800 + (fid - 9000) % 30) if fid >= 9000 else (10, 11)
        return R([{"team": {"id": casa}, "statistics": [{"type": "Shots on Goal", "value": 4}, {"type": "Corner Kicks", "value": 5}]},
                  {"team": {"id": fora}, "statistics": [{"type": "Shots on Goal", "value": 2}, {"type": "Corner Kicks", "value": 3}]}])
    if ep == "fixtures/headtohead":
        assert "last" not in p, "plano grátis não aceita last no H2H"
        return R([])
    if ep == "odds":
        return R([])
    if ep == "injuries":
        return R([])
    raise AssertionError(ep)


requests.get = fake_get
requests.post = lambda *a, **k: R([])
spec = importlib.util.spec_from_file_location("pr", CAMINHO)
pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)
pr.MONTE_CARLO_N = 2000
pr.time.sleep = lambda s: None
pr.enviar_telegram = lambda m: telegramas.append(m)
ok = lambda c, msg: print(("  ✅ " if c else "  ❌ FALHOU: ") + msg) or c
falhas = []


def check(c, msg):
    if not ok(c, msg):
        falhas.append(msg)


def ciclo(b, c, prm):
    return pr.rodar_ciclo(b, c, prm)


print("\n### 1. Virada do dia: orçamento do dia anterior esgotado")
b = {"data": "2020-01-01", "calls_usadas": 999}
b, c, prm = ciclo(b, {}, pr.carregar_params_modelo())
check(b["data"] == pr.datetime.now(timezone.utc).strftime("%Y-%m-%d") and len(chamadas) > 0,
      f"zerou o orçamento e voltou a trabalhar ({len(chamadas)} chamadas)")

print("\n### 2. Time sem histórico e jogo com dado quebrado")
check("999" in c, "jogo sem dados entrou no cache (não gasta cota de novo)")
check("998" in c, "jogo com dado quebrado entrou no cache e o ciclo continuou")
n = len(chamadas)
b, c, prm = ciclo(b, c, prm)
check(len(chamadas) == n, f"2º ciclo não refez nada ({len(chamadas) - n} chamadas)")

print("\n### 3. Fim de semana lotado: orçamento respeitado")
for f in os.listdir(DATA):
    os.remove(os.path.join(DATA, f))
chamadas.clear(); MODO["n_jogos"] = 60; MODO["remaining"] = 100
b, c, prm = ciclo({"data": pr.hoje_utc(), "calls_usadas": 0}, {}, prm)
check(b["calls_usadas"] <= pr.BUDGET_DIARIO, f"usou {b['calls_usadas']}/{pr.BUDGET_DIARIO}")
check(len(chamadas) <= pr.BUDGET_DIARIO, f"chamadas reais {len(chamadas)} ≤ {pr.BUDGET_DIARIO}")
analisados = len([1 for e, _ in chamadas if e == "fixtures/headtohead"])
print(f"     jogos analisados com o orçamento do dia: {analisados}")

print("\n### 4. Erro de plano da API (temporada não liberada)")
for f in os.listdir(DATA):
    os.remove(os.path.join(DATA, f))
chamadas.clear(); telegramas.clear(); MODO["falha"] = "plano"; MODO["remaining"] = 100
b, c, prm = ciclo({"data": pr.hoje_utc(), "calls_usadas": 0}, {}, prm)
avisos = [t for t in telegramas if "recusou" in t]
check(len(avisos) == 1, f"avisou no Telegram uma vez ({len(avisos)})")
b, c, prm = ciclo(b, c, prm)
avisos = [t for t in telegramas if "recusou" in t]
check(len(avisos) == 1, "não repetiu o aviso no mesmo dia")
print(f"     chamadas gastas em 2 ciclos com erro: {len(chamadas)}")

print("\n### 5. API fora do ar (timeout e HTTP 500)")
for modo in ("timeout", "500"):
    MODO["falha"] = modo
    try:
        b, c, prm = ciclo({"data": pr.hoje_utc(), "calls_usadas": 0}, {}, prm)
        check(True, f"{modo}: ciclo terminou sem quebrar")
    except Exception as e:
        check(False, f"{modo}: quebrou com {type(e).__name__}: {e}")
MODO["falha"] = None

print("\n### 6. Resumo diário e relatório semanal: uma vez só, mesmo reiniciando")
for f in os.listdir(DATA):
    os.remove(os.path.join(DATA, f))
telegramas.clear(); MODO["n_jogos"] = 2; MODO["remaining"] = 100
pr.eh_hora_resumo = lambda: True
pr.eh_hora_relatorio_semanal = lambda: True
b, c, prm = ciclo({"data": pr.hoje_utc(), "calls_usadas": 0}, {}, prm)
b, c, prm = ciclo(b, c, prm)
spec2 = importlib.util.spec_from_file_location("pr2", CAMINHO)      # "reinício" do bot
pr2 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(pr2)
pr2.enviar_telegram = lambda m: telegramas.append(m); pr2.time.sleep = lambda s: None
pr2.eh_hora_resumo = lambda: True; pr2.eh_hora_relatorio_semanal = lambda: True; pr2.MONTE_CARLO_N = 2000
pr2.rodar_ciclo(pr2.carregar_budget(), pr2.carregar_cache(), pr2.carregar_params_modelo())
check(len([t for t in telegramas if "BOM DIA" in t]) == 1, "resumo diário enviado 1x")
check(len([t for t in telegramas if "RELATÓRIO SEMANAL" in t]) == 1, "relatório semanal enviado 1x")

print("\n### 7. Parâmetros salvos pelo modelo antigo (Copa) são descartados")
pr._salvar_json(pr.ARQUIVO_PARAMS, {"gamma_casa": 1.18, "prob_minima": 55.0, "versao": 9})
prm2 = pr.carregar_params_modelo()
check(prm2.get("fator_casa") == 1.0 and prm2.get("prob_minima") == 58.0, f"fator_casa={prm2.get('fator_casa')} prob_minima={prm2.get('prob_minima')}")

print("\n### 8. Autoaprendizado com 40 resultados reais")
log = []
for i in range(40):
    log.append({"data": datetime.now().isoformat(), "fixture_id": str(5000 + i),
                "probs_calibradas": {"vitoria_casa": 75, "over25": 70, "under25": 30, "btts": 60},
                "resultado": "acerto", "placar_real": "0-1" if i % 2 else "1-0", "odds_reais": {}})
pr._salvar_json(pr.ARQUIVO_LOG, log)
prm3 = pr.executar_autoaprendizado(pr.carregar_params_modelo())
check(prm3["prob_minima"] > 58.0, f"modelo otimista → prob_minima subiu para {prm3['prob_minima']}")
check(prm3["fator_casa"] < 1.0, f"viés de mandante → fator_casa caiu para {prm3['fator_casa']}")
a, t = pr.taxa_por_mercado(log)
check(t == 120 and a == 20, f"taxa por mercado: {a}/{t} (o antigo contava 40/40 por \"acertou algum mercado\")")

print("\n### 9. Handicap: lado do visitante")
pl = pr.matriz_placares(1.8, 0.8)
ha = pr.selecionar_melhor_handicap(pl, 1.8, 0.8)
P = lambda f: round(sum(x for a, b2, x in pl if f(a, b2)) * 100, 2)
fora05 = pr.calcular_handicap_asiatico(pl, -0.5)["prob_fora"]   # visitante +0.5
check(abs(fora05 - P(lambda a, b2: a <= b2)) < 0.01, f"AH Fora +0.5 = empate ou vitória fora ({fora05}%)")
rec = ha["recomendada"]
check(rec and pr.PROB_MINIMA <= rec["prob"] <= 80, f"recomendada útil: {rec and rec['label']} {rec and rec['prob']}% odd mín {rec and rec['odd_fair']}")

print("\n### 10. Estatísticas em lote: cache e espera de 6h depois de falha")
for f in os.listdir(DATA):
    os.remove(os.path.join(DATA, f))
pr._estats["dados"] = None
chamadas.clear(); MODO["n_jogos"] = 2; MODO["remaining"] = 100; MODO["ids_falha"] = True
b, c, prm = ciclo({"data": pr.hoje_utc(), "calls_usadas": 0}, {}, prm)
n1 = len([1 for e, q in chamadas if e == "fixtures" and "ids" in q])
b, c, prm = ciclo(b, {}, prm)
n2 = len([1 for e, q in chamadas if e == "fixtures" and "ids" in q]) - n1
check(n1 > 0 and n2 == 0, f"falha de estatística não é repetida a cada ciclo (1º ciclo {n1} lotes, 2º ciclo {n2})")
MODO["ids_falha"] = False
for f in os.listdir(DATA):
    os.remove(os.path.join(DATA, f))
pr._estats["dados"] = None; chamadas.clear()
b, c, prm = ciclo({"data": pr.hoje_utc(), "calls_usadas": 0}, {}, prm)
lotes = [q["ids"].count("-") + 1 for e, q in chamadas if e == "fixtures" and "ids" in q]
check(lotes and max(lotes) <= 20, f"lotes de até 20 jogos por chamada: {lotes}")
check(len(pr._cache_estats()) > 0 and any(not v.get("vazio") for v in pr._cache_estats().values()), "estatísticas guardadas em cache")

print("\n### 11. Plano grátis sem busca em lote: estatística jogo a jogo, com teto diário")
for f in os.listdir(DATA):
    os.remove(os.path.join(DATA, f))
pr._estats["dados"] = None; chamadas.clear(); telegramas.clear()
MODO.update(plano_gratis=True, n_jogos=40, remaining=100)
b, c, prm = ciclo({"data": pr.hoje_utc(), "calls_usadas": 0}, {}, prm)
b, c, prm = ciclo(b, c, prm)
lotes = [1 for e, q in chamadas if e == "fixtures" and "ids" in q]
unit = [1 for e, q in chamadas if e == "fixtures/statistics"]
check(len(lotes) == 1, f"tentou o lote uma vez só e mudou de estratégia ({len(lotes)} tentativa)")
check(0 < len(unit) <= pr.ESTATS_MAX_DIA, f"estatísticas jogo a jogo: {len(unit)} (teto {pr.ESTATS_MAX_DIA}/dia)")
check(not any("Ids" in t for t in telegramas), "não manda alerta de erro para o bloqueio de lote (já tratado)")
check(b["calls_usadas"] <= pr.BUDGET_DIARIO, f"orçamento respeitado: {b['calls_usadas']}/{pr.BUDGET_DIARIO}")
com = [v for k, v in pr._cache_estats().items() if k != "_meta" and not v.get("vazio")]
check(len(com) == len(unit), f"cada busca virou estatística em cache ({len(com)})")
MODO["plano_gratis"] = False

print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S): {falhas}"))
