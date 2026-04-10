import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import config
from src.strategies.trend_following import TrendFollowingStrategy
from src.domain.entities import SignalType

# --- Configuração do Backtest ---
SYMBOL = "EURUSD-T" # Ativo para testar
TIMEFRAME = mt5.TIMEFRAME_M1
DAYS_TO_TEST = 10   # Quantos dias para trás
INITIAL_BALANCE = 1000.0

def run_backtest():
    if not mt5.initialize():
        print("Erro ao inicializar MT5")
        return

    print(f"📥 Baixando dados de {DAYS_TO_TEST} dias para {SYMBOL}...")
    
    # Baixa dados históricos
    # M1 = 1440 candles por dia, M5 = 288 candles por dia
    candles_per_day = 1440 if TIMEFRAME == mt5.TIMEFRAME_M1 else 288
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, DAYS_TO_TEST * candles_per_day)
    if rates is None:
        print("❌ Sem dados.")
        return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print(f"✅ {len(df)} candles carregados.")

    # Inicializa Estratégia
    strategy = TrendFollowingStrategy(
        fast_period=config.SMA_FAST,
        slow_period=config.SMA_SLOW,
        rsi_period=config.RSI_PERIOD,
        rsi_upper=config.RSI_OVERBOUGHT,
        rsi_lower=config.RSI_OVERSOLD,
        atr_period=config.ATR_PERIOD
    )

    # Simulação Simplificada
    balance = INITIAL_BALANCE
    position = None # None, 'BUY', 'SELL'
    entry_price = 0.0
    
    trades = []
    
    print("\n🚀 Iniciando Simulação...")
    
    # Loop candle a candle
    # Começamos do candle 50 para ter dados para indicadores
    for i in range(50, len(df)):
        # Recorta os dados até o momento 'i' (simula o tempo real)
        current_data = df.iloc[:i+1].copy()
        current_price = current_data.iloc[-1]['close']
        current_time = current_data.iloc[-1]['time']
        
        # Simula lista de posições para a estratégia
        mock_positions = [1] if position else [] 
        
        signal = strategy.analyze(current_data, mock_positions)
        
        # --- Lógica de Execução Simulada ---
        
        # 1. Fechamento de Posição (Simples: Cruzamento contrário fecha)
        if position == 'BUY' and signal.type == SignalType.SELL:
            profit = (current_price - entry_price) * 10000 # 10000 = alavancagem/pip value approx
            balance += profit
            trades.append({'time': current_time, 'type': 'CLOSE_BUY', 'price': current_price, 'profit': profit})
            position = None
            
        elif position == 'SELL' and signal.type == SignalType.BUY:
            profit = (entry_price - current_price) * 10000
            balance += profit
            trades.append({'time': current_time, 'type': 'CLOSE_SELL', 'price': current_price, 'profit': profit})
            position = None

        # 2. Abertura de Posição
        if position is None and signal.type != SignalType.HOLD:
            position = signal.type.name # 'BUY' or 'SELL'
            entry_price = current_price
            trades.append({'time': current_time, 'type': f'OPEN_{position}', 'price': current_price, 'profit': 0})

    # Relatório Final
    print("\n📊 --- Resultado do Backtest ---")
    print(f"Saldo Inicial: ${INITIAL_BALANCE}")
    print(f"Saldo Final:   ${balance:.2f}")
    print(f"Total Trades:  {len(trades) // 2}")
    print(f"Lucro/Prejuízo: {((balance - INITIAL_BALANCE)/INITIAL_BALANCE)*100:.2f}%")
    
    mt5.shutdown()

if __name__ == "__main__":
    run_backtest()
