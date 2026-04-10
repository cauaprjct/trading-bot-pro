"""
Mean Reversion Strategy - Para mercados laterais (ADX < 20)

Quando o mercado está sem tendência (lateral), Trend Following perde dinheiro.
Mean Reversion assume que preços voltam à média.

Indicadores:
- Bollinger Bands (preço fora das bandas = oportunidade)
- RSI extremo (< 30 ou > 70)
- Z-Score (desvio da média)

Lógica:
- Compra quando preço toca banda inferior + RSI < 30
- Vende quando preço toca banda superior + RSI > 70
"""

import pandas as pd
import numpy as np
from typing import Tuple, List, Dict
from ..utils.logger import setup_logger

logger = setup_logger("MeanReversion")


class MeanReversionStrategy:
    """
    Estratégia de Reversão à Média para mercados laterais.
    Complementa o Trend Following quando ADX < 20.
    """
    
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: int = 30,
        rsi_overbought: int = 70,
        zscore_threshold: float = 2.0,
        min_score: int = 2,
        use_zscore: bool = True,
        use_rsi_confirmation: bool = True,
        use_volume_confirmation: bool = True
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.zscore_threshold = zscore_threshold
        self.min_score = min_score
        self.use_zscore = use_zscore
        self.use_rsi_confirmation = use_rsi_confirmation
        self.use_volume_confirmation = use_volume_confirmation
    
    def calculate_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula Bollinger Bands"""
        df = df.copy()
        df['bb_middle'] = df['close'].rolling(window=self.bb_period).mean()
        df['bb_std'] = df['close'].rolling(window=self.bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * self.bb_std)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * self.bb_std)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
        return df
    
    def calculate_zscore(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Calcula Z-Score do preço em relação à média.
        Z-Score > 2 = muito acima da média (vender)
        Z-Score < -2 = muito abaixo da média (comprar)
        """
        mean = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        zscore = (df['close'] - mean) / std
        return zscore
    
    def calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Calcula RSI"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def analyze(self, df: pd.DataFrame, adx_value: float = 0) -> Dict:
        """
        Analisa mercado para sinais de Mean Reversion.
        
        Só ativa quando ADX < 20 (mercado lateral).
        
        Returns:
            {
                'signal': 'BUY' | 'SELL' | 'NONE',
                'score': int,
                'confirmations': list,
                'bb_position': str,
                'zscore': float,
                'rsi': float
            }
        """
        result = {
            'signal': 'NONE',
            'score': 0,
            'confirmations': [],
            'rejections': [],
            'bb_position': 'MIDDLE',
            'zscore': 0,
            'rsi': 50,
            'active': False
        }
        
        # Só ativa em mercado lateral (ADX < 20)
        if adx_value >= 20:
            result['rejections'].append(f"ADX {adx_value:.0f} >= 20 (mercado com tendência)")
            return result
        
        result['active'] = True
        
        if len(df) < self.bb_period + 5:
            result['rejections'].append("Dados insuficientes")
            return result
        
        # Calcula indicadores
        df = self.calculate_bollinger_bands(df)
        df['zscore'] = self.calculate_zscore(df, self.bb_period)
        df['rsi_mr'] = self.calculate_rsi(df['close'], self.rsi_period)
        
        last = df.iloc[-1]
        current_price = last['close']
        
        result['zscore'] = round(last['zscore'], 2) if not pd.isna(last['zscore']) else 0
        result['rsi'] = round(last['rsi_mr'], 1) if not pd.isna(last['rsi_mr']) else 50
        
        score_buy = 0
        score_sell = 0
        confirmations_buy = []
        confirmations_sell = []
        
        # 1. Bollinger Bands Position
        if current_price <= last['bb_lower']:
            result['bb_position'] = 'LOWER'
            score_buy += 1
            confirmations_buy.append(f"✓ Preço na banda inferior ({current_price:.5f} <= {last['bb_lower']:.5f})")
        elif current_price >= last['bb_upper']:
            result['bb_position'] = 'UPPER'
            score_sell += 1
            confirmations_sell.append(f"✓ Preço na banda superior ({current_price:.5f} >= {last['bb_upper']:.5f})")
        else:
            result['bb_position'] = 'MIDDLE'
        
        # 2. Z-Score
        if self.use_zscore:
            if last['zscore'] <= -self.zscore_threshold:
                score_buy += 1
                confirmations_buy.append(f"✓ Z-Score {last['zscore']:.2f} <= -{self.zscore_threshold} (muito abaixo da média)")
            elif last['zscore'] >= self.zscore_threshold:
                score_sell += 1
                confirmations_sell.append(f"✓ Z-Score {last['zscore']:.2f} >= {self.zscore_threshold} (muito acima da média)")
        
        # 3. RSI Confirmation
        if self.use_rsi_confirmation:
            if last['rsi_mr'] <= self.rsi_oversold:
                score_buy += 1
                confirmations_buy.append(f"✓ RSI {last['rsi_mr']:.1f} <= {self.rsi_oversold} (sobrevenda)")
            elif last['rsi_mr'] >= self.rsi_overbought:
                score_sell += 1
                confirmations_sell.append(f"✓ RSI {last['rsi_mr']:.1f} >= {self.rsi_overbought} (sobrecompra)")
        
        # 4. Volume Confirmation (volume baixo = bom para mean reversion)
        if self.use_volume_confirmation and 'tick_volume' in df.columns:
            vol_sma = df['tick_volume'].rolling(window=20).mean().iloc[-1]
            current_vol = df['tick_volume'].iloc[-1]
            if current_vol < vol_sma * 0.8:  # Volume 20% abaixo da média
                score_buy += 1
                score_sell += 1
                confirmations_buy.append("✓ Volume baixo (mercado calmo)")
                confirmations_sell.append("✓ Volume baixo (mercado calmo)")
        
        # Determina sinal
        if score_buy >= self.min_score and score_buy > score_sell:
            result['signal'] = 'BUY'
            result['score'] = score_buy
            result['confirmations'] = confirmations_buy
            logger.info(f"🔄 MEAN REVERSION: Sinal de COMPRA (Score {score_buy})")
        elif score_sell >= self.min_score and score_sell > score_buy:
            result['signal'] = 'SELL'
            result['score'] = score_sell
            result['confirmations'] = confirmations_sell
            logger.info(f"🔄 MEAN REVERSION: Sinal de VENDA (Score {score_sell})")
        else:
            result['rejections'].append(f"Score insuficiente (Buy: {score_buy}, Sell: {score_sell})")
        
        return result
    
    def get_targets(self, df: pd.DataFrame, signal: str, current_price: float) -> Tuple[float, float]:
        """
        Calcula SL e TP para Mean Reversion.
        
        TP = Banda do meio (média)
        SL = Além da banda oposta
        
        IMPORTANTE: Mínimo de 15 pips SL e 20 pips TP para evitar rejeição da corretora
        """
        df = self.calculate_bollinger_bands(df)
        last = df.iloc[-1]
        
        bb_middle = last['bb_middle']
        bb_upper = last['bb_upper']
        bb_lower = last['bb_lower']
        bb_width = bb_upper - bb_lower
        
        # Mínimos em pips (convertido para preço)
        # Para EURUSD, 1 pip = 0.0001
        min_sl_pips = 15
        min_tp_pips = 20
        pip_value = 0.0001  # Para pares XXX/USD
        
        min_sl_distance = min_sl_pips * pip_value
        min_tp_distance = min_tp_pips * pip_value
        
        if signal == 'BUY':
            # Comprou na banda inferior
            tp_calc = bb_middle  # TP na média
            sl_calc = bb_lower - (bb_width * 0.3)  # SL 30% além da banda inferior
            
            # Garante distância mínima
            tp_distance = tp_calc - current_price
            sl_distance = current_price - sl_calc
            
            if tp_distance < min_tp_distance:
                tp = current_price + min_tp_distance
            else:
                tp = tp_calc
                
            if sl_distance < min_sl_distance:
                sl = current_price - min_sl_distance
            else:
                sl = sl_calc
        else:
            # Vendeu na banda superior
            tp_calc = bb_middle  # TP na média
            sl_calc = bb_upper + (bb_width * 0.3)  # SL 30% além da banda superior
            
            # Garante distância mínima
            tp_distance = current_price - tp_calc
            sl_distance = sl_calc - current_price
            
            if tp_distance < min_tp_distance:
                tp = current_price - min_tp_distance
            else:
                tp = tp_calc
                
            if sl_distance < min_sl_distance:
                sl = current_price + min_sl_distance
            else:
                sl = sl_calc
        
        logger.info(f"🎯 MR Targets: SL={abs(current_price-sl)/pip_value:.1f} pips | TP={abs(tp-current_price)/pip_value:.1f} pips")
        
        return sl, tp
