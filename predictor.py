

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

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

# ║ BALERION PREDICTOR v7.0 — LIGAS (BR, EUROPA, CONMEBOL)     ║

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

# ║ • Histórico: últimos jogos do time em todas as competições ║

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

BUDGET_DIARIO        = int(os.getenv("BUDGET_DIARIO", "90"))  # plano grátis = 100/dia

BUDGET_EMERGENCIA    = 5

INTERVALO_CICLO_MIN  = 30

FUSO_BRT             = -3

RHO_DIXON_COLES      = -0.13

# FIX: estado em diretório configurável. No Railway, monte um volume persistente
# e defina DATA_DIR=/data — senão o filesystem efêmero apaga tudo a cada deploy.
DATA_DIR             = os.getenv("DATA_DIR", ".")

ARQUIVO_BUDGET       = os.path.join(DATA_DIR, "budget_predictor.json")

ARQUIVO_CACHE        = os.path.join(DATA_DIR, "predictor_cache.json")

ARQUIVO_LOG          = os.path.join(DATA_DIR, "predictor_log.json")

ARQUIVO_ODDS_SNAP    = os.path.join(DATA_DIR, "odds_snapshot.json")

ARQUIVO_RELATORIO    = os.path.join(DATA_DIR, "relatorio_semanal.json")

ARQUIVO_PARAMS       = os.path.join(DATA_DIR, "modelo_params.json")

ARQUIVO_FIXTURES     = os.path.join(DATA_DIR, "fixtures_cache.json")

JOGOS_PARA_RETREINAR = 5

# Casas usadas nas value bets (só odds REAIS dessas casas entram no cálculo).
# Configure no Railway com CASAS="Bet365,Betano,Pinnacle" etc.
CASAS_VALUE  = [c.strip() for c in os.getenv(
    "CASAS", "Bet365,Betano,Pinnacle,Betfair,Sportingbet").split(",") if c.strip()]

# ─────────────────────────────────────────
# LIGAS MONITORADAS (id da API-Football → nome)
# A ordem define a prioridade quando o orçamento de chamadas é curto.
# ─────────────────────────────────────────
LIGAS = {
    71:  "Brasileirão Série A",
    13:  "Libertadores",
    11:  "Sul-Americana",
    2:   "Champions League",
    39:  "Premier League",
    140: "La Liga",
    135: "Serie A (Itália)",
    78:  "Bundesliga",
}

# Analisa jogos que começam dentro desta janela
HORAS_ANTECEDENCIA = 24

# Chamadas por jogo analisado: histórico casa, histórico fora, H2H, odds, desfalques
CALLS_POR_JOGO = 5



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



def _carregar_estado_envios() -> dict:
    # guarda em disco o que já foi enviado hoje (sobrevive a reinícios)
    try:
        if os.path.exists(ARQUIVO_RELATORIO):
            with open(ARQUIVO_RELATORIO, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _salvar_estado_envios(estado: dict) -> None:
    try:
        _salvar_json(ARQUIVO_RELATORIO, estado)
    except Exception as e:
        print(f"Erro ao salvar estado de envios: {e}")


def eh_hora_resumo() -> bool:

    b = agora_brt()

    return 8 <= b.hour < 14



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

# ═══════════════════════════════════════════
# PERSISTÊNCIA — escrita atômica + UTF-8
# (grava em arquivo temporário e troca com os.replace: se o processo morrer
#  no meio da escrita, o arquivo original não é corrompido)
# ═══════════════════════════════════════════
def _salvar_json(path: str, dados, indent=None) -> None:
    import tempfile
    pasta = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=pasta, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def hoje_utc() -> str:
    # A API-Football zera o limite diário à meia-noite UTC
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def carregar_budget() -> dict:

    hoje = hoje_utc()

    try:

        if os.path.exists(ARQUIVO_BUDGET):

            with open(ARQUIVO_BUDGET, encoding="utf-8") as f:

                d = json.load(f)

            if d.get("data") == hoje:

                return d

    except Exception as e:

        print(f"Erro em carregar_budget: {e}")

    return {"data": hoje, "calls_usadas": 0}



def salvar_budget(b: dict) -> None:

    try:

        _salvar_json(ARQUIVO_BUDGET, b)

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

            with open(ARQUIVO_CACHE, encoding="utf-8") as f:

                raw = json.load(f)

            agora = datetime.now(timezone.utc)

            return {k: v for k, v in raw.items()

                    if (agora - datetime.fromisoformat(v)).total_seconds() < 86400}

    except Exception as e:

        print(f"Erro em carregar_cache: {e}")

    return {}



def salvar_cache(c: dict) -> None:

    try:

        _salvar_json(ARQUIVO_CACHE, c)

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

            with open(ARQUIVO_LOG, encoding="utf-8") as f:

                return json.load(f)

    except Exception as e:

        print(f"Erro em carregar_log: {e}")

    return []



def salvar_log(entrada: dict) -> None:

    try:

        log = carregar_log()

        log.append(entrada)

        _salvar_json(ARQUIVO_LOG, log[-500:], indent=2)

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

            print(f"[TELEGRAM] falha ao enviar: {type(e).__name__}")



# ═══════════════════════════════════════════

# API-FOOTBALL

# ═══════════════════════════════════════════

BASE_URL = "https://v3.football.api-sports.io"

# Plano grátis da API-Football limita requisições por minuto: espaçamos as chamadas.
INTERVALO_MIN_CHAMADAS = float(os.getenv("API_INTERVALO_SEG", "6.5"))

_ultima_chamada = [0.0]

_aviso_erro_api = {"dia": None}


def _registrar_erro_api(endpoint: str, params: dict, erros) -> None:
    texto = json.dumps(erros, ensure_ascii=False)[:300]
    print(f"  [API] {endpoint} {params} → ERRO: {texto}")
    hoje = agora_brt().strftime("%Y-%m-%d")
    graves = ("plan", "season", "access", "token", "key", "suspend", "limit")
    if _aviso_erro_api["dia"] != hoje and any(p in texto.lower() for p in graves):
        _aviso_erro_api["dia"] = hoje
        enviar_telegram(
            "⚠️ BALERION — a API-Football recusou uma requisição\n"
            f"{endpoint}: {texto}\n\n"
            "Se for restrição do plano grátis (temporada não liberada ou "
            "limite diário), o bot fica sem dados até isso ser resolvido.")


def api_get(endpoint: str, params: dict, budget: dict):
    if calls_disponiveis(budget) <= BUDGET_EMERGENCIA:
        return [], budget
    espera = INTERVALO_MIN_CHAMADAS - (time.time() - _ultima_chamada[0])
    if espera > 0:
        time.sleep(espera)
    _ultima_chamada[0] = time.time()
    try:
        r = requests.get(
            f"{BASE_URL}/{endpoint}",
            headers={"x-apisports-key": APIFOOTBALL_KEY},
            params=params, timeout=15,
        )
        budget = registrar_call(budget)
        # Sincroniza o contador local com o contador real da API
        lim = r.headers.get("x-ratelimit-requests-limit", "")
        rem = r.headers.get("x-ratelimit-requests-remaining", "")
        if lim.isdigit() and rem.isdigit():
            usadas_api = int(lim) - int(rem)
            if usadas_api > budget["calls_usadas"]:
                budget["calls_usadas"] = usadas_api
                salvar_budget(budget)
            if int(rem) < 15:
                print(f"  ⚠️ API: só {rem} requisições restantes hoje!")
        if r.status_code != 200:
            print(f"  [API] {endpoint}: HTTP {r.status_code}")
            return [], budget
        corpo = r.json()
        # A API responde 200 mesmo com erro: o motivo vem no campo "errors"
        erros = corpo.get("errors")
        if erros:
            _registrar_erro_api(endpoint, params, erros)
            return [], budget
        return corpo.get("response", []) or [], budget
    except Exception as e:
        print(f"  [API] {endpoint}: {type(e).__name__}")
        return [], budget


# ── Jogos por data: UMA chamada traz todas as ligas do dia ──

def _carregar_fixtures_cache() -> dict:
    try:
        if os.path.exists(ARQUIVO_FIXTURES):
            with open(ARQUIVO_FIXTURES, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Erro em _carregar_fixtures_cache: {e}")
    return {}


def buscar_jogos_da_data(data_str: str, ttl_horas: float, budget: dict,
                         dia_fechado: bool = False):
    """Jogos das LIGAS numa data (UTC), com cache em disco.

    dia_fechado=True: data já passou; o cache só vale se foi feito depois
    do fim do dia (senão os resultados finais ainda não estavam lá).
    """
    cache = _carregar_fixtures_cache()
    item  = cache.get(data_str)
    agora = time.time()
    if item:
        idade = agora - item.get("ts", 0)
        if dia_fechado:
            fim_dia = datetime.fromisoformat(data_str).replace(
                tzinfo=timezone.utc).timestamp() + 86400 + 3 * 3600
            if item.get("ts", 0) >= fim_dia and (item.get("jogos") or idade < 6 * 3600):
                return item.get("jogos", []), budget
        elif idade < ttl_horas * 3600:
            return item.get("jogos", []), budget
    dados, budget = api_get("fixtures", {"date": data_str}, budget)
    jogos = [j for j in dados if j.get("league", {}).get("id") in LIGAS]
    ts = agora
    if not dados:
        # a lista de um dia inteiro nunca vem vazia: é falha da API.
        # Mantém o que já tinha e marca para tentar de novo em ~30 min.
        jogos = item.get("jogos", []) if item else []
        ts = agora - max(0.0, (ttl_horas or 6) * 3600 - 1800)
    cache[data_str] = {"ts": ts, "jogos": jogos}
    for k in sorted(cache)[:-5]:
        cache.pop(k, None)
    try:
        _salvar_json(ARQUIVO_FIXTURES, cache)
    except Exception as e:
        print(f"Erro ao salvar cache de jogos: {e}")
    return jogos, budget


def _data_utc(jogo: dict):
    try:
        return datetime.fromisoformat(
            jogo.get("fixture", {}).get("date", "").replace("Z", "+00:00"))
    except Exception:
        return None


def buscar_jogos_proximos(budget: dict):
    """Jogos ainda não iniciados nas próximas HORAS_ANTECEDENCIA horas."""
    agora  = datetime.now(timezone.utc)
    hoje   = agora.date()
    j1, budget = buscar_jogos_da_data(hoje.isoformat(), 4, budget)
    j2, budget = buscar_jogos_da_data((hoje + timedelta(days=1)).isoformat(), 8, budget)
    limite = agora + timedelta(hours=HORAS_ANTECEDENCIA)
    prioridade = {lid: i for i, lid in enumerate(LIGAS)}
    proximos = []
    for j in j1 + j2:
        if j.get("fixture", {}).get("status", {}).get("short") != "NS":
            continue
        dt = _data_utc(j)
        if dt and agora < dt <= limite:
            proximos.append((dt, prioridade.get(j["league"]["id"], 99), j))
    proximos.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in proximos], budget


def buscar_jogos_finalizados(budget: dict):
    """Resultados de ontem e hoje (para o backtest e para a força dos times)."""
    hoje  = datetime.now(timezone.utc).date()
    j_ont, budget = buscar_jogos_da_data(
        (hoje - timedelta(days=1)).isoformat(), 0, budget, dia_fechado=True)
    j_hoj, budget = buscar_jogos_da_data(hoje.isoformat(), 4, budget)
    fim = ("FT", "AET", "PEN")
    return [j for j in j_ont + j_hoj
            if j.get("fixture", {}).get("status", {}).get("short") in fim], budget


def buscar_ultimos_jogos(team_id: int, qtd: int, budget: dict):
    # Todas as competições: um time na Champions também tem jogos na liga nacional
    dados, budget = api_get("fixtures", {"team": team_id, "last": qtd}, budget)
    return dados or [], budget


def buscar_h2h(id1: int, id2: int, qtd: int, budget: dict):
    dados, budget = api_get("fixtures/headtohead", {
        "h2h": f"{id1}-{id2}", "last": qtd,
    }, budget)
    return dados or [], budget


def buscar_historico_completo(team_id: int, nome: str, budget: dict):
    jogos, budget = buscar_ultimos_jogos(team_id, JOGOS_HISTORICO, budget)
    jogos = [j for j in jogos
             if j.get("goals", {}).get("home") is not None
             and j.get("goals", {}).get("away") is not None]
    print(f"    📋 {nome}: {len(jogos)} jogos | "
          f"peso recência ativo (λ={LAMBDA_DECAY}/dia)")
    return jogos, budget


# ── Odds REAIS das casas (endpoint /odds) ──

def _mapear_mercado(nome_aposta: str, valor: str):
    if nome_aposta == "Match Winner":
        return {"Home": "vitoria_casa", "Draw": "empate", "Away": "vitoria_fora"}.get(valor)
    if nome_aposta == "Goals Over/Under":
        return {"Over 2.5": "over25", "Under 2.5": "under25", "Over 1.5": "over15"}.get(valor)
    if nome_aposta == "Both Teams Score":
        return "btts" if valor == "Yes" else None
    return None


def buscar_odds_reais(fixture_id: int, budget: dict):
    """Retorna {mercado: {casa: odd}} só com as casas de CASAS_VALUE."""
    dados, budget = api_get("odds", {"fixture": fixture_id}, budget)
    preferidas = {c.lower(): c for c in CASAS_VALUE}
    odds = {}
    for bloco in dados or []:
        for bm in bloco.get("bookmakers", []):
            casa = preferidas.get(str(bm.get("name", "")).lower())
            if not casa:
                continue
            for aposta in bm.get("bets", []):
                for v in aposta.get("values", []):
                    chave = _mapear_mercado(aposta.get("name", ""), str(v.get("value", "")))
                    if not chave:
                        continue
                    try:
                        odd = float(v.get("odd"))
                    except (TypeError, ValueError):
                        continue
                    if odd > 1.0:
                        odds.setdefault(chave, {})[casa] = odd
    return odds, budget


def buscar_desfalques(fixture_id: int, budget: dict):
    # /injuries tem dados ANTES do jogo; /fixtures/players só depois que acaba
    dados, budget = api_get("injuries", {"fixture": fixture_id}, budget)
    return dados or [], budget


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



def _odd_minima_ha(prob_win: float, prob_push: float) -> float:
    """Odd a partir da qual a aposta tem valor (push devolve a aposta)."""
    perda = max(0.0, 100 - prob_win - prob_push)
    return round((prob_win + perda) / prob_win, 2) if prob_win > 0 else 99.0


def selecionar_melhor_handicap(placares: list, lc: float, lf: float) -> dict:
    """Linhas com probabilidade entre PROB_MINIMA e 80% (odds que valem a pena).

    Casa com linha L ganha se (gols casa - gols fora + L) > 0.
    Fora com linha L ganha se (gols fora - gols casa + L) > 0, que é o lado
    "fora" da linha -L do ponto de vista da casa.
    """
    candidatos = []
    for linha in LINHAS_HANDICAP:
        hc = calcular_handicap_asiatico(placares, linha)
        hf = calcular_handicap_asiatico(placares, -linha)
        for tipo, prob, push, nome in (("casa", hc["prob_casa"], hc["prob_push"], "Casa"),
                                       ("fora", hf["prob_fora"], hf["prob_push"], "Fora")):
            if PROB_MINIMA <= prob <= 80:
                candidatos.append({
                    "tipo": tipo, "linha": linha,
                    "label": f"AH {nome} {linha:+.2f}".replace("+0.00", "0"),
                    "prob": prob, "prob_push": push,
                    "odd_fair": _odd_minima_ha(prob, push),
                })
    # mais perto de ~65%: odd razoável (~1.5) com boa chance
    candidatos.sort(key=lambda x: abs(x["prob"] - 65))
    casa = [c for c in candidatos if c["tipo"] == "casa"]
    fora = [c for c in candidatos if c["tipo"] == "fora"]
    return {
        "melhores_casa": casa[:3],
        "melhores_fora": fora[:3],
        "recomendada":   candidatos[0] if candidatos else None,
        "favorito":      "casa" if lc > lf else "fora",
    }


def montar_bloco_handicap(ha_resultado: dict, nc: str, nf: str, stake_base: float = 50.0) -> str:

    if not ha_resultado or not ha_resultado.get("recomendada"):

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

            f"   Odd mínima p/ valer a pena: acima de {rec['odd_fair']}{push_txt}",

            "",

        ]

    if ha_resultado["melhores_casa"]:

        linhas.append(f"🏠 {nc} (Handicap Casa):")

        for h in ha_resultado["melhores_casa"][:3]:

            push_txt = (f" [Push:{h['prob_push']:.0f}%]" if h["prob_push"] > 2 else "")

            linhas.append(f"   {h['linha']:+.2f} → {h['prob']}%  (odd mín. {h['odd_fair']}){push_txt}")

        linhas.append("")

    if ha_resultado["melhores_fora"]:

        linhas.append(f"✈️  {nf} (Handicap Fora):")

        for h in ha_resultado["melhores_fora"][:3]:

            push_txt = (f" [Push:{h['prob_push']:.0f}%]" if h["prob_push"] > 2 else "")

            linhas.append(f"   {h['linha']:+.2f} → {h['prob']}%  (odd mín. {h['odd_fair']}){push_txt}")

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



# Médias de referência de gols por jogo (ligas de primeira divisão)
MEDIA_GOLS_CASA_PADRAO = 1.50
MEDIA_GOLS_FORA_PADRAO = 1.20
# Quantos "jogos fictícios na média" puxam a força estimada para 1.0.
# Com só 10 jogos por time, sem isso o modelo exagera (testado em 3.900 jogos reais).
ENCOLHIMENTO_JOGOS     = 16.0


def medias_de_gols(finalizados: list) -> tuple:
    """Média de gols do mandante e do visitante, puxada para o padrão."""
    gc = gf = n = 0
    for j in finalizados:
        g = j.get("goals", {})
        if g.get("home") is None or g.get("away") is None:
            continue
        gc += int(g["home"]); gf += int(g["away"]); n += 1
    peso = 30.0
    mh = (gc + peso * MEDIA_GOLS_CASA_PADRAO) / (n + peso)
    ma = (gf + peso * MEDIA_GOLS_FORA_PADRAO) / (n + peso)
    return round(mh, 3), round(ma, 3)


def calcular_forca_time(jogos: list, team_id: int, media_geral: float) -> dict:
    """alpha = força de ataque, beta = fragilidade defensiva (1.0 = time médio)."""
    marc = sofr = peso = 0.0
    n = 0
    for j in jogos:
        teams, goals = j.get("teams", {}), j.get("goals", {})
        if goals.get("home") is None or goals.get("away") is None:
            continue
        eh_casa = teams.get("home", {}).get("id") == team_id
        gp = int(goals["home"] if eh_casa else goals["away"])
        gs = int(goals["away"] if eh_casa else goals["home"])
        w = peso_temporal(j.get("fixture", {}).get("date", ""))
        marc += gp * w; sofr += gs * w; peso += w; n += 1
    if n == 0 or peso == 0 or media_geral <= 0:
        return {"alpha": 1.0, "beta": 1.0, "jogos": 0}
    k = ENCOLHIMENTO_JOGOS
    a_bruto = (marc / peso) / media_geral
    b_bruto = (sofr / peso) / media_geral
    return {"alpha": round((n * a_bruto + k) / (n + k), 3),
            "beta":  round((n * b_bruto + k) / (n + k), 3),
            "jogos": n}



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

            with open(ARQUIVO_ODDS_SNAP, encoding="utf-8") as f:

                return json.load(f)

    except Exception as e:

        print(f"[PERSIST] falha ao carregar snapshots: {e}")

    return {}



def salvar_snapshots(snaps: dict) -> None:

    try:

        _salvar_json(ARQUIVO_ODDS_SNAP, snaps)

    except Exception as e:

        print(f"[PERSIST] falha ao salvar snapshots: {e}")



def registrar_snapshot(fixture_id: str, probs: dict) -> None:

    snaps = carregar_snapshots()

    snaps[fixture_id] = {"timestamp": datetime.now(timezone.utc).isoformat(), "probs": probs}

    if len(snaps) > 400:

        for k in sorted(snaps, key=lambda k: snaps[k].get("timestamp", ""))[:-400]:

            snaps.pop(k, None)

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

# Ajuste fino do mando de campo (1.0 = só a média real da liga).
# O autoaprendizado mexe neste valor entre 0.85 e 1.15.
GAMMA_CASA = 1.0


def calcular_lambdas(forca_c: dict, forca_f: dict, media_casa: float, media_fora: float,
                     dias_desc_c: float, dias_desc_f: float) -> tuple:
    """Gols esperados: ataque de um x defesa do outro x média da liga (Maher)."""
    lc = forca_c["alpha"] * forca_f["beta"] * media_casa * GAMMA_CASA * fator_descanso(dias_desc_c)
    lf = forca_f["alpha"] * forca_c["beta"] * media_fora / GAMMA_CASA * fator_descanso(dias_desc_f)
    return (round(max(0.2, min(4.0, lc)), 3), round(max(0.2, min(4.0, lf)), 3))


def ensemble(probs_poisson: dict, probs_mc: dict, h2h: dict, fase: str) -> dict:
    ph2h = PESO_H2H_FASE.get(fase, 0.07) if h2h.get("h2h_jogos", 0) >= 3 else 0.0
    pp   = (1 - ph2h) * 0.60
    pm   = (1 - ph2h) * 0.40

    def blend(k, h2h_val):
        return probs_poisson.get(k, 50) * pp + probs_mc.get(k, 50) * pm + h2h_val * ph2h

    h2h_casa = h2h.get("h2h_aprov_casa", 33)
    vc = blend("vitoria_casa", h2h_casa)
    em = blend("empate", 27.0)
    vf = blend("vitoria_fora", max(0.0, 100 - h2h_casa - 27))
    soma = vc + em + vf or 1.0
    over25 = blend("over25", h2h.get("h2h_over25", 50))
    return {
        # 1X2 sempre soma 100%; Over/Under 2.5 sempre somam 100%
        "vitoria_casa": round(vc / soma * 100, 2),
        "empate":       round(em / soma * 100, 2),
        "vitoria_fora": round(vf / soma * 100, 2),
        "btts":         round(blend("btts", h2h.get("h2h_btts", 50)), 2),
        "over25":       round(over25, 2),
        "under25":      round(100 - over25, 2),
        "over15":       round(probs_poisson.get("over15", 50), 2),
    }


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

    nome_liga = LIGAS.get(league.get("id"), league.get("name", ""))

    nc     = teams.get("home", {}).get("name", "?")

    nf     = teams.get("away", {}).get("name", "?")

    hora   = formatar_brt(fix.get("date", ""))

    rodada = league.get("round", fase)

    mercados_ok = [

        {"k": k, "prob": v, "label": LABELS.get(k, k)}

        for k, v in probs_cal.items() if v >= PROB_MINIMA

    ]

    mercados_ok.sort(key=lambda x: -x["prob"])

    if not mercados_ok and not (ha_resultado or {}).get("recomendada"):

        return ""

    xg_tag  = "✅ xG" if tem_xg else "⚠️  gols brutos"

    SEP      = "━" * 34

    SEP_SLIM = "─" * 34

    linhas = [

        "╔══════════════════════════════════╗",

        f"║ 🏆 {nome_liga[:29]:<29}║",

        f"║ ⚽ {nc[:14]:<14} vs {nf[:9]:<9}║",

        f"║ 📋 {rodada[:32]:<32}║",

        f"║ 🕐 {hora:<29}║",

        "╚══════════════════════════════════╝",

        "",

    ]

    if movimentos:

        linhas += ["🔄 MUDANÇA NAS PROBABILIDADES DO MODELO", SEP_SLIM]

        for merc, mv in movimentos.items():

            linhas.append(f"  {LABELS.get(merc,merc)}: {mv['antes']}% → {mv['agora']}% {mv['direcao']} ({abs(mv['delta'])}%)")

        linhas += ["", SEP, ""]

    if mercados_ok:

        linhas += [SEP, "🎯 MERCADOS MAIS PROVÁVEIS (modelo)", SEP,
                   "Só vale apostar se a odd da casa for MAIOR que a odd mínima."]

        for idx, m in enumerate(mercados_ok, 1):

            odd_min = round(100 / m["prob"], 2)

            linhas += [
                "", f"#{idx} {m['label']}",
                f"{barra(m['prob'])} {m['prob']}%",
                f"Confiança: {nivel(m['prob'])}",
                f"💰 Odd mínima: acima de {odd_min}",

            ]

    if ha_resultado:

        linhas.append(montar_bloco_handicap(ha_resultado, nc, nf))

    linhas += [

        "", SEP, "🔬 MOTOR DO MODELO", SEP,

        f"   Poisson + Dixon-Coles + Monte Carlo",

        f"   Dados: {xg_tag}",

        f"   Gols esperados: {nc} {lc} x {lf} {nf}",

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
        f_atk= fc.get("alpha", 1.0)
        f_def= fc.get("beta", 1.0)
        linhas.append(f"  {nome}: {n_j}J | xG+: {xg_m} | xG-: {xg_s}")
        linhas.append(f"    Ataque: {f_atk} | Defesa (vaza): {f_def}  (1.0 = time médio)")
    
    return "\n".join(linhas)

# RESUMO DIÁRIO

# ═══════════════════════════════════════════

def taxa_por_mercado(log: list, prob_minima: float = None) -> tuple:
    """(acertos, total) contando cada mercado indicado separadamente."""
    lim = PROB_MINIMA if prob_minima is None else prob_minima
    acertos = total = 0
    for e in log:
        res = inferir_resultado_real(e)
        if not res:
            continue
        for m, prob in e.get("probs_calibradas", {}).items():
            if prob >= lim and m in res:
                total += 1
                acertos += res[m]
    return acertos, total


def enviar_resumo_diario(jogos: list) -> None:

    if not jogos: return

    data     = agora_brt().strftime("%d/%m/%Y")

    log      = carregar_log()

    acertos, total_log = taxa_por_mercado(log)

    SEP      = "━" * 34

    linhas   = [f"☀️ BOM DIA! BALERION — {data}", f"⚽ {len(jogos)} jogo(s) programado(s) hoje", SEP]

    for j in jogos:

        nc   = j.get("teams",{}).get("home",{}).get("name","?")

        nf   = j.get("teams",{}).get("away",{}).get("name","?")

        hora = formatar_brt(j.get("fixture",{}).get("date",""))

        rod  = j.get("league",{}).get("round","")

        linhas += [f"⚽ {nc} vs {nf}", f"   {hora} | {rod}", ""]

    if total_log > 0:

        taxa = round(acertos / total_log * 100, 1)

        linhas += [SEP, "📊 DESEMPENHO ACUMULADO", SEP,

                   f"Taxa de acerto : {taxa}%", f"Indicações     : {acertos}/{total_log} certas (por mercado)"]

    linhas += ["", SEP, "🔬 Motor: Poisson+MC+Dixon-Coles+Platt+HA v7.0", "Análises serão enviadas antes de cada jogo."]

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

def calcular_impacto_desfalques(lesoes: list, id_time: int) -> dict:
    """Usa a resposta do endpoint /injuries.

    fator_ataque multiplica os gols DO time; fator_defesa multiplica os gols
    do ADVERSÁRIO (defesa desfalcada → adversário marca mais, por isso > 1).
    """
    ausentes = []
    penalidade = 0.0
    for item in lesoes:
        if item.get("team", {}).get("id") != id_time:
            continue
        p      = item.get("player", {})
        tipo   = str(p.get("type", "")).lower()
        motivo = p.get("reason") or ""
        nome   = p.get("name", "Jogador")
        peso   = 0.5 if ("question" in tipo or "doubt" in tipo) else 1.0
        ausentes.append(f"{nome} ({motivo})" if motivo else nome)
        penalidade += 0.03 * peso
    return {
        "ausentes":       ausentes,
        "fator_ataque":   round(max(0.80, 1.0 - penalidade), 3),
        "fator_defesa":   round(min(1.20, 1.0 + penalidade * 0.7), 3),
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
        }
        # escanteios/cartões ficam de fora: não temos o resultado real deles
        odds_reais = entrada.get("odds_reais", {}) or {}

        acertou_algum = False

        for mercado, prob in probs.items():

            if prob < PROB_MINIMA: continue

            ocorreu  = reais.get(mercado)
            if ocorreu is None: continue
            odd_real = odds_reais.get(mercado)
            stake    = 10.0
            # ROI só existe com a odd REAL registrada no alerta
            lucro    = (round(stake * odd_real - stake, 2) if ocorreu else -stake) if odd_real else 0.0

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

    return brt.weekday() == 6 and 9 <= brt.hour < 14



def gerar_relatorio_semanal(log: list, jogos_proximos: list) -> str:

    semana_atras    = datetime.now().timestamp() - 7 * 86400

    entradas_semana = [e for e in log if datetime.fromisoformat(e.get("data","2020-01-01")).timestamp() > semana_atras]

    com_resultado   = [e for e in entradas_semana if e.get("resultado")]

    total  = len(com_resultado)

    acert  = sum(1 for e in com_resultado if e.get("resultado") == "acerto")

    taxa   = round(acert / total * 100, 1) if total else 0

    roi_semana = {}; acc_semana = {}; tot_semana = {}

    for e in com_resultado:

        try:
            gc, gf = (int(x) for x in str(e.get("placar_real", "")).split("-"))
        except ValueError:
            continue

        reais = {
            "vitoria_casa": gc > gf, "empate": gc == gf, "vitoria_fora": gc < gf,
            "btts": gc > 0 and gf > 0, "over25": gc + gf > 2,
            "under25": gc + gf <= 2, "over15": gc + gf > 1,
        }

        odds_reais = e.get("odds_reais", {}) or {}

        for merc, prob in e.get("probs_calibradas", {}).items():

            if prob < PROB_MINIMA or merc not in reais: continue

            ocorreu  = reais[merc]

            odd_real = odds_reais.get(merc)

            lucro    = ((round(10 * odd_real - 10, 2) if ocorreu else -10.0)
                        if odd_real else 0.0)

            roi_semana[merc] = round(roi_semana.get(merc, 0) + lucro, 2)

            acc_semana[merc] = acc_semana.get(merc, 0) + (1 if ocorreu else 0)

            tot_semana[merc] = tot_semana.get(merc, 0) + 1

    data_str = agora_brt().strftime("%d/%m/%Y")

    linhas   = [f"📊 RELATÓRIO SEMANAL — Balerion", f"📅 {data_str}", "",

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

    linhas += ["", "━" * 34, "🔬 Motor: Poisson+MC+Dixon-Coles+Platt+HA v7.0"]

    return "\n".join(linhas)



# ═══════════════════════════════════════════

# MÓDULO 14 — AUTOAPRENDIZADO

# ═══════════════════════════════════════════

def carregar_params_modelo() -> dict:

    defaults = {

        "rho_dixon_coles": RHO_DIXON_COLES, "lambda_decay": LAMBDA_DECAY,

        "peso_poisson": 0.60, "peso_mc": 0.40, "fator_casa": 1.0, "motor": 7,

        "prob_minima": float(PROB_MINIMA), "versao": 1, "jogos_treinados": 0,

        "ultima_atualizacao": None, "historico_brier": [], "historico_logloss": [],

    }

    try:

        if os.path.exists(ARQUIVO_PARAMS):

            with open(ARQUIVO_PARAMS, encoding="utf-8") as f:

                saved = json.load(f)

            if saved.get("motor") == 7:
                defaults.update(saved)
            else:
                # parâmetros do motor antigo (Copa) não servem para o motor novo
                print("  🧠 Parâmetros do modelo antigo descartados (motor v7)")

    except Exception as e:

        print(f"[PERSIST] falha ao carregar params do modelo: {e}")

    return defaults



def aplicar_params_globais(params: dict) -> None:
    # FIX: o autoaprendizado salvava params em arquivo mas analisar_jogo nunca os lia,
    # então o "modelo atualizado" não mudava nenhuma previsão. Aqui sincronizamos os
    # parâmetros aprendidos de volta nas constantes globais que o motor realmente usa
    # (matriz_placares lê RHO_DIXON_COLES; calcular_lambdas lê GAMMA_CASA; etc.).
    global RHO_DIXON_COLES, PROB_MINIMA, LAMBDA_DECAY, GAMMA_CASA
    RHO_DIXON_COLES = params.get("rho_dixon_coles", RHO_DIXON_COLES)
    PROB_MINIMA     = params.get("prob_minima", PROB_MINIMA)
    LAMBDA_DECAY    = params.get("lambda_decay", LAMBDA_DECAY)
    GAMMA_CASA      = params.get("fator_casa", 1.0)



def salvar_params_modelo(params: dict) -> None:

    try:

        _salvar_json(ARQUIVO_PARAMS, params, indent=2)

    except Exception as e:

        print(f"[PERSIST] falha ao salvar params do modelo: {e}")



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
                "vitoria_fora": int(gc < gf), "btts": int(gc > 0 and gf > 0),
                "over25": int(gc + gf > 2), "under25": int(gc + gf <= 2),
                "over15": int(gc + gf > 1)}

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

            if mercado not in res: continue

            dados_por_mercado[mercado].append((prob / 100, float(res[mercado])))

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
    if abs(vies_casa) > 5.0 and erros.get("vitoria_casa", {}).get("n", 0) >= 20:
        atual      = novos.get("fator_casa", 1.0)
        delta      = max(-0.03, min(0.03, -vies_casa * 0.002))
        novo_fator = max(0.85, min(1.15, round(atual + delta, 3)))
        if novo_fator != atual:
            ajustes_feitos.append(f"fator_casa: {atual} → {novo_fator} (viés vitória_casa={vies_casa:+.1f}%)")
            novos["fator_casa"] = novo_fator
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

    # Calibração: o que o modelo prometeu nas indicações x o que aconteceu
    lim = novos["prob_minima"]
    prometido = []; aconteceu = []
    for e in log:
        res = inferir_resultado_real(e)
        for m, prob in e.get("probs_calibradas", {}).items():
            if prob >= lim and m in res:
                prometido.append(prob); aconteceu.append(res[m] * 100)
    total = len(prometido)
    if total >= 30:
        gap = sum(prometido) / total - sum(aconteceu) / total
        if gap > 5 and novos["prob_minima"] < 72:
            novo_min = round(min(72.0, novos["prob_minima"] + 1.0), 1)
            ajustes_feitos.append(f"prob_minima: {novos['prob_minima']}% → {novo_min}% (modelo otimista {gap:+.1f}%)")
            novos["prob_minima"] = novo_min
        elif gap < -5 and novos["prob_minima"] > 55:
            novo_min = round(max(55.0, novos["prob_minima"] - 0.5), 1)
            ajustes_feitos.append(f"prob_minima: {novos['prob_minima']}% → {novo_min}% (modelo pessimista {gap:+.1f}%)")
            novos["prob_minima"] = novo_min
    total = sum(1 for e in log if e.get("resultado") is not None)

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

# Platt DESLIGADO: os "dados das Copas" não tinham o resultado real de BTTS/Over
# (os rótulos eram calculados a partir do próprio lambda). No teste com 3.900 jogos
# reais ele distorcia tudo: BTTS caía de ~50% para ~15%, Over 2.5 subia para ~70%.
# A calibração passa a vir só do autoaprendizado com resultados reais.

PLATT_PARAMS = {}




# ═══════════════════════════════════════════

# ANALISAR JOGO

# ═══════════════════════════════════════════

def calcular_probabilidades(jogo: dict, jogos_c: list, jogos_f: list, jogos_h2h: list,
                            jogos_finalizados: list, desf_c: dict = None, desf_f: dict = None) -> dict:
    """Todo o modelo, sem rede: recebe os jogos e devolve as probabilidades."""
    teams = jogo.get("teams", {})
    id_c  = teams.get("home", {}).get("id")
    id_f  = teams.get("away", {}).get("id")
    data_jogo = jogo.get("fixture", {}).get("date", "")
    fase  = FASES.get(jogo.get("league", {}).get("round", ""), "fase_grupos")

    mc  = extrair_metricas(jogos_c, id_c)
    mf  = extrair_metricas(jogos_f, id_f)
    h2h = extrair_metricas_h2h(jogos_h2h, id_c)
    dias_c = calcular_dias_descanso(jogos_c, data_jogo)
    dias_f = calcular_dias_descanso(jogos_f, data_jogo)

    mh, ma  = medias_de_gols(jogos_finalizados)
    media   = (mh + ma) / 2
    forca_c = calcular_forca_time(jogos_c, id_c, media)
    forca_f = calcular_forca_time(jogos_f, id_f, media)

    lc, lf = calcular_lambdas(forca_c, forca_f, mh, ma, dias_c, dias_f)
    if desf_c and desf_f:
        lc = round(lc * desf_c["fator_ataque"] * desf_f["fator_defesa"], 3)
        lf = round(lf * desf_f["fator_ataque"] * desf_c["fator_defesa"], 3)

    placares      = matriz_placares(lc, lf)
    probs_poisson = derivar_mercados_poisson(placares)
    probs_mc      = monte_carlo(lc, lf, MONTE_CARLO_N)
    probs_cal     = aplicar_platt_todos(ensemble(probs_poisson, probs_mc, h2h, fase), PLATT_PARAMS)
    return {
        "mc": mc, "mf": mf, "h2h": h2h, "dias_c": dias_c, "dias_f": dias_f,
        "forca_c": forca_c, "forca_f": forca_f, "lc": lc, "lf": lf, "fase": fase,
        "probs_poisson": probs_poisson, "probs_mc": probs_mc, "probs_cal": probs_cal,
        "ha_resultado": selecionar_melhor_handicap(placares, lc, lf),
        "tem_xg": mc.get("tem_xg", False) or mf.get("tem_xg", False),
    }


def analisar_jogo(jogo: dict, budget: dict, cache: dict, jogos_finalizados: list) -> tuple:

    fix   = jogo.get("fixture", {})
    teams = jogo.get("teams",   {})
    league = jogo.get("league", {})
    fid   = str(fix.get("id", ""))
    nc    = teams.get("home", {}).get("name", "?")
    nf    = teams.get("away", {}).get("name", "?")
    id_c  = teams.get("home", {}).get("id")
    id_f  = teams.get("away", {}).get("id")

    if not fid or not id_c or not id_f:
        return budget, cache
    if no_cache(fid, cache):
        print(f"  [CACHE] {nc} vs {nf}")
        return budget, cache
    if calls_disponiveis(budget) < CALLS_POR_JOGO + BUDGET_EMERGENCIA:
        print("  ⚠️  Budget insuficiente.")
        return budget, cache

    print(f"\n  ⚽ {nc} vs {nf} | {LIGAS.get(league.get('id'), league.get('name', ''))}")

    jogos_c, budget = buscar_historico_completo(id_c, nc, budget)
    jogos_f, budget = buscar_historico_completo(id_f, nf, budget)
    if len(jogos_c) < 4 or len(jogos_f) < 4:
        print("  [SEM DADOS SUFICIENTES] — não será reanalisado hoje")
        return budget, add_cache(fid, cache)

    jogos_h2h, budget = buscar_h2h(id_c, id_f, JOGOS_H2H, budget)

    desf_c = desf_f = None
    lesoes, budget = buscar_desfalques(int(fid), budget)
    if lesoes:
        desf_c = calcular_impacto_desfalques(lesoes, id_c)
        desf_f = calcular_impacto_desfalques(lesoes, id_f)

    r = calcular_probabilidades(jogo, jogos_c, jogos_f, jogos_h2h, jogos_finalizados, desf_c, desf_f)
    probs_cal = r["probs_cal"]
    vazio = {"ausentes": [], "total_ausentes": 0}
    desf_c, desf_f = desf_c or vazio, desf_f or vazio

    movimentos = detectar_line_movement(fid, probs_cal)
    registrar_snapshot(fid, probs_cal)
    score, nivel_score, det_score = calcular_score_confianca(
        probs_cal, r["probs_poisson"], r["probs_mc"], r["mc"], r["mf"], r["h2h"],
        r["tem_xg"], r["dias_c"], r["dias_f"], movimentos)
    print(f"    λ {r['lc']} x {r['lf']} | Score {score}/100")

    # Odds REAIS das casas. Sem odd real não existe value bet: nada é estimado.
    odds_reais, budget = buscar_odds_reais(int(fid), budget)
    value_bets = calcular_value_bets(probs_cal, odds_reais) if odds_reais else []
    if odds_reais:
        bloco_vb = montar_bloco_value_bets(value_bets) or (
            "\n" + "━" * 34 + "\n💎 Odds reais conferidas: nenhuma value bet acima de 3%.")
    else:
        bloco_vb = ("\n" + "━" * 34 + "\n💎 Sem odds reais das casas para este jogo "
                    "— value bet não calculada.")
    melhor_odd = {m: max(c.values()) for m, c in odds_reais.items() if c}

    alerta = montar_alerta(
        jogo, probs_cal, r["mc"], r["mf"], r["h2h"], r["fase"], r["lc"], r["lf"],
        r["forca_c"], r["forca_f"], movimentos, r["dias_c"], r["dias_f"],
        None, None, r["tem_xg"], r["ha_resultado"])

    if alerta:
        score_bloco = (f"\n{'─'*34}\n🎯 SCORE DE CONFIANÇA: {score}/100\n{nivel_score}\n"
                       + "\n".join(f"  {d}" for d in det_score))
        desf_bloco = ""
        if desf_c["total_ausentes"] or desf_f["total_ausentes"]:
            desf_bloco = f"\n{'─'*34}\n🏥 DESFALQUES:\n"
            if desf_c["ausentes"]: desf_bloco += f"  {nc}: {', '.join(desf_c['ausentes'][:3])}\n"
            if desf_f["ausentes"]: desf_bloco += f"  {nf}: {', '.join(desf_f['ausentes'][:3])}\n"
        enviar_telegram(alerta + score_bloco + desf_bloco + bloco_vb)
        print("    ✅ Alerta enviado!")
        salvar_log({
            "data": datetime.now().isoformat(), "fixture_id": fid,
            "casa": nc, "fora": nf, "fase": r["fase"],
            "liga": LIGAS.get(league.get("id"), ""),
            "lambda_c": r["lc"], "lambda_f": r["lf"], "tem_xg": r["tem_xg"],
            "dias_desc_c": r["dias_c"], "dias_desc_f": r["dias_f"],
            "score_confianca": score,
            "desfalques_casa": desf_c["ausentes"], "desfalques_fora": desf_f["ausentes"],
            "probs_poisson": r["probs_poisson"], "probs_mc": r["probs_mc"], "probs_calibradas": probs_cal,
            "handicap_recomendado": r["ha_resultado"].get("recomendada"),
            "value_bets": [v["mercado"] for v in value_bets[:3]],
            "odds_reais": melhor_odd,
            "line_movement": movimentos, "resultado": None, "placar_real": None,
        })
    else:
        print(f"    ⚠️  Nenhum mercado ≥ {PROB_MINIMA}%")

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

    aplicar_params_globais(params_modelo)

    # Virada do dia: zera o orçamento (antes ficava travado depois do 1º dia)
    if budget.get("data") != hoje_utc():
        budget = {"data": hoje_utc(), "calls_usadas": 0}
        salvar_budget(budget)

    agora   = agora_brt().strftime("%d/%m/%Y %H:%M:%S")

    disponi = calls_disponiveis(budget)

    print(f"\n{'═'*58}")

    print(f"  🤖 Balerion v7.0 | {agora}")

    print(f"  📊 Budget: {budget['calls_usadas']}/{BUDGET_DIARIO} | {disponi} disponíveis")

    print(f"{'═'*58}")

    if disponi <= BUDGET_EMERGENCIA:

        print("  ⚠️  Budget do dia esgotado.")

        return budget, cache, params_modelo

    jogos, budget = buscar_jogos_proximos(budget)

    finalizados, budget = buscar_jogos_finalizados(budget)

    if jogos:

        print(f"  ⚽ {len(jogos)} jogo(s) nas próximas {HORAS_ANTECEDENCIA}h")

    else:

        print(f"  Nenhum jogo das ligas monitoradas nas próximas {HORAS_ANTECEDENCIA}h.")

    hoje = agora_brt().strftime("%Y-%m-%d")

    estado = _carregar_estado_envios()

    if eh_hora_resumo() and estado.get("resumo") != hoje:

        jogos_hoje = [j for j in jogos if formatar_brt(j.get("fixture",{}).get("date","")).startswith(agora_brt().strftime("%d/%m"))]

        enviar_resumo_diario(jogos_hoje)

        estado["resumo"] = hoje

        _salvar_estado_envios(estado)

    for jogo in jogos:

        if calls_disponiveis(budget) < CALLS_POR_JOGO + BUDGET_EMERGENCIA:

            print("  ⚠️  Budget esgotado — restante fica para amanhã.")

            break

        try:
            budget, cache = analisar_jogo(jogo, budget, cache, finalizados)
        except Exception as e:
            # um jogo com dado estranho não pode derrubar o ciclo nem ser
            # reanalisado a cada 30 min gastando cota
            fid = str(jogo.get("fixture", {}).get("id", ""))
            print(f"  [ERRO jogo {fid}] {type(e).__name__}: {e}")
            if fid:
                cache = add_cache(fid, cache)

    log_atual = carregar_log()

    bt        = processar_backtest(log_atual, finalizados)

    if bt["atualizados"] > 0:

        rel_bt = montar_relatorio_backtest(bt)

        if rel_bt: enviar_telegram(rel_bt)

        try:

            _salvar_json(ARQUIVO_LOG, log_atual[-500:], indent=2)

        except Exception as e:

            print(f"Erro ao salvar arquivo de log no ciclo: {e}")

    global relatorio_semanal_enviado

    hoje_str = agora_brt().strftime("%Y-%m-%d")

    if eh_hora_relatorio_semanal() and estado.get("semanal") != hoje_str:

        rel_sem = gerar_relatorio_semanal(carregar_log(), jogos)

        if rel_sem: enviar_telegram(rel_sem)

        estado["semanal"] = hoje_str

        _salvar_estado_envios(estado)

    params_modelo = executar_autoaprendizado(params_modelo)

    aplicar_params_globais(params_modelo)

    print(f"\n  ✅ Ciclo OK | {budget['calls_usadas']}/{BUDGET_DIARIO}")

    return budget, cache, params_modelo



# ═══════════════════════════════════════════

# ENTRY POINT

# ═══════════════════════════════════════════

if __name__ == "__main__":

    # FIX: valida as credenciais ANTES de tentar enviar qualquer Telegram
    # (a notificação de boot ficava antes da validação e era duplicada).
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT or not APIFOOTBALL_KEY:

        print("❌ ERRO: defina as variáveis de ambiente:")

        print("   TELEGRAM_TOKEN, TELEGRAM_CHAT, APIFOOTBALL_KEY")

        raise SystemExit(1)



    print("╔══════════════════════════════════════════════════════╗")

    print("║    BALERION PREDICTOR v7.0 — LIGAS                 ║")

    print("╠══════════════════════════════════════════════════════╣")

    print("║  [1]  Poisson Bivariado + Dixon-Coles (ρ=-0.13)    ║")

    print("║  [2]  Monte Carlo — 100.000 simulações/jogo        ║")

    print("║  [3]  Força ataque/defesa (Maher) + encolhimento   ║")

    print("║  [4]  xG (Expected Goals)                          ║")

    print("║  [5]  Variáveis contextuais (descanso, fase)       ║")


    print("║  [7]  Variação das probabilidades do modelo        ║")

    print("║  [8]  Ensemble: Poisson 60% + MC 40% + H2H        ║")

    print("║  [9]  Score de Confiança 0-100                     ║")

    print("║  [10] Lesões e desfalques                          ║")

    print("║  [11] Value Bet com odds REAIS das casas           ║")

    print("║  [12] Backtest automático                          ║")

    print("║  [13] Relatório semanal (domingos 9h BRT)          ║")

    print("║  [14] Autoaprendizado online                       ║")

    print("║  [15] Handicap asiático                            ║")

    print("╚══════════════════════════════════════════════════════╝\n")



    budget        = carregar_budget()

    cache         = carregar_cache()

    log           = carregar_log()

    params_modelo = carregar_params_modelo()

    aplicar_params_globais(params_modelo)



    print(f"  💰 Budget ({budget['data']}): {budget['calls_usadas']}/{BUDGET_DIARIO}")

    print(f"  📦 Cache: {len(cache)} jogos | Log: {len(log)} indicações")

    print(f"  🧠 Modelo v{params_modelo.get('versao',1)} | Treinado em {params_modelo.get('jogos_treinados',0)} jogos\n")



    # FIX: notificação de boot opcional (defina NOTIFY_BOOT=0 no Railway para
    # não receber esta mensagem a cada restart/redeploy do serviço).
    if os.getenv("NOTIFY_BOOT", "1") == "1":

        enviar_telegram(

        "🤖 BALERION PREDICTOR v7.0 ONLINE\n🏆 " + ", ".join(LIGAS.values()) + "\n\n"

        "🔬 Motor completo ativo:\n  ✅  Poisson + Dixon-Coles\n"

        "  🎲 Monte Carlo 100k simulações\n  📊 xG (Expected Goals)\n"

        "  💪 Força ataque/defesa por time\n  💤 Fator descanso entre jogos\n"

        "  🔄 Variação do modelo\n"

        "  📊 Score de confiança 0-100\n"

        "  🏥 Lesões e desfalques\n  💎 Value Bet multi-casa\n"

        "  📋 Backtest automático\n  📅 Relatório semanal\n"

        "  🧠 Autoaprendizado\n  🎲 Handicap asiático\n\n"

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