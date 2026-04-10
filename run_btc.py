"""
🪙 Bot de Trading para BTCUSD - Opera 24/7 (incluindo fins de semana)

Execute com: python run_btc.py

Configurações otimizadas para Bitcoin:
- Volatilidade alta → SL/TP maiores
- Spread maior → filtro ajustado
- 24/7 → sem filtro de sessão
- Risco 0.5% → mais conservador
- Auto-treino ML na inicialização
"""

import sys
import os

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importa config_btc como config (substitui o config padrão)
import config_btc as config
sys.modules['config'] = config

print("=" * 60)
print("🪙 BOT BTCUSD - MODO 24/7 (FINS DE SEMANA)")
print("=" * 60)
print(f"📊 Símbolo: {config.SYMBOL}")
print(f"⏱️  Timeframe: M1")
print(f"💰 Risco: {config.RISK_PER_TRADE_PERCENT}% por trade")
print(f"🎯 Score mínimo: {config.MIN_SIGNAL_SCORE}/9")
print(f"🛡️  Anti-Stop Hunt: +{config.SL_BUFFER_PIPS} pips")
print(f"📅 Sessão: 24/7 (sem filtro)")
print("=" * 60)
print()

# ============================================================================
# 🤖 AUTO-TREINO ML - Baixa histórico e treina modelo antes de operar
# ============================================================================
if getattr(config, 'USE_ML_FILTER', False):
    print("🤖 Iniciando Auto-Trainer ML...")
    print("   Isso pode levar 1-2 minutos na primeira vez.")
    print()
    
    try:
        import MetaTrader5 as mt5
        from src.utils.auto_trainer import AutoTrainer
        from src.infrastructure.mt5_adapter import MT5Adapter
        
        # Conecta ao MT5 temporariamente para baixar dados
        if not mt5.initialize():
            print("❌ Erro: Não foi possível conectar ao MT5")
            print("   Verifique se o MetaTrader 5 está aberto e logado.")
            sys.exit(1)
        
        # Cria adapter temporário
        temp_adapter = MT5Adapter(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER
        )
        
        if not temp_adapter.connect():
            print("❌ Erro: Falha na conexão com MT5")
            sys.exit(1)
        
        # Executa auto-treino
        trainer = AutoTrainer(
            symbol=config.SYMBOL,
            timeframe=config.TIMEFRAME,
            history_months=getattr(config, 'HISTORY_MONTHS', 6)
        )
        
        success, model_path, threshold = trainer.run(temp_adapter)
        
        if success:
            # Atualiza config com threshold otimizado
            config.ML_MODEL_PATH = model_path
            config.ML_CONFIDENCE_THRESHOLD = threshold
            print()
            print(f"✅ Modelo ML pronto!")
            print(f"   📁 {os.path.basename(model_path)}")
            print(f"   🎯 Threshold: {threshold:.0%}")
        else:
            print("⚠️ Auto-treino falhou, usando score padrão")
            config.USE_ML_FILTER = False
        
        # Desconecta (main vai reconectar)
        mt5.shutdown()
        
    except ImportError as e:
        print(f"⚠️ Dependência ML não instalada: {e}")
        print("   Execute: pip install lightgbm scikit-learn")
        config.USE_ML_FILTER = False
    except Exception as e:
        print(f"⚠️ Erro no auto-treino: {e}")
        config.USE_ML_FILTER = False

print()
print("=" * 60)
print("🚀 Iniciando bot de trading...")
print("=" * 60)
print()

# Importa e executa o main
from main import main

if __name__ == "__main__":
    main()
