"""
📥 Download Dukascopy API - Baixa histórico Forex via API
Usa a API pública do Dukascopy para baixar dados tick/M1.

Uso: 
  python download_dukascopy.py --years 3 --workers 20
  python download_dukascopy.py --years 1 --symbols EURUSD GBPUSD
"""
import os
import sys
import struct
import lzma
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

print("="*60)
print("📥 DOWNLOAD DUKASCOPY API - Histórico Forex Estendido")
print("="*60)

# Símbolos do bot (formato Dukascopy)
SYMBOLS = {
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "USDCAD": "USDCAD",
    "AUDUSD": "AUDUSD",
    "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY",
}

# URL base da API Dukascopy
BASE_URL = "https://datafeed.dukascopy.com/datafeed"

# Diretório de saída
OUTPUT_DIR = Path("gpu_training/historical_data")

# Session com retry
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})


def download_hour_data(symbol: str, year: int, month: int, day: int, hour: int) -> Optional[pd.DataFrame]:
    """
    Baixa dados de uma hora específica do Dukascopy.
    
    Formato URL: https://datafeed.dukascopy.com/datafeed/EURUSD/2023/00/01/00h_ticks.bi5
    Nota: Mês é 0-indexed (Janeiro = 00)
    """
    # Mês é 0-indexed no Dukascopy
    month_str = f"{month-1:02d}"
    day_str = f"{day:02d}"
    hour_str = f"{hour:02d}"
    
    url = f"{BASE_URL}/{symbol}/{year}/{month_str}/{day_str}/{hour_str}h_ticks.bi5"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200 and len(response.content) > 0:
            # Descomprime LZMA
            try:
                data = lzma.decompress(response.content)
            except:
                return None
            
            if len(data) == 0:
                return None
            
            # Parse dados binários
            # Formato: 4 bytes timestamp (ms), 4 bytes ask, 4 bytes bid, 4 bytes ask_vol, 4 bytes bid_vol
            # Total: 20 bytes por tick
            
            ticks = []
            base_time = datetime(year, month, day, hour)
            
            for i in range(0, len(data), 20):
                if i + 20 > len(data):
                    break
                
                chunk = data[i:i+20]
                
                # Unpack: timestamp (ms), ask (int), bid (int), ask_vol (float), bid_vol (float)
                try:
                    ts_ms, ask_int, bid_int, ask_vol, bid_vol = struct.unpack('>IIIff', chunk)
                except:
                    continue
                
                # Converte timestamp
                tick_time = base_time + timedelta(milliseconds=ts_ms)
                
                # Converte preços (dividir por 100000 para 5 decimais, 1000 para 3 decimais)
                if 'JPY' in symbol:
                    divisor = 1000  # 3 decimais para pares JPY
                else:
                    divisor = 100000  # 5 decimais para outros
                
                ask = ask_int / divisor
                bid = bid_int / divisor
                
                ticks.append({
                    'time': tick_time,
                    'bid': bid,
                    'ask': ask,
                    'bid_vol': bid_vol,
                    'ask_vol': ask_vol
                })
            
            if ticks:
                return pd.DataFrame(ticks)
        
        return None
        
    except Exception as e:
        return None


def download_candles_bi5(symbol: str, year: int, month: int, day: int, hour: int, timeframe: str = 'M1') -> Optional[pd.DataFrame]:
    """
    Baixa candles pré-agregados do Dukascopy (mais rápido que ticks).
    
    Formato: BID_candles_min_1.bi5 ou ASK_candles_min_1.bi5
    """
    month_str = f"{month-1:02d}"
    day_str = f"{day:02d}"
    hour_str = f"{hour:02d}"
    
    # URL para candles M1
    url = f"{BASE_URL}/{symbol}/{year}/{month_str}/{day_str}/{hour_str}h_BID_candles_min_1.bi5"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200 and len(response.content) > 0:
            try:
                data = lzma.decompress(response.content)
            except:
                return None
            
            if len(data) == 0:
                return None
            
            # Formato candle: 4 bytes time_offset, 4 bytes open, 4 bytes close, 4 bytes low, 4 bytes high, 4 bytes volume
            # Total: 24 bytes por candle
            
            candles = []
            base_time = datetime(year, month, day, hour)
            
            if 'JPY' in symbol:
                divisor = 1000
            else:
                divisor = 100000
            
            for i in range(0, len(data), 24):
                if i + 24 > len(data):
                    break
                
                chunk = data[i:i+24]
                
                try:
                    time_offset, open_int, close_int, low_int, high_int, volume = struct.unpack('>IIIIIf', chunk)
                except:
                    continue
                
                candle_time = base_time + timedelta(seconds=time_offset)
                
                candles.append({
                    'time': candle_time,
                    'open': open_int / divisor,
                    'high': high_int / divisor,
                    'low': low_int / divisor,
                    'close': close_int / divisor,
                    'volume': volume
                })
            
            if candles:
                return pd.DataFrame(candles)
        
        return None
        
    except Exception as e:
        return None


def download_day_data(symbol: str, date: datetime, use_candles: bool = True) -> Optional[pd.DataFrame]:
    """Baixa dados de um dia inteiro."""
    all_data = []
    
    for hour in range(24):
        if use_candles:
            # Tenta candles primeiro (mais rápido)
            df = download_candles_bi5(symbol, date.year, date.month, date.day, hour)
        else:
            df = download_hour_data(symbol, date.year, date.month, date.day, hour)
        
        if df is not None and len(df) > 0:
            all_data.append(df)
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None


def candles_to_m5(df: pd.DataFrame) -> pd.DataFrame:
    """Converte candles M1 para M5."""
    if df is None or len(df) == 0:
        return None
    
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


def ticks_to_m5(df: pd.DataFrame) -> pd.DataFrame:
    """Converte ticks para candles M5."""
    if df is None or len(df) == 0:
        return None
    
    # Usa preço médio (bid + ask) / 2
    df['price'] = (df['bid'] + df['ask']) / 2
    df['volume'] = df['bid_vol'] + df['ask_vol']
    
    df = df.set_index('time')
    
    # Resample para M5
    df_m5 = df['price'].resample('5min').ohlc()
    df_m5['tick_volume'] = df['volume'].resample('5min').sum()
    
    df_m5 = df_m5.dropna()
    df_m5 = df_m5.reset_index()
    
    return df_m5


def download_symbol(symbol: str, start_date: datetime, end_date: datetime, max_workers: int = 4, use_candles: bool = True) -> pd.DataFrame:
    """Baixa dados de um símbolo para o período especificado."""
    print(f"\n📊 Baixando {symbol}...")
    print(f"   Período: {start_date.date()} até {end_date.date()}")
    print(f"   Modo: {'Candles M1' if use_candles else 'Ticks'}")
    
    # Gera lista de datas
    dates = []
    current = start_date
    while current <= end_date:
        # Pula fins de semana (mercado fechado)
        if current.weekday() < 5:  # Segunda a Sexta
            dates.append(current)
        current += timedelta(days=1)
    
    print(f"   📅 {len(dates)} dias úteis para baixar")
    
    all_data = []
    downloaded = 0
    errors = 0
    
    # Download paralelo
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_day_data, symbol, date, use_candles): date for date in dates}
        
        for future in as_completed(futures):
            date = futures[future]
            try:
                df = future.result()
                if df is not None and len(df) > 0:
                    all_data.append(df)
                    downloaded += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
            
            # Progress
            total = downloaded + errors
            if total % 50 == 0:
                print(f"   📥 Progresso: {total}/{len(dates)} dias ({downloaded} ok, {errors} erros)")
    
    print(f"   ✅ Download completo: {downloaded} dias, {errors} erros")
    
    if not all_data:
        return None
    
    # Concatena todos os dados
    df_all = pd.concat(all_data, ignore_index=True)
    df_all = df_all.sort_values('time')
    
    print(f"   📊 Total candles M1: {len(df_all):,}")
    
    # Converte para M5
    print(f"   🔄 Convertendo para M5...")
    
    if use_candles:
        df_m5 = candles_to_m5(df_all)
    else:
        df_m5 = ticks_to_m5(df_all)
    
    if df_m5 is not None:
        print(f"   📊 Total M5: {len(df_m5):,} candles")
    
    return df_m5


def save_data(df: pd.DataFrame, symbol: str):
    """Salva dados em formato compatível."""
    if df is None or len(df) == 0:
        return False
    
    symbol_dir = OUTPUT_DIR / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    # Agrupa por ano-mês
    df['year_month'] = df['time'].dt.strftime('%Y-%m')
    
    for ym, group in df.groupby('year_month'):
        filename = f"M5_{ym}.csv"
        filepath = symbol_dir / filename
        
        cols = ['time', 'open', 'high', 'low', 'close', 'tick_volume']
        group[cols].to_csv(filepath, index=False)
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Baixa histórico Forex do Dukascopy')
    parser.add_argument('--years', type=int, default=3, help='Anos de histórico (padrão: 3)')
    parser.add_argument('--symbols', nargs='+', default=None, help='Símbolos específicos')
    parser.add_argument('--workers', type=int, default=20, help='Workers paralelos (padrão: 20)')
    parser.add_argument('--start', type=str, default=None, help='Data inicial (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='Data final (YYYY-MM-DD)')
    parser.add_argument('--candles', action='store_true', help='Usar candles M1 em vez de ticks (mais rápido se disponível)')
    args = parser.parse_args()
    
    use_candles = args.candles  # Ticks por padrão
    
    # Define período
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    else:
        end_date = datetime.now() - timedelta(days=1)  # Ontem
    
    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
    else:
        start_date = end_date - timedelta(days=args.years * 365)
    
    symbols = args.symbols or list(SYMBOLS.keys())
    
    print(f"\n📋 Configuração:")
    print(f"   Período: {start_date.date()} até {end_date.date()} ({args.years} anos)")
    print(f"   Símbolos: {', '.join(symbols)}")
    print(f"   Workers: {args.workers}")
    print(f"   Saída: {OUTPUT_DIR}")
    
    # Cria diretório
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        
        df = download_symbol(symbol, start_date, end_date, args.workers, use_candles)
        
        if df is not None and len(df) > 0:
            if save_data(df, symbol):
                days = (df['time'].max() - df['time'].min()).days
                results[symbol] = {
                    'status': 'ok',
                    'candles': len(df),
                    'days': days,
                    'start': str(df['time'].min())[:10],
                    'end': str(df['time'].max())[:10]
                }
            else:
                results[symbol] = {'status': 'save_error'}
        else:
            results[symbol] = {'status': 'no_data'}
        
        # Pausa entre símbolos
        time.sleep(2)
    
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
    
    print(f"\n📈 Total: {total_candles:,} candles M5")
    
    if total_candles > 0:
        print(f"\n✅ Dados salvos em: {OUTPUT_DIR}")
        print(f"   Próximo passo: python gpu_training/prepare_data.py")


if __name__ == "__main__":
    main()
