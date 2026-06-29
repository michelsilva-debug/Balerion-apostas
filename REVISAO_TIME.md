# Revisão Técnica — apostas-esportivas (TERRORNEGRO PREDICTOR v6.1)

> Análise feita por um time de agentes especializados (arquiteto, segurança, revisor de código, devops) em 2026-06-28, seguida da aplicação das correções críticas. O bot **não foi executado** durante a análise (ele envia Telegram real e consome cota de API).

---

## Visão geral

Bot de Telegram em Python (~3.600 linhas, 1 arquivo) que prevê apostas da Copa 2026 com um motor estatístico sofisticado: Poisson/Dixon-Coles, Monte Carlo 100k, Platt scaling, Kelly, value bets, backtest e autoaprendizado. Roda 24/7 no Railway (`python predictor.py`). O motor matemático é sólido; os problemas estavam na estrutura, infra e segurança ao redor.

---

## ✅ Correções aplicadas nesta revisão

| # | Problema | Correção | Arquivo |
|---|----------|----------|---------|
| 1 | Credenciais vivas em texto puro em rascunhos | Arquivos deletados (`predictor_utf8.py`, `refactor.py`, `fixer.py`, `fixer2.py`, `add_msg.py`, `get-pip.py`) | — |
| 2 | Estado se perdia a cada deploy (FS efêmero) | `DATA_DIR` configurável p/ volume persistente do Railway | `predictor.py` |
| 3 | Autoaprendizado não afetava previsões | `aplicar_params_globais()` sincroniza params aprendidos com as globais que o motor lê; chamado no boot, no início de cada ciclo e após o aprendizado | `predictor.py` |
| 4 | Escrita de JSON não-atômica (risco de corromper arquivo) | Helper `_salvar_json()` (temp + `os.replace` + `fsync`) em todos os 6 pontos de gravação | `predictor.py` |
| 5 | `open()` sem encoding (erro de Unicode no Windows) | `encoding="utf-8"` em todas as leituras | `predictor.py` |
| 6 | `except: pass` silencioso na persistência do modelo | Passou a logar a falha | `predictor.py` |
| 7 | Spam de boot no Telegram (2 msgs, antes da validação) | Removida a msg duplicada; validação antes; msg de boot opcional via `NOTIFY_BOOT` | `predictor.py` |
| 8 | Token podia vazar no log de erro do Telegram | Loga só `type(e).__name__` | `predictor.py` |
| 9 | `.gitignore` corrompido (bytes UTF-16) | Reescrito em UTF-8 limpo + ignora estado e venv | `.gitignore` |
| 10 | Estado mutável versionado | `budget_predictor.json` destrackeado | git |
| 11 | Versão do Python não fixada | `.python-version` (3.12) | `.python-version` |
| 12 | Env vars não documentadas | `.env.example` criado | `.env.example` |
| 13 | Restart não explícito no Railway | `restartPolicyType`/`MaxRetries` | `railway.toml` |

---

## ⚠️ Ação manual necessária (não dá para automatizar)

**ROTACIONAR as credenciais.** O token do Telegram e a chave da API-Football estiveram em texto puro em disco (`predictor_utf8.py`, `refactor.py`). Mesmo com os arquivos deletados, trate-os como comprometidos:
1. Telegram: revogar o token atual no @BotFather e gerar um novo.
2. API-Football: gerar nova key no painel api-sports.io.
3. Atualizar o `.env` local e as variáveis no Railway.

**Configurar o volume no Railway** (para o fix #2 ter efeito): criar um Volume montado em `/data` e definir `DATA_DIR=/data` nas variáveis do serviço.

---

## 🟡 Melhorias futuras (não aplicadas — fora do escopo crítico)

- **Sem testes.** Funções puras do motor (`kelly_stake`, `calcular_edge`, `calcular_brier_score`, `prob_escanteios_over`) são candidatas baratas a `pytest`.
- **`analisar_jogo` e `montar_alerta` são funções gigantes** que misturam rede, cálculo e formatação — candidatas a quebrar em etapas (`coletar_dados` → `calcular_probabilidades` → `montar_alerta`).
- **Extrair o motor estatístico** para um módulo `engine.py` puro e testável.
- **Elo via scraping** casa nomes por string exata contra a API-Football; divergência zera o rating do time silenciosamente. Usar mapa de aliases ou casar por ID, com fallback ao `elo.txt`.
- **Pesos do ensemble** (60/40) estão hardcoded em `ensemble()`; os params `peso_poisson`/`peso_mc` do modelo não são usados (só rho/prob_minima/gamma/lambda_decay passaram a valer).
- **Linhas em branco duplicadas** no fonte (sequela dos scripts `fixer`) — um `black`/reformatação resolveria.

---

## ✅ O que já estava correto

Histórico git limpo (nenhum segredo commitado), `.env` protegido, `predictor.py` usa `os.getenv`, todas as chamadas HTTP têm `timeout`, o loop principal captura exceções e não morre fácil, e o orçamento de API é bem controlado.
