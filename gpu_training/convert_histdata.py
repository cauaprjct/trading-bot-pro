"""
🔄 Conversor HistData.com -> Formato GPU Training
Converte arquivos CSV/ZIP baixados do HistData para o formato usado pelo pipeline.

Uso:
1. Baixe os dados de https://www.histdata.com/download-free-forex-data/
2. Coloque os ZIPs em gpu_training/historical_data_raw/SYMBOL/
3. Execute: python convert_histdata.py

Estrutura esperada:
gpu_training/historical_data_raw/
├── EURUSD/
│   ├── HISTDATA_COM_ASCII_EURUSD_M1_2023.zip
│   ├── HISTDATA_COM_ASCII_EURUSD_M1_2024.zip
│   └── HISTDATA_COM_ASCII_EURUSD_M1_2025.zip
├── GBPUSD/
│   └── ...
"""
import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import glob
import zipfile
import io

print("="*60)
print("🔄 CONVERSOR HISTDATA.COM -> GPU TRAINING")
print("="*60)

# Diretórios
RAW_DIR = Path("gpu_training/historical_data_raw")
OUTPUT_DIR = Path("gpu_training/historical_data")

# Símbolos do bot
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "EURJPY", "GBPJPY"]


def process_histdata_df(df: pd.DataFrame) -> pd.DataFrame:
    """Processa DataFrame do HistData para formato padrão."""
    try:
        if df is None or len(df) == 0:
            return None
        
        # Identifica formato pelo número de colunas
        n_cols = len(df.columns)
        
        if n_cols == 6:
            # Formato: DateTime;Open;High;Low;Close;Volume
            # DateTime pode ser: 20230102 000000 ou 2023.01.02 00:00
            df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
            
            # Parse datetime
            dt_sample = str(df['datetime'].iloc[0])
            
            if ' ' in dt_sample and len(dt_sample) == 15:
                # Formato: 20230102 000000
                df['time'] = pd.to_datetime(df['datetime'], format='%Y%m%d %H%M%S')
            elif '.' in dt_sample:
                # Formato: 2023.01.02 00:00
                df['time'] = pd.to_datetime(df['datetime'], format='%Y.%m.%d %H:%M')
            else:
                # Tenta parse automático
                df['time'] = pd.to_datetime(df['datetime'])
        
        elif n_cols == 7:
            # Formato: Date;Time;Open;High;Low;Close;Volume
            df.columns = ['date', 'time_str', 'open', 'high', 'low', 'close', 'volume']
            df['time'] = pd.to_datetime(df['date'] + ' ' + df['time_str'])
        
        elif n_cols == 8:
            # Formato MetaTrader: Ticker,Date,Time,Open,High,Low,Close,Volume
            df.columns = ['ticker', 'date', 'time_str', 'open', 'high', 'low', 'close', 'volume']
            df['time'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time_str'].astype(str))
        
        else:
            return None
        
        # Converte colunas numéricas
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Seleciona colunas finais
        result = df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
        result = result.dropna()
        result = result.sort_values('time')
        
        return result
        
    except Exception as e:
        return None


def parse_histdata_csv(filepath: Path) -> pd.DataFrame:
    """
    Parse arquivo CSV do HistData.
    
    Formatos possíveis:
    1. Sem header: DateTime;Open;High;Low;Close;Volume
    2. Com header: <TICKER>,<DTYYYYMMDD>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>
    3. Formato ASCII: 20230102 000000;1.06695;1.06695;1.06695;1.06695;0
    """
    try:
        # Tenta ler com diferentes separadores
        df = None
        for sep in [';', ',', '\t']:
            try:
                df = pd.read_csv(filepath, sep=sep, header=None, dtype=str)
                if len(df.columns) >= 5:
                    break
            except:
                continue
        
        if df is None or len(df) == 0:
            return None
        
        return process_histdata_df(df)
        
    except Exception as e:
        print(f"   ❌ Erro ao processar {filepath}: {e}")
        return None


def convert_m1_to_m5(df: pd.DataFrame) -> pd.DataFrame:
    """Converte dados M1 para M5 usando resampling."""
    if df is None or len(df) == 0:
        return None
    
    df = df.set_index('time')
    
    # Resample para 5 minutos
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


def process_symbol(symbol: str) -> dict:
    """Processa todos os arquivos de um símbolo."""
    symbol_raw_dir = RAW_DIR / symbol
    symbol_out_dir = OUTPUT_DIR / symbol
    
    # Procura arquivos ZIP e CSV
    zip_files = list(symbol_raw_dir.glob("*.zip"))
    csv_files = list(symbol_raw_dir.glob("*.csv"))
    
    all_files = zip_files + csv_files
    
    if not all_files:
        return {'status': 'no_files', 'files': 0}
    
    print(f"\n   📁 Encontrados {len(zip_files)} ZIPs, {len(csv_files)} CSVs")
    
    # Processa cada arquivo
    all_data = []
    
    # Processa ZIPs
    for zip_path in sorted(zip_files):
        print(f"   📦 Extraindo: {zip_path.name}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('.csv'):
                        print(f"      📄 {name}")
                        with zf.open(name) as f:
                            content = f.read().decode('utf-8')
                            df = parse_histdata_content(content)
                            
                            if df is not None and len(df) > 0:
                                print(f"         ✅ {len(df):,} candles M1")
                                all_data.append(df)
                            else:
                                print(f"         ⚠️ Sem dados válidos")
        except Exception as e:
            print(f"      ❌ Erro: {e}")
    
    # Processa CSVs diretos
    for csv_path in sorted(csv_files):
        print(f"   📄 Processando: {csv_path.name}")
        
        df = parse_histdata_csv(csv_path)
        
        if df is not None and len(df) > 0:
            print(f"      ✅ {len(df):,} candles M1")
            all_data.append(df)
        else:
            print(f"      ⚠️ Sem dados válidos")
    
    if not all_data:
        return {'status': 'no_valid_data', 'files': len(all_files)}
    
    # Concatena todos os dados
    df_all = pd.concat(all_data, ignore_index=True)
    df_all = df_all.drop_duplicates(subset=['time'])
    df_all = df_all.sort_values('time')
    
    print(f"\n   📊 Total M1: {len(df_all):,} candles")
    print(f"   📅 Período: {df_all['time'].min()} até {df_all['time'].max()}")
    
    # Converte para M5
    print(f"   🔄 Convertendo para M5...")
    df_m5 = convert_m1_to_m5(df_all)
    
    if df_m5 is None or len(df_m5) == 0:
        return {'status': 'conversion_error', 'files': len(all_files)}
    
    print(f"   📊 Total M5: {len(df_m5):,} candles")
    
    # Salva por mês
    symbol_out_dir.mkdir(parents=True, exist_ok=True)
    
    df_m5['year_month'] = df_m5['time'].dt.strftime('%Y-%m')
    
    for ym, group in df_m5.groupby('year_month'):
        filename = f"M5_{ym}.csv"
        filepath = symbol_out_dir / filename
        
        cols = ['time', 'open', 'high', 'low', 'close', 'tick_volume']
        group[cols].to_csv(filepath, index=False)
    
    # Calcula estatísticas
    days = (df_m5['time'].max() - df_m5['time'].min()).days
    
    return {
        'status': 'ok',
        'files': len(all_files),
        'candles_m1': len(df_all),
        'candles_m5': len(df_m5),
        'days': days,
        'start': str(df_m5['time'].min())[:10],
        'end': str(df_m5['time'].max())[:10]
    }


def parse_histdata_content(content: str) -> pd.DataFrame:
    """Parse conteúdo CSV do HistData (de dentro do ZIP)."""
    try:
        # Tenta diferentes separadores
        for sep in [';', ',', '\t']:
            try:
                df = pd.read_csv(io.StringIO(content), sep=sep, header=None, dtype=str)
                if len(df.columns) >= 5:
                    break
            except:
                continue
        
        if df is None or len(df) == 0:
            return None
        
        return process_histdata_df(df)
        
    except Exception as e:
        print(f"         ❌ Erro: {e}")
        return None


def main():
    # Verifica diretório de entrada
    if not RAW_DIR.exists():
        print(f"\n❌ Diretório não encontrado: {RAW_DIR}")
        print(f"\n📋 INSTRUÇÕES:")
        print(f"="*60)
        print("""
1. Crie a pasta: gpu_training/historical_data_raw/

2. Acesse: https://www.histdata.com/download-free-forex-data/

3. Para cada símbolo (EURUSD, GBPUSD, USDJPY, USDCAD, AUDUSD, EURJPY, GBPJPY):
   a. Clique no símbolo
   b. Selecione "ASCII" e "1-Minute Bar Quotes"
   c. Baixe os anos: 2023, 2024, 2025
   d. Extraia os ZIPs na pasta correspondente

4. Estrutura final:
   gpu_training/historical_data_raw/
   ├── EURUSD/
   │   ├── DAT_ASCII_EURUSD_M1_2023.csv
   │   ├── DAT_ASCII_EURUSD_M1_2024.csv
   │   └── DAT_ASCII_EURUSD_M1_2025.csv
   ├── GBPUSD/
   │   └── ...
   └── ...

5. Execute novamente: python gpu_training/convert_histdata.py
        """)
        
        # Cria estrutura de pastas
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        for symbol in SYMBOLS:
            (RAW_DIR / symbol).mkdir(exist_ok=True)
        
        print(f"\n✅ Pastas criadas em: {RAW_DIR}")
        return
    
    # Cria diretório de saída
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Processa cada símbolo
    results = {}
    
    for symbol in SYMBOLS:
        print(f"\n{'='*50}")
        print(f"📊 {symbol}")
        print(f"{'='*50}")
        
        symbol_dir = RAW_DIR / symbol
        
        if not symbol_dir.exists():
            print(f"   ⚠️ Pasta não encontrada: {symbol_dir}")
            results[symbol] = {'status': 'no_folder'}
            continue
        
        results[symbol] = process_symbol(symbol)
    
    # Resumo final
    print(f"\n{'='*60}")
    print("📊 RESUMO DA CONVERSÃO")
    print("="*60)
    
    total_candles = 0
    total_days = 0
    
    for symbol, info in results.items():
        if info['status'] == 'ok':
            print(f"✅ {symbol}: {info['candles_m5']:,} candles M5 | {info['days']} dias | {info['start']} a {info['end']}")
            total_candles += info['candles_m5']
            total_days = max(total_days, info['days'])
        else:
            print(f"❌ {symbol}: {info['status']}")
    
    print(f"\n📈 Total: {total_candles:,} candles M5")
    print(f"📅 Período máximo: {total_days} dias (~{total_days/365:.1f} anos)")
    
    if total_candles > 0:
        print(f"\n✅ Dados salvos em: {OUTPUT_DIR}")
        print(f"   Próximo passo: python gpu_training/prepare_data.py")


if __name__ == "__main__":
    main()
