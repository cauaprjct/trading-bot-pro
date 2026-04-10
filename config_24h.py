# ============================================================================
# 🌍 CONFIGURAÇÃO BOT 24H - MULTI-SESSÃO INTELIGENTE
# ============================================================================
# Opera 24 horas com configurações que se adaptam automaticamente a cada sessão.
#
# SESSÕES (horário BRT):
# ┌─────────────────┬───────────────┬──────────────┬─────────────────────────┐
# │ Sessão          │ Horário BRT   │ Par Ideal    │ Qualidade               │
# ├─────────────────┼───────────────┼──────────────┼─────────────────────────┤
# │ 🌅 Tokyo+London │ 05:00 - 06:00 │ EUR/JPY      │ 🟡 BOM (overlap)        │
# │ 🇬🇧 London      │ 06:00 - 10:00 │ EUR/USD      │ 🟢 MUITO BOM            │
# │ 🔥 London+NY    │ 10:00 - 13:00 │ EUR/USD      │ 🟢 MELHOR (70% volume!) │
# │ 🇺🇸 New York    │ 13:00 - 17:00 │ EUR/USD      │ 🟢 MUITO BOM            │
# │ 🌆 NY Close     │ 17:00 - 19:00 │ EUR/USD      │ 🟡 MODERADO             │
# │ 🌏 Sydney       │ 19:00 - 21:00 │ AUD/USD      │ 🟡 MODERADO             │
# │ 🎯 Tokyo KZ     │ 21:00 - 00:00 │ USD/JPY      │ 🟢 BOM (melhor asiática)│
# │ 🌙 Tokyo+Sydney │ 00:00 - 04:00 │ USD/JPY      │ 🟢 BOM (overlap)        │
# │ 🌅 Pre-London   │ 04:00 - 05:00 │ EUR/USD      │ 🟡 MODERADO             │
# └─────────────────┴───────────────┴──────────────┴─────────────────────────┘
# ============================================================================

from config import *  # Importa todas as configurações base
from datetime import time, datetime
import pytz

# --- Estado separado para 24h ---
STATE_FILE = "bot_state_24h.json"

# ============================================================================
# 🎯 SESSÃO FILTER DESLIGADO - Opera 24h
# ============================================================================
USE_SESSION_FILTER = False  # Opera sempre!

# ============================================================================
# 🧠 SISTEMA INTELIGENTE DE SESSÕES
# ============================================================================

class TradingSession:
    """Enum das sessões de trading"""
    TOKYO_LONDON_OVERLAP = "TOKYO_LONDON"     # 05:00-06:00
    LONDON = "LONDON"                          # 06:00-10:00
    LONDON_NY_OVERLAP = "LONDON_NY"           # 10:00-13:00 (MELHOR!)
    NEW_YORK = "NEW_YORK"                      # 13:00-17:00
    NY_CLOSE = "NY_CLOSE"                      # 17:00-19:00
    SYDNEY = "SYDNEY"                          # 19:00-21:00
    TOKYO_KILLZONE = "TOKYO_KZ"               # 21:00-00:00
    TOKYO_SYDNEY_OVERLAP = "TOKYO_SYDNEY"     # 00:00-04:00
    PRE_LONDON = "PRE_LONDON"                 # 04:00-05:00

# Configurações por sessão
SESSION_CONFIGS = {
    TradingSession.TOKYO_LONDON_OVERLAP: {
        "name": "🌅 Tokyo + London Overlap",
        "hours": "05:00 - 06:00 BRT",
        "symbol": "EURJPY-T",
        "description": "Overlap Tokyo/London - bom para pares JPY/EUR",
        "min_signal_score": 3,
        "use_trailing_stop": True,
        "trailing_trigger": 0.00100,  # 10 pips EUR
        "trailing_step": 0.00050,
        "sl_pips": 15,
        "tp_pips": 30,
        "aggressiveness": "normal",
        "quality": "🟡 BOM",
        "emoji": "🌅"
    },
    TradingSession.LONDON: {
        "name": "🇬🇧 London Session",
        "hours": "06:00 - 10:00 BRT",
        "symbol": "EURUSD-T",
        "description": "Scalping rápido - Alta liquidez",
        "min_signal_score": 2,
        "use_trailing_stop": True,
        "trailing_trigger": 0.00030,  # 3 pips (começa a proteger rápido)
        "trailing_step": 0.00020,     # 2 pips
        "sl_pips": 10,                # Stop curto
        "tp_pips": 10,                # Alvo curto (Scalping)
        "aggressiveness": "muito_agressivo",
        "quality": "🟢 MUITO BOM",
        "emoji": "🇬🇧"
    },
    TradingSession.LONDON_NY_OVERLAP: {
        "name": "🔥 London + NY Overlap",
        "hours": "10:00 - 13:00 BRT",
        "symbol": "EURUSD-T",
        "description": "Scalping Turbo - Volume Máximo",
        "min_signal_score": 2,
        "use_trailing_stop": True,
        "trailing_trigger": 0.00030,
        "trailing_step": 0.00020,
        "sl_pips": 10,
        "tp_pips": 10,                # Alvo curto
        "aggressiveness": "muito_agressivo",
        "quality": "🟢 MELHOR",
        "emoji": "🔥"
    },
    TradingSession.NEW_YORK: {
        "name": "🇺🇸 New York Session",
        "hours": "13:00 - 17:00 BRT",
        "symbol": "EURUSD-T",
        "description": "Scalping Agressivo - NY",
        "min_signal_score": 2,
        "use_trailing_stop": True,
        "trailing_trigger": 0.00030,
        "trailing_step": 0.00020,
        "sl_pips": 10,
        "tp_pips": 10,
        "aggressiveness": "muito_agressivo",
        "quality": "🟢 MUITO BOM",
        "emoji": "🇺🇸"
    },
    TradingSession.NY_CLOSE: {
        "name": "🌆 NY Close",
        "hours": "17:00 - 19:00 BRT",
        "symbol": "EURUSD-T",
        "description": "Scalping de Fim de Tarde",
        "min_signal_score": 2,
        "use_trailing_stop": True,
        "trailing_trigger": 0.00030,
        "trailing_step": 0.00020,
        "sl_pips": 12,
        "tp_pips": 8,                 # Alvo menor (mercado lento)
        "aggressiveness": "agressivo",
        "quality": "🟡 MODERADO",
        "emoji": "🌆"
    },
    TradingSession.SYDNEY: {
        "name": "🌏 Sydney Session",
        "hours": "19:00 - 21:00 BRT",
        "symbol": "AUDUSD-T",
        "description": "Scalping Noturno - AUD",
        "min_signal_score": 2,
        "use_trailing_stop": True,
        "trailing_trigger": 0.00040,
        "trailing_step": 0.00020,
        "sl_pips": 15,
        "tp_pips": 10,
        "aggressiveness": "agressivo",
        "quality": "🟡 MODERADO",
        "emoji": "🌏"
    },
    TradingSession.TOKYO_KILLZONE: {
        "name": "🎯 Tokyo Killzone",
        "hours": "21:00 - 00:00 BRT",
        "symbol": "USDJPY-T",
        "description": "Scalping Asiático - JPY",
        "min_signal_score": 2,
        "use_trailing_stop": True,   # LIGADO AGORA
        "trailing_trigger": 0.050,   # 5 pips (USDJPY tem escala diferente)
        "trailing_step": 0.020,      # 2 pips
        "sl_pips": 15,               # 15 pips
        "tp_pips": 15,               # 15 pips (Alvo curto)
        "aggressiveness": "agressivo",
        "quality": "🟢 BOM",
        "emoji": "🎯"
    },
    TradingSession.TOKYO_SYDNEY_OVERLAP: {
        "name": "🌙 Tokyo + Sydney Overlap",
        "hours": "00:00 - 04:00 BRT",
        "symbol": "USDJPY-T",
        "description": "Overlap asiático - liquidez moderada",
        "min_signal_score": 3,
        "use_trailing_stop": False,
        "trailing_trigger": 0.150,   # 15 pips para USDJPY
        "trailing_step": 0.080,      # 8 pips
        "sl_pips": 30,               # 30 pips (maior que spread de ~10)
        "tp_pips": 60,               # 60 pips (ratio 1:2)
        "aggressiveness": "seletivo",
        "quality": "🟢 BOM",
        "emoji": "🌙"
    },
    TradingSession.PRE_LONDON: {
        "name": "🌅 Pre-London",
        "hours": "04:00 - 05:00 BRT",
        "symbol": "EURUSD-T",
        "description": "Preparação para London - transição",
        "min_signal_score": 4,
        "use_trailing_stop": True,
        "trailing_trigger": 0.00150,
        "trailing_step": 0.00070,
        "sl_pips": 20,
        "tp_pips": 35,
        "aggressiveness": "conservador",
        "quality": "🟡 MODERADO",
        "emoji": "🌅"
    }
}

def get_current_session() -> str:
    """Retorna a sessão atual baseada no horário BRT."""
    tz = pytz.timezone("America/Sao_Paulo")
    now = datetime.now(tz)
    hour = now.hour
    
    if 5 <= hour < 6:
        return TradingSession.TOKYO_LONDON_OVERLAP
    elif 6 <= hour < 10:
        return TradingSession.LONDON
    elif 10 <= hour < 13:
        return TradingSession.LONDON_NY_OVERLAP
    elif 13 <= hour < 17:
        return TradingSession.NEW_YORK
    elif 17 <= hour < 19:
        return TradingSession.NY_CLOSE
    elif 19 <= hour < 21:
        return TradingSession.SYDNEY
    elif 21 <= hour <= 23:
        return TradingSession.TOKYO_KILLZONE
    elif 0 <= hour < 4:
        return TradingSession.TOKYO_SYDNEY_OVERLAP
    else:  # 4-5
        return TradingSession.PRE_LONDON

def get_session_config(session: str = None) -> dict:
    """Retorna a configuração para a sessão especificada ou atual."""
    if session is None:
        session = get_current_session()
    return SESSION_CONFIGS.get(session, SESSION_CONFIGS[TradingSession.LONDON])

def get_current_symbol() -> str:
    """Retorna o símbolo ideal para a sessão atual."""
    config = get_session_config()
    return config["symbol"]

def get_dynamic_params() -> dict:
    """Retorna parâmetros dinâmicos baseados na sessão atual."""
    config = get_session_config()
    return {
        "SYMBOL": config["symbol"],
        "MIN_SIGNAL_SCORE": config["min_signal_score"],
        "USE_TRAILING_STOP": config["use_trailing_stop"],
        "TRAILING_TRIGGER_POINTS": config["trailing_trigger"],
        "TRAILING_STEP_POINTS": config["trailing_step"],
        "STOP_LOSS_PIPS": config["sl_pips"],
        "TAKE_PROFIT_PIPS": config["tp_pips"],
    }

def print_session_status():
    """Imprime o status da sessão atual."""
    session = get_current_session()
    config = get_session_config(session)
    
    print(f"\n{'='*65}")
    print(f"{config['emoji']} SESSÃO ATUAL: {config['name']}")
    print(f"{'='*65}")
    print(f"⏰ Horário: {config['hours']}")
    print(f"💹 Par: {config['symbol']}")
    print(f"📝 {config['description']}")
    print(f"📊 Qualidade: {config['quality']}")
    print(f"🎚️  Agressividade: {config['aggressiveness']}")
    print(f"📈 Score mínimo: {config['min_signal_score']}/9")
    print(f"🛡️ SL: {config['sl_pips']} pips | TP: {config['tp_pips']} pips")
    print(f"📍 Trailing: {'ON' if config['use_trailing_stop'] else 'OFF'}")
    print(f"{'='*65}\n")

def print_full_schedule():
    """Imprime o cronograma completo de 24h."""
    print("\n" + "="*70)
    print("🌍 CRONOGRAMA 24H - MULTI-SESSÃO INTELIGENTE")
    print("="*70)
    print()
    print("┌─────────────────┬───────────────┬──────────────┬─────────────────┐")
    print("│ Sessão          │ Horário BRT   │ Par          │ Qualidade       │")
    print("├─────────────────┼───────────────┼──────────────┼─────────────────┤")
    for session_key, config in SESSION_CONFIGS.items():
        name = config['name'][:15].ljust(15)
        hours = config['hours'].ljust(13)
        symbol = config['symbol'].ljust(12)
        quality = config['quality'].ljust(15)
        print(f"│ {name} │ {hours} │ {symbol} │ {quality} │")
    print("└─────────────────┴───────────────┴──────────────┴─────────────────┘")
    print()

# ============================================================================
# 📊 PARÂMETROS BASE (serão sobrescritos dinamicamente)
# ============================================================================
# Valores padrão - o run_24h.py vai ajustar em tempo real

SYMBOL = "EURUSD-T"           # Padrão, muda por sessão
MIN_SIGNAL_SCORE = 2          # Padrão, muda por sessão

# --- Filtros ---
USE_MTF_FILTER = False
USE_ADX_FILTER = False        # Desligado para mais trades
STRUCTURE_AS_FILTER = False
BOS_AS_FILTER = False
OB_AS_FILTER = False

# --- RSI ---
USE_RSI_EXTREME_ENTRY = True
RSI_EXTREME_OVERSOLD = 35
RSI_EXTREME_OVERBOUGHT = 65

# --- Trailing (padrão EUR) ---
USE_TRAILING_STOP = True
TRAILING_TRIGGER_POINTS = 0.00150
TRAILING_STEP_POINTS = 0.00050

# --- Risk ---
ATR_MULTIPLIER_SL = 1.5
ATR_MULTIPLIER_TP = 2.5
MAX_SPREAD_ABSOLUTE = 30

# --- Smart Exit ---
SMART_EXIT_MIN_PROFIT = 1.50         # Sai assim que passar de $1.50 (garante o lucro mínimo)
SMART_EXIT_MIN_PROFIT_USD = 1.50     # Igual
SMART_EXIT_TAKE_PROFIT_ON_RECOVERY = True # LIGADO DE NOVO - Saiu do vermelho pro verde? FECHA!
SMART_EXIT_WAIT_NEGATIVE_MINUTES = 45

# --- Operação ---
MAX_OPEN_POSITIONS = 1
MIN_SECONDS_BETWEEN_TRADES = 60
VOLUME = 0.1

# ============================================================================
# 📝 NOTAS
# ============================================================================
# O bot 24h troca automaticamente de par conforme a sessão:
# - EUR/USD: 04:00-19:00 (sessões europeias/americanas)
# - AUD/USD: 19:00-21:00 (Sydney)
# - USD/JPY: 21:00-04:00 (Tokyo)
# 
# Melhores horários: 10:00-13:00 (London+NY overlap) = 70% do volume!
# ============================================================================

# Mostra status ao carregar
print_session_status()
