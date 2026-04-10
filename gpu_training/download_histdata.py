"""
📥 Download HistData.com - Baixa histórico Forex de 2-3 anos
Fonte gratuita e confiável para dados M1 de Forex.

Uso: python download_histdata.py --years 3
"""
import os
import sys
import argparse
import requests
import zipfile
import io
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List
import time

print("="*60)
print("📥 DOWNLOAD HISTDATA.COM - Histórico Forex Estendido")
print("="*60)

# Símbolos disponíveis no HistData
SYMBOLS = {
    "EURUSD": "eurusd",
    "GBPUSD": "gbpusd", 
    "USDJPY": "usdjpy",
    "USDCAD": "usdcad",
    "AUDUSD": "audusd",
    "EURJPY": "eurjpy",
    "GBPJPY": "gbpjpy",
}

# URL base do HistData
BASE_URL = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes"


def download_histdata_month(symbol: str, year: int, month: int) -> pd.DataFrame:
    """
    Baixa dados de um mês específico do HistData.
    
    Nota: HistData requer navegação manual ou usa formato específico de URL.
    Vamos tentar o download direto primeiro.
    """
    symbol_lower = SYMBOLS.get(symbol, symbol.lower())
    
    # URL do arquivo (formato típico do HistData)
    # Exemplo: DAT_ASCII_EURUSD_M1_2023.zip
    url = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{symbol_lower}/{year}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Procura link de download na página
            # HistData requer aceitar termos, então vamos usar abordagem alternativa
            return None
            
    except Exception as e:
        print(f"   ⚠️ Erro: {e}")
    
    return None


def convert_m1_to_m5(df: pd.DataFrame) -> pd.DataFrame:
    """Converte dados M1 para M5."""
    if df is None or len(df) == 0:
        return None
    
    df['time'] = pd.to_datetime(df['time'])
    df = df.set_index('time')
    
    # Resample para M5
    df_m5 = df.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    df_m5 = df_m5.reset_index()
    df_m5 = df_m5.rename(columns={'volume': 'tick_volume'})
    
    return df_m5


def download_from_mt5_extended(symbol: str, years: int = 3) -> pd.DataFrame:
    """
    Tenta baixar histórico estendido do MT5.
    MetaQuotes-Demo geralmente tem 1-2 anos disponíveis.
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            print("   ❌ MT5 não inicializado")
            return None
        
        # Calcula período
        from datetime import timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        print(f"   Tentando baixar de {start_date.date()} até {end_date.date()}...")
        
        # Baixa M1 (mais dados disponíveis)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start_date, end_date)
        
        if rates is None or len(rates) == 0:
            # Tenta M5
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, start_date, end_date)
        
        if rates is None or len(rates) == 0:
            print(f"   ⚠️ Sem dados disponíveis para {symbol}")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Se for M1, converte para M5
        if len(df) > 500000:  # Provavelmente M1
            print(f"   📊 Convertendo {len(df):,} candles M1 para M5...")
            df = convert_m1_to_m5(df)
        
        return df
        
    except ImportError:
        print("   ⚠️ MT5 não disponível")
        return None
    except Exception as e:
        print(f"   ❌ Erro MT5: {e}")
        return None


def save_data(df: pd.DataFrame, symbol: str, output_dir: Path):
    """Salva dados em formato compatível."""
    if df is None or len(df) == 0:
        return False
    
    symbol_dir = output_dir / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    # Agrupa por ano-mês
    df['year_month'] = df['time'].dt.strftime('%Y-%m')
    
    for ym, group in df.groupby('year_month'):
        filename = f"M5_{ym}.csv"
        filepath = symbol_dir / filename
        
        # Colunas padrão
        cols = ['time', 'open', 'high', 'low', 'close']
        if 'tick_volume' in group.columns:
            cols.append('tick_volume')
        elif 'volume' in group.columns:
            cols.append('volume')
        
        group[cols].to_csv(filepath, index=False)
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Baixa histórico Forex estendido')
    parser.add_argument('--years', type=int, default=3, help='Anos de histórico')
    parser.add_argument('--symbols', nargs='+', default=None, help='Símbolos')
    parser.add_argument('--output', default='gpu_training/historical_data', help='Pasta de saída')
    args = parser.parse_args()
    
    symbols = args.symbols or list(SYMBOLS.keys())
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📋 Configuração:")
    print(f"   Anos: {args.years}")
    print(f"   Símbolos: {', '.join(symbols)}")
    print(f"   Saída: {output_dir}")
    
    results = {}
    
    for symbol in symbols:
        print(f"\n{'='*50}")
        print(f"📊 {symbol}")
        print(f"{'='*50}")
        
        # Tenta MT5 primeiro (mais fácil)
        df = download_from_mt5_extended(symbol, args.years)
        
        if df is not None and len(df) > 0:
            # Salva
            if save_data(df, symbol, output_dir):
                days = (df['time'].max() - df['time'].min()).days
                results[symbol] = {
                    'status': 'ok',
                    'candles': len(df),
                    'days': days,
                    'start': str(df['time'].min())[:10],
                    'end': str(df['time'].max())[:10]
                }
                print(f"   ✅ {len(df):,} candles salvos ({days} dias)")
                print(f"   📅 {df['time'].min()} até {df['time'].max()}")
            else:
                results[symbol] = {'status': 'save_error'}
        else:
            results[symbol] = {'status': 'no_data'}
            print(f"   ❌ Sem dados disponíveis")
        
        # Pequena pausa entre símbolos
        time.sleep(1)
    
    # Resumo
    print(f"\n{'='*60}")
    print("📊 RESUMO DO DOWNLOAD")
    print("="*60)
    
    total_candles = 0
    for symbol, info in results.items():
        if info['status'] == 'ok':
            print(f"✅ {symbol}: {info['candles']:,} candles | {info['days']} dias | {info['start']} a {info['end']}")
            total_candles += info['candles']
        else:
            print(f"❌ {symbol}: {info['status']}")
    
    print(f"\n📈 Total: {total_candles:,} candles")
    
    # Fecha MT5
    try:
        import MetaTrader5 as mt5
        mt5.shutdown()
    except:
        pass
    
    # Instruções se não conseguiu dados suficientes
    if total_candles < 100000:
        print(f"\n{'='*60}")
        print("💡 PARA MAIS DADOS, BAIXE MANUALMENTE:")
        print("="*60)
        print("""
1. Acesse: https://www.histdata.com/download-free-forex-data/
2. Selecione cada par (EURUSD, GBPUSD, etc.)
3. Escolha: ASCII / 1-Minute Bar Quotes
4. Baixe os anos 2023, 2024, 2025
5. Extraia os ZIPs na pasta: gpu_training/historical_data_raw/
6. Execute: python gpu_training/convert_histdata.py
        """)


if __name__ == "__main__":
    main()
