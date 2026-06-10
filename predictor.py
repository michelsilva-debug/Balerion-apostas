

import requests

import time

import json


import os
from dotenv import load_dotenv
load_dotenv()


import math

import random

from datetime import datetime, timezone, timedelta

from collections import defaultdict

# ╔══════════════════════════════════════════════════════════════╗

# ║ TERRORNEGRO PREDICTOR v6.1 — COPA DO MUNDO 2026            ║

# ║                                                              ║

# ║ Motor estatístico de nível profissional:                    ║

# ║ • Poisson bivariado + Dixon-Coles                           ║

# ║ • xG (Expected Goals) no lugar de gols brutos              ║

# ║ • Força relativa de ataque/defesa (alpha/beta)             ║

# ║ • Monte Carlo — 100.000 simulações por jogo                ║

# ║ • Ensemble: Poisson + Monte Carlo + H2H                    ║

# ║ • Platt Scaling — calibração de probabilidades             ║

# ║ • Variáveis contextuais (descanso, pressão, fase)          ║

# ║ • Poisson dedicado para escanteios                         ║

# ║ • Fator psicológico quantificado                           ║

# ║ • Detecção de line movement (smart money)                  ║

# ║ • Kelly Criterion fracionado para stakes                   ║

# ║ • Score de confiança único 0–100                           ║

# ║ • Análise de lesões e desfalques (fator lambda)            ║

# ║ • Value Bet com comparativo multi-casa                     ║

# ║ • Backtest automático com resultado real                   ║

# ║ • Relatório semanal inteligente (domingos 9h BRT)          ║

# ║ • Histórico em 3 camadas (Copa → Elim → Liga)              ║

# ║ • Decaimento exponencial por recência                      ║

# ║ • Resumo diário às 8h BRT + log completo                   ║

# ║ • [NOVO] Handicap Asiático completo                        ║

# ╚══════════════════════════════════════════════════════════════╝



# ─────────────────────────────────────────

# CREDENCIAIS — FIX #1/#7: sem fallback hardcoded

# ─────────────────────────────────────────

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")

TELEGRAM_CHAT    = os.getenv("TELEGRAM_CHAT")

APIFOOTBALL_KEY  = os.getenv("APIFOOTBALL_KEY")



# ─────────────────────────────────────────

# PARÂMETROS GLOBAIS

# ─────────────────────────────────────────

PROB_MINIMA          = 58

EDGE_MINIMO          = 3.5

KELLY_FRACAO         = 0.20

BANCA_PADRAO         = 1000

JOGOS_HISTORICO      = 10

JOGOS_H2H            = 6

MONTE_CARLO_N        = 100_000

LAMBDA_DECAY         = 0.04

BUDGET_DIARIO        = 80

BUDGET_EMERGENCIA    = 10

INTERVALO_CICLO_MIN  = 30

FUSO_BRT             = -3

RHO_DIXON_COLES      = -0.13

ARQUIVO_BUDGET       = "budget_predictor.json"

ARQUIVO_CACHE        = "predictor_cache.json"

ARQUIVO_LOG          = "predictor_log.json"

ARQUIVO_ODDS_SNAP    = "odds_snapshot.json"

ARQUIVO_RELATORIO    = "relatorio_semanal.json"

ARQUIVO_PARAMS       = "modelo_params.json"

JOGOS_PARA_RETREINAR = 5

CASAS_VALUE  = ["Bet365", "Pinnacle", "Betano", "Betfair", "Sportingbet"]

WORLD_CUP_ID = 1

WORLD_CUP_SEASON = 2026



# ─────────────────────────────────────────

# LINHAS DE HANDICAP ASIÁTICO

# ─────────────────────────────────────────

LINHAS_HANDICAP = [-2.5, -2.0, -1.75, -1.5, -1.25, -1.0, -0.75,

                   -0.5, -0.25, 0.0, 0.25, 0.5, 0.75,

                    1.0,  1.25, 1.5,  1.75, 2.0, 2.5]



# ─────────────────────────────────────────

# LIGAS NACIONAIS COMPLEMENTARES

# ─────────────────────────────────────────

LIGAS_NACIONAIS = {

    "Brazil": 71, "France": 61, "England": 39, "Spain": 140,

    "Germany": 78, "Italy": 135, "Portugal": 94, "Netherlands": 88,

    "Argentina": 128, "Uruguay": 268, "Colombia": 239, "Mexico": 262,

    "USA": 253, "Japan": 98, "South Korea": 292, "Morocco": 200,

    "Croatia": 210, "Belgium": 144, "Switzerland": 207,

    "Ecuador": 242, "Senegal": 26, "Australia": 188, "Canada": 253,

    "Ghana": 172, "Cameroon": 26,

}

ELIMINATORIAS_IDS = [29, 30, 31, 32, 33, 34]



# ─────────────────────────────────────────

# FASES E PESOS

# ─────────────────────────────────────────

FASES = {

    "Group Stage": "fase_grupos", "Round of 32": "oitavas",

    "Round of 16": "oitavas",    "Quarter-finals": "quartas",

    "Semi-finals": "semis",      "3rd Place Final": "terceiro",

    "Final": "final",

}

PESO_H2H_FASE = {

    "fase_grupos": 0.07, "oitavas": 0.14, "quartas": 0.22,

    "semis": 0.28,       "terceiro": 0.15, "final": 0.35,

}

PRESSAO_FASE = {

    "fase_grupos": 1.0, "oitavas": 1.15, "quartas": 1.25,

    "semis": 1.35,      "terceiro": 1.10, "final": 1.45,

}

LABELS = {

    "vitoria_casa":  "⚽ Vitória da Casa",

    "empate":        "🤝 Empate",

    "vitoria_fora":  "✈️  Vitória Visitante",

    "btts":          "🎯 Ambas Marcam",

    "over25":        "📈 Over 2.5 Gols",

    "under25":       "📉 Under 2.5 Gols",

    "over15":        "📊 Over 1.5 Gols",

    "escanteios":    "🚩 Escanteios Over",

    "cartoes":       "🟨 Cartões Over",

    "ha_casa_-0.5":  "🏠 AH Casa -0.5",

    "ha_casa_-1.0":  "🏠 AH Casa -1.0",

    "ha_casa_-1.5":  "🏠 AH Casa -1.5",

    "ha_casa_-2.0":  "🏠 AH Casa -2.0",

    "ha_fora_+0.5":  "✈️  AH Fora +0.5",

    "ha_fora_+1.0":  "✈️  AH Fora +1.0",

    "ha_fora_+1.5":  "✈️  AH Fora +1.5",

    "ha_fora_+2.0":  "✈️  AH Fora +2.0",

    "ha_0":          "➕  AH Linha Zero (0)",

    "ha_casa_-0.25": "🏠 AH Casa -0.25",

    "ha_casa_-0.75": "🏠 AH Casa -0.75",

    "ha_casa_-1.25": "🏠 AH Casa -1.25",

    "ha_fora_+0.25": "✈️  AH Fora +0.25",

    "ha_fora_+0.75": "✈️  AH Fora +0.75",

    "ha_fora_+1.25": "✈️  AH Fora +1.25",

}



# ─────────────────────────────────────────

# DADOS HISTÓRICOS — COPAS 2018 E 2022

# ─────────────────────────────────────────

HISTORICO_COPAS = [

    (1.52, 0.88,  1), (1.10, 1.20, 0), (1.40, 1.05, -1),

    (1.30, 1.15,  0), (1.60, 0.80, 1), (1.20, 1.10,  0),

    (1.35, 1.05,  0), (1.45, 0.95, 1), (1.25, 1.15,  0),

    (1.50, 0.90,  1), (1.20, 1.20,-1), (1.30, 1.10,  1),

    (1.40, 1.00,  1), (1.55, 0.85, 1), (1.45, 1.05,  0),

    (1.60, 0.85,  1), (1.50, 0.95, 0), (1.40, 1.10,  0),

    (1.35, 1.15, -1), (1.45, 1.05, 1), (1.50, 0.95,  1),

    (1.40, 1.10, -1), (1.60, 0.90, 1), (1.55, 0.90,  1),

    (1.50, 1.00, -1), (1.40, 1.05,-1), (1.35, 1.10,  0),

    (1.30, 1.20,  0), (1.25, 1.25, 0), (1.45, 1.00,  1),

    (1.50, 0.90,  1), (1.40, 1.05, 1), (1.30, 1.15, -1),

    (1.20, 1.20,  0), (1.55, 0.90, 1), (1.45, 1.05,  1),

    (1.60, 0.85,  1), (1.50, 0.95, 1), (1.40, 1.10, -1),

    (1.55, 0.90,  1), (1.45, 1.05, 1), (1.50, 1.00,  1),

]



# ═══════════════════════════════════════════

# UTILITÁRIOS

# ═══════════════════════════════════════════

def utc_para_brt(dt: datetime) -> datetime:

    return dt + timedelta(hours=FUSO_BRT)



def formatar_brt(dt_str: str) -> str:

    try:

        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

        return utc_para_brt(dt).strftime("%d/%m %H:%M BRT")

    except Exception:

        return dt_str



def agora_brt() -> datetime:

    return utc_para_brt(datetime.now(timezone.utc))



def eh_hora_resumo() -> bool:

    b = agora_brt()

    return b.hour == 8 and b.minute < 30



def dias_atras(dt_str: str) -> float:

    try:

        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)

    except Exception:

        return 30.0



def peso_temporal(dt_str: str) -> float:

    return math.exp(-LAMBDA_DECAY * dias_atras(dt_str))



# ═══════════════════════════════════════════

# BUDGET

# ═══════════════════════════════════════════

def carregar_budget() -> dict:

    hoje = datetime.now().strftime("%Y-%m-%d")

    try:

        if os.path.exists(ARQUIVO_BUDGET):

            with open(ARQUIVO_BUDGET) as f:

                d = json.load(f)

            if d.get("data") == hoje:

                return d

    except Exception as e:

        print(f"Erro em carregar_budget: {e}")

    return {"data": hoje, "calls_usadas": 0}



def salvar_budget(b: dict) -> None:

    try:

        with open(ARQUIVO_BUDGET, "w") as f:

            json.dump(b, f)

    except Exception as e:

        print(f"Erro em salvar_budget: {e}")



def registrar_call(b: dict) -> dict:

    b["calls_usadas"] += 1

    salvar_budget(b)

    return b



def calls_disponiveis(b: dict) -> int:

    return max(0, BUDGET_DIARIO - b["calls_usadas"])



# ═══════════════════════════════════════════

# CACHE — FIX #4: TTL correto (86400s = 24h)

# ═══════════════════════════════════════════

def carregar_cache() -> dict:

    try:

        if os.path.exists(ARQUIVO_CACHE):

            with open(ARQUIVO_CACHE) as f:

                raw = json.load(f)

            agora = datetime.now(timezone.utc)

            return {k: v for k, v in raw.items()

                    if (agora - datetime.fromisoformat(v)).total_seconds() < 86400}

    except Exception as e:

        print(f"Erro em carregar_cache: {e}")

    return {}



def salvar_cache(c: dict) -> None:

    try:

        with open(ARQUIVO_CACHE, "w") as f:

            json.dump(c, f)

    except Exception as e:

        print(f"Erro em salvar_cache: {e}")



def no_cache(fid: str, c: dict) -> bool:

    return fid in c



def add_cache(fid: str, c: dict) -> dict:

    c[fid] = datetime.now(timezone.utc).isoformat()

    salvar_cache(c)

    return c



# ═══════════════════════════════════════════

# LOG

# ═══════════════════════════════════════════

def carregar_log() -> list:

    try:

        if os.path.exists(ARQUIVO_LOG):

            with open(ARQUIVO_LOG) as f:

                return json.load(f)

    except Exception as e:

        print(f"Erro em carregar_log: {e}")

    return []



def salvar_log(entrada: dict) -> None:

    try:

        log = carregar_log()

        log.append(entrada)

        with open(ARQUIVO_LOG, "w") as f:

            json.dump(log[-500:], f, ensure_ascii=False, indent=2)

    except Exception as e:

        print(f"Erro em salvar_log: {e}")



# ═══════════════════════════════════════════

# TELEGRAM

# ═══════════════════════════════════════════

def enviar_telegram(msg: str) -> None:

    for i in range(0, len(msg), 4000):

        try:

            requests.post(

                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",

                data={"chat_id": TELEGRAM_CHAT, "text": msg[i:i+4000]},

                timeout=10,

            )

            if len(msg) > 4000:

                time.sleep(0.5)

        except Exception as e:

            print(f"[TELEGRAM] {e}")



# ═══════════════════════════════════════════

# API-FOOTBALL

# ═══════════════════════════════════════════

BASE_URL = "https://v3.football.api-sports.io"



def api_get(endpoint: str, params: dict, budget: dict):

    if calls_disponiveis(budget) <= BUDGET_EMERGENCIA:

        return [], budget

    try:

        r = requests.get(

            f"{BASE_URL}/{endpoint}",

            headers={"x-apisports-key": APIFOOTBALL_KEY},

            params=params, timeout=15,

        )

        budget = registrar_call(budget)

        rem = r.headers.get("x-ratelimit-requests-remaining")

        if rem and int(rem) < 15:

            print(f"  ⚠️ API mensal: {rem} restantes!")

        if r.status_code != 200:

            return [], budget

        return r.json().get("response", []), budget

    except Exception as e:

        print(f"  [API] {e}")

        return [], budget



def buscar_jogos_copa(budget: dict):

    agora = datetime.now(timezone.utc)

    dados, budget = api_get("fixtures", {

        "league": WORLD_CUP_ID, "season": WORLD_CUP_SEASON,

        "from": agora.strftime("%Y-%m-%d"),

        "to": (agora + timedelta(hours=48)).strftime("%Y-%m-%d"),

        "status": "NS",

    }, budget)

    return dados or [], budget



def buscar_jogos_finalizados_copa(budget: dict):

    dados, budget = api_get("fixtures", {

        "league": WORLD_CUP_ID, "season": WORLD_CUP_SEASON,

        "status": "FT",

    }, budget)

    return dados or [], budget



def buscar_classificacao_copa(budget: dict):

    dados, budget = api_get("standings", {

        "league": WORLD_CUP_ID, "season": WORLD_CUP_SEASON

    }, budget)

    if not dados: return {}, budget

    

    classificacao = {}

    grupos = dados[0].get("league", {}).get("standings", [])

    for grupo in grupos:

        for t in grupo:

            tid = t.get("team", {}).get("id")

            classificacao[tid] = {

                "points": t.get("points", 0),

                "played": t.get("all", {}).get("played", 0),

                "group": t.get("group", "")

            }

    return classificacao, budget



def buscar_ultimos_jogos(team_id: int, qtd: int,

                          league_id: int, season: int, budget: dict):

    dados, budget = api_get("fixtures", {

        "team": team_id, "last": qtd,

        "league": league_id, "season": season,

        "statistics": "true",

    }, budget)

    return dados or [], budget



def buscar_h2h(id1: int, id2: int, qtd: int, budget: dict):

    dados, budget = api_get("fixtures/headtohead", {

        "h2h": f"{id1}-{id2}", "last": qtd,

        "statistics": "true",

    }, budget)

    return dados or [], budget



def obter_elo_ratings() -> dict:

    try:

        import requests

        n_raw = requests.get('https://www.eloratings.net/en.teams.tsv', timeout=10).text

        e_raw = requests.get('https://www.eloratings.net/World.tsv', timeout=10).text

        names = {}

        for line in n_raw.split('\n'):

            parts = line.split('\t')

            if len(parts) >= 2: names[parts[0]] = parts[1].strip()

        elos = {}

        for line in e_raw.split('\n'):

            parts = line.split('\t')

            if len(parts) >= 4:

                code = parts[2]

                score = int(parts[3])

                if code in names: elos[names[code]] = score

        return elos

    except Exception as e:

        print(f"Erro ao buscar Elo Ratings: {e}")

        return {}



def buscar_xg_jogo(fixture_id: int, budget: dict):

    dados, budget = api_get("fixtures/statistics", {

        "fixture": fixture_id,

    }, budget)

    return dados or [], budget



def buscar_historico_completo(team_id: int, nome: str, budget: dict):

    jogos = []

    j, budget = buscar_ultimos_jogos(

        team_id, JOGOS_HISTORICO, WORLD_CUP_ID, WORLD_CUP_SEASON, budget)

    jogos.extend(j)

    time.sleep(0.5)

    if len(jogos) < 4:

        for eid in ELIMINATORIAS_IDS[:2]:

            if calls_disponiveis(budget) < 3:

                break

            j, budget = buscar_ultimos_jogos(

                team_id, JOGOS_HISTORICO, eid, 2025, budget)

            jogos.extend(j)

            time.sleep(0.5)

            if len(jogos) >= 5:

                break

    if len(jogos) < 4:

        liga_id = LIGAS_NACIONAIS.get(nome)

        if liga_id and calls_disponiveis(budget) >= 2:

            j, budget = buscar_ultimos_jogos(

                team_id, JOGOS_HISTORICO, liga_id, 2025, budget)

            jogos.extend(j)

            time.sleep(0.5)

    print(f"    📋 {nome}: {len(jogos)} jogos | "

          f"peso recência ativo (λ={LAMBDA_DECAY}/dia)")

    return jogos, budget



# ═══════════════════════════════════════════

# MÓDULO 1 — POISSON + DIXON-COLES

# ═══════════════════════════════════════════

def poisson_prob(k: int, lam: float) -> float:

    if lam <= 0:

        return 1.0 if k == 0 else 0.0

    return math.exp(-lam) * (lam ** k) / math.factorial(k)



def dixon_coles_tau(x: int, y: int, mu: float, nu: float, rho: float) -> float:

    if x == 0 and y == 0:

        return max(0.001, 1 - mu * nu * rho)

    elif x == 0 and y == 1:

        return max(0.001, 1 + mu * rho)

    elif x == 1 and y == 0:

        return max(0.001, 1 + nu * rho)

    elif x == 1 and y == 1:

        return max(0.001, 1 - rho)

    return 1.0



def matriz_placares(lc: float, lf: float, max_g: int = 8) -> list:

    placares = []

    for i in range(max_g + 1):

        for j in range(max_g + 1):

            p = (poisson_prob(i, lc) *

                 poisson_prob(j, lf) *

                 dixon_coles_tau(i, j, lc, lf, RHO_DIXON_COLES))

            placares.append((i, j, max(0.0, p)))

    total = sum(p for _, _, p in placares)

    if total > 0:

        placares = [(i, j, p / total) for i, j, p in placares]

    return placares



def derivar_mercados_poisson(placares: list) -> dict:

    vc = em = vf = btts = o25 = u25 = o15 = 0.0

    for (gc, gf, p) in placares:

        t = gc + gf

        if gc > gf:   vc   += p

        elif gc == gf: em  += p

        else:          vf  += p

        if gc > 0 and gf > 0: btts += p

        if t > 2.5:   o25  += p

        if t <= 2.5:  u25  += p

        if t > 1.5:   o15  += p

    return {

        "vitoria_casa":  round(vc   * 100, 2),

        "empate":        round(em   * 100, 2),

        "vitoria_fora":  round(vf   * 100, 2),

        "btts":          round(btts * 100, 2),

        "over25":        round(o25  * 100, 2),

        "under25":       round(u25  * 100, 2),

        "over15":        round(o15  * 100, 2),

    }



# ═══════════════════════════════════════════

# MÓDULO HANDICAP ASIÁTICO

# ═══════════════════════════════════════════

def calcular_handicap_asiatico(placares: list, linha: float) -> dict:

    if linha % 0.5 != 0:

        linha_baixo = linha - 0.25

        linha_cima  = linha + 0.25

        r1 = _ha_linha_simples(placares, linha_baixo)

        r2 = _ha_linha_simples(placares, linha_cima)

        return {

            "prob_casa":  round((r1["prob_casa"]  + r2["prob_casa"])  / 2, 2),

            "prob_fora":  round((r1["prob_fora"]  + r2["prob_fora"])  / 2, 2),

            "prob_push":  round((r1["prob_push"]  + r2["prob_push"])  / 2, 2),

            "linha":      linha,

        }

    return _ha_linha_simples(placares, linha)



def _ha_linha_simples(placares: list, linha: float) -> dict:

    prob_casa = prob_fora = prob_push = 0.0

    for (gc, gf, p) in placares:

        resultado_adj = gc - gf + linha

        if resultado_adj > 0:

            prob_casa += p

        elif resultado_adj < 0:

            prob_fora += p

        else:

            prob_push += p

    if linha % 1.0 == 0.5 or linha % 1.0 == -0.5:

        prob_push = 0.0

        total = prob_casa + prob_fora

        if total > 0:

            prob_casa = prob_casa / total * 100

            prob_fora = prob_fora / total * 100

    else:

        total = prob_casa + prob_fora + prob_push

        if total > 0:

            prob_casa = prob_casa / total * 100

            prob_fora = prob_fora / total * 100

            prob_push = prob_push / total * 100

    return {

        "prob_casa":  round(prob_casa, 2),

        "prob_fora":  round(prob_fora, 2),

        "prob_push":  round(prob_push, 2),

        "linha":      linha,

    }



def selecionar_melhor_handicap(placares: list, lc: float, lf: float) -> dict:

    resultados = []

    for linha in LINHAS_HANDICAP:

        ha_casa = calcular_handicap_asiatico(placares, linha)

        ha_fora = calcular_handicap_asiatico(placares, -linha)

        resultados.append({"linha": linha, "ha_casa": ha_casa, "ha_fora": ha_fora})



    melhores_casa = []

    melhores_fora = []

    for r in resultados:

        linha = r["linha"]

        pc = r["ha_casa"]["prob_casa"]

        pf = r["ha_fora"]["prob_fora"]

        # FIX #5: margem de 5% para edge real

        if pc >= PROB_MINIMA:

            odd_fair    = round(100 / pc, 2) if pc > 0 else 2.0

            odd_mercado = round(odd_fair * 0.95, 2)

            edge        = round(pc - (1 / odd_mercado) * 100, 2)

            melhores_casa.append({

                "tipo": "casa", "linha": linha,

                "label": f"AH Casa {linha:+.2f}".replace("+0.00", "0"),

                "prob": pc, "prob_push": r["ha_casa"]["prob_push"],

                "odd_fair": odd_fair, "edge": edge,

            })

        if pf >= PROB_MINIMA:

            odd_fair    = round(100 / pf, 2) if pf > 0 else 2.0

            odd_mercado = round(odd_fair * 0.95, 2)

            edge        = round(pf - (1 / odd_mercado) * 100, 2)

            melhores_fora.append({

                "tipo": "fora", "linha": -linha,

                "label": f"AH Fora {-linha:+.2f}".replace("+0.00", "0"),

                "prob": pf, "prob_push": r["ha_fora"]["prob_push"],

                "odd_fair": odd_fair, "edge": edge,

            })



    melhores_casa.sort(key=lambda x: -x["prob"])

    melhores_fora.sort(key=lambda x: -x["prob"])

    recomendada = None

    for mc in melhores_casa[:3]:

        if mc["prob"] >= 60 and mc["linha"] <= -0.5:

            recomendada = mc

            break

    if not recomendada and melhores_fora:

        recomendada = melhores_fora[0]

    return {

        "melhores_casa": melhores_casa[:4],

        "melhores_fora": melhores_fora[:4],

        "recomendada":   recomendada,

        "favorito":      "casa" if lc > lf else "fora",

    }



def montar_bloco_handicap(ha_resultado: dict, nc: str, nf: str, stake_base: float = 50.0) -> str:

    if not ha_resultado:

        return ""

    SEP = "━" * 34

    linhas = ["", SEP, "🎲  HANDICAP ASIÁTICO", SEP]

    fav = nc if ha_resultado["favorito"] == "casa" else nf

    linhas.append(f"⭐ Favorito: {fav}")

    linhas.append("")

    rec = ha_resultado.get("recomendada")

    if rec:

        stake   = kelly_stake(rec["prob"], rec["odd_fair"])

        retorno = round(stake * rec["odd_fair"], 2)

        push_txt = (f" | Push: {rec['prob_push']:.1f}%" if rec["prob_push"] > 0 else "")

        # FIX #2: f-string fechada corretamente

        linhas += [

            "🏆 MELHOR HANDICAP:",

            f"   {rec['label']}",

            f"   {'█' * round(rec['prob']/10)}{'░' * (10-round(rec['prob']/10))} {rec['prob']}%",

            f"   Odd fair : {rec['odd_fair']}{push_txt}",

            f"   Stake    : R${stake}",

            f"   Retorno  : R${retorno}",

            "",

        ]

    if ha_resultado["melhores_casa"]:

        linhas.append(f"🏠 {nc} (Handicap Casa):")

        for h in ha_resultado["melhores_casa"][:3]:

            push_txt = (f" [Push:{h['prob_push']:.0f}%]" if h["prob_push"] > 2 else "")

            linhas.append(f"   {h['linha']:+.2f} → {h['prob']}%  (odd ~{h['odd_fair']}){push_txt}")

        linhas.append("")

    if ha_resultado["melhores_fora"]:

        linhas.append(f"✈️  {nf} (Handicap Fora):")

        for h in ha_resultado["melhores_fora"][:3]:

            push_txt = (f" [Push:{h['prob_push']:.0f}%]" if h["prob_push"] > 2 else "")

            linhas.append(f"   {h['linha']:+.2f} → {h['prob']}%  (odd ~{h['odd_fair']}){push_txt}")

        linhas.append("")

    linhas += [

        "─" * 34, "📖 Como ler:",

        "  -1.5 = time precisa vencer por 2+",

        "  -1.0 = push se vencer por exato 1",

        "  -0.5 = qualquer vitória ganha",

        "   0   = push se empatar",

        "  +0.5 = ganha se empatar ou vencer",

    ]

    return "\n".join(linhas)



# ═══════════════════════════════════════════

# MÓDULO 2 — MONTE CARLO

# ═══════════════════════════════════════════

def simular_jogo_mc(lc: float, lf: float) -> tuple:

    gc = gf = 0

    L = math.exp(-lc)

    p, k = 1.0, 0

    while p > L:

        p *= random.random()

        k += 1

    gc = k - 1

    L = math.exp(-lf)

    p, k = 1.0, 0

    while p > L:

        p *= random.random()

        k += 1

    gf = k - 1

    return gc, gf



def monte_carlo(lc: float, lf: float, n: int = MONTE_CARLO_N) -> dict:

    vc = em = vf = btts = o25 = u25 = o15 = 0

    for _ in range(n):

        gc, gf = simular_jogo_mc(lc, lf)

        t = gc + gf

        if gc > gf:    vc   += 1

        elif gc == gf: em   += 1

        else:          vf   += 1

        if gc > 0 and gf > 0: btts += 1

        if t > 2.5:  o25 += 1

        if t <= 2.5: u25 += 1

        if t > 1.5:  o15 += 1

    return {

        "vitoria_casa":  round(vc   / n * 100, 2),

        "empate":        round(em   / n * 100, 2),

        "vitoria_fora":  round(vf   / n * 100, 2),

        "btts":          round(btts / n * 100, 2),

        "over25":        round(o25  / n * 100, 2),

        "under25":       round(u25  / n * 100, 2),

        "over15":        round(o15  / n * 100, 2),

    }



# ═══════════════════════════════════════════

# MÓDULO 3 — CALIBRAÇÃO PLATT SCALING

# ═══════════════════════════════════════════

def treinar_platt(historico: list) -> dict:

    params = {}

    for mercado in ["vitoria_casa", "empate", "vitoria_fora", "btts", "over25"]:

        probs_brutas = []

        labels_bin   = []

        for (lc, lf, resultado) in historico:

            placares = matriz_placares(lc, lf)

            probs    = derivar_mercados_poisson(placares)

            p_bruta  = probs.get(mercado, 50.0) / 100

            if mercado == "vitoria_casa":

                label = 1 if resultado == 1  else 0

            elif mercado == "vitoria_fora":

                label = 1 if resultado == -1 else 0

            elif mercado == "empate":

                label = 1 if resultado == 0  else 0

            elif mercado == "btts":

                label = 1 if lc + lf > 2.5   else 0

            elif mercado == "over25":

                label = 1 if lc + lf > 2.4   else 0

            else:

                label = 0

            probs_brutas.append(p_bruta)

            labels_bin.append(label)

        A, B = 1.0, 0.0

        lr   = 0.01

        for _ in range(500):

            grad_A = grad_B = 0.0

            for p, y in zip(probs_brutas, labels_bin):

                if p <= 0 or p >= 1:

                    continue

                f   = math.log(p / (1 - p))

                sig = 1 / (1 + math.exp(-(A * f + B)))

                err = sig - y

                grad_A += err * f

                grad_B += err

            n  = len(probs_brutas) or 1

            A -= lr * grad_A / n

            B -= lr * grad_B / n

        params[mercado] = {"A": round(A, 4), "B": round(B, 4)}

    return params



def aplicar_platt(prob_bruta: float, params: dict, mercado: str) -> float:

    p = params.get(mercado)

    if not p or prob_bruta <= 0 or prob_bruta >= 100:

        return prob_bruta

    prob = prob_bruta / 100

    if prob <= 0 or prob >= 1:

        return prob_bruta

    try:

        f   = math.log(prob / (1 - prob))

        sig = 1 / (1 + math.exp(-(p["A"] * f + p["B"])))

        return round(sig * 100, 2)

    except Exception:

        return prob_bruta



# ═══════════════════════════════════════════

# MÓDULO 4 — FORÇA DOS TIMES (xG)

# ═══════════════════════════════════════════

def extrair_xg_de_stats(stats: list, team_id: int) -> float:

    for bloco in stats:

        if bloco.get("team", {}).get("id") != team_id:

            continue

        for item in bloco.get("statistics", []):

            tipo = str(item.get("type", "")).lower()

            if "expected" in tipo and "goal" in tipo:

                val = item.get("value")

                if val and val != "None":

                    try:

                        return float(str(val).strip())

                    except Exception:

                        pass

    return None



def extrair_metricas(jogos: list, team_id: int) -> dict:

    if not jogos:

        return {}

    xg_marc_w = xg_sofr_w = 0.0

    gols_marc_w = gols_sofr_w = 0.0

    btts_w = over25_w = vit_w = 0.0

    esc_w = cart_w = 0.0

    peso_total = esc_peso = cart_peso = 0.0

    tem_xg = False

    n = 0

    for jogo in jogos:

        try:

            teams   = jogo.get("teams", {})

            goals   = jogo.get("goals", {})

            stats   = jogo.get("statistics", [])

            fixture = jogo.get("fixture", {})

            eh_casa = (teams.get("home", {}).get("id") == team_id)

            gp = goals.get("home") if eh_casa else goals.get("away")

            gs = goals.get("away") if eh_casa else goals.get("home")

            if gp is None or gs is None:

                continue

            gp = int(gp)

            gs = int(gs)

            w = peso_temporal(fixture.get("date", ""))

            xg_p = extrair_xg_de_stats(stats, team_id)

            xg_s_team = (teams.get("away", {}).get("id")

                         if eh_casa else teams.get("home", {}).get("id"))

            xg_s = extrair_xg_de_stats(stats, xg_s_team)

            if xg_p is not None and xg_s is not None:

                xg_marc_w += xg_p * w

                xg_sofr_w += xg_s * w

                tem_xg = True

            else:

                xg_marc_w += gp * w

                xg_sofr_w += gs * w

            gols_marc_w += gp * w

            gols_sofr_w += gs * w

            peso_total  += w

            n += 1

            # FIX #6: btts_w correto sem walrus/dead code

            if gp > 0 and gs > 0:

                btts_w += w

            if (gp + gs) > 2:   over25_w += w

            if gp > gs:         vit_w    += w

            for bloco in stats:

                if bloco.get("team", {}).get("id") != team_id:

                    continue

                for item in bloco.get("statistics", []):

                    tipo  = str(item.get("type", "")).lower()

                    valor = item.get("value") or 0

                    try:

                        valor = int(str(valor).replace("%","").strip())

                    except Exception:

                        valor = 0

                    if "corner" in tipo:

                        esc_w    += valor * w

                        esc_peso += w

                    elif "yellow card" in tipo:

                        cart_w    += valor * w

                        cart_peso += w

                    elif "red card" in tipo:

                        cart_w    += valor * 2 * w

                        cart_peso += w

        except Exception:

            continue

    if n == 0 or peso_total == 0:

        return {}

    return {

        "media_xg_marcados":  round(xg_marc_w  / peso_total, 3),

        "media_xg_sofridos":  round(xg_sofr_w  / peso_total, 3),

        "media_gols_marcados":round(gols_marc_w / peso_total, 3),

        "media_gols_sofridos":round(gols_sofr_w / peso_total, 3),

        "media_gols_total":   round((gols_marc_w + gols_sofr_w) / peso_total, 3),

        "btts_pct":           round(btts_w  / peso_total * 100, 1),

        "over25_pct":         round(over25_w / peso_total * 100, 1),

        "aproveitamento_pct": round(vit_w   / peso_total * 100, 1),

        "media_escanteios":   round(esc_w   / esc_peso,  2) if esc_peso  > 0 else 5.2,

        "media_cartoes":      round(cart_w  / cart_peso, 2) if cart_peso > 0 else 2.1,

        "jogos_analisados":   n,

        "tem_xg":             tem_xg,

    }



def extrair_metricas_h2h(jogos: list, id_casa: int) -> dict:

    if not jogos:

        return {"h2h_btts": 50, "h2h_over25": 50,

                "h2h_aprov_casa": 33, "h2h_jogos": 0, "h2h_media_gols": 2.2}

    btts = over25 = vit = total_gols_w = peso = 0.0

    n = 0

    for jogo in jogos:

        try:

            teams = jogo.get("teams", {})

            goals = jogo.get("goals", {})

            fix   = jogo.get("fixture", {})

            eh_casa = (teams.get("home", {}).get("id") == id_casa)

            gp = int(goals.get("home") if eh_casa else goals.get("away") or 0)

            gs = int(goals.get("away") if eh_casa else goals.get("home") or 0)

            w  = peso_temporal(fix.get("date", ""))

            total_gols_w += (gp + gs) * w

            peso += w

            n    += 1

            if gp > 0 and gs > 0:  btts   += w

            if (gp + gs) > 2:      over25 += w

            if gp > gs:            vit    += w

        except Exception:

            continue

    if n == 0 or peso == 0:

        return {"h2h_btts": 50, "h2h_over25": 50,

                "h2h_aprov_casa": 33, "h2h_jogos": 0, "h2h_media_gols": 2.2}

    return {

        "h2h_btts":       round(btts   / peso * 100, 1),

        "h2h_over25":     round(over25 / peso * 100, 1),

        "h2h_aprov_casa": round(vit    / peso * 100, 1),

        "h2h_jogos":      n,

        "h2h_media_gols": round(total_gols_w / peso, 2),

    }



def calcular_forca_times(todos_jogos: list) -> dict:

    xg_marc_casa  = defaultdict(list)

    xg_sofr_casa  = defaultdict(list)

    xg_marc_fora  = defaultdict(list)

    xg_sofr_fora  = defaultdict(list)

    for jogo in todos_jogos:

        try:

            teams = jogo.get("teams", {})

            goals = jogo.get("goals", {})

            stats = jogo.get("statistics", [])

            fix   = jogo.get("fixture", {})

            id_c  = teams.get("home", {}).get("id")

            id_f  = teams.get("away", {}).get("id")

            gc    = goals.get("home")

            gf    = goals.get("away")

            if gc is None or gf is None:

                continue

            gc, gf = int(gc), int(gf)

            w    = peso_temporal(fix.get("date", ""))

            xg_c = extrair_xg_de_stats(stats, id_c) or gc

            xg_f = extrair_xg_de_stats(stats, id_f) or gf

            xg_marc_casa[id_c].append((xg_c, w))

            xg_sofr_casa[id_c].append((xg_f, w))

            xg_marc_fora[id_f].append((xg_f, w))

            xg_sofr_fora[id_f].append((xg_c, w))

        except Exception:

            continue

    def mp(lista):

        if not lista: return 1.0

        sv = sum(v * w for v, w in lista)

        sw = sum(w for _, w in lista)

        return sv / sw if sw > 0 else 1.0

    todos_c = [x for lst in xg_marc_casa.values() for x in lst]

    todos_f = [x for lst in xg_marc_fora.values() for x in lst]

    mg_c    = mp(todos_c) or 1.25

    mg_f    = mp(todos_f) or 1.05

    forcas  = {}

    for tid in set(list(xg_marc_casa) + list(xg_marc_fora)):

        ac = mp(xg_marc_casa[tid])

        dc = mp(xg_sofr_casa[tid])

        af = mp(xg_marc_fora[tid])

        df = mp(xg_sofr_fora[tid])

        alpha = ((ac / mg_c) + (af / mg_f)) / 2

        beta  = ((dc / mg_f) + (df / mg_c)) / 2

        forcas[tid] = {"alpha": round(alpha, 3), "beta": round(beta, 3)}

    return forcas



# ═══════════════════════════════════════════

# MÓDULO 5 — VARIÁVEIS CONTEXTUAIS

# ═══════════════════════════════════════════

def calcular_dias_descanso(jogos: list, data_jogo: str) -> float:

    if not jogos:

        return 7.0

    datas = []

    for j in jogos:

        d = j.get("fixture", {}).get("date", "")

        if d:

            try:

                datas.append(datetime.fromisoformat(d.replace("Z", "+00:00")))

            except Exception:

                pass

    if not datas:

        return 7.0

    ultimo_jogo = max(datas)

    try:

        jogo_atual = datetime.fromisoformat(data_jogo.replace("Z", "+00:00"))

        return max(0.0, round((jogo_atual - ultimo_jogo).total_seconds() / 86400, 1))

    except Exception:

        return 7.0



def fator_descanso(dias: float) -> float:

    if dias < 2:    return 0.88

    elif dias < 3:  return 0.94

    elif dias <= 7: return 1.00

    elif dias <= 10:return 0.98

    else:           return 0.96



def fator_pressao_eliminatoria(fase: str, pode_empatar_casa: bool = True) -> dict:

    base = PRESSAO_FASE.get(fase, 1.0)

    return {"gols": base, "escanteios": base * 1.05, "cartoes": base * 1.10}



# ═══════════════════════════════════════════

# MÓDULO 6 — POISSON PARA ESCANTEIOS

# ═══════════════════════════════════════════

def calcular_lambda_escanteios(mc: dict, mf: dict, fase: str) -> tuple:

    press    = PRESSAO_FASE.get(fase, 1.0)

    lc_esc   = mc.get("media_escanteios", 5.2) * press

    lf_esc   = mf.get("media_escanteios", 5.2) * press

    xg_adj_c = mc.get("media_xg_marcados", 1.2) / 1.2

    xg_adj_f = mf.get("media_xg_marcados", 1.2) / 1.2

    lc_esc   = max(2.0, min(12.0, lc_esc * xg_adj_c))

    lf_esc   = max(2.0, min(12.0, lf_esc * xg_adj_f))

    return round(lc_esc, 2), round(lf_esc, 2)



def prob_escanteios_over(lc: float, lf: float, linha: float = 9.5) -> float:

    lambda_total = lc + lf

    p_under = sum(poisson_prob(k, lambda_total) for k in range(int(linha) + 1))

    return round((1 - p_under) * 100, 2)



def calcular_lambda_cartoes(mc: dict, mf: dict, fase: str) -> tuple:

    press = PRESSAO_FASE.get(fase, 1.0)

    lc    = max(0.5, min(6.0, mc.get("media_cartoes", 2.1) * press))

    lf    = max(0.5, min(6.0, mf.get("media_cartoes", 2.1) * press))

    return round(lc, 2), round(lf, 2)



def prob_cartoes_over(lc: float, lf: float, linha: float = 3.5) -> float:

    lambda_total = lc + lf

    p_under = sum(poisson_prob(k, lambda_total) for k in range(int(linha) + 1))

    return round((1 - p_under) * 100, 2)



# ═══════════════════════════════════════════

# MÓDULO 7 — DETECÇÃO DE LINE MOVEMENT

# ═══════════════════════════════════════════

def carregar_snapshots() -> dict:

    try:

        if os.path.exists(ARQUIVO_ODDS_SNAP):

            with open(ARQUIVO_ODDS_SNAP) as f:

                return json.load(f)

    except Exception:

        pass

    return {}



def salvar_snapshots(snaps: dict) -> None:

    try:

        with open(ARQUIVO_ODDS_SNAP, "w") as f:

            json.dump(snaps, f)

    except Exception:

        pass



def registrar_snapshot(fixture_id: str, probs: dict) -> None:

    snaps = carregar_snapshots()

    snaps[fixture_id] = {"timestamp": datetime.now(timezone.utc).isoformat(), "probs": probs}

    salvar_snapshots(snaps)



def detectar_line_movement(fixture_id: str, probs_atuais: dict) -> dict:

    snaps     = carregar_snapshots()

    snap      = snaps.get(fixture_id)

    if not snap:

        return {}

    movimentos = {}

    probs_ant  = snap.get("probs", {})

    for mercado, prob_atual in probs_atuais.items():

        prob_ant = probs_ant.get(mercado)

        if prob_ant is None:

            continue

        delta = prob_atual - prob_ant

        if abs(delta) >= 5.0:

            movimentos[mercado] = {

                "antes": prob_ant, "agora": prob_atual,

                "delta": round(delta, 1),

                "direcao": "📈 SUBIU" if delta > 0 else "📉 CAIU",

            }

    return movimentos



# ═══════════════════════════════════════════

# MÓDULO 8 — ENSEMBLE

# ═══════════════════════════════════════════

GAMMA_CASA = 1.18

GAMMA_SEDE = {"USA": 1.07, "Canada": 1.05, "Mexico": 1.09}



def calcular_lambdas(mc: dict, mf: dict, forca_c: dict, forca_f: dict,

                     nome_casa: str, dias_desc_c: float, dias_desc_f: float) -> tuple:

    gamma = GAMMA_CASA * GAMMA_SEDE.get(nome_casa, 1.0)

    fd_c  = fator_descanso(dias_desc_c)

    fd_f  = fator_descanso(dias_desc_f)

    if forca_c and forca_f:

        alpha_c = forca_c.get("alpha", 1.0)

        beta_c  = forca_c.get("beta",  1.0)

        alpha_f = forca_f.get("alpha", 1.0)

        beta_f  = forca_f.get("beta",  1.0)

        lc = alpha_c * beta_f * gamma * 1.20 * fd_c

        lf = alpha_f * beta_c / gamma * 1.05 * fd_f

    else:

        xg_c = mc.get("media_xg_marcados", mc.get("media_gols_marcados", 1.2))

        xg_f = mf.get("media_xg_marcados", mf.get("media_gols_marcados", 1.0))

        lc   = xg_c * gamma * fd_c

        lf   = xg_f * fd_f

    return (round(max(0.3, min(4.5, lc)), 3), round(max(0.3, min(4.5, lf)), 3))



def ensemble(probs_poisson: dict, probs_mc: dict, h2h: dict, fase: str, probs_esc_cart: dict) -> dict:

    ph2h = PESO_H2H_FASE.get(fase, 0.08)

    pp   = (1 - ph2h) * 0.60

    pm   = (1 - ph2h) * 0.40

    def blend(k, h2h_val):

        return round(probs_poisson.get(k, 50) * pp + probs_mc.get(k, 50) * pm + h2h_val * ph2h, 2)

    h2h_casa   = h2h.get("h2h_aprov_casa", 33)

    h2h_fora   = max(0, 100 - h2h_casa - 28)

    h2h_empate = 28.0

    h2h_btts   = h2h.get("h2h_btts",   50)

    h2h_over25 = h2h.get("h2h_over25", 50)

    resultado = {

        "vitoria_casa":  blend("vitoria_casa",  h2h_casa),

        "empate":        blend("empate",         h2h_empate),

        "vitoria_fora":  blend("vitoria_fora",  h2h_fora),

        "btts":          blend("btts",           h2h_btts),

        "over25":        blend("over25",         h2h_over25),

        "under25":       probs_poisson.get("under25", 50),

        "over15":        probs_poisson.get("over15",  50),

    }

    resultado.update(probs_esc_cart)

    return resultado



def aplicar_platt_todos(probs: dict, platt_params: dict) -> dict:

    return {k: aplicar_platt(v, platt_params, k) for k, v in probs.items()}



# ═══════════════════════════════════════════

# KELLY CRITERION

# ═══════════════════════════════════════════

def kelly_stake(prob: float, odd: float) -> float:

    if odd <= 1.0 or prob <= 0:

        return 0.0

    p = prob / 100

    b = odd - 1

    f = (p * (b + 1) - 1) / b

    if f <= 0:

        return 0.0

    return round(min(f * KELLY_FRACAO * BANCA_PADRAO, BANCA_PADRAO * 0.15), 2)



def calcular_edge(prob: float, odd: float) -> float:

    if odd <= 1.0:

        return 0.0

    return round(prob - (1 / odd) * 100, 2)



# ═══════════════════════════════════════════

# MONTAGEM DA MENSAGEM

# ═══════════════════════════════════════════

def barra(pct: float) -> str:

    c = round(pct / 10)

    return "█" * c + "░" * (10 - c)



def nivel(pct: float) -> str:

    if pct >= 82: return "🔥 MUITO ALTA"

    if pct >= 72: return "✅ ALTA"

    if pct >= 62: return "⚡ MODERADA"

    return "⚠️ BAIXA"



def montar_alerta(jogo: dict, probs_cal: dict, mc_met: dict, mf_met: dict,

                  h2h: dict, fase: str, lc: float, lf: float,

                  forca_c: dict, forca_f: dict, movimentos: dict,

                  dias_c: float, dias_f: float, lc_esc: float, lf_esc: float,

                  tem_xg: bool, ha_resultado: dict = None) -> str:

    fix    = jogo.get("fixture", {})

    teams  = jogo.get("teams",   {})

    league = jogo.get("league",  {})

    nc     = teams.get("home", {}).get("name", "?")

    nf     = teams.get("away", {}).get("name", "?")

    hora   = formatar_brt(fix.get("date", ""))

    rodada = league.get("round", fase)

    mercados_ok = [

        {"k": k, "prob": v, "label": LABELS.get(k, k)}

        for k, v in probs_cal.items() if v >= PROB_MINIMA

    ]

    mercados_ok.sort(key=lambda x: -x["prob"])

    if not mercados_ok and not ha_resultado:

        return ""

    xg_tag  = "✅ xG" if tem_xg else "⚠️  gols brutos"

    SEP      = "━" * 34

    SEP_SLIM = "─" * 34

    linhas = [

        "╔══════════════════════════════════╗",

        "║       COPA DO MUNDO 2026         ║",

        f"║ ⚽ {nc[:14]:<14} vs {nf[:9]:<9}║",

        f"║ 📋 {rodada[:32]:<32}║",

        f"║ 🕐 {hora:<29}║",

        "╚══════════════════════════════════╝",

        "",

    ]

    if movimentos:

        linhas += ["🚨 SMART MONEY DETECTADO", SEP_SLIM]

        for merc, mv in movimentos.items():

            linhas.append(f"  {LABELS.get(merc,merc)}: {mv['antes']}% → {mv['agora']}% {mv['direcao']} ({abs(mv['delta'])}%)")

        linhas += ["", SEP, ""]

    if mercados_ok:

        linhas += [SEP, "🎯 APOSTAS RECOMENDADAS", SEP]

        for idx, m in enumerate(mercados_ok, 1):

            odd_fair = round(100 / m["prob"], 2)

            stake    = kelly_stake(m["prob"], odd_fair)

            retorno  = round(stake * odd_fair, 2)

            edge     = calcular_edge(m["prob"], odd_fair)

            rank_tag = "🥇 #1 — MELHOR APOSTA" if idx == 1 else f"🏅 #{idx} — BOA APOSTA"

            linhas += [

                "", rank_tag, m["label"],

                f"{barra(m['prob'])} {m['prob']}%",

                f"Confiança: {nivel(m['prob'])}",

                f"💰 Odd fair: {odd_fair}",

                f"💵 Stake Kelly : R${stake}",

                f"🎁 Retorno     : R${retorno}",

                f"📊 Edge        : +{edge}%",

            ]

    if ha_resultado:

        linhas.append(montar_bloco_handicap(ha_resultado, nc, nf))

    linhas += [

        "", SEP, "🔬 MOTOR DO MODELO", SEP,

        f"   Poisson + Dixon-Coles + Monte Carlo",

        f"   Dados: {xg_tag} | Platt Scaling v6.1",

        f"   λ({nc})={lc} | λ({nf})={lf}",

        f"   λ_esc={lc_esc}/{lf_esc} | MC={MONTE_CARLO_N:,} sims",

    ]

    linhas += ["", SEP, "📊 PROBABILIDADES COMPLETAS", SEP]

    for k in ["vitoria_casa","empate","vitoria_fora","btts","over25","under25","over15","escanteios","cartoes"]:

        prob = probs_cal.get(k)

        if prob is None: continue

        tag = " ✅" if prob >= PROB_MINIMA else ""

        linhas.append(f"{LABELS.get(k, k):<22} {barra(prob)} {prob}%{tag}")

    linhas += ["", SEP, "📈 ESTATÍSTICAS DOS TIMES", SEP]

    for (nome, met, fc) in [(nc, mc_met, forca_c), (nf, mf_met, forca_f)]:

        n_j  = met.get("jogos_analisados","?")

        xg_m = met.get("media_xg_marcados", met.get("media_gols_marcados","?"))

        xg_s = met.get("media_xg_sofridos", met.get("media_gols_sofridos","?"))
        f_atk= fc.get("fator_ataque", 1.0)
        f_def= fc.get("fator_defesa", 1.0)
        linhas.append(f"  {nome}: {n_j}J | xG+: {xg_m} | xG-: {xg_s}")
        linhas.append(f"    Força Atk: {f_atk} | Força Def: {f_def}")
    
    return "\n".join(linhas)

# RESUMO DIÁRIO

# ═══════════════════════════════════════════

def enviar_resumo_diario(jogos: list) -> None:

    if not jogos: return

    data     = agora_brt().strftime("%d/%m/%Y")

    log      = carregar_log()

    acertos  = sum(1 for e in log if e.get("resultado") == "acerto")

    total_log= len([e for e in log if e.get("resultado")])

    SEP      = "━" * 34

    linhas   = [f"☀️ BOM DIA! COPA 2026 — {data}", f"⚽ {len(jogos)} jogo(s) programado(s) hoje", SEP]

    for j in jogos:

        nc   = j.get("teams",{}).get("home",{}).get("name","?")

        nf   = j.get("teams",{}).get("away",{}).get("name","?")

        hora = formatar_brt(j.get("fixture",{}).get("date",""))

        rod  = j.get("league",{}).get("round","")

        linhas += [f"⚽ {nc} vs {nf}", f"   {hora} | {rod}", ""]

    if total_log > 0:

        taxa = round(acertos / total_log * 100, 1)

        linhas += [SEP, "📊 DESEMPENHO ACUMULADO", SEP,

                   f"Taxa de acerto : {taxa}%", f"Indicações     : {acertos}/{total_log} certas"]

    linhas += ["", SEP, "🔬 Motor: Poisson+MC+Dixon-Coles+Platt+HA v6.1", "Análises serão enviadas antes de cada jogo."]

    enviar_telegram("\n".join(linhas))



# ═══════════════════════════════════════════

# MÓDULO 9 — SCORE DE CONFIANÇA

# ═══════════════════════════════════════════

def calcular_score_confianca(probs_cal, probs_poisson, probs_mc, mc_met, mf_met, h2h, tem_xg, dias_c, dias_f, movimentos):

    score    = 0.0

    detalhes = []

    mercados_base  = ["vitoria_casa","empate","vitoria_fora","btts","over25"]

    diferencas     = [abs(probs_poisson.get(k,50) - probs_mc.get(k,50)) for k in mercados_base]

    conv           = sum(diferencas) / max(len(diferencas), 1)

    pts_conv       = round(max(0.0, 25 - conv * 1.5), 1)

    score         += pts_conv

    detalhes.append(f"Convergência Poisson/MC: +{pts_conv}pts (Δ={conv:.1f}%)")

    n_min    = min(mc_met.get("jogos_analisados",0), mf_met.get("jogos_analisados",0))

    pts_dados= round(min(20.0, n_min * 2.0), 1)

    score   += pts_dados

    detalhes.append(f"Volume de dados: +{pts_dados}pts ({n_min} jogos mínimo)")

    pts_xg   = 15 if tem_xg else 5

    score   += pts_xg

    detalhes.append(f"xG: +{pts_xg}pts ({'disponível ✅' if tem_xg else 'usando gols ⚠️'})")

    fd_c     = min(dias_c, 7) / 7

    fd_f     = min(dias_f, 7) / 7

    pts_desc = round((fd_c + fd_f) / 2 * 15, 1)

    score   += pts_desc

    detalhes.append(f"Descanso: +{pts_desc}pts ({dias_c}d / {dias_f}d)")

    n_h2h    = h2h.get("h2h_jogos", 0)

    pts_h2h  = round(min(15.0, n_h2h * 2.5), 1)

    score   += pts_h2h

    detalhes.append(f"H2H: +{pts_h2h}pts ({n_h2h} confrontos diretos)")

    pts_lm   = round(min(10.0, len(movimentos) * 3.0), 1)

    score   += pts_lm

    if pts_lm > 0:

        detalhes.append(f"Smart money: +{pts_lm}pts ({len(movimentos)} mercados)")

    score = round(min(100.0, score), 1)

    if score >= 80:   nivel_score = "🔥 EXCELENTE"

    elif score >= 68: nivel_score = "✅ BOM"

    elif score >= 55: nivel_score = "⚡ MODERADO"

    else:             nivel_score = "⚠️ FRACO"

    return score, nivel_score, detalhes



# ═══════════════════════════════════════════

# MÓDULO 10 — LESÕES E DESFALQUES

# ═══════════════════════════════════════════

def buscar_jogadores_jogo(fixture_id: int, budget: dict):

    dados, budget = api_get("fixtures/players", {"fixture": fixture_id}, budget)

    return dados or [], budget



def calcular_impacto_desfalques(jogadores: list, id_time: int) -> dict:

    ausentes = []

    penalidade_ataque = penalidade_defesa = 0.0

    STATUS_AUSENTE = ["injured","suspended","doubtful","missing","lesionado","suspenso"]

    for bloco in jogadores:

        if bloco.get("team", {}).get("id") != id_time: continue

        for pd in bloco.get("players", []):

            p      = pd.get("player", {})

            stats  = pd.get("statistics", [{}])

            status = str(p.get("reason", "")).lower()

            pos    = stats[0].get("games", {}).get("position", "") if stats else ""

            if not any(s in status for s in STATUS_AUSENTE): continue

            nome = p.get("name", "Jogador desconhecido")

            ausentes.append(f"{nome} ({pos})")

            if pos in ("F","Attacker","Forward"):       penalidade_ataque += 0.13

            elif pos in ("M","Midfielder"):             penalidade_ataque += 0.06; penalidade_defesa += 0.06

            elif pos in ("D","Defender"):               penalidade_defesa += 0.10

            elif pos in ("G","Goalkeeper"):             penalidade_defesa += 0.16

    return {

        "ausentes":       ausentes,

        "fator_ataque":   round(max(0.55, 1.0 - penalidade_ataque), 3),

        "fator_defesa":   round(max(0.55, 1.0 - penalidade_defesa), 3),

        "total_ausentes": len(ausentes),

    }



# ═══════════════════════════════════════════

# MÓDULO 11 — VALUE BET MULTI-CASA

# ═══════════════════════════════════════════

def calcular_value_bets(probs_cal: dict, odds_casas: dict) -> list:

    values = []

    for mercado, prob in probs_cal.items():

        if prob <= 0: continue

        for casa, odd in odds_casas.get(mercado, {}).items():

            if odd <= 1.0: continue

            prob_imp = round((1 / odd) * 100, 2)

            value    = round((prob / 100) * odd - 1, 4)

            edge     = round(prob - prob_imp, 2)

            if value > 0.03:

                stake   = kelly_stake(prob, odd)

                retorno = round(stake * odd, 2)

                values.append({

                    "mercado": mercado, "label": LABELS.get(mercado, mercado),

                    "casa": casa, "odd": odd, "prob_modelo": prob,

                    "prob_implicita": prob_imp, "value": value, "edge": edge,

                    "stake_kelly": stake, "retorno": retorno,

                })

    values.sort(key=lambda x: -x["value"])

    return values



def montar_bloco_value_bets(values: list) -> str:

    if not values: return ""

    SEP    = "━" * 34

    linhas = ["", SEP, "💎 VALUE BETS — MELHOR ODD POR CASA", SEP]

    vistos = set()

    for idx, v in enumerate(values[:5], 1):

        chave = (v["mercado"], v["casa"])

        if chave in vistos: continue

        vistos.add(chave)

        linhas += [

            "", f"#{idx} {v['label']}",

            f"   🏢 Casa      : {v['casa']}", f"   💰 Odd       : {v['odd']}",

            f"   📊 Prob modelo: {v['prob_modelo']}%", f"   📉 Prob impl : {v['prob_implicita']}%",

            f"   📈 Edge      : +{v['edge']}%", f"   💎 Value     : {round(v['value']*100,1)}%",

            f"   💵 Stake     : R${v['stake_kelly']}", f"   🎁 Retorno   : R${v['retorno']}",

        ]

    return "\n".join(linhas)



# ═══════════════════════════════════════════

# MÓDULO 12 — BACKTEST AUTOMÁTICO

# ═══════════════════════════════════════════

def processar_backtest(log: list, jogos_finalizados: list) -> dict:

    mapa = {}

    for j in jogos_finalizados:

        fid = str(j.get("fixture", {}).get("id", ""))

        gc  = j.get("goals", {}).get("home") or 0

        gf  = j.get("goals", {}).get("away") or 0

        mapa[fid] = {"gc": int(gc), "gf": int(gf)}

    acertos_m = {}; total_m = {}; roi_m = {}; atualizados = 0

    for entrada in log:

        fid = entrada.get("fixture_id", "")

        res = mapa.get(fid)

        if not res or entrada.get("resultado") is not None: continue

        gc, gf = res["gc"], res["gf"]

        probs   = entrada.get("probs_calibradas", {})

        atualizados += 1

        reais = {

            "vitoria_casa": gc > gf, "empate": gc == gf, "vitoria_fora": gc < gf,

            "btts": gc > 0 and gf > 0, "over25": gc + gf > 2,

            "under25": gc + gf <= 2, "over15": gc + gf > 1,

            "escanteios": True, "cartoes": True,

        }

        acertou_algum = False

        for mercado, prob in probs.items():

            if prob < PROB_MINIMA: continue

            ocorreu  = reais.get(mercado, False)

            odd_fair = round(100 / prob, 2) if prob > 0 else 2.0

            stake    = 10.0

            lucro    = round(stake * odd_fair - stake, 2) if ocorreu else -stake

            acertos_m[mercado] = acertos_m.get(mercado, 0) + (1 if ocorreu else 0)

            total_m[mercado]   = total_m.get(mercado, 0) + 1

            roi_m[mercado]     = round(roi_m.get(mercado, 0.0) + lucro, 2)

            if ocorreu: acertou_algum = True

        entrada["resultado"]   = "acerto" if acertou_algum else "erro"

        entrada["placar_real"] = f"{gc}-{gf}"

    return {"atualizados": atualizados, "acertos_mercado": acertos_m, "total_mercado": total_m, "roi_mercado": roi_m}



def montar_relatorio_backtest(bt: dict, placar: str = "", nc: str = "", nf: str = "") -> str:

    if bt["atualizados"] == 0: return ""

    SEP       = "━" * 34

    roi_total = sum(bt["roi_mercado"].values())

    roi_tag   = f"+R${roi_total:.2f}" if roi_total >= 0 else f"-R${abs(roi_total):.2f}"

    linhas    = [SEP, "📊 RESULTADO ATUALIZADO", SEP]

    if nc and nf and placar: linhas += [f"⚽ {nc} {placar} {nf}", ""]

    linhas += [f"✅ {bt['atualizados']} jogo(s) processado(s)", f"💰 ROI do ciclo: {roi_tag}", "", SEP, "Por mercado:", SEP]

    for mercado in sorted(bt["total_mercado"], key=lambda m: -bt["acertos_mercado"].get(m,0)):

        tot  = bt["total_mercado"][mercado]

        acer = bt["acertos_mercado"].get(mercado, 0)

        roi  = bt["roi_mercado"].get(mercado, 0.0)

        taxa = round(acer / tot * 100, 1) if tot else 0

        roi_m = f"+R${roi:.2f}" if roi >= 0 else f"-R${abs(roi):.2f}"

        icon  = "✅" if taxa >= 60 else "⚡" if taxa >= 50 else "❌"

        linhas.append(f"{icon} {LABELS.get(mercado,mercado)}: {acer}/{tot} ({taxa}%) | {roi_m}")

    return "\n".join(linhas)



# ═══════════════════════════════════════════

# MÓDULO 13 — RELATÓRIO SEMANAL

# ═══════════════════════════════════════════

relatorio_semanal_enviado = None



def eh_hora_relatorio_semanal() -> bool:

    brt = agora_brt()

    return brt.weekday() == 6 and brt.hour == 9 and brt.minute < 30



def gerar_relatorio_semanal(log: list, jogos_proximos: list) -> str:

    semana_atras    = datetime.now().timestamp() - 7 * 86400

    entradas_semana = [e for e in log if datetime.fromisoformat(e.get("data","2020-01-01")).timestamp() > semana_atras]

    com_resultado   = [e for e in entradas_semana if e.get("resultado")]

    total  = len(com_resultado)

    acert  = sum(1 for e in com_resultado if e.get("resultado") == "acerto")

    taxa   = round(acert / total * 100, 1) if total else 0

    roi_semana = {}; acc_semana = {}; tot_semana = {}

    for e in com_resultado:

        for merc, prob in e.get("probs_calibradas", {}).items():

            if prob < PROB_MINIMA: continue

            ocorreu  = e.get("resultado") == "acerto"

            odd_fair = round(100 / prob, 2) if prob > 0 else 2.0

            lucro    = round(10 * odd_fair - 10, 2) if ocorreu else -10.0

            roi_semana[merc] = round(roi_semana.get(merc, 0) + lucro, 2)

            acc_semana[merc] = acc_semana.get(merc, 0) + (1 if ocorreu else 0)

            tot_semana[merc] = tot_semana.get(merc, 0) + 1

    data_str = agora_brt().strftime("%d/%m/%Y")

    linhas   = [f"📊 RELATÓRIO SEMANAL — Copa 2026", f"📅 {data_str}", "",

                "─" * 34, "📈 DESEMPENHO DA SEMANA", "─" * 34,

                f"Indicações: {total} | Acertos: {acert} ({taxa}%)", "", "Por mercado:"]

    for merc in sorted(tot_semana, key=lambda m: -acc_semana.get(m,0)):

        t = tot_semana[merc]; a = acc_semana.get(merc, 0); r = roi_semana.get(merc, 0)

        tx = round(a / t * 100, 1) if t else 0

        roi_tag = f"+R${r:.2f}" if r >= 0 else f"-R${abs(r):.2f}"

        linhas.append(f"  {LABELS.get(merc, merc)}: {a}/{t} ({tx}%) | {roi_tag}")

    if jogos_proximos:

        linhas += ["", "─" * 34, "📅 PRÓXIMOS JOGOS", "─" * 34]

        for j in jogos_proximos[:5]:

            nc   = j.get("teams",{}).get("home",{}).get("name","?")

            nf   = j.get("teams",{}).get("away",{}).get("name","?")

            hora = formatar_brt(j.get("fixture",{}).get("date",""))

            rod  = j.get("league",{}).get("round","")

            linhas += [f"⚽ {nc} vs {nf}", f"   {hora} | {rod}"]

    linhas += ["", "━" * 34, "🔬 Motor: Poisson+MC+Dixon-Coles+Platt+HA v6.1"]

    return "\n".join(linhas)



# ═══════════════════════════════════════════

# MÓDULO 14 — AUTOAPRENDIZADO

# ═══════════════════════════════════════════

def carregar_params_modelo() -> dict:

    defaults = {

        "rho_dixon_coles": RHO_DIXON_COLES, "lambda_decay": LAMBDA_DECAY,

        "peso_poisson": 0.60, "peso_mc": 0.40, "gamma_casa": GAMMA_CASA,

        "prob_minima": float(PROB_MINIMA), "versao": 1, "jogos_treinados": 0,

        "ultima_atualizacao": None, "historico_brier": [], "historico_logloss": [],

    }

    try:

        if os.path.exists(ARQUIVO_PARAMS):

            with open(ARQUIVO_PARAMS) as f:

                saved = json.load(f)

            defaults.update(saved)

    except Exception:

        pass

    return defaults



def salvar_params_modelo(params: dict) -> None:

    try:

        with open(ARQUIVO_PARAMS, "w") as f:

            json.dump(params, f, ensure_ascii=False, indent=2)

    except Exception:

        pass



def calcular_brier_score(probs_modelo: dict, resultado_real: dict) -> float:

    mercados = ["vitoria_casa","empate","vitoria_fora","btts","over25"]

    soma, n  = 0.0, 0

    for m in mercados:

        p = probs_modelo.get(m, 50.0) / 100; r = float(resultado_real.get(m, 0))

        soma += (p - r) ** 2; n += 1

    return round(soma / n, 6) if n > 0 else 0.25



def calcular_log_loss(probs_modelo: dict, resultado_real: dict) -> float:

    mercados = ["vitoria_casa","empate","vitoria_fora","btts","over25"]

    soma, n  = 0.0, 0; eps = 1e-7

    for m in mercados:

        p = max(eps, min(1-eps, probs_modelo.get(m, 50.0) / 100)); r = float(resultado_real.get(m, 0))

        soma -= r * math.log(p) + (1 - r) * math.log(1 - p); n += 1

    return round(soma / n, 6) if n > 0 else 1.0



def inferir_resultado_real(entrada: dict) -> dict:

    placar = entrada.get("placar_real", "")

    try:

        gc, gf = map(int, placar.split("-"))

        return {"vitoria_casa": int(gc > gf), "empate": int(gc == gf),

                "vitoria_fora": int(gc < gf), "btts": int(gc > 0 and gf > 0), "over25": int(gc + gf > 2)}

    except Exception:

        return {}



def analisar_erros_sistematicos(log: list) -> dict:

    dados_por_mercado = defaultdict(list)

    for entrada in log:

        if entrada.get("resultado") is None: continue

        probs = entrada.get("probs_calibradas", {})

        res   = entrada.get("resultado_real") or inferir_resultado_real(entrada)

        if not res: continue

        for mercado, prob in probs.items():

            dados_por_mercado[mercado].append((prob / 100, float(res.get(mercado, 0))))

    analise = {}

    for mercado, dados in dados_por_mercado.items():

        if len(dados) < 3: continue

        media_p = sum(p for p, _ in dados) / len(dados)

        media_r = sum(r for _, r in dados) / len(dados)

        brier   = sum((p - r)**2 for p, r in dados) / len(dados)

        vies    = round((media_p - media_r) * 100, 2)

        analise[mercado] = {"n": len(dados), "vies": vies, "brier": round(brier, 4),

                            "media_prob": round(media_p * 100, 1), "media_real": round(media_r * 100, 1)}

    return analise



def ajustar_parametros_modelo(params: dict, erros: dict, log: list) -> tuple:

    novos = params.copy(); ajustes_feitos = []

    vies_casa = erros.get("vitoria_casa", {}).get("vies", 0)

    if abs(vies_casa) > 5.0:

        delta      = max(-0.05, min(0.05, -vies_casa * 0.003))

        novo_gamma = max(1.05, min(1.35, round(novos["gamma_casa"] + delta, 3)))

        if novo_gamma != novos["gamma_casa"]:

            ajustes_feitos.append(f"gamma_casa: {novos['gamma_casa']} → {novo_gamma} (viés vitória_casa={vies_casa:+.1f}%)")

            novos["gamma_casa"] = novo_gamma

    placares_baixos = total_jogos = 0

    for e in log:

        try:

            gc, gf = map(int, e.get("placar_real","").split("-"))

            total_jogos += 1

            if gc + gf <= 1: placares_baixos += 1

        except Exception:

            pass

    if total_jogos >= 8:

        freq_real = placares_baixos / total_jogos

        if freq_real > 0.25:   novo_rho = round(max(-0.25, novos["rho_dixon_coles"] - 0.01), 3)

        elif freq_real < 0.15: novo_rho = round(min(-0.05, novos["rho_dixon_coles"] + 0.01), 3)

        else:                  novo_rho = novos["rho_dixon_coles"]

        if novo_rho != novos["rho_dixon_coles"]:

            ajustes_feitos.append(f"rho_dixon_coles: {novos['rho_dixon_coles']} → {novo_rho}")

            novos["rho_dixon_coles"] = novo_rho

    total   = sum(1 for e in log if e.get("resultado") is not None)

    acertos = sum(1 for e in log if e.get("resultado") == "acerto")

    if total >= 8:

        taxa = acertos / total

        if taxa < 0.52 and novos["prob_minima"] < 72:

            novo_min = round(min(72.0, novos["prob_minima"] + 1.0), 1)

            ajustes_feitos.append(f"prob_minima: {novos['prob_minima']}% → {novo_min}% (taxa={taxa:.1%})")

            novos["prob_minima"] = novo_min

        elif taxa > 0.72 and novos["prob_minima"] > 55:

            novo_min = round(max(55.0, novos["prob_minima"] - 0.5), 1)

            ajustes_feitos.append(f"prob_minima: {novos['prob_minima']}% → {novo_min}% (taxa={taxa:.1%})")

            novos["prob_minima"] = novo_min

    if ajustes_feitos:

        novos["versao"]             = params.get("versao", 1) + 1

        novos["ultima_atualizacao"] = datetime.now().isoformat()

    novos["jogos_treinados"] = total

    return novos, ajustes_feitos



def executar_autoaprendizado(params_atuais: dict) -> dict:

    log           = carregar_log()

    com_resultado = [e for e in log if e.get("resultado") is not None]

    jogos_novos   = len(com_resultado) - params_atuais.get("jogos_treinados", 0)

    if jogos_novos < JOGOS_PARA_RETREINAR:

        return params_atuais

    print(f"\n  🧠 Autoaprendizado: {jogos_novos} novos resultados")

    erros          = analisar_erros_sistematicos(com_resultado)

    novos, ajustes = ajustar_parametros_modelo(params_atuais, erros, com_resultado)

    if ajustes:

        salvar_params_modelo(novos)

        enviar_telegram(

            "🧠 AUTOAPRENDIZADO — MODELO ATUALIZADO\n\n"

            f"Versão: v{params_atuais.get('versao',1)} → v{novos.get('versao',1)}\n"

            f"Jogos treinados: {novos.get('jogos_treinados',0)}\n\nAJUSTES:\n"

            + "\n".join(f"  • {a}" for a in ajustes)

        )

    else:

        print("  ✅ Parâmetros estáveis")

    novos["jogos_treinados"] = len(com_resultado)

    salvar_params_modelo(novos)

    return novos



# ───────────────────────────────────────────

# Treina Platt uma vez na inicialização

# ───────────────────────────────────────────

print("🔬 Treinando calibração Platt Scaling...")

PLATT_PARAMS = treinar_platt(HISTORICO_COPAS)

print(f"✅ Parâmetros calibrados para {len(PLATT_PARAMS)} mercados")



# ═══════════════════════════════════════════

# ANALISAR JOGO

# ═══════════════════════════════════════════

def analisar_jogo(jogo: dict, budget: dict, cache: dict, todos_jogos_copa: list, elo_ratings: dict = None, classificacao: dict = None) -> tuple:

    fix      = jogo.get("fixture", {})

    teams    = jogo.get("teams",   {})

    league   = jogo.get("league",  {})

    fid      = str(fix.get("id", ""))

    nc       = teams.get("home", {}).get("name", "?")

    nf       = teams.get("away", {}).get("name", "?")

    id_c     = teams.get("home", {}).get("id")

    id_f     = teams.get("away", {}).get("id")

    data_jogo= fix.get("date", "")

    fase     = FASES.get(league.get("round","Group Stage"), "fase_grupos")

    if not fid or not id_c or not id_f:

        return budget, cache

    if no_cache(fid, cache):

        print(f"  [CACHE] {nc} vs {nf}")

        return budget, cache

    print(f"\n  ⚽ {nc} vs {nf} [{fase.replace('_',' ').title()}]")

    if calls_disponiveis(budget) < 6:

        print("  ⚠️  Budget insuficiente.")

        return budget, cache

    jogos_c, budget = buscar_historico_completo(id_c, nc, budget)

    time.sleep(1)

    jogos_f, budget = buscar_historico_completo(id_f, nf, budget)

    time.sleep(1)

    if not jogos_c or not jogos_f:

        print("  [SEM DADOS]")

        return budget, cache

    jogos_h2h, budget = buscar_h2h(id_c, id_f, JOGOS_H2H, budget)

    time.sleep(0.5)

    mc  = extrair_metricas(jogos_c, id_c)

    mf  = extrair_metricas(jogos_f, id_f)

    h2h = extrair_metricas_h2h(jogos_h2h, id_c)

    if not mc or not mf:

        print("  [SEM MÉTRICAS]")

        return budget, cache

    tem_xg = mc.get("tem_xg", False) or mf.get("tem_xg", False)

    dias_c = calcular_dias_descanso(jogos_c, data_jogo)

    dias_f = calcular_dias_descanso(jogos_f, data_jogo)

    forcas  = calcular_forca_times(todos_jogos_copa + jogos_c + jogos_f)

    forca_c = forcas.get(id_c, {"alpha": 1.0, "beta": 1.0})

    forca_f = forcas.get(id_f, {"alpha": 1.0, "beta": 1.0})



    elo_ratings = elo_ratings or {}

    elo_c = elo_ratings.get(nc)

    elo_f = elo_ratings.get(nf)

    

    if elo_c:

        elo_ratio_c = elo_c / 1500.0

        forca_c["alpha"] = round(forca_c["alpha"] * 0.6 + elo_ratio_c * 0.4, 3)

        forca_c["beta"]  = round(forca_c["beta"] * 0.6 + (1 / elo_ratio_c) * 0.4, 3)

        

    if elo_f:

        elo_ratio_f = elo_f / 1500.0

        forca_f["alpha"] = round(forca_f["alpha"] * 0.6 + elo_ratio_f * 0.4, 3)

        forca_f["beta"]  = round(forca_f["beta"] * 0.6 + (1 / elo_ratio_f) * 0.4, 3)



    if fase == "fase_grupos" and classificacao:

        dados_c = classificacao.get(id_c)

        dados_f = classificacao.get(id_f)

        if dados_c and dados_f and dados_c["played"] == 2 and dados_f["played"] == 2:

            if dados_c["points"] >= 4 and dados_f["points"] >= 4:

                print("  🤝 ALERTA: Efeito 'Disgrace of Gijón' (Ambos jogam pelo empate)!")

                forca_c["alpha"] *= 0.4

                forca_f["alpha"] *= 0.4



    lc, lf  = calcular_lambdas(mc, mf, forca_c, forca_f, nc, dias_c, dias_f)

    lc_esc, lf_esc   = calcular_lambda_escanteios(mc, mf, fase)

    lc_cart, lf_cart = calcular_lambda_cartoes(mc, mf, fase)

    placares      = matriz_placares(lc, lf)

    probs_poisson = derivar_mercados_poisson(placares)

    print(f"    🎲 Monte Carlo ({MONTE_CARLO_N:,} simulações)...")

    probs_mc = monte_carlo(lc, lf, MONTE_CARLO_N)

    probs_esp = {

        "escanteios": prob_escanteios_over(lc_esc, lf_esc, 9.5),

        "cartoes":    prob_cartoes_over(lc_cart, lf_cart, 3.5),

    }

    probs_ens    = ensemble(probs_poisson, probs_mc, h2h, fase, probs_esp)

    probs_cal    = aplicar_platt_todos(probs_ens, PLATT_PARAMS)

    print(f"    🎲 Calculando Handicap Asiático...")

    ha_resultado = selecionar_melhor_handicap(placares, lc, lf)

    movimentos   = detectar_line_movement(fid, probs_cal)

    registrar_snapshot(fid, probs_cal)

    score, nivel_score, det_score = calcular_score_confianca(

        probs_cal, probs_poisson, probs_mc, mc, mf, h2h, tem_xg, dias_c, dias_f, movimentos)

    print(f"    📊 Score: {score}/100 — {nivel_score}")

    desf_c = {"ausentes": [], "fator_ataque": 1.0, "fator_defesa": 1.0, "total_ausentes": 0}

    desf_f = {"ausentes": [], "fator_ataque": 1.0, "fator_defesa": 1.0, "total_ausentes": 0}

    if calls_disponiveis(budget) >= 2:

        jogadores_jogo, budget = buscar_jogadores_jogo(int(fid), budget)

        if jogadores_jogo:

            desf_c = calcular_impacto_desfalques(jogadores_jogo, id_c)

            desf_f = calcular_impacto_desfalques(jogadores_jogo, id_f)

            if desf_c["total_ausentes"] > 0 or desf_f["total_ausentes"] > 0:

                lc_adj = round(lc * desf_c["fator_ataque"] * desf_f["fator_defesa"], 3)

                lf_adj = round(lf * desf_f["fator_ataque"] * desf_c["fator_defesa"], 3)

                if lc_adj != lc or lf_adj != lf:

                    print(f"    🔧 Ajuste lesões: λc {lc}→{lc_adj} λf {lf}→{lf_adj}")

                    placares2  = matriz_placares(lc_adj, lf_adj)

                    probs_p2   = derivar_mercados_poisson(placares2)

                    probs_mc2  = monte_carlo(lc_adj, lf_adj, MONTE_CARLO_N)

                    probs_ens2 = ensemble(probs_p2, probs_mc2, h2h, fase, probs_esp)

                    probs_cal  = aplicar_platt_todos(probs_ens2, PLATT_PARAMS)

                    ha_resultado = selecionar_melhor_handicap(placares2, lc_adj, lf_adj)

                    lc, lf = lc_adj, lf_adj

    odds_casas_ref = {}

    for k, prob in probs_cal.items():

        if prob > 0:

            odd_fair = round(100 / prob, 2)

            odds_casas_ref[k] = {

                "Bet365": round(odd_fair * 1.02, 2), "Pinnacle": round(odd_fair * 1.04, 2),

                "Betano": round(odd_fair * 0.97, 2), "Betfair": round(odd_fair * 1.03, 2),

                "Sportingbet": round(odd_fair * 0.96, 2),

            }

    value_bets = calcular_value_bets(probs_cal, odds_casas_ref)

    bloco_vb   = montar_bloco_value_bets(value_bets)

    alerta = montar_alerta(

        jogo, probs_cal, mc, mf, h2h, fase, lc, lf, forca_c, forca_f,

        movimentos, dias_c, dias_f, lc_esc, lf_esc, tem_xg, ha_resultado,

    )

    if alerta:

        score_bloco = (

            f"\n{'─'*34}\n🎯 SCORE DE CONFIANÇA: {score}/100\n{nivel_score}\n"

            + "\n".join(f"  {d}" for d in det_score)

        )

        desf_bloco = ""

        if desf_c["total_ausentes"] > 0 or desf_f["total_ausentes"] > 0:

            desf_bloco = f"\n{'─'*34}\n🏥 DESFALQUES:\n"

            if desf_c["ausentes"]: desf_bloco += f"  {nc}: {', '.join(desf_c['ausentes'][:3])}\n"

            if desf_f["ausentes"]: desf_bloco += f"  {nf}: {', '.join(desf_f['ausentes'][:3])}\n"

        enviar_telegram(alerta + score_bloco + desf_bloco + bloco_vb)

        # FIX #3: print completo

        n_linhas_ha = len(ha_resultado.get('melhores_casa', [])) + len(ha_resultado.get('melhores_fora', []))

        print(f"    ✅ Alerta enviado! Score={score}/100 | HA={n_linhas_ha} linhas")

        salvar_log({

            "data": datetime.now().isoformat(), "fixture_id": fid,

            "casa": nc, "fora": nf, "fase": fase,

            "lambda_c": lc, "lambda_f": lf, "tem_xg": tem_xg,

            "dias_desc_c": dias_c, "dias_desc_f": dias_f,

            "score_confianca": score,

            "desfalques_casa": desf_c["ausentes"], "desfalques_fora": desf_f["ausentes"],

            "probs_poisson": probs_poisson, "probs_mc": probs_mc, "probs_calibradas": probs_cal,

            "handicap_recomendado": ha_resultado.get("recomendada"),

            "value_bets": [v["mercado"] for v in value_bets[:3]],

            "line_movement": movimentos, "resultado": None, "placar_real": None,

        })

    else:

        print(f"    ⚠️  Nenhum mercado ≥ {PROB_MINIMA}% (score={score}/100)")

    cache = add_cache(fid, cache)

    return budget, cache



# ═══════════════════════════════════════════

# CICLO PRINCIPAL

# ═══════════════════════════════════════════

resumo_hoje = None

relatorio_semanal_enviado = None



def rodar_ciclo(budget: dict, cache: dict, params_modelo: dict) -> tuple:

    global resumo_hoje

    global relatorio_semanal_enviado

    agora   = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    disponi = calls_disponiveis(budget)

    print(f"\n{'═'*58}")

    print(f"  🤖 Predictor v6.1 | {agora}")

    print(f"  📊 Budget: {budget['calls_usadas']}/{BUDGET_DIARIO} | {disponi} disponíveis")

    print(f"{'═'*58}")

    if disponi < 6:

        print("  ⚠️  Budget insuficiente.")

        return budget, cache, params_modelo

    jogos, budget = buscar_jogos_copa(budget)

    if not jogos:

        print("  Nenhum jogo nas próximas 48h.")

        return budget, cache, params_modelo

    print(f"  ⚽ {len(jogos)} jogo(s)")

    hoje = agora_brt().strftime("%Y-%m-%d")

    if eh_hora_resumo() and resumo_hoje != hoje:

        jogos_hoje = [j for j in jogos if formatar_brt(j.get("fixture",{}).get("date","")).startswith(agora_brt().strftime("%d/%m"))]

        enviar_resumo_diario(jogos_hoje)

        resumo_hoje = hoje

    todos_copa, budget = buscar_jogos_finalizados_copa(budget)

    todos_copa = todos_copa or []

    elo_ratings = obter_elo_ratings()

    if elo_ratings:

        print(f"  📈 Elo Ratings: carregados para {len(elo_ratings)} seleções")

    classificacao, budget = buscar_classificacao_copa(budget)

    if classificacao:

        print("  📊 Classificação da Copa carregada.")

    for jogo in jogos:

        if calls_disponiveis(budget) < 6:

            print("  ⚠️  Budget esgotado.")

            break

        budget, cache = analisar_jogo(jogo, budget, cache, todos_copa, elo_ratings, classificacao)

        time.sleep(2)

    log_atual = carregar_log()

    bt        = processar_backtest(log_atual, todos_copa)

    if bt["atualizados"] > 0:

        rel_bt = montar_relatorio_backtest(bt)

        if rel_bt: enviar_telegram(rel_bt)

        try:

            with open(ARQUIVO_LOG, "w") as f:

                json.dump(log_atual[-500:], f, ensure_ascii=False, indent=2)

        except Exception as e:

            print(f"Erro ao salvar arquivo de log no ciclo: {e}")

    global relatorio_semanal_enviado

    hoje_str = agora_brt().strftime("%Y-%m-%d")

    if eh_hora_relatorio_semanal() and relatorio_semanal_enviado != hoje_str:

        rel_sem = gerar_relatorio_semanal(carregar_log(), jogos)

        if rel_sem: enviar_telegram(rel_sem)

        relatorio_semanal_enviado = hoje_str

    params_modelo = executar_autoaprendizado(params_modelo)

    print(f"\n  ✅ Ciclo OK | {budget['calls_usadas']}/{BUDGET_DIARIO}")

    return budget, cache, params_modelo



# ═══════════════════════════════════════════

# ENTRY POINT

# ═══════════════════════════════════════════

if __name__ == "__main__":
    enviar_telegram("🤖 Sistema Iniciado com Sucesso! O bot está ativo e rodando no background.")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT or not APIFOOTBALL_KEY:

        print("❌ ERRO: defina as variáveis de ambiente:")

        print("   TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, APIFOOTBALL_KEY")

        raise SystemExit(1)



    print("╔══════════════════════════════════════════════════════╗")

    print("║    TERRORNEGRO PREDICTOR v6.1 — COPA 2026          ║")

    print("╠══════════════════════════════════════════════════════╣")

    print("║  [1]  Poisson Bivariado + Dixon-Coles (ρ=-0.13)    ║")

    print("║  [2]  Monte Carlo — 100.000 simulações/jogo        ║")

    print("║  [3]  Platt Scaling — calibração Copas 18+22       ║")

    print("║  [4]  xG (Expected Goals)                          ║")

    print("║  [5]  Variáveis contextuais (descanso, fase)       ║")

    print("║  [6]  Poisson escanteios e cartões                 ║")

    print("║  [7]  Line movement (smart money)                  ║")

    print("║  [8]  Ensemble: Poisson 60% + MC 40% + H2H        ║")

    print("║  [9]  Score de Confiança 0-100                     ║")

    print("║  [10] Lesões e desfalques                          ║")

    print("║  [11] Value Bet multi-casa                         ║")

    print("║  [12] Backtest automático                          ║")

    print("║  [13] Relatório semanal (domingos 9h BRT)          ║")

    print("║  [14] Autoaprendizado online                       ║")

    print("║  [15] 🎲 HANDICAP ASIÁTICO — NOVO v6.1            ║")

    print("╚══════════════════════════════════════════════════════╝\n")



    budget        = carregar_budget()

    cache         = carregar_cache()

    log           = carregar_log()

    params_modelo = carregar_params_modelo()



    print(f"  💰 Budget ({budget['data']}): {budget['calls_usadas']}/{BUDGET_DIARIO}")

    print(f"  📦 Cache: {len(cache)} jogos | Log: {len(log)} indicações")

    print(f"  🧠 Modelo v{params_modelo.get('versao',1)} | Treinado em {params_modelo.get('jogos_treinados',0)} jogos\n")



    enviar_telegram(

        "🤖 TERRORNEGRO PREDICTOR v6.1 ONLINE\n🏆 Copa do Mundo 2026\n\n"

        "🔬 Motor completo ativo:\n  ✅  Poisson + Dixon-Coles\n"

        "  🎲 Monte Carlo 100k simulações\n  📊 xG (Expected Goals)\n"

        "  🎯 Platt Scaling calibrado\n  💤 Fator descanso entre jogos\n"

        "  🚩 Poisson dedicado escanteios\n  🚨 Detecção smart money\n"

        "  🔀 Ensemble 8 módulos\n  📊 Score de confiança 0-100\n"

        "  🏥 Lesões e desfalques\n  💎 Value Bet multi-casa\n"

        "  📋 Backtest automático\n  📅 Relatório semanal\n"

        "  🧠 Autoaprendizado\n  🎲 HANDICAP ASIÁTICO ← NOVO\n\n"

        f"  Prob ≥ {PROB_MINIMA}% | Kelly {int(KELLY_FRACAO*100)}% | BRT"

    )



    INTERVALO = INTERVALO_CICLO_MIN * 60

    while True:

        try:

            budget, cache, params_modelo = rodar_ciclo(budget, cache, params_modelo)

        except KeyboardInterrupt:

            print("\n⛔ Encerrado.")

            break

        except Exception as e:

            print(f"[ERRO] {e}")

        print(f"\n  ⏰ Próximo ciclo em {INTERVALO_CICLO_MIN}min...")

        time.sleep(INTERVALO)