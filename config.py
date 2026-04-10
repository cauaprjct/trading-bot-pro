import MetaTrader5 as mt5
import os
from datetime import time

# --- Configurações da Conta ---
# Se deixados como None, o bot tentará usar a conta já logada no terminal MT5
MT5_LOGIN = int(os.getenv("MT5_LOGIN")) if os.getenv("MT5_LOGIN") else None
MT5_PASSWORD = os.getenv("MT5_PASSWORD") if os.getenv("MT5_PASSWORD") else None
MT5_SERVER = os.getenv("MT5_SERVER") if os.getenv("MT5_SERVER") else None

# --- Configurações do Ativo e Operacionais ---
SYMBOL = "GBPUSD"  # 🏆 MELHOR SPREAD da sua corretora (0.15 pts!)
TIMEFRAME = mt5.TIMEFRAME_M5  # M5 - melhor equilíbrio entre sinais e qualidade
VOLUME = 0.05      # 💰 LOTE MAIOR - cada pip = ~$0.50 (mais lucro!)
MAGIC_NUMBER = 20240101

# --- Gerenciamento de Risco Profissional ---
RISK_PER_TRADE_PERCENT = 5.0  # 5% do saldo por operação (~R$10 de R$200)
USE_ATR_FOR_SL = True         # Usa volatilidade para calcular Stop
ATR_PERIOD = 14
ATR_MULTIPLIER_SL = 1.2       # Stop Loss = 1.2x ATR (mais apertado = menos risco)
ATR_MULTIPLIER_TP = 2.4       # Take Profit = 2.4x ATR (ratio 1:2 mantido)

# --- Limites de Segurança ---
MAX_LOT_SIZE = 0.10           # 💰 Permite até 0.10 para sinais fortes
MAX_OPEN_POSITIONS = 2        # Até 2 posições simultâneas
MIN_SECONDS_BETWEEN_TRADES = 45   # 45s entre trades
AGGRESSIVE_MODE = True        # 🔥 ATIVADO
HEARTBEAT_INTERVAL = 10       # Log a cada 10s

# --- Entradas por RSI Extremo ---
USE_RSI_EXTREME_ENTRY = True  # 🔥 ATIVADO - RSI extremo + ML = boas entradas
RSI_EXTREME_OVERSOLD = 30     # RSI < 30 = sobrevenda
RSI_EXTREME_OVERBOUGHT = 70   # RSI > 70 = sobrecompra

# ============================================================================
# 🎯 ESTRATÉGIA PRO v2.0 - SISTEMA DE SCORE DE CONFIANÇA
# ============================================================================
# Cada sinal recebe pontuação de 0-5 baseada em múltiplas confirmações.
# Só executa trades com score >= MIN_SIGNAL_SCORE

MIN_SIGNAL_SCORE = 2          # 💰 Score 2/9 - ML + Smart Exit protegem
USE_MACD_FILTER = True        # Usa MACD como confirmação adicional
USE_VOLUME_FILTER = False     # Volume em forex é menos confiável
RSI_MOMENTUM_SELL = 50        # RSI neutro - mais entradas
RSI_MOMENTUM_BUY = 50         # RSI neutro - mais entradas

# SISTEMA DE PONTUAÇÃO:
# +1 ponto: SMA Crossover (tendência)
# +1 ponto: RSI Momentum (força)
# +1 ponto: MACD Confirmação (momentum)
# +1 ponto: Preço vs SMA21 (posição)
# +1 ponto: Volume acima da média (interesse)
#
# Score 5/5 = SINAL FORTE 💪
# Score 4/5 = SINAL BOM 👍
# Score 3/5 = SINAL MÉDIO ⚠️ (mínimo padrão)
# Score 2/5 = SINAL FRACO ❌ (não entra)
# Score 1/5 = SINAL MUITO FRACO 🚫 (não entra)

# --- Reconexão Automática ---
MAX_RECONNECT_ATTEMPTS = 5    # Tentativas máximas de reconexão
RECONNECT_DELAY_SECONDS = 10  # Delay entre tentativas (aumenta exponencialmente)

# --- Persistência de Estado ---
STATE_FILE = "bot_state.json"  # Arquivo para salvar estado do bot

# --- Notificações Telegram ---
# Para configurar:
# 1. Fale com @BotFather no Telegram e crie um bot com /newbot
# 2. Copie o token fornecido
# 3. Inicie uma conversa com seu bot e envie /start
# 4. Acesse: https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
# 5. Copie o chat_id da resposta
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8398006198:AAF9Ss9DW9t7Xp-fKH2QEXO7LsL5enRzWdE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-5153173676")  # Grupo tradertwo

# --- Filtro de Notícias ---
USE_NEWS_FILTER = True           # Ativa/desativa filtro de notícias
NEWS_BLACKOUT_MINUTES = 30       # Minutos antes/depois do evento para não operar
NEWS_FILTER_CURRENCIES = ["USD", "EUR", "GBP"]  # Moedas para monitorar

# ============================================================================
# 🎯 FILTRO DE SESSÃO (KILLZONES) - Smart Money
# ============================================================================
# Só opera durante horários de alta liquidez e baixa manipulação.
# Baseado em conceitos de ICT/Smart Money.

USE_SESSION_FILTER = False       # ❌ DESATIVADO - ML + Score filtram melhor que horário

# Killzones (horário de Brasília - BRT) - AMPLIADAS para mais oportunidades
# London Killzone: Melhor liquidez europeia
KILLZONE_LONDON_START = time(4, 0)   # 04:00 BRT
KILLZONE_LONDON_END = time(8, 0)     # 08:00 BRT

# NY Killzone: Overlap Londres/NY - maior volume do dia
KILLZONE_NY_START = time(9, 30)      # 09:30 BRT
KILLZONE_NY_END = time(14, 0)        # 14:00 BRT ⬅️ ALTERADO de 13:00 (1h mais tarde)

# Minutos para evitar após abertura de sessão (manipulação)
AVOID_SESSION_OPEN_MINUTES = 15      # ⬅️ ALTERADO de 30 (menos tempo de espera)

# ============================================================================
# 💹 FILTRO DE SPREAD - Evita baixa liquidez
# ============================================================================
# Bloqueia trades quando spread está alto (indica manipulação/baixa liquidez)

USE_SPREAD_FILTER = True             # Ativa/desativa filtro de spread
MAX_SPREAD_MULTIPLIER = 2.0          # Bloqueia se spread > 2x a média
MAX_SPREAD_ABSOLUTE = 30             # Bloqueia se spread > 30 pontos (3 pips)
SPREAD_HISTORY_SIZE = 100            # Amostras para calcular média

# ============================================================================
# 📊 FILTRO ADX - Detecção de Tendência vs Range
# ============================================================================
# ADX (Average Directional Index) mede a FORÇA da tendência:
# - ADX < 15: Mercado LATERAL - NÃO OPERAR (trend following perde dinheiro)
# - ADX 15-20: Tendência FRACA - Cuidado
# - ADX 20-50: Tendência FORTE - Ideal para trend following
# - ADX > 50: Tendência MUITO FORTE - Pode estar no fim

USE_ADX_FILTER = False                # ❌ DESATIVADO - Modo Híbrido usa ADX internamente
ADX_PERIOD = 14
ADX_THRESHOLD = 15                   # Threshold baixo - deixa o Hybrid decidir
ADX_STRONG = 20                      # ADX 20+ = tendência
ADX_IGNORE_RSI_EXTREME = 40          # Só ignora RSI extremo se ADX > 40

# ============================================================================
# 🛡️ ANTI-STOP HUNT - SL Inteligente
# ============================================================================
# Evita que o SL seja colocado em níveis óbvios onde market makers caçam stops.

USE_ANTI_STOP_HUNT = True            # Ativa/desativa proteção anti-stop hunt
SL_BUFFER_PIPS = 5                   # Pips extras além do ATR (proteção adicional)
AVOID_ROUND_NUMBERS = True           # Evita SL em números redondos (X.XX00, X.XX50)
ROUND_NUMBER_BUFFER_PIPS = 3         # Distância mínima de números redondos
USE_SWING_SL = True                  # Usa swing high/low como referência para SL

# ============================================================================
# 📈 FILTRO DE VOLATILIDADE (ATR Percentil)
# ============================================================================
# Evita operar em momentos de volatilidade extrema.
# ATR muito baixo = mercado parado, spread come o lucro
# ATR muito alto = mercado caótico, stops atingidos facilmente

USE_VOLATILITY_FILTER = True         # Evita extremos de volatilidade
ATR_PERCENTILE_LOW = 10              # ⬅️ ALTERADO de 20 (aceita mercado mais calmo)
ATR_PERCENTILE_HIGH = 90             # ⬅️ ALTERADO de 80 (aceita mais volatilidade)
ATR_LOOKBACK = 100                   # Períodos para calcular percentil

# ============================================================================
# 📐 MARKET STRUCTURE (HH, HL, LH, LL)
# ============================================================================
# Detecta a estrutura real do mercado usando swing points.
# Só permite trades na direção da estrutura confirmada.
#
# Estrutura de ALTA: Higher Highs (HH) + Higher Lows (HL)
# Estrutura de BAIXA: Lower Highs (LH) + Lower Lows (LL)

USE_MARKET_STRUCTURE = True          # Ativa/desativa filtro de estrutura
SWING_LOOKBACK = 5                   # Candles para confirmar swing point
MIN_SWING_POINTS = 3                 # Mínimo de swings para determinar estrutura
STRUCTURE_AS_FILTER = False          # ⬅️ ALTERADO de True (não bloqueia, só adiciona ao score)

# ============================================================================
# 🎯 BREAK OF STRUCTURE (BOS) + PULLBACK - Smart Money
# ============================================================================
# Detecta rompimentos de estrutura e aguarda pullback para entrada.
# Técnica usada por traders institucionais para melhor preço de entrada.
#
# BOS Bullish: Preço rompe swing high anterior → aguarda pullback → BUY
# BOS Bearish: Preço rompe swing low anterior → aguarda pullback → SELL

USE_BOS_PULLBACK = True              # Mantém análise
BOS_PULLBACK_MIN = 0.1               # Mínimo de retração muito baixo (10%)
BOS_PULLBACK_MAX = 1.0               # Máximo de retração total
BOS_EXPIRY_BARS = 50                 # BOS expira após N candles
BOS_AS_FILTER = False                # NÃO FILTRA, só adiciona score
                                     # False = adiciona ao score

# ============================================================================
# 📦 ORDER BLOCKS - Smart Money (ICT)
# ============================================================================
# Order Blocks são zonas onde institucionais acumularam posições antes de
# um movimento forte. Quando o preço retorna a essas zonas, tende a reagir.
#
# Bullish OB: Último candle de BAIXA antes de impulso de ALTA
# Bearish OB: Último candle de ALTA antes de impulso de BAIXA

USE_ORDER_BLOCKS = True              # Ativa/desativa Order Blocks
OB_LOOKBACK = 50                     # Candles para buscar OBs
OB_MIN_IMPULSE_ATR = 1.5             # Impulso mínimo em múltiplos de ATR
OB_AS_FILTER = False                 # True = só entra em OB
                                     # False = adiciona ao score
OB_MITIGATION_PERCENT = 0.5          # % do OB para considerar "mitigado"
OB_MAX_AGE_BARS = 100                # OB expira após N candles

# --- Histórico e Multi-Timeframe ---
USE_HISTORY_MANAGER = True       # Usa gerenciador de histórico local
HISTORY_MONTHS = 6               # Meses de histórico para baixar/manter
USE_MTF_FILTER = False            # ❌ DESATIVADO - opera M1 puro
HIGHER_TIMEFRAME = mt5.TIMEFRAME_H1  # Timeframe maior para filtro de tendência

# --- Conversão para BRL ---
USD_TO_BRL = 6.10                 # Taxa de conversão USD -> BRL (atualize conforme necessário)

# ============================================================================
# 🛡️ MODO CONSERVADOR (CAPITAL BAIXO - $20-50)
# ============================================================================
# Ative este modo se você tem capital limitado. Ele prioriza SOBREVIVÊNCIA
# sobre lucro, usando configurações ultra-conservadoras.

CONSERVATIVE_MODE = False        # ❌ DESATIVADO - Bot é bom o suficiente, confia no sistema

# ============================================================================
# 🎮 MODO DEMO/TREINO (APENAS PARA CONTA DEMO!)
# ============================================================================
# Ative para treinar o bot mais rápido. NÃO USE EM CONTA REAL!

DEMO_TRAINING_MODE = False       # Modo real (mesmo em demo)
# 💰 CONFIGURADO PARA LUCRO - R$200 trabalhando FORTE

INITIAL_CAPITAL = 33.0           # Capital em USD (~R$200 / 6.10)

# Limites de proteção
MAX_DAILY_LOSS_PERCENT = 25.0    # Para se perder 25% no dia (R$50) - agressivo mas controlado
MAX_DAILY_TRADES = 20            # Até 20 trades por dia
FIXED_LOT_SIZE = 0.05            # Lote base maior

# Se CONSERVATIVE_MODE = True, estas configs são sobrescritas automaticamente:
# - VOLUME = 0.01 (fixo)
# - MAX_LOT_SIZE = 0.01
# - MAX_OPEN_POSITIONS = 1
# - MIN_SECONDS_BETWEEN_TRADES = 1800 (30 min)
# - ATR_MULTIPLIER_SL = 1.0 (SL mais apertado)
# - ATR_MULTIPLIER_TP = 2.0 (ratio 1:2)
# - USE_RSI_EXTREME_ENTRY = False (mais conservador)
# - AGGRESSIVE_MODE = False (nunca em capital baixo)

# --- Trailing Stop (Proteção de Lucro) ---
USE_TRAILING_STOP = True
TRAILING_TRIGGER_POINTS = 0.00100 # Começa a mover o stop após andar X pontos (10 pips)
TRAILING_STEP_POINTS = 0.00050    # Move o stop a cada Y pontos (5 pips)

# ============================================================================
# 🧠 SAÍDA INTELIGENTE - Sem Stop Loss Tradicional
# ============================================================================
# Em vez de sair automaticamente no prejuízo, o bot ESPERA o preço voltar.
# Só sai quando está no LUCRO ou após muito tempo negativo.
#
# Filosofia: O mercado oscila. Se entrou na direção certa, eventualmente volta.

USE_SMART_EXIT = True                # Ativa saída inteligente
SMART_EXIT_MIN_PROFIT_USD = 1.00     # 💰 Lucro mínimo $1.00 (~R$6) 
SMART_EXIT_MIN_PROFIT_BRL = 6.00     # Lucro mínimo em BRL
SMART_EXIT_WAIT_NEGATIVE_MINUTES = 20 # Espera 20 min
SMART_EXIT_EMERGENCY_LOSS_PERCENT = 20 # EMERGÊNCIA em 20% (R$40 máximo por trade)
SMART_EXIT_TAKE_PROFIT_ON_RECOVERY = True  # ✅ Sai quando recuperar

# Níveis de confiança para saída
SMART_EXIT_HIGH_CONFIDENCE_SCORE = 4   # 💰 Score 4+ = deixa correr até TP
SMART_EXIT_QUICK_PROFIT_PIPS = 5       # Sai com 5 pips se score baixo

# ============================================================================
# 💰 SIMULAÇÃO DE CAPITAL PEQUENO
# ============================================================================
# Para testar com capital limitado mesmo em conta demo grande.
# O bot vai calcular risco e lotes como se tivesse apenas esse valor.

USE_SIMULATED_CAPITAL = True         # ✅ ATIVADO - simula capital de R$200
SIMULATED_CAPITAL_BRL = 200.0        # Capital simulado em BRL (R$200)
SIMULATED_CAPITAL_USD = 33.0         # 🛡️ Capital simulado em USD (~$33 = R$200 / 6.10)

# --- Configurações Antigas (Backup) ---
STOP_LOSS_POINTS = 0.00100    
TAKE_PROFIT_POINTS = 0.00200
MAX_DAILY_LOSS = 50.0    
MAX_DAILY_GAIN = 100.0

# --- Horários de Negociação (Brasília) ---
# Forex roda 24h. Vamos deixar aberto.
START_TIME = time(0, 1)  
END_TIME = time(23, 59)   
FORCE_EXIT_TIME = time(23, 59)

# --- Estratégia ---
SMA_FAST = 9
SMA_SLOW = 21
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30


# ============================================================================
# 🔄 MEAN REVERSION - Para mercados laterais (ADX < 20)
# ============================================================================
# Quando o mercado está sem tendência, usa estratégia de reversão à média.
# Compra na banda inferior, vende na banda superior.

USE_MEAN_REVERSION = False           # ❌ DESATIVADO - modelo ML não foi treinado para MR
MR_BB_PERIOD = 20                    # Período das Bollinger Bands
MR_BB_STD = 2.0                      # Desvios padrão das bandas
MR_RSI_OVERSOLD = 30                 # RSI para compra
MR_RSI_OVERBOUGHT = 70               # RSI para venda
MR_ZSCORE_THRESHOLD = 2.0            # Z-Score para entrada
MR_MIN_SCORE = 4                     # Score mínimo para Mean Reversion (quando reativado)
MR_ADX_MAX = 20                      # ADX máximo para ativar Mean Reversion

# ============================================================================
# 🤖 MACHINE LEARNING FILTER - Filtro inteligente de sinais
# ============================================================================
# Usa histórico de trades para prever probabilidade de sucesso.
# Aprende com os resultados e melhora com o tempo.

USE_ML_FILTER = True                 # Ativa filtro de ML
ML_MIN_SAMPLES = 20                  # Mínimo de trades para ativar ML
ML_CONFIDENCE_THRESHOLD = 0.55       # Probabilidade mínima para operar (55%)
ML_USE_TIME_FILTER = True            # Considera hora do dia
ML_USE_VOLATILITY_FILTER = True      # Considera volatilidade
ML_HISTORY_FILE = "ml_trade_history.json"  # Arquivo de histórico

# ============================================================================
# 📊 MULTI-TIMEFRAME ANALYSIS - Confirmação com H1
# ============================================================================
# Confirma sinais do M1 com tendência do H1.
# Evita trades contra a tendência maior.

USE_MTF_ANALYSIS = True              # Ativa análise multi-timeframe
MTF_HIGHER_TF = mt5.TIMEFRAME_H1     # Timeframe maior (H1)
MTF_MIN_TREND_STRENGTH = 0.3         # Força mínima da tendência HTF
MTF_BLOCK_COUNTER_TREND = True       # Bloqueia trades contra tendência HTF

# ============================================================================
# 🎯 MODO HÍBRIDO - Combina Trend Following + Mean Reversion
# ============================================================================
# O bot escolhe automaticamente a estratégia baseado no ADX:
# - ADX >= 20: Usa Trend Following (estratégia atual)
# - ADX < 20: Usa Mean Reversion (nova estratégia)

USE_HYBRID_MODE = True               # Ativa modo híbrido automático
HYBRID_ADX_THRESHOLD = 20            # Limite para trocar de estratégia
