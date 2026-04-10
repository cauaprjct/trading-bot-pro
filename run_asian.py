# ============================================================================
# 🌙 BOT NOTURNO INTELIGENTE - SESSÃO ASIÁTICA
# ============================================================================
# Executa o bot com configurações que se adaptam ao período da noite.
#
# PERÍODOS (horário BRT):
# 🌅 19:00-21:00 - Sydney Warmup (calmo)
# 🎯 21:00-00:00 - Tokyo Killzone (MELHOR MOMENTO)
# 🌙 00:00-04:00 - Tokyo Late (liquidez caindo)
# ⏰ 04:00-05:00 - London Prep (transição)
# ============================================================================

import sys
sys.path.insert(0, '.')

# Substitui o config antes de importar main
import config_asian as config
sys.modules['config'] = config

# Importa funções de período
from config_asian import (
    get_current_asian_period, 
    get_period_config, 
    print_period_status,
    AsianPeriod
)

def show_welcome():
    """Mostra mensagem de boas-vindas com info do período atual"""
    print()
    print("=" * 65)
    print("🌙 BOT NOTURNO INTELIGENTE - SESSÃO ASIÁTICA")
    print("=" * 65)
    print()
    print("📊 Par: USD/JPY-T (principal da sessão asiática)")
    print("⏰ Horário de operação: 19:00 - 05:00 BRT")
    print()
    print("┌─────────────────┬───────────────┬──────────────────────┐")
    print("│ Período         │ Horário       │ Estratégia           │")
    print("├─────────────────┼───────────────┼──────────────────────┤")
    print("│ 🌅 Sydney       │ 19:00 - 21:00 │ Conservador          │")
    print("│ 🎯 Tokyo KZ     │ 21:00 - 00:00 │ MELHOR MOMENTO       │")
    print("│ 🌙 Tokyo Late   │ 00:00 - 04:00 │ Seletivo             │")
    print("│ ⏰ London Prep  │ 04:00 - 05:00 │ Muito conservador    │")
    print("└─────────────────┴───────────────┴──────────────────────┘")
    print()
    
    # Mostra período atual
    period = get_current_asian_period()
    config_info = get_period_config(period)
    
    print(f"{'='*65}")
    print(f"📍 PERÍODO ATUAL: {config_info['emoji']} {config_info['name']}")
    print(f"{'='*65}")
    print(f"   {config_info['description']}")
    print(f"   🎚️  Modo: {config_info['aggressiveness']}")
    print(f"   📊 Score mínimo: {config_info['min_signal_score']}/9")
    print(f"   💹 Pares ideais: {', '.join(config_info['preferred_pairs'])}")
    print(f"{'='*65}")
    print()
    
    if period == AsianPeriod.OUTSIDE:
        print("⚠️  ATENÇÃO: Você está FORA da sessão asiática!")
        print("   Aguarde até 19:00 BRT para melhores condições.")
        print()
    elif period == AsianPeriod.TOKYO_KILLZONE:
        print("🎯 EXCELENTE! Você está no MELHOR período para operar!")
        print("   Aproveite a alta liquidez do mercado japonês.")
        print()
    elif period == AsianPeriod.SYDNEY_WARMUP:
        print("🌅 Mercado aquecendo. Bom para começar com calma.")
        print("   Tokyo Killzone começa às 21:00 BRT.")
        print()

if __name__ == "__main__":
    show_welcome()
    
    # Importa e executa o main
    from main import main
    main()
