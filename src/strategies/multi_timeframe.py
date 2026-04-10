"""
Multi-Timeframe Analysis - Confirmação com timeframe maior

Conceito: Sinais no M1 são mais confiáveis quando confirmados pelo H1.

Regras:
- Só compra no M1 se H1 também está em tendência de alta
- Só vende no M1 se H1 também está em tendência de baixa
- Evita trades contra a tendência maior
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import MetaTrader5 as mt5
from ..utils.logger import setup_logger

logger = setup_logger("MTF")


class MultiTimeframeAnalyzer:
    """
    Analisador Multi-Timeframe para confirmar sinais.
    
    Usa timeframe maior (H1) para confirmar direção do M1.
    """
    
    def __init__(
        self,
        higher_tf: int = mt5.TIMEFRAME_H1,
        sma_fast: int = 9,
        sma_slow: int = 21,
        rsi_period: int = 14,
        use_trend_filter: bool = True,
        use_rsi_filter: bool = True,
        min_trend_strength: float = 0.3
    ):
        self.higher_tf = higher_tf
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.rsi_period = rsi_period
        self.use_trend_filter = use_trend_filter
        self.use_rsi_filter = use_rsi_filter
        self.min_trend_strength = min_trend_strength
        
        # Cache do último análise
        self._cache = {
            'timestamp': None,
            'result': None,
            'ttl': 60  # Cache válido por 60 segundos
        }
    
    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Calcula RSI"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _get_higher_tf_data(self, symbol: str, bars: int = 100) -> Optional[pd.DataFrame]:
        """Obtém dados do timeframe maior"""
        try:
            rates = mt5.copy_rates_from_pos(symbol, self.higher_tf, 0, bars)
            if rates is None or len(rates) == 0:
                return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except Exception as e:
            logger.warning(f"Erro ao obter dados HTF: {e}")
            return None
    
    def analyze(self, symbol: str, signal_type: str = None) -> Dict:
        """
        Analisa timeframe maior para confirmar sinal.
        
        Args:
            symbol: Par de moedas
            signal_type: 'BUY' ou 'SELL' (opcional, para verificar alinhamento)
        
        Returns:
            {
                'trend': 'BULLISH' | 'BEARISH' | 'NEUTRAL',
                'trend_strength': float (0-1),
                'rsi': float,
                'rsi_zone': str,
                'aligned': bool (se signal_type fornecido),
                'recommendation': str,
                'details': str
            }
        """
        result = {
            'trend': 'NEUTRAL',
            'trend_strength': 0,
            'rsi': 50,
            'rsi_zone': 'NEUTRAL',
            'aligned': True,
            'recommendation': 'OK',
            'details': ''
        }
        
        # Obtém dados do timeframe maior
        df = self._get_higher_tf_data(symbol)
        if df is None or len(df) < self.sma_slow + 5:
            result['details'] = "Dados HTF insuficientes"
            return result
        
        # Calcula indicadores
        df['sma_fast'] = df['close'].rolling(window=self.sma_fast).mean()
        df['sma_slow'] = df['close'].rolling(window=self.sma_slow).mean()
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        
        last = df.iloc[-1]
        
        # Determina tendência
        sma_diff = last['sma_fast'] - last['sma_slow']
        price_vs_sma = last['close'] - last['sma_slow']
        
        # Normaliza para calcular força (0-1)
        atr = (df['high'] - df['low']).rolling(window=14).mean().iloc[-1]
        if atr > 0:
            trend_strength = min(abs(sma_diff) / atr, 1.0)
        else:
            trend_strength = 0
        
        result['trend_strength'] = round(trend_strength, 2)
        
        # Determina direção
        if sma_diff > 0 and price_vs_sma > 0:
            result['trend'] = 'BULLISH'
        elif sma_diff < 0 and price_vs_sma < 0:
            result['trend'] = 'BEARISH'
        else:
            result['trend'] = 'NEUTRAL'
        
        # RSI
        result['rsi'] = round(last['rsi'], 1) if not pd.isna(last['rsi']) else 50
        if result['rsi'] < 40:
            result['rsi_zone'] = 'OVERSOLD'
        elif result['rsi'] > 60:
            result['rsi_zone'] = 'OVERBOUGHT'
        else:
            result['rsi_zone'] = 'NEUTRAL'
        
        # Verifica alinhamento com sinal
        if signal_type:
            if signal_type == 'BUY':
                result['aligned'] = result['trend'] != 'BEARISH'
                if result['trend'] == 'BEARISH':
                    result['recommendation'] = 'AVOID'
                    result['details'] = f"⚠️ HTF em tendência de BAIXA - evitar COMPRA"
                elif result['trend'] == 'BULLISH':
                    result['recommendation'] = 'STRONG'
                    result['details'] = f"✓ HTF confirma tendência de ALTA"
                else:
                    result['recommendation'] = 'OK'
                    result['details'] = f"HTF neutro - sinal OK"
            
            elif signal_type == 'SELL':
                result['aligned'] = result['trend'] != 'BULLISH'
                if result['trend'] == 'BULLISH':
                    result['recommendation'] = 'AVOID'
                    result['details'] = f"⚠️ HTF em tendência de ALTA - evitar VENDA"
                elif result['trend'] == 'BEARISH':
                    result['recommendation'] = 'STRONG'
                    result['details'] = f"✓ HTF confirma tendência de BAIXA"
                else:
                    result['recommendation'] = 'OK'
                    result['details'] = f"HTF neutro - sinal OK"
        
        # Log
        tf_name = self._get_tf_name()
        logger.info(f"📊 MTF ({tf_name}): {result['trend']} | Força: {result['trend_strength']*100:.0f}% | RSI: {result['rsi']:.0f}")
        
        return result
    
    def _get_tf_name(self) -> str:
        """Retorna nome legível do timeframe"""
        tf_names = {
            mt5.TIMEFRAME_M1: 'M1',
            mt5.TIMEFRAME_M5: 'M5',
            mt5.TIMEFRAME_M15: 'M15',
            mt5.TIMEFRAME_M30: 'M30',
            mt5.TIMEFRAME_H1: 'H1',
            mt5.TIMEFRAME_H4: 'H4',
            mt5.TIMEFRAME_D1: 'D1',
        }
        return tf_names.get(self.higher_tf, str(self.higher_tf))
    
    def should_trade(self, symbol: str, signal_type: str) -> Tuple[bool, str]:
        """
        Verifica se deve executar o trade baseado no MTF.
        
        Returns:
            (should_trade: bool, reason: str)
        """
        analysis = self.analyze(symbol, signal_type)
        
        if not self.use_trend_filter:
            return True, "MTF filter desativado"
        
        if analysis['recommendation'] == 'AVOID':
            return False, analysis['details']
        
        if analysis['recommendation'] == 'STRONG':
            return True, analysis['details']
        
        # Se tendência fraca, ainda permite
        if analysis['trend_strength'] < self.min_trend_strength:
            return True, f"HTF sem tendência forte ({analysis['trend_strength']*100:.0f}%)"
        
        return analysis['aligned'], analysis['details']
    
    def get_bias(self, symbol: str) -> str:
        """
        Retorna o viés do timeframe maior.
        
        Returns:
            'BUY' | 'SELL' | 'NEUTRAL'
        """
        analysis = self.analyze(symbol)
        
        if analysis['trend'] == 'BULLISH' and analysis['trend_strength'] >= self.min_trend_strength:
            return 'BUY'
        elif analysis['trend'] == 'BEARISH' and analysis['trend_strength'] >= self.min_trend_strength:
            return 'SELL'
        else:
            return 'NEUTRAL'
