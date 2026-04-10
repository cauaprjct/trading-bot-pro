"""
📦 Prepare Data - Prepara dados para treinamento GPU
Este script verifica e prepara os dados históricos.

IMPORTANTE: Copie a pasta 'historical_data/' do Windows para a instância GPU
antes de executar este script.
"""
import os
import sys
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

print("="*60)
print("📦 PREPARAÇÃO DE DADOS PARA TREINAMENTO GPU")
print("="*60)


def check_data(data_dir: Path, symbols: list, timeframe: str = "M5") -> dict:
    """Verifica dados disponíveis."""
    results = {}
    
    print(f"\n📁 Verificando dados em: {data_dir}")
    print("-"*50)
    
    if not data_dir.exists():
        print(f"❌ Pasta não encontrada: {data_dir}")
        print(f"\n💡 INSTRUÇÕES:")
        print(f"   1. Copie a pasta 'historical_data/' do Windows")
        print(f"   2. Cole na mesma pasta deste script")
        print(f"   3. Execute novamente")
        return {}
    
    for symbol in symbols:
        symbol_dir = data_dir / symbol.replace("-", "_")
        
        if not symbol_dir.exists():
            print(f"❌ {symbol}: Pasta não encontrada")
            results[symbol] = {"status": "missing", "candles": 0}
            continue
        
        # Conta candles
        total_candles = 0
        files = list(symbol_dir.glob(f"{timeframe}_*.csv"))
        
        if not files:
            print(f"⚠️ {symbol}: Nenhum arquivo {timeframe} encontrado")
            results[symbol] = {"status": "no_files", "candles": 0}
            continue
        
        min_date = None
        max_date = None
        
        for f in files:
            try:
                df = pd.read_csv(f)
                total_candles += len(df)
                
                df['time'] = pd.to_datetime(df['time'])
                if min_date is None or df['time'].min() < min_date:
                    min_date = df['time'].min()
                if max_date is None or df['time'].max() > max_date:
                    max_date = df['time'].max()
            except Exception as e:
                print(f"   ⚠️ Erro em {f.name}: {e}")
        
        days = (max_date - min_date).days if min_date and max_date else 0
        
        status = "ok" if total_candles >= 10000 else "low_data"
        results[symbol] = {
            "status": status,
            "candles": total_candles,
            "files": len(files),
            "min_date": str(min_date)[:10] if min_date else None,
            "max_date": str(max_date)[:10] if max_date else None,
            "days": days
        }
        
        status_emoji = "✅" if status == "ok" else "⚠️"
        print(f"{status_emoji} {symbol}: {total_candles:,} candles | {len(files)} arquivos | {days} dias")
    
    return results


def merge_data(data_dir: Path, symbol: str, timeframe: str = "M5") -> pd.DataFrame:
    """Combina todos os arquivos de um símbolo em um DataFrame."""
    symbol_dir = data_dir / symbol.replace("-", "_")
    
    if not symbol_dir.exists():
        return None
    
    dfs = []
    for f in sorted(symbol_dir.glob(f"{timeframe}_*.csv")):
        df = pd.read_csv(f)
        df['time'] = pd.to_datetime(df['time'])
        dfs.append(df)
    
    if not dfs:
        return None
    
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=['time'])
    combined = combined.sort_values('time').reset_index(drop=True)
    
    return combined


def validate_data(df: pd.DataFrame) -> dict:
    """Valida qualidade dos dados."""
    issues = []
    
    # Verifica colunas necessárias
    required_cols = ['time', 'open', 'high', 'low', 'close']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        issues.append(f"Colunas faltando: {missing_cols}")
    
    # Verifica NaN
    nan_count = df[required_cols].isna().sum().sum()
    if nan_count > 0:
        issues.append(f"NaN encontrados: {nan_count}")
    
    # Verifica valores negativos
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns and (df[col] <= 0).any():
            issues.append(f"Valores <= 0 em {col}")
    
    # Verifica high >= low
    if 'high' in df.columns and 'low' in df.columns:
        invalid = (df['high'] < df['low']).sum()
        if invalid > 0:
            issues.append(f"high < low em {invalid} linhas")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "rows": len(df),
        "date_range": f"{df['time'].min()} até {df['time'].max()}"
    }


def main():
    parser = argparse.ArgumentParser(description='Prepara dados para treinamento')
    parser.add_argument('--data-dir', default='historical_data', help='Pasta com dados')
    parser.add_argument('--symbols', nargs='+', default=None, help='Símbolos')
    parser.add_argument('--timeframe', default='M5', help='Timeframe')
    parser.add_argument('--validate', action='store_true', help='Valida qualidade dos dados')
    args = parser.parse_args()
    
    # Símbolos padrão
    if args.symbols:
        symbols = args.symbols
    else:
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "EURJPY", "GBPJPY"]
    
    data_dir = Path(args.data_dir)
    
    # Verifica dados
    results = check_data(data_dir, symbols, args.timeframe)
    
    if not results:
        return
    
    # Validação detalhada
    if args.validate:
        print(f"\n{'='*60}")
        print("🔍 VALIDAÇÃO DETALHADA")
        print("="*60)
        
        for symbol in symbols:
            if results.get(symbol, {}).get("status") != "ok":
                continue
            
            print(f"\n📊 {symbol}:")
            df = merge_data(data_dir, symbol, args.timeframe)
            if df is not None:
                validation = validate_data(df)
                if validation["valid"]:
                    print(f"   ✅ Dados válidos: {validation['rows']:,} linhas")
                    print(f"   📅 {validation['date_range']}")
                else:
                    print(f"   ⚠️ Problemas encontrados:")
                    for issue in validation["issues"]:
                        print(f"      - {issue}")
    
    # Resumo
    print(f"\n{'='*60}")
    print("📊 RESUMO")
    print("="*60)
    
    ok_count = sum(1 for r in results.values() if r.get("status") == "ok")
    total_candles = sum(r.get("candles", 0) for r in results.values())
    
    print(f"   Símbolos prontos: {ok_count}/{len(symbols)}")
    print(f"   Total de candles: {total_candles:,}")
    
    if ok_count < len(symbols):
        print(f"\n⚠️ Alguns símbolos precisam de mais dados.")
        print(f"   Execute no Windows: python download_all_history.py")
    else:
        print(f"\n✅ Dados prontos para treinamento!")
        print(f"   Execute: python gpu_training/run_full_pipeline.py")


if __name__ == "__main__":
    main()
