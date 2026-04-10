"""
🧠 Deep ML Filter - Carrega e usa modelos LSTM treinados na GPU
"""
import os
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from .logger import setup_logger

logger = setup_logger("DeepMLFilter")

# Tenta importar PyTorch (opcional)
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
    
    class LSTMModel(nn.Module):
        """LSTM para trading - deve corresponder à arquitetura de treino."""
        
        def __init__(self, input_size: int, hidden_size: int = 128, num_layers: int = 2, dropout: float = 0.3):
            super().__init__()
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
            self.fc = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 1)
            )
        
        def forward(self, x):
            lstm_out, _ = self.lstm(x)
            return self.fc(lstm_out[:, -1, :]).squeeze()

except ImportError:
    TORCH_AVAILABLE = False
    LSTMModel = None
    logger.warning("⚠️ PyTorch não instalado - modelos deep learning desabilitados")


class DeepMLFilter:
    """
    Gerencia modelos Deep Learning LSTM para múltiplos ativos.
    Usa features expandidas e sequências temporais.
    """
    
    def __init__(self, models_dir: str = "gpu_training_models_production", min_confidence: float = 0.50, seq_length: int = 20):
        self.models_dir = models_dir
        self.min_confidence = min_confidence
        self.seq_length = seq_length
        self.models = {}  # {symbol: model_data}
        self.price_history = {}  # {symbol: DataFrame} - histórico para sequências
        self._stats = {"predictions": 0, "approved": 0, "rejected": 0, "by_symbol": {}}
        
        if TORCH_AVAILABLE:
            self._load_all_models()
        else:
            logger.warning("🧠 Deep ML Filter desabilitado (PyTorch não disponível)")
    
    def _load_all_models(self):
        """Carrega todos os modelos deep learning."""
        if not os.path.exists(self.models_dir):
            logger.warning(f"⚠️ Pasta de modelos não encontrada: {self.models_dir}")
            return
        
        for filename in os.listdir(self.models_dir):
            if filename.endswith("_lstm_deep.pkl"):
                symbol = filename.replace("_lstm_deep.pkl", "").upper()
                filepath = os.path.join(self.models_dir, filename)
                
                try:
                    with open(filepath, 'rb') as f:
                        data = pickle.load(f)
                    
                    # Recria modelo PyTorch
                    input_size = len(data['feature_names'])
                    model = LSTMModel(input_size=input_size)
                    model.load_state_dict(data['model_state_dict'])
                    model.eval()
                    
                    self.models[symbol] = {
                        'model': model,
                        'feature_names': data['feature_names'],
                        'scaler_mean': data['scaler_mean'],
                        'scaler_scale': data['scaler_scale'],
                        'threshold': data.get('threshold', self.min_confidence),
                        'metrics': data.get('metrics', {})
                    }
                    
                    self._stats["by_symbol"][symbol] = {"predictions": 0, "approved": 0, "rejected": 0}
                    self.price_history[symbol] = pd.DataFrame()
                    
                    metrics = data.get('metrics', {})
                    f1 = metrics.get('f1', 0)
                    logger.info(f"🧠 Modelo LSTM carregado: {symbol} (F1: {f1:.1%})")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao carregar {filename}: {e}")
        
        logger.info(f"🧠 {len(self.models)} modelos Deep Learning carregados")
    
    def is_ready(self, symbol: str = None, min_f1: float = 0.0) -> bool:
        """Verifica se há modelo disponível e com F1 mínimo."""
        if not TORCH_AVAILABLE:
            return False
        if symbol:
            symbol = symbol.upper()
            if symbol not in self.models:
                return False
            # Verifica F1 mínimo
            if min_f1 > 0:
                metrics = self.models[symbol].get('metrics', {})
                f1 = metrics.get('f1', 0)
                if f1 < min_f1:
                    return False
            return True
        return len(self.models) > 0
    
    def update_price_history(self, symbol: str, candle: Dict):
        """Atualiza histórico de preços para o símbolo."""
        symbol = symbol.upper()
        if symbol not in self.price_history:
            self.price_history[symbol] = pd.DataFrame()
        
        new_row = pd.DataFrame([{
            'time': candle.get('time'),
            'open': candle.get('open'),
            'high': candle.get('high'),
            'low': candle.get('low'),
            'close': candle.get('close'),
            'tick_volume': candle.get('tick_volume', candle.get('volume', 0))
        }])
        
        self.price_history[symbol] = pd.concat([self.price_history[symbol], new_row], ignore_index=True)
        
        # Mantém apenas últimas N candles
        max_history = self.seq_length + 50
        if len(self.price_history[symbol]) > max_history:
            self.price_history[symbol] = self.price_history[symbol].tail(max_history).reset_index(drop=True)

    def _calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula features técnicas - MESMAS do treino."""
        # === PRICE ACTION ===
        df['returns'] = df['close'].pct_change().fillna(0)
        df['returns_2'] = df['close'].pct_change(2).fillna(0)
        df['returns_5'] = df['close'].pct_change(5).fillna(0)
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1)).fillna(0)
        
        df['hl_range'] = (df['high'] - df['low']) / df['close']
        df['body'] = (df['close'] - df['open']) / df['close']
        df['upper_shadow'] = (df['high'] - df[['open', 'close']].max(axis=1)) / df['close']
        df['lower_shadow'] = (df[['open', 'close']].min(axis=1) - df['low']) / df['close']
        
        # === MOVING AVERAGES ===
        df['sma_5'] = df['close'].rolling(5, min_periods=1).mean()
        df['sma_20'] = df['close'].rolling(20, min_periods=1).mean()
        df['price_vs_sma5'] = (df['close'] - df['sma_5']) / df['sma_5']
        df['price_vs_sma20'] = (df['close'] - df['sma_20']) / df['sma_20']
        df['sma_cross'] = (df['sma_5'] - df['sma_20']) / df['sma_20']
        
        # === RSI ===
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=1).mean()
        rs = gain / (loss + 1e-10)
        df['rsi_norm'] = ((100 - (100 / (1 + rs))) - 50) / 50
        
        # === MACD ===
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        df['macd_norm'] = df['macd'] / df['close']
        
        # === ATR & VOLATILITY ===
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(14, min_periods=1).mean()
        df['atr_norm'] = df['atr'] / df['close']
        df['volatility'] = df['returns'].rolling(20, min_periods=1).std().fillna(0)
        
        # === BOLLINGER BANDS ===
        df['bb_mid'] = df['close'].rolling(20, min_periods=1).mean()
        df['bb_std'] = df['close'].rolling(20, min_periods=1).std().fillna(0)
        df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        
        # === MOMENTUM ===
        df['momentum_5'] = (df['close'] / df['close'].shift(5) - 1).fillna(0)
        df['momentum_10'] = (df['close'] / df['close'].shift(10) - 1).fillna(0)
        df['momentum_20'] = (df['close'] / df['close'].shift(20) - 1).fillna(0)
        
        # === VOLUME ===
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
        
        return df
    
    def predict(self, symbol: str, candles: List[Dict] = None) -> Tuple[float, bool, str]:
        """
        Prediz probabilidade de sucesso usando modelo LSTM.
        
        Args:
            symbol: Símbolo do ativo
            candles: Lista de candles recentes (opcional, usa histórico interno)
            
        Returns:
            (probabilidade, aprovado, motivo)
        """
        if not TORCH_AVAILABLE:
            return 0.5, True, "PyTorch não disponível"
        
        symbol = symbol.upper()
        self._stats["predictions"] += 1
        
        if symbol not in self._stats["by_symbol"]:
            self._stats["by_symbol"][symbol] = {"predictions": 0, "approved": 0, "rejected": 0}
        self._stats["by_symbol"][symbol]["predictions"] += 1
        
        model_data = self.models.get(symbol)
        if not model_data:
            return 0.5, True, f"Sem modelo LSTM para {symbol}"
        
        # Usa candles fornecidos ou histórico interno
        if candles:
            df = pd.DataFrame(candles)
        else:
            df = self.price_history.get(symbol, pd.DataFrame())
        
        if len(df) < self.seq_length:
            return 0.5, True, f"Histórico insuficiente ({len(df)}/{self.seq_length})"
        
        try:
            # Calcula features
            df = self._calculate_features(df)
            
            # Extrai features na ordem correta
            feature_names = model_data['feature_names']
            features = df[feature_names].tail(self.seq_length).values
            
            # Normaliza
            scaler_mean = model_data['scaler_mean']
            scaler_scale = model_data['scaler_scale']
            features_norm = (features - scaler_mean) / (scaler_scale + 1e-10)
            
            # Converte para tensor
            x = torch.tensor(features_norm, dtype=torch.float32).unsqueeze(0)
            
            # Predição
            model = model_data['model']
            with torch.no_grad():
                logits = model(x)
                prob = torch.sigmoid(logits).item()
            
            threshold = model_data['threshold']
            approved = prob >= threshold
            
            if approved:
                self._stats["approved"] += 1
                self._stats["by_symbol"][symbol]["approved"] += 1
                reason = f"LSTM {symbol}: {prob:.1%} >= {threshold:.0%} ✅"
            else:
                self._stats["rejected"] += 1
                self._stats["by_symbol"][symbol]["rejected"] += 1
                reason = f"LSTM {symbol}: {prob:.1%} < {threshold:.0%} ❌"
            
            return prob, approved, reason
            
        except Exception as e:
            logger.warning(f"Erro na predição LSTM para {symbol}: {e}")
            return 0.5, True, f"Erro LSTM: {e}"
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de uso."""
        total = self._stats["predictions"]
        return {
            **self._stats,
            "approval_rate": self._stats["approved"] / total if total > 0 else 0,
            "rejection_rate": self._stats["rejected"] / total if total > 0 else 0
        }
    
    def print_status(self):
        """Imprime status dos modelos."""
        print("\n" + "="*50)
        print("🧠 STATUS DOS MODELOS DEEP LEARNING")
        print("="*50)
        
        if not TORCH_AVAILABLE:
            print("  ⚠️ PyTorch não instalado")
            return
        
        for symbol, data in self.models.items():
            metrics = data.get('metrics', {})
            threshold = data.get('threshold', 0.5)
            f1 = metrics.get('f1', 0)
            precision = metrics.get('precision', 0)
            recall = metrics.get('recall', 0)
            
            print(f"  {symbol}: F1 {f1:.1%} | Prec {precision:.1%} | Rec {recall:.1%} | Thr {threshold:.0%}")
        
        print("="*50 + "\n")
