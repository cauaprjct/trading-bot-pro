"""
Configuração para operar BTCUSD nos fins de semana (24/7)
Crypto é mais volátil que Forex - configurações ajustadas para isso.
"""

import MetaTrader5 as mt5
import os
from datetime import time

# --- Configurações da Conta ---
MT5_LOGIN = int(os.getenv("MT5_LOGIN")) if os.getenv("MT5_LOGIN") else None
MT5_PASSWORD = os.getenv("MT5_PASSWORD") if os.getenv("MT5_PASSWORD") else None
MT5_SERVER = os.getenv("MT5_SERVER") if os.getenv("MT5_SERVER") else None

# --- Configurações do Ativo ---
SYMBOL = "BTCUSD-T"  # Bitcoin vs USD CFD
TIMEFRAME = mt5.TIMEFRAME_M1  # M1 conforme solicitado
VOLUME = 0.01      # Lote mínimo para BTC (crypto é caro)
MAGIC_NUMBER = 20240102  # Diferente do bot de Forex

# --- Gerenciamento de Risco (CONSERVADOR para Crypto) ---
RISK_PER_TRADE_PERCENT = 0.5  # 0.5% por trade (crypto é volátil!)
USE_ATR_FOR_SL = True
ATR_PERIOD = 14
ATR_MULTIPLIER_SL = 2.5       # SL maior para crypto
ATR_MULTIPLIER_TP = 5.0       # TP maior (ratio 1:2)

# --- Limites de Segurança ---
MAX_LOT_SIZE = 0.1            # Máximo 0.1 lote em BTC
MAX_OPEN_POSITIONS = 1        # 1 posição por vez
MIN_SECONDS_BETWEEN_TRADES = 60   # 1 minuto entre trades (era 2)
AGGRESSIVE_MODE = True        # TESTE: Entra sem esperar cruzamento
HEARTBEAT_INTERVAL = 30

# --- RSI Extremo (ajustado para crypto) ---
USE_RSI_EXTREME_ENTRY = True
RSI_EXTREME_OVERSOLD = 25     # Crypto cai mais forte
RSI_EXTREME_OVERBOUGHT = 75   # Crypto sobe mais forte

# --- Sistema de Score ---
MIN_SIGNAL_SCORE = 3          # Score 3/9 (reduzido para demo/teste)
USE_MACD_FILTER = True
USE_VOLUME_FILTER = False     # Volume em crypto CFD não é confiável
RSI_MOMENTUM_SELL = 55
RSI_MOMENTUM_BUY = 45

# --- Reconexão ---
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY_SECONDS = 10

# --- Estado ---
STATE_FILE = "bot_state_btc.json"

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8398006198:AAF9Ss9DW9t7Xp-fKH2QEXO7LsL5enRzWdE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-5153173676")

# --- Filtro de Notícias ---
USE_NEWS_FILTER = False       # Crypto não liga muito para notícias tradicionais

# ============================================================================
# 🎯 FILTRO DE SESSÃO - DESATIVADO (Crypto opera 24/7)
# ============================================================================
USE_SESSION_FILTER = False    # ❌ Desativado para operar fins de semana

KILLZONE_LONDON_START = time(0, 0)
KILLZONE_LONDON_END = time(23, 59)
KILLZONE_NY_START = time(0, 0)
KILLZONE_NY_END = time(23, 59)
AVOID_SESSION_OPEN_MINUTES = 0

# ============================================================================
# 💹 FILTRO DE SPREAD - Importante para Crypto
# ============================================================================
USE_SPREAD_FILTER = True
MAX_SPREAD_MULTIPLIER = 3.0   # Crypto tem spread maior
MAX_SPREAD_ABSOLUTE = 20000   # 20000 pontos (~$200 em BTC) - ajustado para crypto
SPREAD_HISTORY_SIZE = 100

# ============================================================================
# 📊 FILTRO ADX - DESATIVADO para teste
# ============================================================================
USE_ADX_FILTER = False        # Desativado para operar mais
ADX_PERIOD = 14
ADX_THRESHOLD = 10            # Reduzido
ADX_STRONG = 20
ADX_IGNORE_RSI_EXTREME = 30

# ============================================================================
# 🛡️ ANTI-STOP HUNT - Muito importante para Crypto
# ============================================================================
USE_ANTI_STOP_HUNT = True
SL_BUFFER_PIPS = 50           # 50 pips extras (crypto tem wicks grandes)
AVOID_ROUND_NUMBERS = True
ROUND_NUMBER_BUFFER_PIPS = 20 # Evita números como 90000, 91000, etc.
USE_SWING_SL = True

# ============================================================================
# 📈 FILTRO DE VOLATILIDADE - DESATIVADO para teste
# ============================================================================
USE_VOLATILITY_FILTER = False  # Desativado para operar mais
ATR_PERCENTILE_LOW = 0
ATR_PERCENTILE_HIGH = 100
ATR_LOOKBACK = 100

# ============================================================================
# 📐 MARKET STRUCTURE - Não filtra, só analisa
# ============================================================================
USE_MARKET_STRUCTURE = True
SWING_LOOKBACK = 5
MIN_SWING_POINTS = 3
STRUCTURE_AS_FILTER = False   # Não bloqueia trades

# ============================================================================
# 🎯 BOS + PULLBACK
# ============================================================================
USE_BOS_PULLBACK = True
BOS_PULLBACK_MIN = 0.3
BOS_PULLBACK_MAX = 0.7
BOS_EXPIRY_BARS = 30          # Mais tempo para crypto
BOS_AS_FILTER = False

# ============================================================================
# 📦 ORDER BLOCKS
# ============================================================================
USE_ORDER_BLOCKS = True
OB_LOOKBACK = 50
OB_MIN_IMPULSE_ATR = 2.0      # Impulso maior para crypto
OB_AS_FILTER = False
OB_MITIGATION_PERCENT = 0.5
OB_MAX_AGE_BARS = 150

# --- Histórico ---
USE_HISTORY_MANAGER = True
HISTORY_MONTHS = 6            # 6 meses de histórico (era 3) - melhora ML
USE_MTF_FILTER = False
HIGHER_TIMEFRAME = mt5.TIMEFRAME_H1

# --- Conversão ---
USD_TO_BRL = 6.10

# ============================================================================
# 🛡️ MODO CONSERVADOR
# ============================================================================
CONSERVATIVE_MODE = False
DEMO_TRAINING_MODE = False
INITIAL_CAPITAL = 100000.0
MAX_DAILY_LOSS_PERCENT = 20.0  # 20% máximo para crypto
MAX_DAILY_TRADES = 10
FIXED_LOT_SIZE = 0.01

# --- Trailing Stop ---
USE_TRAILING_STOP = True
TRAILING_TRIGGER_POINTS = 100.0  # Começa após $100 de lucro
TRAILING_STEP_POINTS = 50.0      # Move a cada $50

# ============================================================================
# 🧠 SAÍDA INTELIGENTE
# ============================================================================
USE_SMART_EXIT = True
SMART_EXIT_MIN_PROFIT_USD = 5.00    # Mínimo $5 para sair (crypto move mais)
SMART_EXIT_MIN_PROFIT_BRL = 30.00
SMART_EXIT_WAIT_NEGATIVE_MINUTES = 60  # 1 hora de paciência
SMART_EXIT_EMERGENCY_LOSS_PERCENT = 25
SMART_EXIT_TAKE_PROFIT_ON_RECOVERY = True
SMART_EXIT_HIGH_CONFIDENCE_SCORE = 7
SMART_EXIT_QUICK_PROFIT_PIPS = 20

# ============================================================================
# 💰 SIMULAÇÃO DE CAPITAL
# ============================================================================
USE_SIMULATED_CAPITAL = True
SIMULATED_CAPITAL_BRL = 200.0
SIMULATED_CAPITAL_USD = 37.0

# --- Configurações Antigas ---
STOP_LOSS_POINTS = 200.0      # $200 de SL em BTC
TAKE_PROFIT_POINTS = 400.0    # $400 de TP
MAX_DAILY_LOSS = 50.0
MAX_DAILY_GAIN = 200.0

# --- Horários (24/7 para crypto) ---
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
# 🔄 MEAN REVERSION
# ============================================================================
USE_MEAN_REVERSION = True
MR_BB_PERIOD = 20
MR_BB_STD = 2.5               # Bandas mais largas para crypto
MR_RSI_OVERSOLD = 25
MR_RSI_OVERBOUGHT = 75
MR_ZSCORE_THRESHOLD = 2.5
MR_MIN_SCORE = 3
MR_ADX_MAX = 20

# ============================================================================
# 🤖 ML FILTER (LightGBM) - Threshold reduzido para teste
# ============================================================================
USE_ML_FILTER = True
ML_MODEL_PATH = "models/btcusd_t_lgbm.pkl"
ML_CONFIDENCE_THRESHOLD = 0.35              # Reduzido para operar mais
ML_FALLBACK_TO_SCORE = True
ML_LOG_PREDICTIONS = True
ML_AUTO_TRAIN = True
ML_RETRAIN_DAYS = 7

# ============================================================================
# 📊 MULTI-TIMEFRAME
# ============================================================================
USE_MTF_ANALYSIS = True
MTF_HIGHER_TF = mt5.TIMEFRAME_H1
MTF_MIN_TREND_STRENGTH = 0.3
MTF_BLOCK_COUNTER_TREND = True

# ============================================================================
# 🎯 MODO HÍBRIDO
# ============================================================================
USE_HYBRID_MODE = True
HYBRID_ADX_THRESHOLD = 20
