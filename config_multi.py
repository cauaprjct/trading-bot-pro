# ============================================================================
# 🚀 CONFIGURAÇÃO MULTI-ATIVO AVANÇADO
# ============================================================================
# Opera múltiplos ativos simultaneamente para maximizar oportunidades.
# 
# ESTRATÉGIA:
# - Forex (EURUSD, GBPUSD, USDJPY): Segunda a Sexta
# - Crypto (BTCUSD, ETHUSD): 24/7 incluindo fins de semana
# - Cada ativo tem suas próprias configurações otimizadas
# ============================================================================

from config import *
from datetime import datetime, time as dt_time
import pytz

# --- Estado separado ---
STATE_FILE = "bot_state_multi.json"

# ============================================================================
# 🎯 ATIVOS CONFIGURADOS
# ============================================================================

MULTI_ASSETS = {
    # ═══════════════════════════════════════════════════════════════════════
    # 💱 CENÁRIO A - SCALPER CONSERVADOR
    # ═══════════════════════════════════════════════════════════════════════
    # Meta: R$100/dia = 19 trades de $1 cada
    # Lote: 0.05 | SL: 5 pips | Saída: $1 lucro (~3 pips)
    # ═══════════════════════════════════════════════════════════════════════
    
    "GBPUSD": {
        "enabled": True,
        "type": "forex",
        "description": "Libra/Dólar - MELHOR SPREAD!",
        "pip_value": 0.0001,
        "spread_max": 10,           # Mais restrito para scalping
        "volume": 0.05,             # 🔧 Aumentado para $0.35/pip
        "max_volume": 0.10,
        "atr_mult_sl": 0.5,         # 🔧 SL curto (~5 pips)
        "atr_mult_tp": 1.0,         # 🔧 TP curto (~10 pips) - mas sai manual com $1
        "min_score": 3,
        "trailing_trigger": 0.00003,  # 3 pips = $1 lucro
        "trailing_step": 0.00002,
        "best_hours": [(4, 18)],
        "weekend": False,
        "emoji": "🇬🇧"
    },
    
    "EURUSD": {
        "enabled": True,
        "type": "forex",
        "description": "Euro/Dólar - Par mais líquido",
        "pip_value": 0.0001,
        "spread_max": 10,
        "volume": 0.05,
        "max_volume": 0.10,
        "atr_mult_sl": 0.5,
        "atr_mult_tp": 1.0,
        "min_score": 3,
        "trailing_trigger": 0.00003,
        "trailing_step": 0.00002,
        "best_hours": [(4, 18)],
        "weekend": False,
        "emoji": "🇪🇺"
    },
    
    "USDCAD": {
        "enabled": True,
        "type": "forex",
        "description": "Dólar/Canadense - Spread baixo",
        "pip_value": 0.0001,
        "spread_max": 10,
        "volume": 0.05,
        "max_volume": 0.10,
        "atr_mult_sl": 0.5,
        "atr_mult_tp": 1.0,
        "min_score": 3,
        "trailing_trigger": 0.00003,
        "trailing_step": 0.00002,
        "best_hours": [(9, 18)],
        "weekend": False,
        "emoji": "🇨🇦"
    },
    
    "USDJPY": {
        "enabled": True,
        "type": "forex",
        "description": "Dólar/Iene - Sessão asiática",
        "pip_value": 0.01,
        "spread_max": 15,           # JPY tem spread maior
        "volume": 0.05,
        "max_volume": 0.10,
        "atr_mult_sl": 0.5,
        "atr_mult_tp": 1.0,
        "min_score": 3,
        "trailing_trigger": 0.030,    # 3 pips para JPY
        "trailing_step": 0.020,
        "best_hours": [(0, 4), (9, 18), (21, 24)],
        "weekend": False,
        "emoji": "🇯🇵"
    },
    
    "EURJPY": {
        "enabled": True,
        "type": "forex",
        "description": "Euro/Iene - Volátil",
        "pip_value": 0.01,
        "spread_max": 20,
        "volume": 0.05,
        "max_volume": 0.10,
        "atr_mult_sl": 0.5,
        "atr_mult_tp": 1.0,
        "min_score": 3,
        "trailing_trigger": 0.030,
        "trailing_step": 0.020,
        "best_hours": [(4, 18), (21, 24)],
        "weekend": False,
        "emoji": "🇪🇺🇯🇵"
    },
    
    "GBPJPY": {
        "enabled": True,
        "type": "forex",
        "description": "Libra/Iene - Muito volátil",
        "pip_value": 0.01,
        "spread_max": 25,
        "volume": 0.05,             # 🔧 Igual aos outros agora
        "max_volume": 0.10,
        "atr_mult_sl": 0.5,
        "atr_mult_tp": 1.0,
        "min_score": 3,
        "trailing_trigger": 0.030,
        "trailing_step": 0.020,
        "best_hours": [(4, 18)],
        "weekend": False,
        "emoji": "🇬🇧🇯🇵"
    },
    
    "AUDUSD": {
        "enabled": True,
        "type": "forex",
        "description": "Aussie/Dólar - Sessão asiática",
        "pip_value": 0.0001,
        "spread_max": 12,
        "volume": 0.05,
        "max_volume": 0.10,
        "atr_mult_sl": 0.5,
        "atr_mult_tp": 1.0,
        "min_score": 3,
        "trailing_trigger": 0.00003,
        "trailing_step": 0.00002,
        "best_hours": [(0, 4), (9, 18), (19, 24)],
        "weekend": False,
        "emoji": "🇦🇺"
    },
}

# ============================================================================
# 🧠 FUNÇÕES DE SELEÇÃO DE ATIVOS
# ============================================================================

def is_weekend() -> bool:
    """Verifica se é fim de semana."""
    tz = pytz.timezone("America/Sao_Paulo")
    now = datetime.now(tz)
    # Sábado = 5, Domingo = 6
    return now.weekday() >= 5

def is_forex_open() -> bool:
    """Verifica se o mercado Forex está aberto."""
    tz = pytz.timezone("America/Sao_Paulo")
    now = datetime.now(tz)
    
    # Forex fecha sexta 18h e abre domingo 18h (BRT)
    weekday = now.weekday()
    hour = now.hour
    
    if weekday == 4 and hour >= 18:  # Sexta após 18h
        return False
    if weekday == 5:  # Sábado
        return False
    if weekday == 6 and hour < 18:  # Domingo antes 18h
        return False
    
    return True

def get_current_hour() -> int:
    """Retorna hora atual em BRT."""
    tz = pytz.timezone("America/Sao_Paulo")
    return datetime.now(tz).hour

def is_good_hour_for_asset(asset_config: dict) -> bool:
    """Verifica se é um bom horário para o ativo."""
    best_hours = asset_config.get("best_hours")
    if best_hours is None:  # 24/7 (crypto)
        return True
    
    current_hour = get_current_hour()
    for start, end in best_hours:
        if start <= end:
            if start <= current_hour < end:
                return True
        else:  # Passa da meia-noite (ex: 21-4)
            if current_hour >= start or current_hour < end:
                return True
    return False

def get_active_assets() -> list:
    """
    Retorna lista de ativos ativos para o momento atual.
    
    Lógica:
    - Fim de semana: Só crypto
    - Semana: Forex + Crypto (priorizando melhores horários)
    """
    active = []
    weekend = is_weekend()
    forex_open = is_forex_open()
    
    for symbol, config in MULTI_ASSETS.items():
        if not config["enabled"]:
            continue
        
        asset_type = config["type"]
        
        # Crypto sempre disponível
        if asset_type == "crypto":
            if is_good_hour_for_asset(config):
                active.append(symbol)
        
        # Forex só quando mercado aberto
        elif asset_type == "forex" and forex_open:
            if is_good_hour_for_asset(config):
                active.append(symbol)
    
    return active

def get_asset_config(symbol: str) -> dict:
    """Retorna configuração do ativo."""
    return MULTI_ASSETS.get(symbol, MULTI_ASSETS["EURUSD"])

def get_priority_asset() -> str:
    """
    Retorna o ativo prioritário para o momento.
    Útil quando quer focar em um só.
    """
    active = get_active_assets()
    if not active:
        return "BTCUSD"  # Fallback para crypto (sempre aberto)
    
    hour = get_current_hour()
    
    # Prioridades por horário
    if 4 <= hour < 9:  # Manhã Europa
        priorities = ["EURUSD", "GBPUSD", "BTCUSD"]
    elif 9 <= hour < 14:  # Overlap
        priorities = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]
    elif 14 <= hour < 18:  # Tarde NY
        priorities = ["EURUSD", "USDJPY", "BTCUSD"]
    elif 21 <= hour or hour < 4:  # Noite/Madrugada
        priorities = ["USDJPY", "BTCUSD", "ETHUSD"]
    else:  # Transição
        priorities = ["BTCUSD", "ETHUSD", "EURUSD"]
    
    for p in priorities:
        if p in active:
            return p
    
    return active[0] if active else "BTCUSD"

# ============================================================================
# 📊 CONFIGURAÇÕES GLOBAIS - SCALPER CONSERVADOR
# ============================================================================

# Quantos ativos operar simultaneamente (máximo)
MAX_CONCURRENT_ASSETS = 7  # 🔧 Todos os 7 ativos

# Máximo de posições TOTAL (somando todos os ativos)
MAX_TOTAL_POSITIONS = 7    # 🔧 1 por ativo = 7 total

# Máximo de posições POR ATIVO
MAX_POSITIONS_PER_ASSET = 1

# Intervalo entre trades NO MESMO ATIVO (segundos)
MIN_SECONDS_BETWEEN_TRADES = 30  # 🔧 30 segundos (scalping rápido)

# Intervalo entre trades EM ATIVOS DIFERENTES (segundos)
MIN_SECONDS_BETWEEN_ANY_TRADE = 5  # 🔧 5 segundos

# Risco total máximo (% do capital em risco ao mesmo tempo)
MAX_TOTAL_RISK_PERCENT = 15.0  # 🔧 15% com 7 posições

# ============================================================================
# 💰 CONFIGURAÇÕES DE CAPITAL (R$200) - DISTRIBUIÇÃO INTELIGENTE
# ============================================================================

USE_SIMULATED_CAPITAL = True
SIMULATED_CAPITAL_BRL = 200.0
SIMULATED_CAPITAL_USD = 33.0

# ═══════════════════════════════════════════════════════════════════════════
# 🧠 GESTÃO INTELIGENTE DE CAPITAL
# ═══════════════════════════════════════════════════════════════════════════
# Com 7 ativos, distribuímos o risco de forma inteligente:
# - Cada trade arrisca apenas 1.5% do capital (~R$3)
# - Máximo 4 posições simultâneas = 6% do capital em risco
# - Se um ativo perde, outros podem compensar
# ═══════════════════════════════════════════════════════════════════════════

RISK_PER_TRADE_PERCENT = 1.5      # 1.5% por trade (~R$3 de R$200)
MAX_RISK_TOTAL_PERCENT = 8.0     # Máximo 8% do capital em risco ao mesmo tempo

# Distribuição de capital por tipo (não usado diretamente, só referência)
CAPITAL_ALLOCATION = {
    "forex": 1.0,   # 100% para Forex (não temos crypto)
}

# ============================================================================
# 🛡️ PROTEÇÕES - SCALPER CONSERVADOR
# ============================================================================

MAX_DAILY_LOSS_PERCENT = 20.0    # Para se perder 20% no dia (R$40)
MAX_DAILY_TRADES = 50            # 🔧 Até 50 trades/dia (scalping)
EMERGENCY_STOP_LOSS_PERCENT = 25 # Emergência: para tudo

# Smart Exit - SAI COM $1 DE LUCRO GARANTIDO
USE_SMART_EXIT = True
SMART_EXIT_MIN_PROFIT_USD = 1.00     # 🎯 Meta: $1 por trade (R$5.38)
SMART_EXIT_WAIT_NEGATIVE_MINUTES = 5  # 🔧 Espera só 5 min se negativo
SMART_EXIT_EMERGENCY_LOSS_PERCENT = 5 # 🔧 Sai se perder 5% em 1 trade (~$1.75)
SMART_EXIT_TAKE_PROFIT_ON_RECOVERY = True

# ============================================================================
# 📈 FILTROS E ESTRATÉGIA
# ============================================================================

# ═══════════════════════════════════════════════════════════════════════════
# 🎯 ENSEMBLE ML - Combina LightGBM + LSTM para decisões mais robustas
# ═══════════════════════════════════════════════════════════════════════════
USE_ENSEMBLE_ML = True  # 🆕 Usa ensemble em vez de filtros separados

# Configurações do Ensemble
ENSEMBLE_VOTING_MODE = "WEIGHTED"  # UNANIMOUS, MAJORITY, WEIGHTED
ENSEMBLE_MIN_SCORE = 0.28  # Score mínimo combinado (28% - permite mais trades)
ENSEMBLE_LGBM_WEIGHT = 0.85  # LightGBM domina (precision ~50%)
ENSEMBLE_LSTM_WEIGHT = 0.15  # LSTM só como filtro leve (F1 ~25%)

# Filtros individuais (usados se USE_ENSEMBLE_ML = False)
USE_ML_FILTER = False  # 🔧 Desativado - Ensemble ML cuida disso no run_multi.py
ML_CONFIDENCE_THRESHOLD = 0.40  # Threshold ótimo do treino

# Deep Learning (LSTM treinado na GPU)
USE_DEEP_ML_FILTER = True
DEEP_ML_CONFIDENCE_THRESHOLD = 0.45  # Ajustado
DEEP_ML_MIN_F1_TO_USE = 0.15  # 🔧 Baixei de 0.20 para incluir mais modelos

# Desativa modo agressivo para multi-ativo (gera muitos logs)
AGGRESSIVE_MODE = False

USE_HYBRID_MODE = True
USE_MARKET_STRUCTURE = True
USE_BOS_PULLBACK = True
USE_ORDER_BLOCKS = True

# Desativados para mais trades
USE_SESSION_FILTER = False
USE_ADX_FILTER = False
STRUCTURE_AS_FILTER = False
BOS_AS_FILTER = False
OB_AS_FILTER = False

# ============================================================================
# 🖨️ FUNÇÕES DE DISPLAY
# ============================================================================

def print_multi_status():
    """Imprime status do sistema multi-ativo."""
    weekend = is_weekend()
    forex_open = is_forex_open()
    active = get_active_assets()
    priority = get_priority_asset()
    hour = get_current_hour()
    
    print("\n" + "="*70)
    print("🚀 SISTEMA MULTI-ATIVO - STATUS")
    print("="*70)
    print(f"⏰ Hora atual: {hour}:00 BRT")
    print(f"📅 Fim de semana: {'Sim' if weekend else 'Não'}")
    print(f"💱 Forex aberto: {'Sim' if forex_open else 'Não'}")
    print(f"🎯 Ativo prioritário: {priority}")
    print()
    print("📊 ATIVOS ATIVOS AGORA:")
    print("-"*50)
    
    for symbol in active:
        config = MULTI_ASSETS[symbol]
        emoji = config["emoji"]
        desc = config["description"][:30]
        vol = config["volume"]
        print(f"  {emoji} {symbol}: {desc}... (lote: {vol})")
    
    if not active:
        print("  ⚠️ Nenhum ativo ativo no momento!")
    
    print()
    print("="*70 + "\n")

def print_all_assets():
    """Imprime todos os ativos configurados."""
    print("\n" + "="*70)
    print("📋 TODOS OS ATIVOS CONFIGURADOS")
    print("="*70)
    print()
    print("┌────────────┬──────────┬─────────┬────────┬─────────────────────────┐")
    print("│ Ativo      │ Tipo     │ Lote    │ Score  │ Descrição               │")
    print("├────────────┼──────────┼─────────┼────────┼─────────────────────────┤")
    
    for symbol, config in MULTI_ASSETS.items():
        enabled = "✅" if config["enabled"] else "❌"
        tipo = config["type"].upper()[:6].ljust(6)
        lote = f"{config['volume']:.2f}".ljust(5)
        score = str(config["min_score"]).ljust(4)
        desc = config["description"][:23].ljust(23)
        print(f"│ {enabled} {symbol.ljust(8)} │ {tipo}   │ {lote}   │ {score}   │ {desc} │")
    
    print("└────────────┴──────────┴─────────┴────────┴─────────────────────────┘")
    print()

# Mostra status ao carregar
print_multi_status()
