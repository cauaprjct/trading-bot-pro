"""
🎯 Optimize Hyperparameters - Otimização Bayesiana com Optuna
Encontra os melhores hiperparâmetros para o modelo.
"""
import os
import sys
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple
import json

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score

try:
    import optuna
    from optuna.pruners import MedianPruner
    from optuna.samplers import TPESampler
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False
    print("⚠️ Optuna não instalado. Execute: pip install optuna")

print("="*60)
print("🎯 OTIMIZAÇÃO DE HIPERPARÂMETROS COM OPTUNA")
print("="*60)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Device: {device}")


class TradingDataset(Dataset):
    """Dataset para séries temporais."""
    
    def __init__(self, X: np.ndarray, y: np.ndarray, seq_length: int = 60):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32)
        self.seq_length = seq_length
    
    def __len__(self):
        return len(self.X) - self.seq_length
    
    def __getitem__(self, idx):
        return self.X[idx:idx + self.seq_length], self.y[idx + self.seq_length]


class FlexibleLSTM(nn.Module):
    """LSTM com hiperparâmetros flexíveis."""
    
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float):
        super().__init__()
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        out = lstm_out[:, -1, :]
        return self.fc(out).squeeze()


class HyperparamOptimizer:
    """Otimizador de hiperparâmetros com Optuna."""
    
    def __init__(self, data_dir: Path, output_dir: Path):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.X = None
        self.y = None
        self.feature_names = []
        self.scaler = StandardScaler()
    
    def load_data(self, symbol: str, timeframe: str = "M5") -> bool:
        """Carrega e prepara dados."""
        symbol_dir = self.data_dir / symbol.replace("-", "_")
        
        if not symbol_dir.exists():
            print(f"❌ Pasta não encontrada: {symbol_dir}")
            return False
        
        # Carrega CSVs
        dfs = []
        for f in sorted(symbol_dir.glob(f"{timeframe}_*.csv")):
            df = pd.read_csv(f)
            df['time'] = pd.to_datetime(df['time'])
            dfs.append(df)
        
        if not dfs:
            return False
        
        df = pd.concat(dfs, ignore_index=True)
        df = df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
        
        print(f"   📊 {len(df):,} candles carregados")
        
        # Features
        df = self._calculate_features(df)
        df = self._generate_labels(df)
        df = df.dropna()
        
        self.X = self.scaler.fit_transform(df[self.feature_names].values)
        self.y = df['label'].values
        
        print(f"   ✅ Dataset: {len(self.X):,} amostras")
        
        return True
    
    def _calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula features."""
        df['returns'] = df['close'].pct_change()
        
        for period in [5, 9, 21, 50]:
            df[f'sma_{period}'] = df['close'].rolling(period).mean()
            df[f'close_vs_sma_{period}'] = (df['close'] - df[f'sma_{period}']) / df[f'sma_{period}']
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
        
        # MACD
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        
        # ATR
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = tr.rolling(14).mean()
        df['atr_pct'] = df['atr'] / df['close']
        
        # Volatilidade
        df['volatility'] = df['returns'].rolling(20).std()
        
        # Momentum
        df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
        df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        
        # Hora
        df['hour'] = df['time'].dt.hour
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        
        self.feature_names = [
            'returns', 'close_vs_sma_5', 'close_vs_sma_9', 'close_vs_sma_21',
            'rsi', 'macd', 'macd_signal', 'atr_pct', 'volatility',
            'momentum_5', 'momentum_10', 'hour_sin', 'hour_cos'
        ]
        
        return df
    
    def _generate_labels(self, df: pd.DataFrame, lookahead: int = 20) -> pd.DataFrame:
        """Gera labels."""
        future_return = df['close'].shift(-lookahead) / df['close'] - 1
        df['label'] = (future_return > 0.001).astype(float)
        return df
    
    def objective(self, trial: optuna.Trial) -> float:
        """Função objetivo para Optuna."""
        # Hiperparâmetros a otimizar
        hidden_size = trial.suggest_int('hidden_size', 32, 256, step=32)
        num_layers = trial.suggest_int('num_layers', 1, 4)
        dropout = trial.suggest_float('dropout', 0.1, 0.5)
        seq_length = trial.suggest_int('seq_length', 20, 100, step=10)
        learning_rate = trial.suggest_float('learning_rate', 1e-5, 1e-2, log=True)
        batch_size = trial.suggest_categorical('batch_size', [64, 128, 256, 512])
        
        # Time series split
        tscv = TimeSeriesSplit(n_splits=3)
        f1_scores = []
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(self.X)):
            X_train, X_val = self.X[train_idx], self.X[val_idx]
            y_train, y_val = self.y[train_idx], self.y[val_idx]
            
            # Datasets
            train_dataset = TradingDataset(X_train, y_train, seq_length)
            val_dataset = TradingDataset(X_val, y_val, seq_length)
            
            if len(train_dataset) < batch_size or len(val_dataset) < batch_size:
                continue
            
            train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
            
            # Modelo
            model = FlexibleLSTM(
                input_size=self.X.shape[1],
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout
            ).to(device)
            
            criterion = nn.BCELoss()
            optimizer = optim.AdamW(model.parameters(), lr=learning_rate)
            
            # Treino rápido (20 epochs)
            for epoch in range(20):
                model.train()
                for X_batch, y_batch in train_loader:
                    X_batch = X_batch.to(device)
                    y_batch = y_batch.to(device)
                    
                    optimizer.zero_grad()
                    outputs = model(X_batch)
                    loss = criterion(outputs, y_batch)
                    loss.backward()
                    optimizer.step()
            
            # Validação
            model.eval()
            all_preds = []
            all_labels = []
            
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(device)
                    outputs = model(X_batch)
                    preds = (outputs > 0.5).float()
                    all_preds.extend(preds.cpu().numpy())
                    all_labels.extend(y_batch.numpy())
            
            f1 = f1_score(all_labels, all_preds)
            f1_scores.append(f1)
            
            # Pruning
            trial.report(f1, fold)
            if trial.should_prune():
                raise optuna.TrialPruned()
        
        return np.mean(f1_scores) if f1_scores else 0.0
    
    def optimize(self, n_trials: int = 100) -> Dict:
        """Executa otimização."""
        if not HAS_OPTUNA:
            print("❌ Optuna não instalado!")
            return {}
        
        print(f"\n🎯 Iniciando otimização com {n_trials} trials...")
        
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(n_startup_trials=10, n_warmup_steps=5)
        )
        
        study.optimize(
            self.objective,
            n_trials=n_trials,
            show_progress_bar=True,
            n_jobs=1  # GPU não suporta multiprocessing
        )
        
        print(f"\n🏆 MELHORES HIPERPARÂMETROS:")
        print(f"   F1 Score: {study.best_value:.3f}")
        for key, value in study.best_params.items():
            print(f"   {key}: {value}")
        
        return study.best_params
    
    def save_results(self, best_params: Dict, symbol: str):
        """Salva resultados."""
        results_file = self.output_dir / f"{symbol.lower()}_best_params.json"
        
        with open(results_file, 'w') as f:
            json.dump({
                'symbol': symbol,
                'best_params': best_params,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n💾 Resultados salvos: {results_file}")


def main():
    parser = argparse.ArgumentParser(description='Otimiza hiperparâmetros')
    parser.add_argument('--data-dir', default='historical_data', help='Pasta com dados')
    parser.add_argument('--output-dir', default='gpu_training/results', help='Pasta de saída')
    parser.add_argument('--symbol', default='EURUSD', help='Símbolo')
    parser.add_argument('--trials', type=int, default=100, help='Número de trials')
    args = parser.parse_args()
    
    optimizer = HyperparamOptimizer(Path(args.data_dir), Path(args.output_dir))
    
    print(f"\n📊 Carregando dados para {args.symbol}...")
    if not optimizer.load_data(args.symbol):
        print("❌ Falha ao carregar dados")
        return
    
    best_params = optimizer.optimize(n_trials=args.trials)
    optimizer.save_results(best_params, args.symbol)
    
    print(f"\n{'='*60}")
    print(f"✅ Otimização concluída!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
