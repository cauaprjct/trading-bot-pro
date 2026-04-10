"""
Configuração Unificada para Trading de Criptomoedas
Suporta: BTC, ETH, SOL

O bot analisa os 3 ativos e executa ordem no que tiver melhor oportunidade.
"""

import MetaTrader5 as mt5
import os
from datetime import time

# --- Configurações da Conta ---
MT5_LOGIN = int(os.getenv("MT5_LOGIN")) if os.getenv("MT5_LOGIN") else None
MT5_PASSWORD = os.getenv("MT5_PASSWORD") if os.getenv("MT5_PASSWORD") else None
MT5_SERVER = os.getenv("MT5_SERVER") if os.getenv("MT5_SERVER") else None

# ============================================================================
# 🪙 ATIVOS CRYPTO - Configurações específicas por ativo
# ============================================================================
CRYPTO_ASSETS = {
    'BTCUSD-T': {
        'name': 'Bitcoin',
        'min_lot': 0.01,
        'max_lot': 0.1,
        'spread_max': 20000,      # ~$200 de spread máximo
        'atr_mult_sl': 2.5,
        'atr_mult_tp': 5.0,
        'priority': 1,            # Maior prioridade em empates
        'volatility': 'medium',
        'enabled': True,
    },
    'ETHUSD-T': {
        'name': 'Ethereum',
        'min_lot': 0.01,
        'max_lot': 0.5,
        'spread_max': 5000,       # ~$50 de spread máximo
        'atr_mult_sl': 3.0,       # Aumentado para dar mais espaço
        'atr_mult_tp': 6.0,       # Aumentado proporcionalmente
        'priority': 2,
        'volatility': 'medium',
        'enabled': True,
    },
    'SOLUSD-T': {
        'name': 'Solana',
        'min_lot': 0.1,
        'max_lot': 2.0,
        'spread_max': 500,        # ~$5 de spread máximo
        'atr_mult_sl': 3.0,       # Mais volátil, SL maior
        'atr_mult_tp': 6.0,
        'priority': 3,
        'volatility': 'high',
        'enabled': True,
    }
}

# Símbolo padrão (usado para compatibilidade)
SYMBOL = 'BTCUSD-T'
TIMEFRAME = mt5.TIMEFRAME_M1  # M1 para crypto
MAGIC_NUMBER = 20260110

# --- Gerenciamento de Risco ---
RISK_PER_TRADE_PERCENT = 0.5  # 0.5% por trade
VOLUME = 0.01
USE_ATR_FOR_SL = True
ATR_PERIOD = 14
ATR_MULTIPLIER_SL = 2.5       # Padrão, sobrescrito por ativo
ATR_MULTIPLIER_TP = 5.0

# --- Limites de Segurança ---
MAX_LOT_SIZE = 0.1
MAX_OPEN_POSITIONS = 1        # 1 posição TOTAL (entre todos os ativos)
MIN_SECONDS_BETWEEN_TRADES = 60
AGGRESSIVE_MODE = True        # Para testes
HEARTBEAT_INTERVAL = 30

# --- RSI ---
USE_RSI_EXTREME_ENTRY = True
RSI_EXTREME_OVERSOLD = 25
RSI_EXTREME_OVERBOUGHT = 75
RSI_MOMENTUM_SELL = 55
RSI_MOMENTUM_BUY = 45

# --- Sistema de Score ---
MIN_SIGNAL_SCORE = 3
USE_MACD_FILTER = True
USE_VOLUME_FILTER = False

# --- Estado ---
STATE_FILE = "bot_state_crypto.json"

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Filtros ---
USE_NEWS_FILTER = False
USE_SESSION_FILTER = False    # Crypto opera 24/7
USE_SPREAD_FILTER = True
MAX_SPREAD_MULTIPLIER = 3.0
MAX_SPREAD_ABSOLUTE = 20000   # Padrão, sobrescrito por ativo
SPREAD_HISTORY_SIZE = 100

# --- ADX ---
USE_ADX_FILTER = False
ADX_PERIOD = 14
ADX_THRESHOLD = 15
ADX_STRONG = 25
ADX_IGNORE_RSI_EXTREME = 30

# --- Anti-Stop Hunt ---
USE_ANTI_STOP_HUNT = True
SL_BUFFER_PIPS = 50
AVOID_ROUND_NUMBERS = True
ROUND_NUMBER_BUFFER_PIPS = 20
USE_SWING_SL = True

# --- Volatilidade ---
USE_VOLATILITY_FILTER = False
ATR_PERCENTILE_LOW = 0
ATR_PERCENTILE_HIGH = 100
ATR_LOOKBACK = 100

# --- Market Structure ---
USE_MARKET_STRUCTURE = True
SWING_LOOKBACK = 5
MIN_SWING_POINTS = 3
STRUCTURE_AS_FILTER = False

# --- BOS + Pullback ---
USE_BOS_PULLBACK = True
BOS_PULLBACK_MIN = 0.3
BOS_PULLBACK_MAX = 0.7
BOS_EXPIRY_BARS = 30
BOS_AS_FILTER = False

# --- Order Blocks ---
USE_ORDER_BLOCKS = True
OB_LOOKBACK = 50
OB_MIN_IMPULSE_ATR = 2.0
OB_AS_FILTER = False
OB_MITIGATION_PERCENT = 0.5
OB_MAX_AGE_BARS = 150

# --- Histórico ---
USE_HISTORY_MANAGER = True
HISTORY_MONTHS = 6
USE_MTF_FILTER = False
HIGHER_TIMEFRAME = mt5.TIMEFRAME_H1

# --- Conversão ---
USD_TO_BRL = 6.10

# --- Modo Conservador ---
CONSERVATIVE_MODE = False
DEMO_TRAINING_MODE = False
INITIAL_CAPITAL = 100000.0
MAX_DAILY_LOSS_PERCENT = 20.0
MAX_DAILY_TRADES = 10
FIXED_LOT_SIZE = 0.01

# --- Trailing Stop ---
USE_TRAILING_STOP = True
TRAILING_TRIGGER_POINTS = 100.0
TRAILING_STEP_POINTS = 50.0

# --- Saída Inteligente ---
USE_SMART_EXIT = True
SMART_EXIT_MIN_PROFIT_USD = 5.00
SMART_EXIT_MIN_PROFIT_BRL = 30.00
SMART_EXIT_WAIT_NEGATIVE_MINUTES = 60
SMART_EXIT_EMERGENCY_LOSS_PERCENT = 25
SMART_EXIT_TAKE_PROFIT_ON_RECOVERY = True
SMART_EXIT_HIGH_CONFIDENCE_SCORE = 7
SMART_EXIT_QUICK_PROFIT_PIPS = 20

# --- Capital Simulado ---
USE_SIMULATED_CAPITAL = True
SIMULATED_CAPITAL_BRL = 200.0
SIMULATED_CAPITAL_USD = 37.0

# --- Horários (24/7) ---
START_TIME = time(0, 1)
END_TIME = time(23, 59)
FORCE_EXIT_TIME = time(23, 59)

# --- Estratégia ---
SMA_FAST = 9
SMA_SLOW = 21
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# --- Mean Reversion ---
USE_MEAN_REVERSION = True
MR_BB_PERIOD = 20
MR_BB_STD = 2.5
MR_RSI_OVERSOLD = 25
MR_RSI_OVERBOUGHT = 75
MR_ZSCORE_THRESHOLD = 2.5
MR_MIN_SCORE = 3
MR_ADX_MAX = 20

# ============================================================================
# 🤖 ML FILTER UNIVERSAL
# ============================================================================
USE_ML_FILTER = True
ML_MODEL_PATH = "models/crypto_universal_lgbm.pkl"
ML_CONFIDENCE_THRESHOLD = 0.40
ML_FALLBACK_TO_SCORE = True
ML_LOG_PREDICTIONS = True
ML_AUTO_TRAIN = True
ML_RETRAIN_DAYS = 7

# Mapeamento de símbolos para IDs (usado no modelo ML)
SYMBOL_ID_MAP = {
    'BTCUSD-T': 0,
    'ETHUSD-T': 1,
    'SOLUSD-T': 2,
}

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

# ============================================================================
# 🔄 CRYPTO SELECTOR - Configurações de seleção
# ============================================================================
# Peso de cada fator na seleção
SELECTOR_ML_WEIGHT = 0.5      # Peso do ML na decisão
SELECTOR_SCORE_WEIGHT = 0.3   # Peso do score de sinal
SELECTOR_SPREAD_WEIGHT = 0.2  # Peso do spread (menor = melhor)

# Threshold mínimo para considerar oportunidade
SELECTOR_MIN_COMBINED_SCORE = 0.3

# Se True, só opera se ML aprovar
SELECTOR_REQUIRE_ML_APPROVAL = True
