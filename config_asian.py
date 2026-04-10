# ============================================================================
# 🌙 CONFIGURAÇÃO BOT NOTURNO - SESSÃO ASIÁTICA v2.0
# ============================================================================
# Configurado com base em análise detalhada do mercado asiático (Grok Research)
#
# CARACTERÍSTICAS DO MERCADO ASIÁTICO:
# - Volatilidade: 30-60 pips/dia (50% menor que NY/London)
# - Movimentos: LENTOS e previsíveis, tendência a RANGES
# - Spread USD/JPY: 0.1-0.3 pips (muito baixo)
# - ATR médio: ~30 pips
# - Melhor estratégia: RANGE TRADING (não trend following!)
#
# PERÍODOS (horário BRT):
# ┌─────────────────┬───────────────┬─────────────────────────────────────┐
# │ Período         │ Horário       │ Característica                      │
# ├─────────────────┼───────────────┼─────────────────────────────────────┤
# │ 🌅 SYDNEY       │ 19:00 - 21:00 │ EVITAR - baixa liquidez, gaps       │
# │ 🎯 TOKYO KZ     │ 21:00 - 00:00 │ MELHOR MOMENTO - pico de liquidez   │
# │ 🌙 TOKYO LATE   │ 00:00 - 03:00 │ OK - liquidez moderada              │
# │ ⚠️ EVITAR       │ 03:00 - 05:00 │ EVITAR - volume cai drasticamente   │
# └─────────────────┴───────────────┴─────────────────────────────────────┘
# ============================================================================

from config import *  # Importa todas as configurações base
from datetime import time, datetime
import pytz

# --- Override do Ativo ---
SYMBOL = "USDJPY-T"  # Par principal da sessão asiática (melhor risco/retorno)
STATE_FILE = "bot_state_asian.json"  # Estado separado

# ============================================================================
# 🎯 KILLZONE ASIÁTICA - APENAS HORÁRIOS BOM
# ============================================================================
# Grok recomenda: Operar 21:00-03:00, EVITAR 19:00-21:00 e 03:00-05:00
USE_SESSION_FILTER = True

# Killzone otimizada: 21:00 - 03:00 BRT (melhor liquidez)
KILLZONE_LONDON_START = time(21, 0)   # 21:00 BRT - Tokyo Open
KILLZONE_LONDON_END = time(23, 59)    # 23:59 BRT

# Continuação após meia-noite
KILLZONE_NY_START = time(0, 0)        # 00:00 BRT
KILLZONE_NY_END = time(3, 0)          # 03:00 BRT - Para antes da queda de liquidez

# ============================================================================
# 🧠 SISTEMA INTELIGENTE DE PERÍODOS
# ============================================================================

class AsianPeriod:
    """Enum dos períodos da sessão asiática"""
    SYDNEY_WARMUP = "SYDNEY_WARMUP"      # 19:00-21:00 - EVITAR
    TOKYO_KILLZONE = "TOKYO_KILLZONE"    # 21:00-00:00 - MELHOR
    TOKYO_LATE = "TOKYO_LATE"            # 00:00-03:00 - BOM
    LOW_LIQUIDITY = "LOW_LIQUIDITY"      # 03:00-05:00 - EVITAR
    OUTSIDE = "OUTSIDE"                   # Fora da sessão

# Configurações por período (baseado em Grok Research)
PERIOD_CONFIGS = {
    AsianPeriod.SYDNEY_WARMUP: {
        "name": "🌅 Sydney Warmup",
        "description": "⚠️ EVITAR - Baixa liquidez, risco de gaps",
        "min_signal_score": 5,        # Alto para evitar trades
        "adx_threshold": 25,
        "adx_strong": 30,
        "atr_percentile_low": 20,
        "atr_percentile_high": 80,
        "max_spread_multiplier": 1.5,
        "preferred_pairs": ["AUDUSD", "NZDUSD"],
        "aggressiveness": "evitar",
        "emoji": "🌅"
    },
    AsianPeriod.TOKYO_KILLZONE: {
        "name": "🎯 Tokyo Killzone",
        "description": "✅ MELHOR MOMENTO - Pico de liquidez JPY",
        "min_signal_score": 3,        # Mais agressivo no melhor horário
        "adx_threshold": 20,
        "adx_strong": 25,
        "atr_percentile_low": 10,
        "atr_percentile_high": 90,
        "max_spread_multiplier": 3.0,
        "preferred_pairs": ["USDJPY", "EURJPY", "GBPJPY"],
        "aggressiveness": "normal",
        "emoji": "🎯"
    },
    AsianPeriod.TOKYO_LATE: {
        "name": "🌙 Tokyo Late",
        "description": "✅ BOM - Liquidez moderada, ser seletivo",
        "min_signal_score": 4,
        "adx_threshold": 22,
        "adx_strong": 28,
        "atr_percentile_low": 15,
        "atr_percentile_high": 85,
        "max_spread_multiplier": 2.5,
        "preferred_pairs": ["USDJPY", "AUDJPY"],
        "aggressiveness": "seletivo",
        "emoji": "🌙"
    },
    AsianPeriod.LOW_LIQUIDITY: {
        "name": "⚠️ Baixa Liquidez",
        "description": "❌ EVITAR - Volume cai drasticamente",
        "min_signal_score": 6,        # Praticamente não opera
        "adx_threshold": 30,
        "adx_strong": 35,
        "atr_percentile_low": 25,
        "atr_percentile_high": 75,
        "max_spread_multiplier": 1.0,
        "preferred_pairs": [],
        "aggressiveness": "bloqueado",
        "emoji": "⚠️"
    },
    AsianPeriod.OUTSIDE: {
        "name": "❌ Fora da Sessão",
        "description": "Aguardando sessão asiática (21:00 BRT)",
        "min_signal_score": 6,
        "adx_threshold": 30,
        "adx_strong": 35,
        "atr_percentile_low": 25,
        "atr_percentile_high": 75,
        "max_spread_multiplier": 1.0,
        "preferred_pairs": [],
        "aggressiveness": "bloqueado",
        "emoji": "❌"
    }
}

def get_current_asian_period() -> str:
    """Retorna o período atual da sessão asiática."""
    tz = pytz.timezone("America/Sao_Paulo")
    now = datetime.now(tz)
    hour = now.hour
    
    if 19 <= hour < 21:
        return AsianPeriod.SYDNEY_WARMUP      # EVITAR
    elif 21 <= hour <= 23:
        return AsianPeriod.TOKYO_KILLZONE     # MELHOR
    elif 0 <= hour < 3:
        return AsianPeriod.TOKYO_LATE         # BOM
    elif 3 <= hour < 5:
        return AsianPeriod.LOW_LIQUIDITY      # EVITAR
    else:
        return AsianPeriod.OUTSIDE

def get_period_config(period: str = None) -> dict:
    """Retorna a configuração para o período especificado ou atual."""
    if period is None:
        period = get_current_asian_period()
    return PERIOD_CONFIGS.get(period, PERIOD_CONFIGS[AsianPeriod.OUTSIDE])

def get_dynamic_params() -> dict:
    """Retorna parâmetros dinâmicos baseados no período atual."""
    config = get_period_config()
    return {
        "MIN_SIGNAL_SCORE": config["min_signal_score"],
        "ADX_THRESHOLD": config["adx_threshold"],
        "ADX_STRONG": config["adx_strong"],
        "ATR_PERCENTILE_LOW": config["atr_percentile_low"],
        "ATR_PERCENTILE_HIGH": config["atr_percentile_high"],
        "MAX_SPREAD_MULTIPLIER": config["max_spread_multiplier"],
    }

def print_period_status():
    """Imprime o status do período atual."""
    period = get_current_asian_period()
    config = get_period_config(period)
    
    print(f"\n{'='*65}")
    print(f"{config['emoji']} PERÍODO ATUAL: {config['name']}")
    print(f"{'='*65}")
    print(f"📝 {config['description']}")
    print(f"🎚️  Agressividade: {config['aggressiveness']}")
    print(f"📊 Score mínimo: {config['min_signal_score']}/9")
    print(f"📈 ADX mínimo: {config['adx_threshold']}")
    print(f"💹 Pares ideais: {', '.join(config['preferred_pairs']) if config['preferred_pairs'] else 'Nenhum'}")
    print(f"{'='*65}\n")

# ============================================================================
# 📊 PARÂMETROS OTIMIZADOS PARA SESSÃO ASIÁTICA
# ============================================================================
# Baseado em Grok Research:
# - Mercado é RANGE-BOUND (lateral), não trend following
# - RSI extremo é CONFIÁVEL em ranges
# - ADX mínimo 25-30 para confirmar trends (raros)
# - Trailing stop NÃO recomendado (preço anda devagar)

# --- Score e Confirmações ---
# Grok: "Score mínimo mais alto (3-4) na asiática devido à baixa liquidez"
MIN_SIGNAL_SCORE = 3          # Score mínimo 3/9 no melhor horário

# --- ADX - Filtro de Tendência ---
# Grok: "ADX mínimo de 25-30 para confirmar trends, mercado é mais lateral"
ADX_THRESHOLD = 20            # ADX mínimo para considerar tendência
ADX_STRONG = 25               # ADX considerado forte (trends são raros!)
USE_ADX_FILTER = False        # DESLIGADO - mercado asiático é lateral!

# --- Volatilidade ---
# Grok: "ATR médio ~30 pips na sessão asiática"
ATR_PERCENTILE_LOW = 10       # Aceita volatilidade baixa (normal na asiática)
ATR_PERCENTILE_HIGH = 90      # Evita apenas extremos

# --- Gerenciamento de Risco ---
# Grok: "SL = 1x ATR (20-30 pips), TP = 2-3x ATR (50-100 pips)"
ATR_MULTIPLIER_SL = 1.0       # SL = 1x ATR (~30 pips)
ATR_MULTIPLIER_TP = 2.5       # TP = 2.5x ATR (~75 pips) - ratio 1:2.5
STOP_LOSS_PIPS = 25           # SL fixo: 25 pips (dentro do range recomendado)
TAKE_PROFIT_PIPS = 60         # TP fixo: 60 pips (ratio ~1:2.4)

# --- Spread ---
# Grok: "Spread 0.1-0.3 pips, pode aumentar para 0.5-1 pip em baixa liquidez"
MAX_SPREAD_ABSOLUTE = 15      # Máximo 1.5 pips (conservador)
MAX_SPREAD_MULTIPLIER = 2.5   # Tolerante com spread

# --- FILTROS ---
USE_MTF_FILTER = False        # M1 é suficiente
STRUCTURE_AS_FILTER = False   # Mercado lateral, estrutura muda muito
BOS_AS_FILTER = False         # BOS como bonus
OB_AS_FILTER = False          # OB como bonus (bom para identificar ranges)

# --- RSI Extremo ---
# Grok: "RSI extremos são CONFIÁVEIS em mercados range-bound como a asiática"
USE_RSI_EXTREME_ENTRY = True
RSI_EXTREME_OVERSOLD = 30     # Compra se RSI < 30 (confiável em range)
RSI_EXTREME_OVERBOUGHT = 70   # Vende se RSI > 70 (confiável em range)

# --- Trailing Stop ---
# Grok: "Trailing stops podem NÃO fazer sentido na asiática, preços andam devagar"
USE_TRAILING_STOP = False     # DESLIGADO - preço anda devagar demais!

# --- Smart Exit ---
# Como não usa trailing, Smart Exit é importante para sair no lucro
SMART_EXIT_MIN_PROFIT = 0.50  # Sai com lucro mínimo de $0.50
SMART_EXIT_WAIT_NEGATIVE_MINUTES = 60  # Espera mais tempo (mercado lento)

# ============================================================================
# 🎮 MODO DE OPERAÇÃO
# ============================================================================
DEMO_TRAINING_MODE = False
AGGRESSIVE_MODE = False
CONSERVATIVE_MODE = False

MAX_OPEN_POSITIONS = 1
MIN_SECONDS_BETWEEN_TRADES = 300  # 5 minutos (cooldown)
VOLUME = 0.1

# ============================================================================
# 📝 RESUMO DAS MUDANÇAS (vs config.py diurno)
# ============================================================================
# | Parâmetro          | Diurno (EUR/USD) | Noturno (USD/JPY) | Motivo           |
# |--------------------|------------------|-------------------|------------------|
# | Trailing Stop      | ON               | OFF               | Preço lento      |
# | ADX Filter         | OFF              | OFF               | Mercado lateral  |
# | RSI Extreme        | 35/65            | 30/70             | Confiável range  |
# | SL/TP              | 15/20 pips       | 25/60 pips        | Menor volatil.   |
# | Smart Exit Wait    | 45 min           | 60 min            | Mercado lento    |
# | Killzone           | Livre            | 21:00-03:00       | Melhor liquidez  |
# ============================================================================

# Mostra status ao carregar
print_period_status()
