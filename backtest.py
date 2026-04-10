"""
Backtest Script - Testa a estratégia em dados históricos

Uso:
    python backtest.py                    # Usa configurações padrão
    python backtest.py --days 30          # Últimos 30 dias
    python backtest.py --symbol EURUSD    # Símbolo específico
"""

import argparse
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import pandas as pd
import config
from src.strategies.trend_following import TrendFollowingStrategy
from src.utils.backtester import Backtester
from src.utils.logger import setup_logger

logger = setup_logger("Backtest")

def get_historical_data(symbol: str, timeframe, days: int = 30) -> pd.DataFrame:
    """Baixa dados históricos do MT5"""
    
    # Inicializa MT5
    if not mt5.initialize():
        logger.error(f"Falha ao inicializar MT5: {mt5.last_error()}")
        return pd.DataFrame()
    
    # Calcula datas
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    logger.info(f"📥 Baixando dados: {symbol} de {start_date.date()} até {end_date.date()}")
    
    # Baixa dados
    rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
    
    if rates is None or len(rates) == 0:
        logger.error(f"Não foi possível obter dados para {symbol}")
        mt5.shutdown()
        return pd.DataFrame()
    
    # Converte para DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    logger.info(f"✅ {len(df)} barras baixadas")
    
    mt5.shutdown()
    return df

def run_backtest(symbol: str = None, timeframe = None, days: int = 30, 
                 initial_balance: float = 100000.0):
    """Executa o backtest"""
    
    # Usa config se não especificado
    symbol = symbol or config.SYMBOL
    timeframe = timeframe or config.TIMEFRAME
    
    print("\n" + "🔬 "*20)
    print("       B3 TRADING BOT - BACKTEST")
    print("🔬 "*20 + "\n")
    
    # Baixa dados históricos
    df = get_historical_data(symbol, timeframe, days)
    
    if df.empty:
        logger.error("Sem dados para backtest. Verifique se o MT5 está aberto.")
        return None
    
    # Cria estratégia com mesmas configurações do config
    strategy = TrendFollowingStrategy(
        fast_period=config.SMA_FAST,
        slow_period=config.SMA_SLOW,
        rsi_period=config.RSI_PERIOD,
        rsi_upper=config.RSI_OVERBOUGHT,
        rsi_lower=config.RSI_OVERSOLD,
        atr_period=config.ATR_PERIOD,
        atr_mult_sl=config.ATR_MULTIPLIER_SL,
        atr_mult_tp=config.ATR_MULTIPLIER_TP,
        aggressive_mode=getattr(config, 'AGGRESSIVE_MODE', False),
        use_rsi_extreme=getattr(config, 'USE_RSI_EXTREME_ENTRY', False),
        rsi_extreme_oversold=getattr(config, 'RSI_EXTREME_OVERSOLD', 25),
        rsi_extreme_overbought=getattr(config, 'RSI_EXTREME_OVERBOUGHT', 75)
    )
    
    # Cria backtester
    backtester = Backtester(
        strategy=strategy,
        initial_balance=initial_balance,
        risk_per_trade=config.RISK_PER_TRADE_PERCENT,
        max_lot=getattr(config, 'MAX_LOT_SIZE', 1.0),
        commission_per_lot=0.0,  # Ajuste conforme sua corretora
        spread_points=1.0  # 1 pip de spread
    )
    
    # Executa backtest
    result = backtester.run(df, symbol)
    
    # Imprime relatório
    backtester.print_report(result)
    
    return result

def main():
    parser = argparse.ArgumentParser(description='Backtest do B3 Trading Bot')
    parser.add_argument('--symbol', type=str, default=None, help='Símbolo (ex: EURUSD)')
    parser.add_argument('--days', type=int, default=30, help='Dias de histórico')
    parser.add_argument('--balance', type=float, default=100000.0, help='Capital inicial')
    
    args = parser.parse_args()
    
    run_backtest(
        symbol=args.symbol,
        days=args.days,
        initial_balance=args.balance
    )

if __name__ == "__main__":
    main()
