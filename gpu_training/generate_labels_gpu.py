"""
🚀 Generate Labels GPU - Simulação massiva de trades com CUDA
Testa milhares de combinações de parâmetros em paralelo.
"""
import os
import sys
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import json

# Verifica CUDA
try:
    import torch
    import torch.cuda as cuda
    HAS_CUDA = cuda.is_available()
    if HAS_CUDA:
        print(f"🚀 CUDA disponível: {cuda.get_device_name(0)}")
        print(f"   Memória: {cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    else:
        print("⚠️ CUDA não disponível, usando CPU")
except ImportError:
    HAS_CUDA = False
    print("⚠️ PyTorch não instalado")

print("="*60)
print("🎯 GERAÇÃO DE LABELS COM GPU")
print("="*60)


class GPUTradeSimulator:
    """Simulador de trades massivamente paralelo com CUDA."""
    
    def __init__(self, device: str = 'cuda'):
        self.device = torch.device(device if HAS_CUDA else 'cpu')
        print(f"   Device: {self.device}")
    
    def load_data(self, data_dir: Path, symbol: str, timeframe: str = "M5") -> pd.DataFrame:
        """Carrega dados históricos."""
        symbol_dir = data_dir / symbol.replace("-", "_")
        
        if not symbol_dir.exists():
            print(f"❌ Pasta não encontrada: {symbol_dir}")
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
    
    def calculate_indicators_gpu(self, df: pd.DataFrame) -> Dict[str, torch.Tensor]:
        """Calcula indicadores técnicos na GPU."""
        # Converte para tensores
        close = torch.tensor(df['close'].values, dtype=torch.float32, device=self.device)
        high = torch.tensor(df['high'].values, dtype=torch.float32, device=self.device)
        low = torch.tensor(df['low'].values, dtype=torch.float32, device=self.device)
        
        n = len(close)
        
        # SMA (usando convolução)
        def sma_gpu(data: torch.Tensor, period: int) -> torch.Tensor:
            kernel = torch.ones(period, device=self.device) / period
            # Pad para manter tamanho
            padded = torch.nn.functional.pad(data.unsqueeze(0).unsqueeze(0), (period-1, 0), mode='replicate')
            result = torch.nn.functional.conv1d(padded, kernel.unsqueeze(0).unsqueeze(0))
            return result.squeeze()
        
        sma9 = sma_gpu(close, 9)
        sma21 = sma_gpu(close, 21)
        
        # RSI
        delta = close[1:] - close[:-1]
        delta = torch.cat([torch.zeros(1, device=self.device), delta])
        
        gain = torch.where(delta > 0, delta, torch.zeros_like(delta))
        loss = torch.where(delta < 0, -delta, torch.zeros_like(delta))
        
        avg_gain = sma_gpu(gain, 14)
        avg_loss = sma_gpu(loss, 14)
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        # ATR
        tr1 = high - low
        tr2 = torch.abs(high - torch.cat([close[:1], close[:-1]]))
        tr3 = torch.abs(low - torch.cat([close[:1], close[:-1]]))
        tr = torch.maximum(torch.maximum(tr1, tr2), tr3)
        atr = sma_gpu(tr, 14)
        
        # MACD
        def ema_gpu(data: torch.Tensor, period: int) -> torch.Tensor:
            alpha = 2 / (period + 1)
            result = torch.zeros_like(data)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
            return result
        
        ema12 = ema_gpu(close, 12)
        ema26 = ema_gpu(close, 26)
        macd_line = ema12 - ema26
        macd_signal = ema_gpu(macd_line, 9)
        macd_hist = macd_line - macd_signal
        
        return {
            'close': close,
            'high': high,
            'low': low,
            'sma9': sma9,
            'sma21': sma21,
            'rsi': rsi,
            'atr': atr,
            'macd_line': macd_line,
            'macd_signal': macd_signal,
            'macd_hist': macd_hist,
        }
    
    def simulate_trades_gpu(
        self,
        indicators: Dict[str, torch.Tensor],
        sl_multipliers: List[float],
        tp_multipliers: List[float],
        lookahead_bars: List[int],
        use_trailing: List[bool]
    ) -> Dict:
        """
        Simula trades com múltiplas combinações de parâmetros em paralelo.
        
        Returns:
            Dict com resultados de cada combinação
        """
        close = indicators['close']
        high = indicators['high']
        low = indicators['low']
        atr = indicators['atr']
        sma9 = indicators['sma9']
        sma21 = indicators['sma21']
        rsi = indicators['rsi']
        
        n = len(close)
        results = []
        
        # Gera sinais de entrada (SMA crossover + RSI)
        sma_cross = (sma9 > sma21).float() - (sma9 < sma21).float()
        buy_signal = (sma_cross == 1) & (rsi < 70)
        sell_signal = (sma_cross == -1) & (rsi > 30)
        
        total_combinations = len(sl_multipliers) * len(tp_multipliers) * len(lookahead_bars) * len(use_trailing)
        print(f"   Testando {total_combinations:,} combinações de parâmetros...")
        
        combo_idx = 0
        for sl_mult in sl_multipliers:
            for tp_mult in tp_multipliers:
                for lookahead in lookahead_bars:
                    for trailing in use_trailing:
                        combo_idx += 1
                        
                        # Simula trades para esta combinação
                        wins = 0
                        losses = 0
                        total_profit = 0.0
                        trades = []
                        
                        # Processa cada candle
                        for i in range(50, n - lookahead):
                            if atr[i] == 0:
                                continue
                            
                            entry_price = close[i].item()
                            current_atr = atr[i].item()
                            
                            # BUY signal
                            if buy_signal[i]:
                                sl = entry_price - current_atr * sl_mult
                                tp = entry_price + current_atr * tp_mult
                                trailing_sl = sl
                                
                                result = None
                                exit_price = entry_price
                                
                                for j in range(i+1, min(i+lookahead, n)):
                                    current_low = low[j].item()
                                    current_high = high[j].item()
                                    current_close = close[j].item()
                                    
                                    # Check SL
                                    if current_low <= trailing_sl:
                                        exit_price = trailing_sl
                                        result = 1 if trailing_sl > entry_price else 0
                                        break
                                    
                                    # Check TP
                                    if current_high >= tp:
                                        exit_price = tp
                                        result = 1
                                        break
                                    
                                    # Trailing stop
                                    if trailing:
                                        new_trailing = current_close - current_atr * 1.0
                                        if new_trailing > trailing_sl:
                                            trailing_sl = new_trailing
                                
                                if result is None:
                                    exit_price = close[min(i+lookahead-1, n-1)].item()
                                    result = 1 if exit_price > entry_price else 0
                                
                                profit = (exit_price - entry_price) / entry_price * 100
                                
                                if result == 1:
                                    wins += 1
                                else:
                                    losses += 1
                                total_profit += profit
                                
                                trades.append({
                                    'type': 'BUY',
                                    'entry': entry_price,
                                    'exit': exit_price,
                                    'profit_pct': profit,
                                    'result': result
                                })
                            
                            # SELL signal
                            elif sell_signal[i]:
                                sl = entry_price + current_atr * sl_mult
                                tp = entry_price - current_atr * tp_mult
                                trailing_sl = sl
                                
                                result = None
                                exit_price = entry_price
                                
                                for j in range(i+1, min(i+lookahead, n)):
                                    current_low = low[j].item()
                                    current_high = high[j].item()
                                    current_close = close[j].item()
                                    
                                    # Check SL
                                    if current_high >= trailing_sl:
                                        exit_price = trailing_sl
                                        result = 1 if trailing_sl < entry_price else 0
                                        break
                                    
                                    # Check TP
                                    if current_low <= tp:
                                        exit_price = tp
                                        result = 1
                                        break
                                    
                                    # Trailing stop
                                    if trailing:
                                        new_trailing = current_close + current_atr * 1.0
                                        if new_trailing < trailing_sl:
                                            trailing_sl = new_trailing
                                
                                if result is None:
                                    exit_price = close[min(i+lookahead-1, n-1)].item()
                                    result = 1 if exit_price < entry_price else 0
                                
                                profit = (entry_price - exit_price) / entry_price * 100
                                
                                if result == 1:
                                    wins += 1
                                else:
                                    losses += 1
                                total_profit += profit
                                
                                trades.append({
                                    'type': 'SELL',
                                    'entry': entry_price,
                                    'exit': exit_price,
                                    'profit_pct': profit,
                                    'result': result
                                })
                        
                        total_trades = wins + losses
                        win_rate = wins / total_trades if total_trades > 0 else 0
                        avg_profit = total_profit / total_trades if total_trades > 0 else 0
                        
                        results.append({
                            'sl_mult': sl_mult,
                            'tp_mult': tp_mult,
                            'lookahead': lookahead,
                            'trailing': trailing,
                            'total_trades': total_trades,
                            'wins': wins,
                            'losses': losses,
                            'win_rate': win_rate,
                            'total_profit_pct': total_profit,
                            'avg_profit_pct': avg_profit,
                            'profit_factor': (wins * avg_profit) / (losses * abs(avg_profit) + 1e-10) if losses > 0 else float('inf')
                        })
                        
                        if combo_idx % 100 == 0:
                            print(f"   Progresso: {combo_idx}/{total_combinations}")
        
        return results
    
    def find_best_params(self, results: List[Dict]) -> Dict:
        """Encontra os melhores parâmetros."""
        # Ordena por win_rate * profit_factor
        scored = []
        for r in results:
            if r['total_trades'] < 100:  # Mínimo de trades
                continue
            score = r['win_rate'] * (1 + r['avg_profit_pct'])
            scored.append((score, r))
        
        scored.sort(key=lambda x: -x[0])
        
        if not scored:
            return None
        
        return scored[0][1]


def main():
    parser = argparse.ArgumentParser(description='Gera labels com simulação GPU')
    parser.add_argument('--data-dir', default='historical_data', help='Pasta com dados')
    parser.add_argument('--output-dir', default='gpu_training/results', help='Pasta de saída')
    parser.add_argument('--symbols', nargs='+', default=None, help='Símbolos')
    parser.add_argument('--simulations', type=int, default=1000, help='Número de simulações')
    args = parser.parse_args()
    
    # Símbolos padrão
    if args.symbols:
        symbols = args.symbols
    else:
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "EURJPY", "GBPJPY"]
    
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Parâmetros para testar
    sl_multipliers = np.arange(0.5, 3.0, 0.25).tolist()  # 10 valores
    tp_multipliers = np.arange(1.0, 5.0, 0.5).tolist()   # 8 valores
    lookahead_bars = [10, 15, 20, 25, 30, 40, 50]        # 7 valores
    use_trailing = [True, False]                         # 2 valores
    
    total_combos = len(sl_multipliers) * len(tp_multipliers) * len(lookahead_bars) * len(use_trailing)
    print(f"\n📋 Configuração:")
    print(f"   Combinações por símbolo: {total_combos:,}")
    print(f"   Símbolos: {len(symbols)}")
    print(f"   Total de simulações: {total_combos * len(symbols):,}")
    
    # Simulador
    simulator = GPUTradeSimulator()
    
    all_results = {}
    best_params = {}
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"📊 Processando {symbol}...")
        print(f"{'='*60}")
        
        # Carrega dados
        df = simulator.load_data(data_dir, symbol)
        if df is None or len(df) < 1000:
            print(f"   ⚠️ Dados insuficientes para {symbol}")
            continue
        
        print(f"   📅 {len(df):,} candles ({df['time'].min()} até {df['time'].max()})")
        
        # Calcula indicadores
        print(f"   🔧 Calculando indicadores...")
        indicators = simulator.calculate_indicators_gpu(df)
        
        # Simula trades
        print(f"   🎯 Simulando trades...")
        results = simulator.simulate_trades_gpu(
            indicators,
            sl_multipliers,
            tp_multipliers,
            lookahead_bars,
            use_trailing
        )
        
        all_results[symbol] = results
        
        # Encontra melhores parâmetros
        best = simulator.find_best_params(results)
        if best:
            best_params[symbol] = best
            print(f"\n   🏆 MELHORES PARÂMETROS PARA {symbol}:")
            print(f"      SL Mult: {best['sl_mult']:.2f}")
            print(f"      TP Mult: {best['tp_mult']:.2f}")
            print(f"      Lookahead: {best['lookahead']} bars")
            print(f"      Trailing: {best['trailing']}")
            print(f"      Win Rate: {best['win_rate']:.1%}")
            print(f"      Trades: {best['total_trades']:,}")
            print(f"      Avg Profit: {best['avg_profit_pct']:.3f}%")
    
    # Salva resultados
    results_file = output_dir / "simulation_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            'best_params': best_params,
            'timestamp': datetime.now().isoformat(),
            'total_simulations': total_combos * len(symbols)
        }, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"✅ Simulação concluída!")
    print(f"   Resultados salvos em: {results_file}")
    print(f"{'='*60}")
    
    # Resumo
    print(f"\n📊 RESUMO DOS MELHORES PARÂMETROS:")
    print("-"*60)
    for symbol, params in best_params.items():
        print(f"{symbol}: SL={params['sl_mult']:.1f}x TP={params['tp_mult']:.1f}x "
              f"WR={params['win_rate']:.1%} ({params['total_trades']} trades)")


if __name__ == "__main__":
    main()
