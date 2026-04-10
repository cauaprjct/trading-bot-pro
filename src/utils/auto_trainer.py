"""
🤖 Auto Trainer - Treina modelo ML automaticamente na inicialização do bot

Fluxo:
1. Conecta ao MT5
2. Baixa histórico mais recente
3. Treina/retreina modelo se necessário
4. Retorna modelo pronto para uso
"""
import os
import pickle
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple
from .logger import setup_logger

logger = setup_logger("AutoTrainer")


class AutoTrainer:
    """Treina modelo ML automaticamente na inicialização."""
    
    def __init__(self, symbol: str, timeframe: int, data_dir: str = "historical_data",
                 models_dir: str = "models", history_months: int = 6):
        self.symbol = symbol
        self.timeframe = timeframe
        self.data_dir = data_dir
        self.models_dir = models_dir
        self.history_months = history_months
        
        # Cria pastas se não existirem
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(project_dir, data_dir)
        self.models_dir = os.path.join(project_dir, models_dir)
        
        for d in [self.data_dir, self.models_dir]:
            if not os.path.exists(d):
                os.makedirs(d)
        
        # Parâmetros de treino
        self.min_samples = 5000  # Mínimo de amostras para treinar
        self.retrain_days = 7    # Retreina se modelo tem mais de 7 dias
        
        # Features
        self.feature_names = [
            'sma_crossover', 'price_vs_sma21', 'rsi', 'rsi_zone',
            'macd_signal', 'macd_histogram', 'adx', 'adx_direction',
            'atr_percentile', 'market_structure', 'bos_type',
            'bos_pullback_valid', 'in_order_block', 'volume_above_avg'
        ]
        
        # Parâmetros de indicadores
        self.sma_fast = 9
        self.sma_slow = 21
        self.rsi_period = 14
        self.atr_period = 14
        self.adx_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal_period = 9
        
        # Parâmetros de simulação
        self.atr_mult_sl = 2.5
        self.atr_mult_tp = 5.0
        self.lookahead_bars = 50
    
    def get_model_path(self) -> str:
        """Retorna caminho do modelo para o símbolo."""
        symbol_clean = self.symbol.replace("-", "_").lower()
        return os.path.join(self.models_dir, f"{symbol_clean}_lgbm.pkl")
    
    def needs_retrain(self) -> Tuple[bool, str]:
        """Verifica se precisa retreinar o modelo."""
        model_path = self.get_model_path()
        
        if not os.path.exists(model_path):
            return True, "Modelo não existe"
        
        # Verifica idade do modelo
        try:
            with open(model_path, 'rb') as f:
                data = pickle.load(f)
            
            trained_at = data.get('trained_at', '')
            if trained_at:
                trained_date = datetime.fromisoformat(trained_at)
                age_days = (datetime.now() - trained_date).days
                
                if age_days >= self.retrain_days:
                    return True, f"Modelo tem {age_days} dias (máx: {self.retrain_days})"
            
            return False, "Modelo atualizado"
            
        except Exception as e:
            return True, f"Erro ao ler modelo: {e}"
    
    def download_history(self, mt5_adapter) -> bool:
        """Baixa histórico do MT5."""
        import MetaTrader5 as mt5
        
        logger.info(f"📥 Baixando histórico de {self.symbol}...")
        
        symbol_dir = os.path.join(self.data_dir, self.symbol.replace("-", "_"))
        if not os.path.exists(symbol_dir):
            os.makedirs(symbol_dir)
        
        # Mapeia timeframe para nome
        tf_names = {
            mt5.TIMEFRAME_M1: "M1", mt5.TIMEFRAME_M5: "M5",
            mt5.TIMEFRAME_M15: "M15", mt5.TIMEFRAME_M30: "M30",
            mt5.TIMEFRAME_H1: "H1", mt5.TIMEFRAME_H4: "H4",
            mt5.TIMEFRAME_D1: "D1"
        }
        tf_name = tf_names.get(self.timeframe, f"TF{self.timeframe}")
        
        now = datetime.now()
        months_downloaded = 0
        
        for i in range(self.history_months):
            target_date = now - timedelta(days=30 * i)
            year = target_date.year
            month = target_date.month
            year_month = f"{year}-{month:02d}"
            
            file_path = os.path.join(symbol_dir, f"{tf_name}_{year_month}.csv")
            
            # Calcula período do mês
            start = datetime(year, month, 1)
            if month == 12:
                end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end = datetime(year, month + 1, 1) - timedelta(seconds=1)
            
            if end > now:
                end = now
            
            if start > now:
                continue
            
            # Verifica se precisa baixar
            is_current_month = (year == now.year and month == now.month)
            
            if os.path.exists(file_path) and not is_current_month:
                # Arquivo existe e não é mês atual - pula
                months_downloaded += 1
                continue
            
            # Baixa do MT5
            try:
                rates = mt5.copy_rates_range(self.symbol, self.timeframe, start, end)
                
                if rates is None or len(rates) == 0:
                    logger.warning(f"   ⚠️ Sem dados para {year_month}")
                    continue
                
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.to_csv(file_path, index=False)
                
                logger.info(f"   ✅ {year_month}: {len(df):,} candles")
                months_downloaded += 1
                
            except Exception as e:
                logger.warning(f"   ❌ Erro em {year_month}: {e}")
        
        logger.info(f"📊 Histórico: {months_downloaded}/{self.history_months} meses")
        return months_downloaded > 0
    
    def load_data(self) -> pd.DataFrame:
        """Carrega todos os dados históricos."""
        import MetaTrader5 as mt5
        
        symbol_dir = os.path.join(self.data_dir, self.symbol.replace("-", "_"))
        
        if not os.path.exists(symbol_dir):
            return pd.DataFrame()
        
        tf_names = {
            mt5.TIMEFRAME_M1: "M1", mt5.TIMEFRAME_M5: "M5",
            mt5.TIMEFRAME_M15: "M15", mt5.TIMEFRAME_M30: "M30",
            mt5.TIMEFRAME_H1: "H1", mt5.TIMEFRAME_H4: "H4",
            mt5.TIMEFRAME_D1: "D1"
        }
        tf_name = tf_names.get(self.timeframe, f"TF{self.timeframe}")
        
        dfs = []
        for fn in sorted(os.listdir(symbol_dir)):
            if fn.startswith(f"{tf_name}_") and fn.endswith(".csv"):
                try:
                    fp = os.path.join(symbol_dir, fn)
                    df = pd.read_csv(fp)
                    df['time'] = pd.to_datetime(df['time'])
                    dfs.append(df)
                except Exception as e:
                    logger.warning(f"   ⚠️ Erro em {fn}: {e}")
        
        if not dfs:
            return pd.DataFrame()
        
        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=['time'])
        combined = combined.sort_values('time').reset_index(drop=True)
        
        return combined
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores técnicos."""
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
        df['macd_signal_line'] = df['macd_line'].ewm(span=self.macd_signal_period, adjust=False).mean()
        df['macd_histogram'] = df['macd_line'] - df['macd_signal_line']
        df['macd_signal'] = np.where(df['macd_line'] > df['macd_signal_line'], 1, -1)
        
        # ATR
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(self.atr_period).mean()
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
        
        return df
    
    def _calculate_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula ADX."""
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
        """Calcula estrutura de mercado (versão vetorizada)."""
        lookback = 20
        
        # Calcula higher highs e higher lows usando rolling
        high_diff = df['high'].diff()
        low_diff = df['low'].diff()
        
        # Conta quantos são positivos na janela
        hh_count = (high_diff > 0).rolling(lookback).sum()
        hl_count = (low_diff > 0).rolling(lookback).sum()
        
        # Determina estrutura
        structure = np.where(
            (hh_count > lookback * 0.6) & (hl_count > lookback * 0.6), 1,
            np.where(
                (hh_count < lookback * 0.4) & (hl_count < lookback * 0.4), -1, 0
            )
        )
        
        return pd.Series(structure, index=df.index).fillna(0).astype(int)
    
    def _calculate_bos(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calcula BOS (versão vetorizada)."""
        lookback = 20  # lookback * 2 do original
        
        # Swing high/low usando rolling
        swing_high = df['high'].rolling(lookback).max()
        swing_low = df['low'].rolling(lookback).min()
        
        # Recent high/low (últimos 5 candles)
        recent_high = df['high'].rolling(5).max()
        recent_low = df['low'].rolling(5).min()
        
        # Range para cálculo de retracement
        swing_range = swing_high - swing_low + 0.0001
        
        # BOS bullish: close > swing_high anterior
        bos_bullish = df['close'] > swing_high.shift(1)
        
        # BOS bearish: close < swing_low anterior
        bos_bearish = df['close'] < swing_low.shift(1)
        
        # Tipo de BOS
        bos_type = np.where(bos_bullish, 1, np.where(bos_bearish, -1, 0))
        
        # Retracement para pullback
        retracement_bull = (swing_high - recent_low) / swing_range
        retracement_bear = (recent_high - swing_low) / swing_range
        
        # Pullback válido
        pullback_bull = (retracement_bull >= 0.3) & (retracement_bull <= 0.7)
        pullback_bear = (retracement_bear >= 0.3) & (retracement_bear <= 0.7)
        
        bos_pullback = np.where(
            bos_bullish & pullback_bull, 1,
            np.where(bos_bearish & pullback_bear, 1, 0)
        )
        
        return (
            pd.Series(bos_type, index=df.index).fillna(0).astype(int),
            pd.Series(bos_pullback, index=df.index).fillna(0).astype(int)
        )
    
    def _calculate_order_blocks(self, df: pd.DataFrame) -> pd.Series:
        """Detecta Order Blocks (versão simplificada e vetorizada)."""
        # Versão simplificada: detecta candles de impulso recentes
        # que podem ser order blocks
        
        atr = df['atr'] if 'atr' in df.columns else df['close'].rolling(14).std()
        
        # Candle bearish/bullish
        is_bearish = df['close'] < df['open']
        is_bullish = df['close'] > df['open']
        
        # Tamanho do candle
        candle_size = abs(df['close'] - df['open'])
        
        # Impulso: candle grande (> 1.5 ATR)
        is_impulse = candle_size > (atr * 1.5)
        
        # Future move (próximos 5 candles)
        future_high = df['high'].shift(-5).rolling(5).max()
        future_low = df['low'].shift(-5).rolling(5).min()
        
        # Bullish OB: candle bearish seguido de alta forte
        bullish_ob = is_bearish & ((future_high - df['high']) > atr * 1.5)
        
        # Bearish OB: candle bullish seguido de queda forte
        bearish_ob = is_bullish & ((df['low'] - future_low) > atr * 1.5)
        
        # Marca OBs
        ob_high = df['high'].where(bullish_ob | bearish_ob)
        ob_low = df['low'].where(bullish_ob | bearish_ob)
        
        # Propaga OBs por 30 candles
        ob_high_filled = ob_high.ffill(limit=30)
        ob_low_filled = ob_low.ffill(limit=30)
        
        # Verifica se preço está dentro de algum OB
        in_ob = (df['close'] >= ob_low_filled) & (df['close'] <= ob_high_filled)
        
        return in_ob.fillna(False).astype(int)
    
    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gera labels para treino (versão otimizada)."""
        n = len(df)
        labels = np.full(n, np.nan)
        
        # Pré-calcula arrays para acesso rápido
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        atr = df['atr'].values if 'atr' in df.columns else np.zeros(n)
        sma_cross = df['sma_crossover'].values if 'sma_crossover' in df.columns else np.zeros(n)
        rsi = df['rsi'].values if 'rsi' in df.columns else np.full(n, 50)
        
        # Pré-calcula max/min futuros usando rolling reverso
        # Isso é mais eficiente que loops
        future_high_max = np.full(n, np.nan)
        future_low_min = np.full(n, np.nan)
        future_close = np.full(n, np.nan)
        
        # Calcula de trás pra frente
        for i in range(n - self.lookahead_bars - 1, -1, -1):
            end_idx = min(i + self.lookahead_bars, n)
            future_high_max[i] = np.max(high[i+1:end_idx])
            future_low_min[i] = np.min(low[i+1:end_idx])
            future_close[i] = close[min(i + self.lookahead_bars - 1, n - 1)]
        
        # Condições para sinais
        valid_idx = (np.arange(n) >= 50) & (np.arange(n) < n - self.lookahead_bars)
        valid_idx &= ~np.isnan(atr) & (atr > 0)
        
        # Sinais de compra
        buy_signal = valid_idx & (sma_cross == 1) & (rsi < 70)
        buy_sl = close - atr * self.atr_mult_sl
        buy_tp = close + atr * self.atr_mult_tp
        
        # Para compras: win se TP atingido antes de SL
        buy_hit_sl = future_low_min <= buy_sl
        buy_hit_tp = future_high_max >= buy_tp
        
        # Se TP atingido e SL não, ou se preço final > entrada
        buy_win = buy_signal & (
            (buy_hit_tp & ~buy_hit_sl) |  # TP sem SL
            (~buy_hit_tp & ~buy_hit_sl & (future_close > close))  # Nem TP nem SL, mas subiu
        )
        buy_loss = buy_signal & (
            (buy_hit_sl & ~buy_hit_tp) |  # SL sem TP
            (~buy_hit_tp & ~buy_hit_sl & (future_close <= close))  # Nem TP nem SL, mas caiu
        )
        
        # Sinais de venda
        sell_signal = valid_idx & (sma_cross == -1) & (rsi > 30)
        sell_sl = close + atr * self.atr_mult_sl
        sell_tp = close - atr * self.atr_mult_tp
        
        # Para vendas: win se TP atingido antes de SL
        sell_hit_sl = future_high_max >= sell_sl
        sell_hit_tp = future_low_min <= sell_tp
        
        sell_win = sell_signal & (
            (sell_hit_tp & ~sell_hit_sl) |
            (~sell_hit_tp & ~sell_hit_sl & (future_close < close))
        )
        sell_loss = sell_signal & (
            (sell_hit_sl & ~sell_hit_tp) |
            (~sell_hit_tp & ~sell_hit_sl & (future_close >= close))
        )
        
        # Atribui labels
        labels[buy_win | sell_win] = 1
        labels[buy_loss | sell_loss] = 0
        
        df['label'] = labels
        return df
    
    def train_model(self, df: pd.DataFrame) -> Tuple[Optional[object], dict]:
        """Treina modelo LightGBM."""
        from lightgbm import LGBMClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        # Prepara dados
        df_clean = df.dropna(subset=['label'] + self.feature_names)
        
        if len(df_clean) < self.min_samples:
            logger.warning(f"⚠️ Dados insuficientes: {len(df_clean)} < {self.min_samples}")
            return None, {}
        
        X = df_clean[self.feature_names].values
        y = df_clean['label'].values
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Treina
        model = LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=0.1,
            random_state=42,
            verbose=-1,
            n_jobs=-1
        )
        
        model.fit(X_train, y_train)
        
        # Avalia
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'f1': f1_score(y_test, y_pred),
            'samples': len(X),
            'wins': int((y == 1).sum()),
            'losses': int((y == 0).sum())
        }
        
        # Threshold ótimo
        best_f1 = 0
        best_threshold = 0.5
        for threshold in np.arange(0.3, 0.7, 0.05):
            y_pred_t = (y_proba >= threshold).astype(int)
            f1 = f1_score(y_test, y_pred_t)
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
        
        metrics['threshold'] = best_threshold
        
        return model, metrics
    
    def save_model(self, model, metrics: dict) -> str:
        """Salva modelo."""
        model_path = self.get_model_path()
        
        data = {
            'model': model,
            'feature_names': self.feature_names,
            'threshold': metrics.get('threshold', 0.5),
            'metrics': metrics,
            'trained_at': datetime.now().isoformat(),
            'symbol': self.symbol
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(data, f)
        
        return model_path
    
    def run(self, mt5_adapter, force_retrain: bool = False) -> Tuple[bool, str, float]:
        """
        Executa auto-treino completo.
        
        Returns:
            (success, model_path, threshold)
        """
        logger.info("=" * 50)
        logger.info("🤖 AUTO-TRAINER - Inicializando ML")
        logger.info("=" * 50)
        
        # 1. Verifica se precisa retreinar
        needs_train, reason = self.needs_retrain()
        
        if not needs_train and not force_retrain:
            model_path = self.get_model_path()
            try:
                with open(model_path, 'rb') as f:
                    data = pickle.load(f)
                threshold = data.get('threshold', 0.5)
                logger.info(f"✅ Modelo existente OK: {reason}")
                logger.info(f"   Threshold: {threshold:.0%}")
                return True, model_path, threshold
            except:
                needs_train = True
                reason = "Erro ao carregar modelo"
        
        logger.info(f"🔄 Retreino necessário: {reason}")
        
        # 2. Baixa histórico
        logger.info(f"📥 Baixando {self.history_months} meses de histórico...")
        self.download_history(mt5_adapter)
        
        # 3. Carrega dados
        logger.info("📊 Carregando dados...")
        df = self.load_data()
        
        if df.empty:
            logger.error("❌ Sem dados para treinar!")
            return False, "", 0.5
        
        logger.info(f"   {len(df):,} candles carregados")
        
        # 4. Calcula indicadores
        logger.info("🔧 Calculando indicadores...")
        df = self.calculate_indicators(df)
        
        # 5. Gera labels
        logger.info("🎯 Gerando labels...")
        df = self.generate_labels(df)
        
        valid_labels = df['label'].dropna()
        wins = (valid_labels == 1).sum()
        losses = (valid_labels == 0).sum()
        total = len(valid_labels)
        
        if total < self.min_samples:
            logger.warning(f"⚠️ Amostras insuficientes: {total} < {self.min_samples}")
            # Retorna modelo existente se houver
            model_path = self.get_model_path()
            if os.path.exists(model_path):
                return True, model_path, 0.5
            return False, "", 0.5
        
        logger.info(f"   {total:,} amostras | Win: {wins:,} ({wins/total*100:.1f}%) | Loss: {losses:,}")
        
        # 6. Treina modelo
        logger.info("🚀 Treinando modelo...")
        model, metrics = self.train_model(df)
        
        if model is None:
            logger.error("❌ Falha no treino!")
            return False, "", 0.5
        
        # 7. Salva modelo
        model_path = self.save_model(model, metrics)
        threshold = metrics.get('threshold', 0.5)
        
        logger.info("=" * 50)
        logger.info("✅ TREINO CONCLUÍDO!")
        logger.info(f"   Accuracy:  {metrics['accuracy']:.1%}")
        logger.info(f"   Precision: {metrics['precision']:.1%}")
        logger.info(f"   F1 Score:  {metrics['f1']:.1%}")
        logger.info(f"   Threshold: {threshold:.0%}")
        logger.info("=" * 50)
        
        return True, model_path, threshold


class UniversalAutoTrainer(AutoTrainer):
    """
    Treina modelo ML universal para múltiplas criptomoedas.
    
    Combina dados de BTC, ETH, SOL em um único modelo,
    adicionando feature 'symbol_id' para diferenciar os ativos.
    """
    
    def __init__(self, symbols: list, timeframe: int, data_dir: str = "historical_data",
                 models_dir: str = "models", history_months: int = 6):
        # Inicializa com primeiro símbolo (para compatibilidade)
        super().__init__(symbols[0], timeframe, data_dir, models_dir, history_months)
        
        self.symbols = symbols
        self.symbol_map = {s: i for i, s in enumerate(symbols)}
        
        # Features universais (inclui symbol_id e hour)
        self.feature_names = [
            'sma_crossover', 'price_vs_sma21', 'rsi', 'rsi_zone',
            'macd_signal', 'macd_histogram', 'adx', 'adx_direction',
            'atr_percentile', 'market_structure', 'bos_type',
            'bos_pullback_valid', 'in_order_block', 'volume_above_avg',
            'symbol_id', 'hour'
        ]
    
    def get_model_path(self) -> str:
        """Retorna caminho do modelo universal."""
        return os.path.join(self.models_dir, "crypto_universal_lgbm.pkl")
    
    def download_all_history(self, mt5_adapter) -> bool:
        """Baixa histórico de todos os símbolos."""
        success = True
        
        for symbol in self.symbols:
            logger.info(f"📥 Baixando histórico de {symbol}...")
            self.symbol = symbol  # Temporariamente muda o símbolo
            if not self.download_history(mt5_adapter):
                success = False
        
        return success
    
    def load_all_data(self) -> pd.DataFrame:
        """Carrega dados de todos os símbolos e combina."""
        all_dfs = []
        
        for symbol in self.symbols:
            self.symbol = symbol
            df = self.load_data()
            
            if df.empty:
                logger.warning(f"⚠️ Sem dados para {symbol}")
                continue
            
            # Adiciona identificador do símbolo
            df['symbol'] = symbol
            df['symbol_id'] = self.symbol_map[symbol]
            
            # Adiciona hora do dia
            if 'time' in df.columns:
                df['hour'] = pd.to_datetime(df['time']).dt.hour
            else:
                df['hour'] = 12  # Padrão
            
            all_dfs.append(df)
            logger.info(f"   {symbol}: {len(df):,} candles")
        
        if not all_dfs:
            return pd.DataFrame()
        
        # Combina todos os dados
        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined.sort_values('time').reset_index(drop=True)
        
        logger.info(f"📊 Total combinado: {len(combined):,} candles")
        return combined
    
    def calculate_indicators_universal(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores para cada símbolo separadamente."""
        result_dfs = []
        
        for symbol in df['symbol'].unique():
            symbol_df = df[df['symbol'] == symbol].copy().reset_index(drop=True)
            symbol_df = self.calculate_indicators(symbol_df)
            result_dfs.append(symbol_df)
        
        return pd.concat(result_dfs, ignore_index=True)
    
    def run(self, mt5_adapter, force_retrain: bool = False) -> Tuple[bool, str, float]:
        """
        Executa auto-treino universal.
        
        Returns:
            (success, model_path, threshold)
        """
        logger.info("=" * 50)
        logger.info("🤖 AUTO-TRAINER UNIVERSAL - Multi-Crypto ML")
        logger.info(f"   Ativos: {', '.join(self.symbols)}")
        logger.info("=" * 50)
        
        # 1. Verifica se precisa retreinar
        needs_train, reason = self.needs_retrain()
        
        if not needs_train and not force_retrain:
            model_path = self.get_model_path()
            try:
                with open(model_path, 'rb') as f:
                    data = pickle.load(f)
                threshold = data.get('threshold', 0.5)
                logger.info(f"✅ Modelo universal existente OK: {reason}")
                logger.info(f"   Threshold: {threshold:.0%}")
                return True, model_path, threshold
            except:
                needs_train = True
                reason = "Erro ao carregar modelo"
        
        logger.info(f"🔄 Retreino necessário: {reason}")
        
        # 2. Baixa histórico de todos os símbolos
        logger.info(f"📥 Baixando {self.history_months} meses de histórico...")
        self.download_all_history(mt5_adapter)
        
        # 3. Carrega dados combinados
        logger.info("📊 Carregando dados de todos os ativos...")
        df = self.load_all_data()
        
        if df.empty:
            logger.error("❌ Sem dados para treinar!")
            return False, "", 0.5
        
        # 4. Calcula indicadores
        logger.info("🔧 Calculando indicadores...")
        df = self.calculate_indicators_universal(df)
        
        # 5. Gera labels
        logger.info("🎯 Gerando labels...")
        df = self.generate_labels(df)
        
        valid_labels = df['label'].dropna()
        wins = (valid_labels == 1).sum()
        losses = (valid_labels == 0).sum()
        total = len(valid_labels)
        
        if total < self.min_samples:
            logger.warning(f"⚠️ Amostras insuficientes: {total} < {self.min_samples}")
            model_path = self.get_model_path()
            if os.path.exists(model_path):
                return True, model_path, 0.5
            return False, "", 0.5
        
        logger.info(f"   {total:,} amostras | Win: {wins:,} ({wins/total*100:.1f}%) | Loss: {losses:,}")
        
        # Log por símbolo
        for symbol in self.symbols:
            symbol_df = df[df['symbol'] == symbol]
            symbol_labels = symbol_df['label'].dropna()
            if len(symbol_labels) > 0:
                symbol_wins = (symbol_labels == 1).sum()
                logger.info(f"   {symbol}: {len(symbol_labels):,} amostras | Win: {symbol_wins/len(symbol_labels)*100:.1f}%")
        
        # 6. Treina modelo
        logger.info("🚀 Treinando modelo universal...")
        model, metrics = self.train_model(df)
        
        if model is None:
            logger.error("❌ Falha no treino!")
            return False, "", 0.5
        
        # 7. Salva modelo
        model_path = self.save_model(model, metrics)
        threshold = metrics.get('threshold', 0.5)
        
        # Adiciona info dos símbolos ao modelo
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
        
        data['symbols'] = self.symbols
        data['symbol_map'] = self.symbol_map
        
        with open(model_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("=" * 50)
        logger.info("✅ TREINO UNIVERSAL CONCLUÍDO!")
        logger.info(f"   Ativos: {', '.join(self.symbols)}")
        logger.info(f"   Accuracy:  {metrics['accuracy']:.1%}")
        logger.info(f"   Precision: {metrics['precision']:.1%}")
        logger.info(f"   F1 Score:  {metrics['f1']:.1%}")
        logger.info(f"   Threshold: {threshold:.0%}")
        logger.info("=" * 50)
        
        return True, model_path, threshold
