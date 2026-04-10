"""
📥 Download Extended History - Baixa 2-5 anos de dados históricos
Usa yfinance como backup se MT5 não tiver dados suficientes.
"""
import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Tenta importar MT5
try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    HAS_MT5 = False
    print("⚠️ MT5 não disponível, usando yfinance")

# Tenta importar yfinance
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

print("="*60)
print("📥 DOWNLOAD DE HISTÓRICO ESTENDIDO")
print("="*60)

# Mapeamento de símbolos MT5 -> Yahoo Finance
SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCAD": "USDCAD=X",
    "AUDUSD": "AUDUSD=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
}

# Timeframes
TIMEFRAMES = {
    "M1": {"mt5": 1, "yf": "1m", "minutes": 1},
    "M5": {"mt5": 5, "yf": "5m", "minutes": 5},
    "M15": {"mt5": 15, "yf": "15m", "minutes": 15},
    "H1": {"mt5": 60, "yf": "1h", "minutes": 60},
    "H4": {"mt5": 240, "yf": "1h", "minutes": 240},  # yf não tem H4, usamos H1
    "D1": {"mt5": 1440, "yf": "1d", "minutes": 1440},
}


def download_mt5(symbol: str, timeframe: str, years: int, output_dir: Path) -> pd.DataFrame:
    """Baixa dados do MT5."""
    if not HAS_MT5:
        return None
    
    if not mt5.initialize():
        print(f"❌ Falha ao inicializar MT5")
        return None
    
    tf_info = TIMEFRAMES.get(timeframe, TIMEFRAMES["M5"])
    tf_mt5 = getattr(mt5, f"TIMEFRAME_{timeframe}", mt5.TIMEFRAME_M5)
    
    # Calcula datas
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    print(f"   Baixando {symbol} {timeframe} de {start_date.date()} até {end_date.date()}...")
    
    # Baixa dados
    rates = mt5.copy_rates_range(symbol, tf_mt5, start_date, end_date)
    
    if rates is None or len(rates) == 0:
        print(f"   ⚠️ Sem dados MT5 para {symbol}")
        return None
    
    # Converte para DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print(f"   ✅ {len(df):,} candles baixados")
    
    return df


def download_yfinance(symbol: str, timeframe: str, years: int, output_dir: Path) -> pd.DataFrame:
    """Baixa dados do Yahoo Finance."""
    if not HAS_YFINANCE:
        print("❌ yfinance não instalado. Execute: pip install yfinance")
        return None
    
    yf_symbol = SYMBOL_MAP.get(symbol, symbol)
    tf_info = TIMEFRAMES.get(timeframe, TIMEFRAMES["M5"])
    
    # Yahoo Finance tem limitações de período por timeframe
    # M1/M5: máximo 7 dias
    # M15/H1: máximo 60 dias
    # D1: sem limite
    
    print(f"   Baixando {yf_symbol} {timeframe} via Yahoo Finance...")
    
    try:
        ticker = yf.Ticker(yf_symbol)
        
        if timeframe in ["M1", "M5"]:
            # Para M1/M5, baixamos em chunks de 7 dias
            all_data = []
            end_date = datetime.now()
            
            # Máximo de dados disponíveis para M5 é ~60 dias
            max_days = min(years * 365, 60)
            start_date = end_date - timedelta(days=max_days)
            
            df = ticker.history(start=start_date, end=end_date, interval=tf_info["yf"])
            if len(df) > 0:
                all_data.append(df)
            
            if all_data:
                df = pd.concat(all_data)
            else:
                return None
                
        elif timeframe in ["M15", "H1"]:
            # Máximo 60 dias
            max_days = min(years * 365, 60)
            df = ticker.history(period=f"{max_days}d", interval=tf_info["yf"])
            
        else:
            # D1 - sem limite
            df = ticker.history(period=f"{years}y", interval=tf_info["yf"])
        
        if df is None or len(df) == 0:
            print(f"   ⚠️ Sem dados yfinance para {yf_symbol}")
            return None
        
        # Renomeia colunas para padrão MT5
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        
        if 'datetime' in df.columns:
            df = df.rename(columns={'datetime': 'time'})
        elif 'date' in df.columns:
            df = df.rename(columns={'date': 'time'})
        
        # Adiciona tick_volume se não existir
        if 'tick_volume' not in df.columns:
            df['tick_volume'] = df.get('volume', 0)
        
        print(f"   ✅ {len(df):,} candles baixados")
        
        return df
        
    except Exception as e:
        print(f"   ❌ Erro yfinance: {e}")
        return None


def download_symbol(symbol: str, timeframe: str, years: int, output_dir: Path) -> bool:
    """Baixa dados de um símbolo."""
    print(f"\n📊 {symbol}:")
    
    # Tenta MT5 primeiro
    df = download_mt5(symbol, timeframe, years, output_dir)
    
    # Fallback para yfinance
    if df is None or len(df) < 1000:
        df_yf = download_yfinance(symbol, timeframe, years, output_dir)
        if df_yf is not None and len(df_yf) > len(df or []):
            df = df_yf
    
    if df is None or len(df) < 100:
        print(f"   ❌ Dados insuficientes para {symbol}")
        return False
    
    # Salva
    symbol_dir = output_dir / symbol.replace("-", "_")
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    # Salva por ano/mês para facilitar
    df['year_month'] = df['time'].dt.strftime('%Y-%m')
    
    for ym, group in df.groupby('year_month'):
        filename = f"{timeframe}_{ym}.csv"
        filepath = symbol_dir / filename
        group.drop(columns=['year_month']).to_csv(filepath, index=False)
    
    print(f"   💾 Salvo em {symbol_dir}")
    print(f"   📅 Período: {df['time'].min()} até {df['time'].max()}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Download histórico estendido')
    parser.add_argument('--years', type=int, default=3, help='Anos de histórico (default: 3)')
    parser.add_argument('--timeframe', default='M5', help='Timeframe (default: M5)')
    parser.add_argument('--symbols', nargs='+', default=None, help='Símbolos específicos')
    parser.add_argument('--output', default='historical_data_extended', help='Pasta de saída')
    args = parser.parse_args()
    
    # Símbolos padrão
    if args.symbols:
        symbols = args.symbols
    else:
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "EURJPY", "GBPJPY"]
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📋 Configuração:")
    print(f"   Anos: {args.years}")
    print(f"   Timeframe: {args.timeframe}")
    print(f"   Símbolos: {', '.join(symbols)}")
    print(f"   Saída: {output_dir}")
    
    # Download
    success = 0
    for symbol in symbols:
        if download_symbol(symbol, args.timeframe, args.years, output_dir):
            success += 1
    
    print(f"\n{'='*60}")
    print(f"✅ Download concluído: {success}/{len(symbols)} símbolos")
    print(f"{'='*60}")
    
    # Fecha MT5
    if HAS_MT5:
        mt5.shutdown()


if __name__ == "__main__":
    main()
