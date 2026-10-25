# Auditoria — Balerion Predictor v7.0 (25/10/2026)

Leitura completa do `predictor.py`, testes da matemática, 9 cenários de falha com a
API simulada e **backtest em 3.932 jogos reais** (Premier League, La Liga, Serie A,
Bundesliga 2022-25 e Brasileirão 2025), usando só o que o bot saberia antes de cada jogo.

## Resultado do backtest: antes x depois

"Melhora" = quanto o modelo erra menos que simplesmente chutar a média do campeonato
(Brier score). Negativo = pior que o chute.

| Mercado | Antes | Depois |
|---|---|---|
| Vitória casa | −2,9% | **+6,6%** |
| Empate | −2,5% | +0,3% |
| Vitória fora | +0,6% | **+6,5%** |
| Over 2.5 | −9,9% | +0,2% |
| Under 2.5 | −16,2% | +0,2% |
| Ambas marcam | **−67,5%** | −0,6% |
| Over 1.5 | −19,3% | −0,1% |

Calibração (o que o modelo promete x o que aconteceu):

| Faixa | Antes | Depois |
|---|---|---|
| 70–79% | aconteceu 58,9% | aconteceu 73,1% |
| 80–89% | aconteceu 63,2% | aconteceu 81,6% |
| 90–99% | aconteceu 68,9% | aconteceu 82,1% |

## Problemas encontrados e corrigidos

### Críticos (o bot parava ou mentia)
1. **Orçamento nunca virava o dia** — depois do 1º dia a cota ficava "esgotada" para
   sempre e o bot parava de analisar até ser reiniciado.
2. **Calibração Platt com rótulos inventados** — os "dados das Copas" não tinham o
   resultado de BTTS/Over (o rótulo vinha do próprio lambda). Ambas Marcam caía de
   ~50% para ~13%; Over 2.5 subia para ~70%. Desligada.
3. **Handicap do visitante com sinal trocado** — "AH Fora −2.5 a 88%" era na verdade
   o visitante +2.5. E as linhas sugeridas eram as triviais (odd ~1.0).
4. **Over 2.5 e Under 2.5 indicados no mesmo jogo** (somavam ~120%); 1X2 não somava 100%.
5. **Mando de campo exagerado** — times iguais davam ~59% de gols do mandante a mais;
   o modelo previa 2,3 gols/jogo (real ~2,7).
6. **Cartões Over 3.5 indicados em todo jogo** — vinha de um valor padrão fixo
   (não há estatística de cartões nos dados buscados). Escanteios e cartões removidos.

### Operacionais
7. Time sem histórico ou jogo com dado quebrado era reanalisado a cada 30 min,
   gastando cota sem parar — agora entra no cache.
8. Um erro num jogo derrubava o ciclo inteiro — agora é isolado por jogo.
9. Falha ao listar os jogos do dia "cegava" o bot por 4h — agora tenta de novo em ~30 min.
10. Resumo das 8h e relatório de domingo tinham janela de 30 min e podiam ser
    pulados (o ciclo leva mais que isso); repetiam a cada reinício.
11. "Taxa de acerto" contava o jogo como acerto se **qualquer** mercado batesse,
    e o autoaprendizado usava isso para baixar o corte de probabilidade (mais indicações).
    Agora é por mercado e compara prometido x real.
12. Parâmetros salvos pelo motor antigo (Copa) são descartados automaticamente.
13. "Força Atk/Def" no alerta mostrava sempre 1.0.

## Modelo novo (em uma frase)
Força de ataque/defesa de cada time pelos últimos 10 jogos (com peso de recência),
"puxada" para a média com o equivalente a 16 jogos médios (melhor valor no backtest),
vezes a média de gols de mandante/visitante — Poisson com Dixon-Coles.

## Limites que continuam (honestidade)
- **Calibrado não é lucrativo** — confirmado na auditoria 2 abaixo.
- Ambas Marcam e Over/Under ficam no nível do "chute pela média".
- Sem xG (custa chamadas extras no plano grátis).
- Plano grátis da API-Football: não confirmado se libera a temporada atual.

---

# Auditoria 2 — Regras de aposta (25/10/2026)

## Teste contra odds REAIS da Bet365 (2022-07 → 2026)
6.486 jogos (Premier, La Liga, Serie A, Bundesliga, Brasileirão), modelo vendo só o
passado. Dados: github.com/xgabora/Club-Football-Match-Data-2000-2025.

| Estratégia | Apostas | ROI |
|---|---|---|
| Apostar em tudo na Bet365 (sem modelo) | 42.365 | −5,3% (margem da casa) |
| **Regra do bot: value > 3% (1X2 + Over/Under 2.5)** | 12.132 | **−11,9% ± 2,9%** |
| Mesma regra com a melhor odd de ~17 casas | 14.029 | −6,3% |
| Handicap asiático visitante (value > 3%) | 2.839 | +4,5% ± 3,3% — **não confiável**: temporada atual −6,6%, e apostar em todo AH visitante sem modelo já dava +0,6% |

Banca simulada de R$1.000 com a regra: zerada com Kelly do código, com Kelly 10%/teto 2%
e com stake fixo de 1%.

**Conclusão:** quando o modelo discorda da Bet365, na maior parte das vezes o errado
é o modelo. A regra "odd acima da odd justa = aposta" perde dinheiro. Por isso o bot
passou para **modo observação**: continua mandando as análises e registra as
divergências como **apostas simuladas**, e o relatório semanal mostra o ROI real
delas. Só faz sentido apostar se esse ROI ficar positivo por vários meses.

## Bugs de regra corrigidos
1. **ROI media a estratégia errada** — "apostava" em todo mercado ≥ 58%, não nas
   value bets que o alerta sugeria. Agora o ROI vem só das apostas simuladas,
   gravadas no log com casa e odd.
2. **Prorrogação** — mata-mata (Libertadores/Champions) seria liquidado com o placar
   da prorrogação. Casas liquidam pelos 90 min: agora usa `score.fulltime`.
3. **Handicap asiático sem liquidação** — criada `lucro_aposta()` com linhas inteiras
   (devolução), meias e quartos (meia vitória / meia derrota). 33 casos conferidos à mão.
4. **Stake de até 15% da banca** numa aposta e banca fixa no código — teto de 2% e
   banca por variável `BANCA`. Stake não aparece mais no alerta.
5. Mesmo mercado repetido uma vez por casa — agora só a melhor odd.
6. Texto "só vale apostar se a odd for maior que a mínima" — era exatamente a regra
   que perde dinheiro; trocado por "odd justa" e aviso de modo observação.
7. `EDGE_MINIMO` declarado e nunca usado — removido (`VALUE_MINIMO = 0.03`).

Conferido também: a odd justa do handicap (inclusive quartos de linha) dá EV ≈ 0 pela
liquidação exata; Kelly fracionado e cálculo de value batem com a fórmula.

---

# Melhorias v8 — Handicap asiático e escanteios (25/10/2026)

Tudo o que existia continua. Validado com o **código real do bot** em 9.390 jogos de
7 ligas (Premier, La Liga, Serie A, Bundesliga, Ligue 1, Portugal, Holanda), com
treino 2022-24 e prova 2024-26 separados. Dados: github.com/xgabora/Club-Football-Match-Data-2000-2025.

## O que mudou no modelo
- **Chutes no alvo**: a força de cada time mistura gols reais (50%) com
  "chutes no alvo x conversão da liga" (50%). Chute no alvo é sinal mais estável.
- **Histórico maior**: 20 jogos (antes 10), recência mais suave (0,01/dia) e
  encolhimento de 8 jogos — escolhidos no treino, confirmados na prova.
- **Escanteios (mercado novo)**: força a favor/contra de cada time x média da liga,
  binomial negativa (escanteios variam mais que Poisson). Linhas 8.5 / 9.5 / 10.5.
- **Odds reais de handicap asiático e escanteios** lidas da API (as duas convenções
  de linha do visitante são detectadas automaticamente).
- **Estatísticas em lote**: até 20 jogos por chamada (`fixtures?ids=`), com cache em
  disco; falha só é tentada de novo após 6h. Cada análise gasta até 7 chamadas.

## Resultados
| | Treino | Prova |
|---|---|---|
| Todo AH visitante, sem modelo | −0,3% | +0,7% |
| **⭐ AH visitante com EV > 8% (estratégia em teste)** | **+4,7% ± 4,1** | **+4,9% ± 4,2** |
| AH mandante (divergência) | +1,5% | −1,6% |

Positiva em 6 das 7 ligas (Portugal ≈ 0%). **Não está comprovada**: cada metade ainda
cabe dentro da margem de erro. Fica como **sinal em teste** no alerta e na simulação;
o relatório semanal mostra o ROI dela separado das outras divergências.

Escanteios (prova): calibrado — promete 56% → acontece 56%, 64% → 65%, 73% → 74% (+8.5).
Ganho sobre a média da liga é pequeno (~1%) e não há odds históricas de escanteio
para medir lucro: só a simulação ao vivo vai dizer.

Gols/1X2 (openfootball, 3.932 jogos): vitória casa/fora agora 8,4% / 8,7% melhores
que a média do campeonato (antes 6,6% / 6,5%).

## Brasileirão e Libertadores
O conjunto histórico não tem chutes, escanteios nem odds de AH do Brasil: as melhorias
valem lá também, mas **só foram provadas nas ligas europeias**.

## Como repetir os testes
```
python3 testes/teste_regras.py                       # regras, liquidação, escanteios, odds AH
python3 testes/teste_falhas.py                       # 10 cenários de falha
git clone --depth 1 https://github.com/openfootball/football.json
OPENFOOTBALL_DIR=football.json python3 testes/backtest_real.py
git clone --depth 1 https://github.com/xgabora/Club-Football-Match-Data-2000-2025
python3 testes/backtest_odds.py                      # regra x odds reais da Bet365
python3 testes/backtest_handicap.py                  # AH visitante + escanteios (código do bot)
```
