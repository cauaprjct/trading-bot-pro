"""
📥 Download de Histórico para TODOS os Ativos
Baixa dados históricos de M5 para treinar o ML em cada ativo.

Uso: python download_all_history.py
"""

import os
import sys
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

# Ativos para baixar
ASSETS = [
    "GBPUSD",
    "EURUSD", 
    "USDCAD",
    "USDJPY",
    "EURJPY",
    "GBPJPY",
    "AUDUSD",
]

# Configurações
TIMEFRAME = mt5.TIMEFRAME_M5  # M5 para treino
MONTHS_HISTORY = 6            # 6 meses de histórico
OUTPUT_DIR = "historical_data"


def download_symbol(symbol: str, timeframe, months: int) -> bool:
    """Baixa histórico de um símbolo."""
    
    # Verifica se símbolo existe
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"  ❌ {symbol}: Símbolo não encontrado")
        return False
    
    if not info.visible:
        # Tenta habilitar
        if not mt5.symbol_select(symbol, True):
            print(f"  ❌ {symbol}: Não foi possível habilitar")
            return False
    
    # Calcula período
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30)
    
    # Baixa dados
    rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
    
    if rates is None or len(rates) == 0:
        print(f"  ❌ {symbol}: Sem dados disponíveis")
        return False
    
    # Converte para DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Cria pasta do símbolo
    symbol_dir = os.path.join(OUTPUT_DIR, symbol)
    if not os.path.exists(symbol_dir):
        os.makedirs(symbol_dir)
    
    # Salva por mês
    df['month'] = df['time'].dt.to_period('M')
    
    files_saved = 0
    for month, group in df.groupby('month'):
        filename = f"M5_{month}.csv"
        filepath = os.path.join(symbol_dir, filename)
        group.drop('month', axis=1).to_csv(filepath, index=False)
        files_saved += 1
    
    print(f"  ✅ {symbol}: {len(df):,} candles | {files_saved} arquivos")
    return True


def main():
    print("="*60)
    print("📥 DOWNLOAD DE HISTÓRICO - MULTI-ATIVO")
    print("="*60)
    print()
    
    # Conecta ao MT5
    if not mt5.initialize():
        print("❌ Falha ao conectar ao MT5!")
        return
    
    print("✅ Conectado ao MT5")
    print()
    
    # Cria pasta principal
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Baixa cada ativo
    print(f"📊 Baixando {MONTHS_HISTORY} meses de histórico M5...")
    print("-"*50)
    
    success = 0
    failed = 0
    
    for symbol in ASSETS:
        if download_symbol(symbol, TIMEFRAME, MONTHS_HISTORY):
            success += 1
        else:
            failed += 1
    
    print("-"*50)
    print()
    print(f"✅ Sucesso: {success} ativos")
    print(f"❌ Falha: {failed} ativos")
    print()
    
    # Lista arquivos baixados
    print("📁 Arquivos salvos:")
    for symbol in ASSETS:
        symbol_dir = os.path.join(OUTPUT_DIR, symbol)
        if os.path.exists(symbol_dir):
            files = os.listdir(symbol_dir)
            total_size = sum(os.path.getsize(os.path.join(symbol_dir, f)) for f in files)
            print(f"  {symbol}: {len(files)} arquivos ({total_size/1024/1024:.1f} MB)")
    
    print()
    print("="*60)
    print("✅ Download concluído!")
    print("   Agora rode: python train_all_models.py")
    print("="*60)
    
    mt5.shutdown()


if __name__ == "__main__":
    main()
