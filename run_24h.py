# ============================================================================
# 🌍 BOT 24H INTELIGENTE - MULTI-SESSÃO
# ============================================================================
# Executa o bot 24 horas por dia, trocando automaticamente de par e
# configurações conforme a sessão de mercado.
#
# SESSÕES (horário BRT):
# ┌─────────────────┬───────────────┬──────────────┬─────────────────────────┐
# │ Sessão          │ Horário BRT   │ Par          │ Qualidade               │
# ├─────────────────┼───────────────┼──────────────┼─────────────────────────┤
# │ 🌅 Tokyo+London │ 05:00 - 06:00 │ EUR/JPY      │ 🟡 BOM                  │
# │ 🇬🇧 London      │ 06:00 - 10:00 │ EUR/USD      │ 🟢 MUITO BOM            │
# │ 🔥 London+NY    │ 10:00 - 13:00 │ EUR/USD      │ 🟢 MELHOR (70% volume!) │
# │ 🇺🇸 New York    │ 13:00 - 17:00 │ EUR/USD      │ 🟢 MUITO BOM            │
# │ 🌆 NY Close     │ 17:00 - 19:00 │ EUR/USD      │ 🟡 MODERADO             │
# │ 🌏 Sydney       │ 19:00 - 21:00 │ AUD/USD      │ 🟡 MODERADO             │
# │ 🎯 Tokyo KZ     │ 21:00 - 00:00 │ USD/JPY      │ 🟢 BOM                  │
# │ 🌙 Tokyo+Sydney │ 00:00 - 04:00 │ USD/JPY      │ 🟢 BOM                  │
# │ 🌅 Pre-London   │ 04:00 - 05:00 │ EUR/USD      │ 🟡 MODERADO             │
# └─────────────────┴───────────────┴──────────────┴─────────────────────────┘
# ============================================================================

import sys
import time as time_module
from datetime import datetime
import pytz

sys.path.insert(0, '.')

# Importa o config 24h
import config_24h as config
sys.modules['config'] = config

from config_24h import (
    get_current_session,
    get_session_config,
    get_current_symbol,
    get_dynamic_params,
    print_session_status,
    print_full_schedule,
    TradingSession,
    SESSION_CONFIGS
)

# Variável global para rastrear sessão atual
_current_session = None
_current_symbol = None

def show_welcome():
    """Mostra mensagem de boas-vindas."""
    print()
    print("=" * 70)
    print("🌍 BOT 24H INTELIGENTE - MULTI-SESSÃO")
    print("=" * 70)
    print()
    print("📊 Opera 24 horas com troca automática de par e configurações")
    print("⏰ Adapta-se automaticamente a cada sessão de mercado")
    print()
    
    # Mostra cronograma completo
    print_full_schedule()
    
    # Mostra sessão atual
    print_session_status()
    
    session = get_current_session()
    session_config = get_session_config(session)
    
    if session == TradingSession.LONDON_NY_OVERLAP:
        print("🔥 EXCELENTE! Você está no MELHOR período do dia!")
        print("   70% do volume diário acontece agora!")
        print()
    elif session in [TradingSession.LONDON, TradingSession.NEW_YORK]:
        print("🟢 Ótimo momento para operar! Alta liquidez.")
        print()
    elif session == TradingSession.TOKYO_KILLZONE:
        print("🎯 Melhor momento da sessão asiática!")
        print()

def update_config_for_session():
    """Atualiza as configurações do config module para a sessão atual."""
    global _current_session, _current_symbol
    
    session = get_current_session()
    session_config = get_session_config(session)
    
    # Verifica se mudou de sessão
    if session != _current_session:
        old_session = _current_session
        _current_session = session
        _current_symbol = session_config["symbol"]
        
        if old_session is not None:
            print()
            print("=" * 70)
            print(f"🔄 MUDANÇA DE SESSÃO DETECTADA!")
            print("=" * 70)
            print_session_status()
        
        # Atualiza o módulo config
        config.SYMBOL = session_config["symbol"]
        config.MIN_SIGNAL_SCORE = session_config["min_signal_score"]
        config.USE_TRAILING_STOP = session_config["use_trailing_stop"]
        config.TRAILING_TRIGGER_POINTS = session_config["trailing_trigger"]
        config.TRAILING_STEP_POINTS = session_config["trailing_step"]
        
        # Ajusta Smart Exit baseado na sessão
        if session in [TradingSession.TOKYO_KILLZONE, TradingSession.TOKYO_SYDNEY_OVERLAP]:
            # Sessão asiática: mercado mais lento
            config.SMART_EXIT_WAIT_NEGATIVE_MINUTES = 60
        else:
            # Sessões ocidentais: mercado mais rápido
            config.SMART_EXIT_WAIT_NEGATIVE_MINUTES = 45
        
        return True  # Sessão mudou
    
    return False  # Sessão não mudou

def check_session_change():
    """Verifica se houve mudança de sessão e atualiza configs."""
    return update_config_for_session()

# Patch para o main.py verificar mudança de sessão
def patch_main_loop():
    """
    Injeta verificação de sessão no loop principal.
    Chamado a cada iteração do loop.
    """
    check_session_change()

if __name__ == "__main__":
    show_welcome()
    
    # Inicializa a sessão
    update_config_for_session()
    
    print(f"💹 Iniciando com par: {config.SYMBOL}")
    print(f"📊 Score mínimo: {config.MIN_SIGNAL_SCORE}/9")
    print(f"📍 Trailing Stop: {'ON' if config.USE_TRAILING_STOP else 'OFF'}")
    print()
    
    # Importa e executa o main com wrapper
    from main import main
    
    # O main.py vai rodar normalmente, mas com as configs do config_24h
    # A cada 30 segundos (loop do main), as configs são atualizadas
    main()
