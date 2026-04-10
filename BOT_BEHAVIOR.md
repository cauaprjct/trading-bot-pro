# Relatório de Comportamento do Bot - Hybrid Edition

Este documento descreve detalhadamente o comportamento do **B3 Trading Bot PRO 3.0** com técnicas **Smart Money (ICT)** + **Mean Reversion** + **Machine Learning** + **Multi-Timeframe**.

---

## 🆕 Novidades da v3.0

### 1. Modo Híbrido Automático
O bot agora escolhe automaticamente a melhor estratégia:
- **ADX >= 20**: Usa Trend Following (mercado com tendência)
- **ADX < 20**: Usa Mean Reversion (mercado lateral)

### 2. Mean Reversion Strategy
Para mercados laterais, usa:
- Bollinger Bands (compra na banda inferior, vende na superior)
- Z-Score (desvio da média)
- RSI extremo como confirmação

### 3. Machine Learning Filter
Aprende com o histórico de trades:
- Calcula probabilidade de sucesso do sinal
- Considera hora do dia, RSI, ADX, estrutura
- Bloqueia sinais com baixa probabilidade (<55%)

### 4. Multi-Timeframe Analysis
Confirma sinais com timeframe maior (H1):
- Evita trades contra a tendência do H1
- Aumenta confiança quando H1 confirma

---

## 🎯 Sistema de Score 9/9 - Confirmações Múltiplas

### O Problema Resolvido
Traders de varejo entram em sinais fracos e são "caçados" por institucionais. O bot agora usa 9 confirmações como traders profissionais.

### As 9 Confirmações

| # | Confirmação | Descrição |
|---|-------------|-----------|
| 1 | **SMA Crossover** | Cruzamento de médias (tendência) |
| 2 | **RSI Momentum** | RSI > 55 venda, < 45 compra |
| 3 | **MACD** | MACD confirma direção |
| 4 | **Preço vs SMA21** | Preço na direção da tendência |
| 5 | **Volume** | Volume acima da média |
| 6 | **ADX + DI** | ADX > 25 + DI confirma direção |
| 7 | **Market Structure** | HH/HL (alta) ou LH/LL (baixa) |
| 8 | **BOS + Pullback** | Rompimento + retração 30-70% |
| 9 | **Order Block** | Preço em zona institucional |

### Classificação de Sinais
- **🔥 Score 9/9** = SINAL PERFEITO
- **💪 Score 8/9** = SINAL MUITO FORTE
- **👍 Score 7/9** = SINAL FORTE
- **✅ Score 6/9** = SINAL BOM
- **⚠️ Score 5/9** = SINAL MÉDIO
- **❌ Score 4/9** = SINAL FRACO (mínimo padrão)
- **🚫 Score <4** = NÃO ENTRA

---

## 🛡️ Filtros Smart Money (Prioridade Alta)

### 1. Session Filter (Killzones)
**Conceito ICT**: Só opera quando há liquidez institucional.

| Sessão | Horário BRT | Motivo |
|--------|-------------|--------|
| Londres | 05:00-07:00 | Abertura europeia, alta liquidez |
| NY | 10:00-12:00 | Overlap Londres/NY, maior volume |

**Evita**:
- Sessão Asiática (baixa liquidez)
- Primeiros 30 min de cada sessão (manipulação)

### 2. Spread Filter
**Conceito**: Spread alto = baixa liquidez = manipulação.

| Condição | Ação |
|----------|------|
| Spread > 2x média | BLOQUEIA |
| Spread > 30 pontos | BLOQUEIA |

### 3. ADX Filter (Tendência vs Range)
**Conceito**: Trend Following só funciona em tendência!

| ADX | Status | Ação |
|-----|--------|------|
| < 20 | LATERAL | BLOQUEIA (não opera) |
| 20-25 | FRACA | Opera com cautela |
| 25-50 | FORTE | Ideal (+1 no score) |
| > 50 | MUITO FORTE | Pode estar no fim |

### 4. Anti-Stop Hunt (SL Inteligente)
**Conceito ICT**: Market makers caçam stops em níveis óbvios.

**Proteções**:
- ❌ Evita SL em X.XX00 e X.XX50 (números redondos)
- ✅ Adiciona +5 pips de buffer
- ✅ Usa swing high/low como referência
- ✅ Move SL para ALÉM do número redondo

**Exemplo**:
```
SL calculado: 1.08500 (número redondo!)
SL ajustado:  1.08497 (3 pips abaixo)
```

---

## 📊 Filtros Smart Money (Prioridade Média)

### 5. Volatility Filter (ATR Percentil)
**Conceito**: Evita extremos de volatilidade.

| ATR Percentil | Status | Ação |
|---------------|--------|------|
| < 20% | BAIXA | BLOQUEIA (mercado parado) |
| 20-80% | NORMAL | Opera normalmente |
| > 80% | ALTA | BLOQUEIA (mercado caótico) |

### 6. Market Structure (HH/HL/LH/LL)
**Conceito ICT**: Identifica a estrutura real do mercado.

| Estrutura | Padrão | Trades Permitidos |
|-----------|--------|-------------------|
| BULLISH | HH + HL | Só COMPRA |
| BEARISH | LH + LL | Só VENDA |
| RANGING | Misto | Nenhum (se filtro ativo) |

**Detecção**:
- Identifica swing highs e swing lows
- Analisa últimos 3+ swings
- Determina se topos/fundos são ascendentes ou descendentes

### 7. BOS + Pullback (Break of Structure)
**Conceito ICT**: Entrada após rompimento + retração.

**Fluxo**:
1. Detecta BOS (preço fecha acima/abaixo de swing)
2. Aguarda pullback (retração 30-70%)
3. Entra na direção do BOS

**Exemplo BOS Bullish**:
```
1. Preço rompe swing high anterior → BOS BULLISH
2. Preço retrai 45% do movimento → PULLBACK VÁLIDO
3. Sinal de COMPRA gerado (+1 no score)
```

### 8. Order Blocks (Zonas Institucionais)
**Conceito ICT**: Zonas onde institucionais acumularam posições antes de um movimento forte.

**Tipos de Order Block**:
| Tipo | Descrição | Uso |
|------|-----------|-----|
| **Bullish OB** | Último candle de BAIXA antes de impulso de ALTA | Zona de suporte para COMPRA |
| **Bearish OB** | Último candle de ALTA antes de impulso de BAIXA | Zona de resistência para VENDA |

**Critérios de Detecção**:
1. Candle de reversão (bearish antes de alta, bullish antes de baixa)
2. Impulso significativo (> 1.5x ATR)
3. OB não foi "mitigado" (preço não retornou e tocou 50%+)
4. OB não é muito antigo (< 100 candles)

**Exemplo**:
```
Candle bearish em 1.08400-1.08420
Preço sobe 25 pips (> 1.5x ATR) → BULLISH OB detectado
Preço retorna a 1.08410 → Preço em OB! (+1 no score)
```

---

## 📋 Exemplo de Log Completo

### Sinal Aceito (Score 7/9)
```log
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ANÁLISE DE SINAL DE COMPRA
📈 👍 SINAL FORTE (7/9)
   ✓ SMA9 cruzou acima de SMA21
   ✓ RSI 42.5 < 45 (momentum comprador)
   ✓ MACD acima da Signal Line
   ✓ Preço acima da SMA21 (tendência)
   ✗ Volume abaixo da média
   ✓ ADX 28 forte + DI+ > DI- (tendência alta)
   ✓ Estrutura BULLISH (HH + HL)
   ✗ Sem BOS Bullish
   ✓ Preço em Bullish OB (1.08400-1.08420)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ Anti-Stop Hunt: ATR + 5 pips buffer
✅ Score 7/9 >= 4 - EXECUTANDO COMPRA!
```

### Sinal Bloqueado (Filtros)
```log
⏰ Fora da Killzone - Sessão Asiática (baixa liquidez)
📊 Status: 🌙 Sessão Asiática | Próxima: Londres em 2h
```

```log
📊 ADX 15 < 20 | 📊 LATERAL (sem tendência)
```

```log
🚫 Market Structure: Sinal de COMPRA bloqueado - Estrutura BEARISH
```

---

## ⚙️ Configurações Recomendadas

### Para Iniciantes (Conservador)
```python
MIN_SIGNAL_SCORE = 5          # Só sinais fortes
USE_SESSION_FILTER = True     # Só Killzones
STRUCTURE_AS_FILTER = True    # Bloqueia contra-estrutura
BOS_AS_FILTER = False         # BOS como bonus, não obrigatório
```

### Para Experientes (Agressivo)
```python
MIN_SIGNAL_SCORE = 3          # Aceita sinais médios
USE_SESSION_FILTER = False    # Opera qualquer horário
STRUCTURE_AS_FILTER = False   # Estrutura como bonus
BOS_AS_FILTER = True          # Só entra com BOS+Pullback
```

---

## 📊 Heartbeat (Sinal de Vida)

A cada 30 segundos, o bot mostra:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔎 ANÁLISE DE MERCADO | EURUSD-T
💹 Preço: 1.08500 | Tendência: 📈 ALTA
📉 RSI: 45.2 | Zona: ⚪ NEUTRO
📈 SMA9: 1.08480 | SMA21: 1.08450
💪 ADX 28 - Tendência FORTE (↑ DI+)
🟢 Volatilidade NORMAL (55%)
📈 Estrutura BULLISH (HH+HL)
🎯 🟢 BOS BULLISH | ✓ Pullback 45%
📦 🟢 OB @ 1.08400-1.08420 | 🔴 OB @ 1.08600-1.08620
💰 Saldo: $100,000.00 (R$610,000.00)
📰 Notícias: ✅ Livre
⏰ Sessão: 🇬🇧 Killzone Londres (05:30)
💹 Spread: 12 pts (média: 15) ✅
📋 Hoje: 2 trades | W/L: 1/1 | P&L: $5.00
🎯 📈 Tendência de alta + RSI baixo - aguardando confirmação
📈 Performance: 👍 Bom
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🆚 Comparação: Varejo vs Smart Money

| Aspecto | Trader Varejo | Bot Smart Money |
|---------|---------------|-----------------|
| Horário | Qualquer | Só Killzones |
| SL | Número redondo | Longe de redondos |
| Entrada | Qualquer sinal | 9 confirmações |
| Estrutura | Ignora | Analisa HH/HL/LH/LL |
| BOS | Não conhece | Detecta e aguarda pullback |
| Order Blocks | Não conhece | Detecta zonas institucionais |
| ADX | Não usa | Filtra mercado lateral |
| Spread | Ignora | Bloqueia spread alto |

---

## 📝 Changelog

### v3.0 (Janeiro 2026) - Hybrid Edition
- ✅ **Modo Híbrido** (Trend Following + Mean Reversion automático)
- ✅ **Mean Reversion Strategy** (Bollinger Bands + Z-Score)
- ✅ **ML Signal Filter** (Machine Learning para filtrar sinais)
- ✅ **Multi-Timeframe Analysis** (Confirmação com H1)
- ✅ Sistema de Score 9/9 mantido

### v2.3 (Janeiro 2026) - Smart Money Edition
- ✅ **Order Blocks Detection** (zonas institucionais)
- ✅ Sistema de Score 9/9

### v2.2 (Janeiro 2026) - Smart Money Edition
- ✅ Session Filter (Killzones)
- ✅ Spread Filter
- ✅ ADX Filter
- ✅ Anti-Stop Hunt
- ✅ Volatility Filter (ATR%)
- ✅ Market Structure (HH/HL/LH/LL)
- ✅ BOS + Pullback
- ✅ Sistema de Score 8/8

### v2.1 (Janeiro 2026)
- ✅ Sistema de Score 5/5
- ✅ MACD + Volume
- ✅ Telegram + Dashboard

---

**Conceitos baseados em ICT (Inner Circle Trader) e Smart Money Concepts.**
