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
- **Calibrado não é lucrativo.** O backtest mede se as probabilidades batem com a
  realidade; ele não prova que o modelo vence as odds das casas, que já embutem
  tudo isso. Value bet só vale com odd real acima da odd mínima, e mesmo assim
  precisa de semanas de registro (relatório semanal) antes de apostar dinheiro sério.
- Ambas Marcam e Over/Under ficam no nível do "chute pela média": o modelo não tem
  vantagem real nesses mercados.
- Sem xG (custa chamadas extras no plano grátis).
- Plano grátis da API-Football: não confirmado se libera a temporada atual.

## Como repetir os testes
```
python3 testes/teste_falhas.py                       # 9 cenários de falha
git clone --depth 1 https://github.com/openfootball/football.json
OPENFOOTBALL_DIR=football.json python3 testes/backtest_real.py
```
