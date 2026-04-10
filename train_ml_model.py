"""
🤖 Script de Treino do Modelo ML para Trading Bot
Roda OFFLINE uma vez para gerar o modelo.

Uso: python train_ml_model.py [--symbol BTCUSD-T] [--months 3]

Tempo estimado: 30-60 segundos
RAM: ~200MB durante treino, ~10MB após
"""
import os
import sys
import pickle
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# Adiciona path do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("🤖 TREINAMENTO DO MODELO ML - Trading Bot PRO")
print("=" * 60)

# Verifica dependências
try:
    from lightgbm import LGBMClassifier
    print("✅ LightGBM instalado")
except ImportError:
    print("❌ LightGBM não encontrado. Instalando...")
    os.system("pip install lightgbm")
    from lightgbm import LGBMClassifier

try:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    print("✅ Scikit-learn instalado")
except ImportError:
    print("❌ Scikit-learn não encontrado. Instalando...")
    os.system("pip install scikit-learn")
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

print()


class MLTrainer:
    """Treina modelo LightGBM com dados históricos."""
    
    def __init__(self, symbol: str = "BTCUSD-T", timeframe: str = "M5"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.data_dir = os.path.join(os.path.dirname(__file__), "historical_data")
        self.models_dir = os.path.join(os.path.dirname(__file__), "models")
        
        # Cria pasta de modelos
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
        
        # Features que vamos usar
        self.feature_names = [
            'sma_crossover', 'price_vs_sma21', 'rsi', 'rsi_zone',
            'macd_signal', 'macd_histogram', 'adx', 'adx_direction',
            'atr_percentile', 'market_structure', 'bos_type',
            'bos_pullback_valid', 'in_order_block', 'volume_above_avg'
        ]
        
        # Parâmetros da estratégia
        self.sma_fast = 9
        self.sma_slow = 21
        self.rsi_period = 14
        self.atr_period = 14
        self.adx_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
        # Parâmetros de simulação - OTIMIZADOS para melhor win rate
        self.atr_mult_sl = 1.5       # SL mais apertado (era 2.5)
        self.atr_mult_tp = 2.5       # TP mais realista (era 5.0)
        self.lookahead_bars = 25     # Menos tempo de espera (era 50)
    
    def load_historical_data(self) -> pd.DataFrame:
        """Carrega dados históricos dos CSVs."""
        symbol_dir = os.path.join(self.data_dir, self.symbol.replace("-", "_"))
        
        if not os.path.exists(symbol_dir):
            # Tenta sem o _T
            symbol_dir = os.path.join(self.data_dir, self.symbol.replace("-T", "_T"))
        
        if not os.path.exists(symbol_dir):
            print(f"❌ Pasta não encontrada: {symbol_dir}")
            return pd.DataFrame()
        
        dfs = []
        for fn in sorted(os.listdir(symbol_dir)):
            if fn.startswith(f"{self.timeframe}_") and fn.endswith(".csv"):
                fp = os.path.join(symbol_dir, fn)
                try:
                    df = pd.read_csv(fp)
                    df['time'] = pd.to_datetime(df['time'])
                    dfs.append(df)
                    print(f"   📂 {fn}: {len(df):,} candles")
                except Exception as e:
                    print(f"   ⚠️ Erro em {fn}: {e}")
        
        if not dfs:
            print("❌ Nenhum arquivo CSV encontrado!")
            return pd.DataFrame()
        
        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=['time'])
        combined = combined.sort_values('time').reset_index(drop=True)
        
        print(f"\n📊 Total: {len(combined):,} candles")
        print(f"📅 Período: {combined['time'].min()} até {combined['time'].max()}")
        
        return combined
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula todos os indicadores técnicos."""
        print("\n🔧 Calculando indicadores...")
        
        # SMAs
        df['sma_fast'] = df['close'].rolling(self.sma_fast).mean()
        df['sma_slow'] = df['close'].rolling(self.sma_slow).mean()
        df['sma_crossover'] = np.where(df['sma_fast'] > df['sma_slow'], 1, 
                                       np.where(df['sma_fast'] < df['sma_slow'], -1, 0))
        df['price_vs_sma21'] = np.where(df['close'] > df['sma_slow'], 1, -1)
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi_zone'] = np.where(df['rsi'] < 30, 1, np.where(df['rsi'] > 70, -1, 0))
        
        # MACD
        ema_fast = df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        df['macd_line'] = ema_fast - ema_slow
        df['macd_signal_line'] = df['macd_line'].ewm(span=self.macd_signal, adjust=False).mean()
        df['macd_histogram'] = df['macd_line'] - df['macd_signal_line']
        df['macd_signal'] = np.where(df['macd_line'] > df['macd_signal_line'], 1, -1)
        
        # ATR
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(self.atr_period).mean()
        
        # ATR Percentile
        df['atr_percentile'] = df['atr'].rolling(100).apply(
            lambda x: (x < x.iloc[-1]).sum() / len(x) * 100 if len(x) > 0 else 50
        )
        
        # ADX
        df = self._calculate_adx(df)
        
        # Volume
        vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
        if vol_col in df.columns:
            df['volume_sma'] = df[vol_col].rolling(20).mean()
            df['volume_above_avg'] = np.where(df[vol_col] > df['volume_sma'], 1, 0)
        else:
            df['volume_above_avg'] = 0
        
        # Market Structure (simplificado)
        df['market_structure'] = self._calculate_market_structure(df)
        
        # BOS (simplificado)
        df['bos_type'], df['bos_pullback_valid'] = self._calculate_bos(df)
        
        # Order Blocks (simplificado)
        df['in_order_block'] = self._calculate_order_blocks(df)
        
        print("✅ Indicadores calculados!")
        return df
    
    def _calculate_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula ADX e DI+/DI-."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)
        
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        atr = tr.ewm(alpha=1/self.adx_period, adjust=False).mean()
        smooth_plus = pd.Series(plus_dm).ewm(alpha=1/self.adx_period, adjust=False).mean()
        smooth_minus = pd.Series(minus_dm).ewm(alpha=1/self.adx_period, adjust=False).mean()
        
        plus_di = 100 * smooth_plus / atr.replace(0, np.nan)
        minus_di = 100 * smooth_minus / atr.replace(0, np.nan)
        
        di_sum = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / di_sum.replace(0, np.nan)
        
        df['adx'] = dx.ewm(alpha=1/self.adx_period, adjust=False).mean()
        df['adx_direction'] = np.where(plus_di > minus_di, 1, -1)
        
        return df
    
    def _calculate_market_structure(self, df: pd.DataFrame) -> pd.Series:
        """Calcula estrutura de mercado simplificada - OTIMIZADO."""
        lookback = 20
        structure = np.zeros(len(df))
        
        highs = df['high'].values
        lows = df['low'].values
        
        for i in range(lookback, len(df)):
            window_highs = highs[i-lookback:i]
            window_lows = lows[i-lookback:i]
            
            # Conta higher highs/lows vs lower highs/lows
            hh = sum(1 for j in range(1, len(window_highs)) if window_highs[j] > window_highs[j-1])
            hl = sum(1 for j in range(1, len(window_lows)) if window_lows[j] > window_lows[j-1])
            
            if hh > lookback * 0.6 and hl > lookback * 0.6:
                structure[i] = 1  # BULLISH
            elif hh < lookback * 0.4 and hl < lookback * 0.4:
                structure[i] = -1  # BEARISH
            # else: 0 = RANGING
        
        return pd.Series(structure, index=df.index)
    
    def _calculate_bos(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calcula BOS simplificado - OTIMIZADO."""
        lookback = 10
        bos_type = np.zeros(len(df))
        bos_pullback = np.zeros(len(df))
        
        close_values = df['close'].values
        high_values = df['high'].values
        low_values = df['low'].values
        
        for i in range(lookback * 2, len(df)):
            window_start = i - lookback * 2
            window_end = i
            
            current_close = close_values[i]
            
            # Swing high/low recentes
            swing_high = np.max(high_values[window_start:window_end])
            swing_low = np.min(low_values[window_start:window_end])
            
            # BOS Bullish: fechou acima do swing high
            if current_close > swing_high:
                bos_type[i] = 1
                # Verifica pullback
                recent_start = max(0, i-5)
                retracement = (swing_high - np.min(low_values[recent_start:i])) / (swing_high - swing_low + 0.0001)
                bos_pullback[i] = 1 if 0.3 <= retracement <= 0.7 else 0
            # BOS Bearish: fechou abaixo do swing low
            elif current_close < swing_low:
                bos_type[i] = -1
                recent_start = max(0, i-5)
                retracement = (np.max(high_values[recent_start:i]) - swing_low) / (swing_high - swing_low + 0.0001)
                bos_pullback[i] = 1 if 0.3 <= retracement <= 0.7 else 0
        
        return pd.Series(bos_type, index=df.index), pd.Series(bos_pullback, index=df.index)
    
    def _calculate_order_blocks(self, df: pd.DataFrame) -> pd.Series:
        """Detecta se preço está em Order Block - OTIMIZADO."""
        lookback = 30
        in_ob = np.zeros(len(df))
        
        # Pré-calcula ATR se não existir
        if 'atr' not in df.columns:
            return pd.Series(in_ob, index=df.index)
        
        atr_values = df['atr'].values
        close_values = df['close'].values
        open_values = df['open'].values
        high_values = df['high'].values
        low_values = df['low'].values
        
        for i in range(lookback + 5, len(df)):
            current_price = close_values[i]
            atr = atr_values[i]
            
            if atr == 0 or np.isnan(atr):
                continue
            
            # Procura OBs nos últimos N candles (simplificado)
            found_ob = 0
            for j in range(max(0, i-lookback), i-5):
                candle_close = close_values[j]
                candle_open = open_values[j]
                candle_high = high_values[j]
                candle_low = low_values[j]
                
                is_bearish = candle_close < candle_open
                is_bullish = candle_close > candle_open
                
                # Verifica impulso após o candle
                future_end = min(j + 6, i)
                future_high = np.max(high_values[j+1:future_end])
                future_low = np.min(low_values[j+1:future_end])
                
                # Bullish OB
                if is_bearish and (future_high - candle_high) > atr * 1.5:
                    if candle_low <= current_price <= candle_high:
                        found_ob = 1
                        break
                
                # Bearish OB
                if is_bullish and (candle_low - future_low) > atr * 1.5:
                    if candle_low <= current_price <= candle_high:
                        found_ob = 1
                        break
            
            in_ob[i] = found_ob
        
        return pd.Series(in_ob, index=df.index)
    
    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera labels (target) baseado no resultado do trade simulado.
        OTIMIZADO: Inclui trailing stop simulado para melhor win rate.
        
        Label = 1 se trade seria lucrativo, 0 se não.
        """
        print("\n🎯 Gerando labels (simulando trades com trailing stop)...")
        
        labels = []
        close_values = df['close'].values
        high_values = df['high'].values
        low_values = df['low'].values
        atr_values = df['atr'].values if 'atr' in df.columns else None
        sma_cross = df['sma_crossover'].values
        rsi_values = df['rsi'].values
        
        for i in range(len(df)):
            if i < 50 or i >= len(df) - self.lookahead_bars:
                labels.append(np.nan)
                continue
            
            if atr_values is None:
                labels.append(np.nan)
                continue
                
            atr = atr_values[i]
            if np.isnan(atr) or atr == 0:
                labels.append(np.nan)
                continue
            
            entry_price = close_values[i]
            cross = sma_cross[i]
            rsi = rsi_values[i]
            
            # Sinal de compra
            if cross == 1 and rsi < 70:
                sl = entry_price - atr * self.atr_mult_sl
                tp = entry_price + atr * self.atr_mult_tp
                trailing_sl = sl  # Trailing stop começa no SL
                
                result = None
                for j in range(i+1, min(i+self.lookahead_bars, len(df))):
                    current_high = high_values[j]
                    current_low = low_values[j]
                    current_close = close_values[j]
                    
                    # Verifica SL primeiro
                    if current_low <= trailing_sl:
                        # Verifica se fechou no lucro mesmo com SL
                        if trailing_sl > entry_price:
                            result = 1  # Trailing stop no lucro!
                        else:
                            result = 0  # Stop loss
                        break
                    
                    # Verifica TP
                    if current_high >= tp:
                        result = 1  # Take profit
                        break
                    
                    # Atualiza trailing stop (move para cima se preço subiu)
                    new_trailing = current_close - atr * 1.0  # Trailing de 1x ATR
                    if new_trailing > trailing_sl:
                        trailing_sl = new_trailing
                
                if result is None:
                    # Não atingiu nem SL nem TP - verifica resultado final
                    final_price = close_values[min(i+self.lookahead_bars-1, len(df)-1)]
                    result = 1 if final_price > entry_price else 0
                
                labels.append(result)
            
            # Sinal de venda
            elif cross == -1 and rsi > 30:
                sl = entry_price + atr * self.atr_mult_sl
                tp = entry_price - atr * self.atr_mult_tp
                trailing_sl = sl
                
                result = None
                for j in range(i+1, min(i+self.lookahead_bars, len(df))):
                    current_high = high_values[j]
                    current_low = low_values[j]
                    current_close = close_values[j]
                    
                    # Verifica SL primeiro
                    if current_high >= trailing_sl:
                        if trailing_sl < entry_price:
                            result = 1  # Trailing stop no lucro!
                        else:
                            result = 0
                        break
                    
                    # Verifica TP
                    if current_low <= tp:
                        result = 1
                        break
                    
                    # Atualiza trailing stop (move para baixo se preço caiu)
                    new_trailing = current_close + atr * 1.0
                    if new_trailing < trailing_sl:
                        trailing_sl = new_trailing
                
                if result is None:
                    final_price = close_values[min(i+self.lookahead_bars-1, len(df)-1)]
                    result = 1 if final_price < entry_price else 0
                
                labels.append(result)
            
            else:
                labels.append(np.nan)  # Sem sinal
        
        df['label'] = labels
        
        valid_labels = df['label'].dropna()
        wins = (valid_labels == 1).sum()
        losses = (valid_labels == 0).sum()
        total = len(valid_labels)
        
        print(f"✅ Labels gerados: {total:,} amostras")
        print(f"   🟢 Wins: {wins:,} ({wins/total*100:.1f}%)")
        print(f"   🔴 Losses: {losses:,} ({losses/total*100:.1f}%)")
        
        return df
    
    def prepare_dataset(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepara X e y para treino."""
        # Remove linhas sem label
        df_clean = df.dropna(subset=['label'] + self.feature_names)
        
        X = df_clean[self.feature_names].values
        y = df_clean['label'].values
        
        print(f"\n📦 Dataset preparado: {len(X):,} amostras x {len(self.feature_names)} features")
        
        return X, y
    
    def train_model(self, X: np.ndarray, y: np.ndarray) -> Tuple[object, Dict]:
        """Treina modelo LightGBM."""
        print("\n🚀 Treinando modelo LightGBM...")
        
        # Split treino/teste
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        print(f"   Treino: {len(X_train):,} | Teste: {len(X_test):,}")
        
        # Modelo otimizado para ser leve e rápido
        model = LGBMClassifier(
            n_estimators=200,       # Número de árvores
            learning_rate=0.05,     # Taxa de aprendizado
            max_depth=6,            # Profundidade máxima
            num_leaves=31,          # Folhas por árvore
            min_child_samples=20,   # Mínimo de amostras por folha
            subsample=0.8,          # Amostragem de dados
            colsample_bytree=0.8,   # Amostragem de features
            reg_alpha=0.1,          # Regularização L1
            reg_lambda=0.1,         # Regularização L2
            random_state=42,
            verbose=-1,             # Silencioso
            n_jobs=-1               # Usa todos os cores
        )
        
        # Treina
        model.fit(X_train, y_train)
        
        # Avalia
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'f1': f1_score(y_test, y_pred)
        }
        
        print(f"\n📊 Métricas no conjunto de teste:")
        print(f"   Accuracy:  {metrics['accuracy']:.1%}")
        print(f"   Precision: {metrics['precision']:.1%}")
        print(f"   Recall:    {metrics['recall']:.1%}")
        print(f"   F1 Score:  {metrics['f1']:.1%}")
        
        # Feature importance
        print(f"\n🔍 Importância das Features:")
        importance = dict(zip(self.feature_names, model.feature_importances_))
        for name, imp in sorted(importance.items(), key=lambda x: -x[1])[:5]:
            print(f"   {name}: {imp:.3f}")
        
        # Encontra threshold ótimo
        best_threshold = self._find_optimal_threshold(y_test, y_proba)
        metrics['threshold'] = best_threshold
        
        return model, metrics
    
    def _find_optimal_threshold(self, y_true: np.ndarray, y_proba: np.ndarray) -> float:
        """Encontra threshold que maximiza F1."""
        best_f1 = 0
        best_threshold = 0.5
        
        for threshold in np.arange(0.4, 0.8, 0.05):
            y_pred = (y_proba >= threshold).astype(int)
            f1 = f1_score(y_true, y_pred)
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
        
        print(f"\n🎯 Threshold ótimo: {best_threshold:.0%} (F1: {best_f1:.1%})")
        return best_threshold
    
    def save_model(self, model: object, metrics: Dict) -> str:
        """Salva modelo treinado."""
        symbol_clean = self.symbol.replace("-", "_").lower()
        model_path = os.path.join(self.models_dir, f"{symbol_clean}_lgbm.pkl")
        
        data = {
            'model': model,
            'feature_names': self.feature_names,
            'threshold': metrics['threshold'],
            'metrics': metrics,
            'trained_at': datetime.now().isoformat(),
            'symbol': self.symbol
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(data, f)
        
        # Tamanho do arquivo
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        
        print(f"\n💾 Modelo salvo: {model_path}")
        print(f"   Tamanho: {size_mb:.2f} MB")
        
        return model_path
    
    def run(self) -> str:
        """Executa pipeline completo de treino."""
        # 1. Carrega dados
        df = self.load_historical_data()
        if df.empty:
            print("❌ Sem dados para treinar!")
            return None
        
        # 2. Calcula indicadores
        df = self.calculate_indicators(df)
        
        # 3. Gera labels
        df = self.generate_labels(df)
        
        # 4. Prepara dataset
        X, y = self.prepare_dataset(df)
        
        if len(X) < 100:
            print("❌ Dados insuficientes para treinar (mínimo 100 amostras)")
            return None
        
        # 5. Treina modelo
        model, metrics = self.train_model(X, y)
        
        # 6. Salva modelo
        model_path = self.save_model(model, metrics)
        
        print("\n" + "=" * 60)
        print("✅ TREINO CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        print(f"\n📁 Modelo salvo em: {model_path}")
        print(f"🎯 Use threshold: {metrics['threshold']:.0%}")
        print(f"\n💡 Para usar no bot, adicione no config:")
        print(f"   USE_ML_FILTER = True")
        print(f"   ML_MODEL_PATH = '{model_path}'")
        print(f"   ML_CONFIDENCE_THRESHOLD = {metrics['threshold']}")
        
        return model_path


def main():
    parser = argparse.ArgumentParser(description='Treina modelo ML para trading')
    parser.add_argument('--symbol', default='BTCUSD-T', help='Símbolo (ex: BTCUSD-T)')
    parser.add_argument('--timeframe', default='M5', help='Timeframe (ex: M5)')
    args = parser.parse_args()
    
    trainer = MLTrainer(symbol=args.symbol, timeframe=args.timeframe)
    trainer.run()


if __name__ == "__main__":
    main()
