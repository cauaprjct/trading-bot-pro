"""
🧠 Train Deep Model - LSTM/Transformer para Trading
Usa GPU para treinar modelos de deep learning.
"""
import os
import sys
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import json
import pickle

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

print("="*60)
print("🧠 TREINAMENTO DE MODELO DEEP LEARNING")
print("="*60)


class FocalLoss(nn.Module):
    """Focal Loss para classes desbalanceadas."""
    def __init__(self, alpha=0.25, gamma=2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
    
    def forward(self, inputs, targets):
        bce = nn.functional.binary_cross_entropy_with_logits(inputs, targets, reduction='none')
        pt = torch.exp(-bce)
        focal_loss = self.alpha * (1 - pt) ** self.gamma * bce
        return focal_loss.mean()

# Verifica GPU
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Device: {device}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")


class TradingDataset(Dataset):
    """Dataset para séries temporais de trading."""
    
    def __init__(self, X: np.ndarray, y: np.ndarray, seq_length: int = 60):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32)
        self.seq_length = seq_length
    
    def __len__(self):
        return len(self.X) - self.seq_length
    
    def __getitem__(self, idx):
        X_seq = self.X[idx:idx + self.seq_length]
        y_val = self.y[idx + self.seq_length]
        return X_seq, y_val


class LSTMModel(nn.Module):
    """LSTM para trading com features expandidas."""
    
    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )
    
    def forward(self, x):
        # LSTM
        lstm_out, _ = self.lstm(x)
        
        # Usa última saída
        out = lstm_out[:, -1, :]
        
        # Classificação
        return self.fc(out).squeeze()


class TransformerModel(nn.Module):
    """Transformer para previsão de trades."""
    
    def __init__(
        self,
        input_size: int,
        d_model: int = 128,
        nhead: int = 8,
        num_layers: int = 4,
        dropout: float = 0.2
    ):
        super().__init__()
        
        self.input_projection = nn.Linear(input_size, d_model)
        
        self.pos_encoder = PositionalEncoding(d_model, dropout)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True
        )
        
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        self.fc = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
            # Sem Sigmoid - usamos BCEWithLogitsLoss
        )
    
    def forward(self, x):
        # Projeção de entrada
        x = self.input_projection(x)
        
        # Positional encoding
        x = self.pos_encoder(x)
        
        # Transformer
        x = self.transformer(x)
        
        # Usa última posição
        x = x[:, -1, :]
        
        # Classificação
        return self.fc(x).squeeze()


class PositionalEncoding(nn.Module):
    """Positional encoding para Transformer."""
    
    def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 500):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))
        
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe.unsqueeze(0))
    
    def forward(self, x):
        x = x + self.pe[:, :x.size(1)]
        return self.dropout(x)


class DeepTrainer:
    """Treinador de modelos deep learning."""
    
    def __init__(self, data_dir: Path, output_dir: Path):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.scaler = StandardScaler()
        self.feature_names = []
    
    def load_and_prepare_data(self, symbol: str, timeframe: str = "M5") -> Tuple[np.ndarray, np.ndarray]:
        """Carrega dados e prepara features."""
        symbol_dir = self.data_dir / symbol.replace("-", "_")
        
        if not symbol_dir.exists():
            print(f"❌ Pasta não encontrada: {symbol_dir}")
            return None, None
        
        # Carrega CSVs
        dfs = []
        for f in sorted(symbol_dir.glob(f"{timeframe}_*.csv")):
            df = pd.read_csv(f)
            df['time'] = pd.to_datetime(df['time'])
            dfs.append(df)
        
        if not dfs:
            return None, None
        
        df = pd.concat(dfs, ignore_index=True)
        df = df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
        
        print(f"   📊 {len(df):,} candles carregados")
        
        # Calcula features
        df = self._calculate_features(df)
        
        # Gera labels
        df = self._generate_labels(df)
        
        # Preenche NaN com valores padrão em vez de remover linhas
        # Isso preserva muito mais dados para treino
        for col in self.feature_names:
            if col in df.columns:
                df[col] = df[col].fillna(0)
        
        # Remove apenas linhas onde label é NaN (últimas N linhas do lookahead)
        df = df.dropna(subset=['label'])
        
        # Prepara X e y
        X = df[self.feature_names].values
        y = df['label'].values
        
        # Calcula class weights para lidar com desbalanceamento
        n_pos = y.sum()
        n_neg = len(y) - n_pos
        # Peso balanceado
        self.pos_weight = min(n_neg / (n_pos + 1e-10), 2.5)  # 2.5 para equilíbrio
        
        # Normaliza
        X = self.scaler.fit_transform(X)
        
        print(f"   ✅ Dataset: {len(X):,} amostras x {len(self.feature_names)} features")
        print(f"   📈 Win rate nos dados: {y.mean():.1%}")
        print(f"   ⚖️  Class weight (pos): {self.pos_weight:.2f}")
        
        return X, y
    
    def _calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula features técnicas - VERSÃO EXPANDIDA para Deep Learning."""
        # ═══════════════════════════════════════════════════════════════
        # Features expandidas para melhor performance em Deep Learning
        # ═══════════════════════════════════════════════════════════════
        
        # === PRICE ACTION ===
        df['returns'] = df['close'].pct_change()
        df['returns_2'] = df['close'].pct_change(2)
        df['returns_5'] = df['close'].pct_change(5)
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # High-Low range
        df['hl_range'] = (df['high'] - df['low']) / df['close']
        df['hl_range_ma'] = df['hl_range'].rolling(10, min_periods=1).mean()
        
        # Body size
        df['body'] = (df['close'] - df['open']) / df['close']
        df['body_abs'] = abs(df['body'])
        
        # Upper/Lower shadows
        df['upper_shadow'] = (df['high'] - df[['open', 'close']].max(axis=1)) / df['close']
        df['lower_shadow'] = (df[['open', 'close']].min(axis=1) - df['low']) / df['close']
        
        # === MOVING AVERAGES ===
        df['sma_5'] = df['close'].rolling(5, min_periods=1).mean()
        df['sma_10'] = df['close'].rolling(10, min_periods=1).mean()
        df['sma_20'] = df['close'].rolling(20, min_periods=1).mean()
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        
        # Price vs MAs (normalized)
        df['price_vs_sma5'] = (df['close'] - df['sma_5']) / df['sma_5']
        df['price_vs_sma20'] = (df['close'] - df['sma_20']) / df['sma_20']
        df['sma_cross'] = (df['sma_5'] - df['sma_20']) / df['sma_20']
        
        # === RSI ===
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=1).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi_norm'] = (df['rsi'] - 50) / 50  # Normalizado -1 a 1
        
        # === MACD ===
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        df['macd_norm'] = df['macd'] / df['close']  # Normalizado
        
        # === ATR & VOLATILITY ===
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(14, min_periods=1).mean()
        df['atr_norm'] = df['atr'] / df['close']
        
        # Volatility
        df['volatility'] = df['returns'].rolling(20, min_periods=1).std()
        
        # === BOLLINGER BANDS ===
        df['bb_mid'] = df['close'].rolling(20, min_periods=1).mean()
        df['bb_std'] = df['close'].rolling(20, min_periods=1).std()
        df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        
        # === MOMENTUM ===
        df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
        df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        df['momentum_20'] = df['close'] / df['close'].shift(20) - 1
        
        # === VOLUME (se disponível) ===
        vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
        if vol_col in df.columns and df[vol_col].sum() > 0:
            df['volume_ma'] = df[vol_col].rolling(20, min_periods=1).mean()
            df['volume_ratio'] = df[vol_col] / (df['volume_ma'] + 1e-10)
        else:
            df['volume_ratio'] = 1.0
        
        # === TREND ===
        df['trend_5'] = np.where(df['close'] > df['close'].shift(5), 1, -1)
        df['trend_10'] = np.where(df['close'] > df['close'].shift(10), 1, -1)
        df['higher_high'] = np.where(df['high'] > df['high'].shift(1), 1, 0)
        df['lower_low'] = np.where(df['low'] < df['low'].shift(1), 1, 0)
        
        # Define feature names - EXPANDIDO
        self.feature_names = [
            # Price action
            'returns', 'returns_2', 'returns_5', 'log_returns',
            'hl_range', 'body', 'upper_shadow', 'lower_shadow',
            # MAs
            'price_vs_sma5', 'price_vs_sma20', 'sma_cross',
            # RSI
            'rsi_norm',
            # MACD
            'macd_norm', 'macd_hist',
            # Volatility
            'atr_norm', 'volatility', 'bb_position', 'bb_width',
            # Momentum
            'momentum_5', 'momentum_10', 'momentum_20',
            # Volume
            'volume_ratio',
            # Trend
            'trend_5', 'trend_10', 'higher_high', 'lower_low'
        ]
        
        return df
    
    def _generate_labels(self, df: pd.DataFrame, lookahead: int = 12) -> pd.DataFrame:
        """Gera labels baseado em resultado futuro."""
        # Label = 1 se preço subiu mais que 0.05% em N bars (12 bars = 1 hora em M5)
        future_return = df['close'].shift(-lookahead) / df['close'] - 1
        df['label'] = (future_return > 0.0005).astype(float)  # 0.05% = 5 pips
        
        return df
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model_type: str = 'lstm',
        seq_length: int = 60,
        epochs: int = 100,
        batch_size: int = 256,
        learning_rate: float = 0.001
    ) -> Tuple[nn.Module, Dict]:
        """Treina modelo."""
        print(f"\n🚀 Treinando modelo {model_type.upper()}...")
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False  # Não embaralha para séries temporais
        )
        
        print(f"   Treino: {len(X_train):,} | Teste: {len(X_test):,}")
        
        # Datasets
        train_dataset = TradingDataset(X_train, y_train, seq_length)
        test_dataset = TradingDataset(X_test, y_test, seq_length)
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
        
        # Modelo
        input_size = X.shape[1]
        
        if model_type == 'lstm':
            model = LSTMModel(input_size=input_size, hidden_size=128, num_layers=2)
        elif model_type == 'transformer':
            model = TransformerModel(input_size=input_size, d_model=128, nhead=8, num_layers=4)
        else:
            raise ValueError(f"Modelo desconhecido: {model_type}")
        
        model = model.to(device)
        
        # BCE Loss simples com pos_weight moderado
        pos_weight = torch.tensor([2.0]).to(device)
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
        
        # Treino com early stopping
        best_f1 = 0
        best_val_loss = float('inf')
        best_model_state = None
        history = {'train_loss': [], 'val_loss': [], 'val_f1': []}
        patience_counter = 0
        patience = 15  # Reduzido para treinar mais rápido
        
        # Threshold para classificação
        threshold = 0.5
        
        for epoch in range(epochs):
            # Train
            model.train()
            train_loss = 0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(device)
                y_batch = y_batch.to(device)
                
                optimizer.zero_grad()
                outputs = model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                
                optimizer.step()
                train_loss += loss.item()
            
            train_loss /= len(train_loader)
            
            # Validation
            model.eval()
            val_loss = 0
            all_preds = []
            all_labels = []
            
            with torch.no_grad():
                for X_batch, y_batch in test_loader:
                    X_batch = X_batch.to(device)
                    y_batch = y_batch.to(device)
                    
                    outputs = model(X_batch)
                    loss = criterion(outputs, y_batch)
                    val_loss += loss.item()
                    
                    # Aplica sigmoid para obter probabilidades
                    probs = torch.sigmoid(outputs)
                    preds = (probs > threshold).float()
                    all_preds.extend(preds.cpu().numpy())
                    all_labels.extend(y_batch.cpu().numpy())
            
            val_loss /= len(test_loader)
            
            # Métricas
            f1 = f1_score(all_labels, all_preds, zero_division=0)
            
            history['train_loss'].append(train_loss)
            history['val_loss'].append(val_loss)
            history['val_f1'].append(f1)
            
            # Scheduler step após calcular val_loss
            scheduler.step(val_loss)
            
            # Early stopping baseado em F1 (não val_loss)
            if f1 > best_f1:
                best_f1 = f1
                best_val_loss = val_loss
                best_model_state = {k: v.clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
            
            if (epoch + 1) % 10 == 0:
                print(f"   Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f} | "
                      f"Val Loss: {val_loss:.4f} | F1: {f1:.3f}")
            
            # Early stopping
            if patience_counter >= patience:
                print(f"   ⏹️  Early stopping na época {epoch+1} (sem melhora por {patience} épocas)")
                break
        
        # Carrega melhor modelo
        if best_model_state is not None:
            model.load_state_dict(best_model_state)
        
        # Métricas finais
        model.eval()
        all_preds = []
        all_probs = []
        all_labels = []
        
        with torch.no_grad():
            for X_batch, y_batch in test_loader:
                X_batch = X_batch.to(device)
                outputs = model(X_batch)
                probs = torch.sigmoid(outputs)
                
                all_probs.extend(probs.cpu().numpy())
                all_preds.extend((probs > threshold).float().cpu().numpy())
                all_labels.extend(y_batch.numpy())
        
        metrics = {
            'accuracy': accuracy_score(all_labels, all_preds),
            'precision': precision_score(all_labels, all_preds, zero_division=0),
            'recall': recall_score(all_labels, all_preds, zero_division=0),
            'f1': f1_score(all_labels, all_preds, zero_division=0),
            'best_f1': best_f1,
            'threshold': threshold
        }
        
        print(f"\n📊 Métricas finais (threshold={threshold}):")
        print(f"   Accuracy:  {metrics['accuracy']:.1%}")
        print(f"   Precision: {metrics['precision']:.1%}")
        print(f"   Recall:    {metrics['recall']:.1%}")
        print(f"   F1 Score:  {metrics['f1']:.1%}")
        
        return model, metrics, history
    
    def save_model(self, model: nn.Module, symbol: str, model_type: str, metrics: Dict):
        """Salva modelo treinado."""
        model_path = self.output_dir / f"{symbol.lower()}_{model_type}.pt"
        
        # Salva modelo PyTorch
        torch.save({
            'model_state_dict': model.state_dict(),
            'model_type': model_type,
            'feature_names': self.feature_names,
            'scaler_mean': self.scaler.mean_,
            'scaler_scale': self.scaler.scale_,
            'metrics': metrics,
            'trained_at': datetime.now().isoformat()
        }, model_path)
        
        print(f"\n💾 Modelo salvo: {model_path}")
        
        return model_path


def main():
    parser = argparse.ArgumentParser(description='Treina modelo deep learning')
    parser.add_argument('--data-dir', default='historical_data', help='Pasta com dados')
    parser.add_argument('--output-dir', default='gpu_training/models', help='Pasta de saída')
    parser.add_argument('--model', default='lstm', choices=['lstm', 'transformer'], help='Tipo de modelo')
    parser.add_argument('--symbols', nargs='+', default=None, help='Símbolos')
    parser.add_argument('--epochs', type=int, default=100, help='Épocas de treino')
    parser.add_argument('--seq-length', type=int, default=20, help='Tamanho da sequência')
    parser.add_argument('--batch-size', type=int, default=512, help='Batch size')
    args = parser.parse_args()
    
    # Símbolos padrão
    if args.symbols:
        symbols = args.symbols
    else:
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    
    trainer = DeepTrainer(data_dir, output_dir)
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"📊 Treinando modelo para {symbol}...")
        print(f"{'='*60}")
        
        # Carrega dados
        X, y = trainer.load_and_prepare_data(symbol)
        if X is None:
            continue
        
        # Treina
        model, metrics, history = trainer.train(
            X, y,
            model_type=args.model,
            seq_length=args.seq_length,
            epochs=args.epochs,
            batch_size=args.batch_size
        )
        
        # Salva
        trainer.save_model(model, symbol, args.model, metrics)
    
    print(f"\n{'='*60}")
    print(f"✅ Treinamento concluído!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
