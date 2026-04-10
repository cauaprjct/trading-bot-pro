"""
Hybrid Strategy - Combina Trend Following + Mean Reversion + ML Filter + MTF

Este é o cérebro do bot v3.0. Ele:
1. Analisa o mercado (ADX) para escolher a estratégia
2. Gera sinal com a estratégia apropriada
3. Filtra com ML (probabilidade de sucesso)
4. Confirma com MTF (tendência maior)
5. Executa ou rejeita o trade

Fluxo:
ADX >= 20 → Trend Following → ML Filter → MTF Confirm → Trade
ADX < 20  → Mean Reversion  → ML Filter → MTF Confirm → Trade
"""

import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime

from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .ml_signal_filter import MLSignalFilter
from .multi_timeframe import MultiTimeframeAnalyzer
from ..domain.entities import TradeSignal, SignalType
from ..utils.logger import setup_logger

logger = setup_logger("HybridStrategy")


class HybridStrategy:
    """
    Estratégia Híbrida v3.0
    
    Combina múltiplas estratégias e filtros para maximizar win rate.
    """
    
    def __init__(self, config, exchange_adapter=None):
        self.config = config
        self.adapter = exchange_adapter
        
        # Estratégia principal (Trend Following)
        self.trend_strategy = TrendFollowingStrategy(
            fast_period=config.SMA_FAST,
            slow_period=config.SMA_SLOW,
            rsi_period=config.RSI_PERIOD,
            rsi_upper=config.RSI_OVERBOUGHT,
            rsi_lower=config.RSI_OVERSOLD,
            atr_period=config.ATR_PERIOD,
            atr_mult_sl=config.ATR_MULTIPLIER_SL,
            atr_mult_tp=config.ATR_MULTIPLIER_TP,
            aggressive_mode=config.AGGRESSIVE_MODE,
            use_rsi_extreme=config.USE_RSI_EXTREME_ENTRY,
            rsi_extreme_oversold=config.RSI_EXTREME_OVERSOLD,
            rsi_extreme_overbought=config.RSI_EXTREME_OVERBOUGHT,
            min_signal_score=config.MIN_SIGNAL_SCORE,
            use_macd_filter=config.USE_MACD_FILTER,
            use_volume_filter=config.USE_VOLUME_FILTER,
            rsi_momentum_sell=config.RSI_MOMENTUM_SELL,
            rsi_momentum_buy=config.RSI_MOMENTUM_BUY,
            use_adx_filter=config.USE_ADX_FILTER,
            adx_period=config.ADX_PERIOD,
            adx_threshold=config.ADX_THRESHOLD,
            adx_strong=config.ADX_STRONG,
            use_anti_stop_hunt=config.USE_ANTI_STOP_HUNT,
            sl_buffer_pips=config.SL_BUFFER_PIPS,
            avoid_round_numbers=config.AVOID_ROUND_NUMBERS,
            round_number_buffer_pips=config.ROUND_NUMBER_BUFFER_PIPS,
            use_swing_sl=config.USE_SWING_SL,
            use_volatility_filter=config.USE_VOLATILITY_FILTER,
            atr_percentile_low=config.ATR_PERCENTILE_LOW,
            atr_percentile_high=config.ATR_PERCENTILE_HIGH,
            atr_lookback=config.ATR_LOOKBACK,
            use_market_structure=config.USE_MARKET_STRUCTURE,
            swing_lookback=config.SWING_LOOKBACK,
            min_swing_points=config.MIN_SWING_POINTS,
            structure_as_filter=config.STRUCTURE_AS_FILTER,
            use_bos_pullback=config.USE_BOS_PULLBACK,
            bos_pullback_min=config.BOS_PULLBACK_MIN,
            bos_pullback_max=config.BOS_PULLBACK_MAX,
            bos_expiry_bars=config.BOS_EXPIRY_BARS,
            bos_as_filter=config.BOS_AS_FILTER,
            use_order_blocks=config.USE_ORDER_BLOCKS,
            ob_lookback=config.OB_LOOKBACK,
            ob_min_impulse_atr=config.OB_MIN_IMPULSE_ATR,
            ob_as_filter=config.OB_AS_FILTER,
            ob_mitigation_percent=config.OB_MITIGATION_PERCENT,
            ob_max_age_bars=config.OB_MAX_AGE_BARS
        )
        
        # Estratégia secundária (Mean Reversion)
        self.mean_reversion = None
        if getattr(config, 'USE_MEAN_REVERSION', False):
            self.mean_reversion = MeanReversionStrategy(
                bb_period=getattr(config, 'MR_BB_PERIOD', 20),
                bb_std=getattr(config, 'MR_BB_STD', 2.0),
                rsi_oversold=getattr(config, 'MR_RSI_OVERSOLD', 30),
                rsi_overbought=getattr(config, 'MR_RSI_OVERBOUGHT', 70),
                zscore_threshold=getattr(config, 'MR_ZSCORE_THRESHOLD', 2.0),
                min_score=getattr(config, 'MR_MIN_SCORE', 2)
            )
            logger.info("🔄 Mean Reversion Strategy: ATIVO")
        
        # Filtro ML
        self.ml_filter = None
        if getattr(config, 'USE_ML_FILTER', False):
            self.ml_filter = MLSignalFilter(
                history_file=getattr(config, 'ML_HISTORY_FILE', 'ml_trade_history.json'),
                min_samples=getattr(config, 'ML_MIN_SAMPLES', 20),
                confidence_threshold=getattr(config, 'ML_CONFIDENCE_THRESHOLD', 0.55),
                use_time_filter=getattr(config, 'ML_USE_TIME_FILTER', True),
                use_volatility_filter=getattr(config, 'ML_USE_VOLATILITY_FILTER', True)
            )
            logger.info("🤖 ML Signal Filter: ATIVO")
        
        # Multi-Timeframe
        self.mtf_analyzer = None
        if getattr(config, 'USE_MTF_ANALYSIS', False):
            import MetaTrader5 as mt5
            self.mtf_analyzer = MultiTimeframeAnalyzer(
                higher_tf=getattr(config, 'MTF_HIGHER_TF', mt5.TIMEFRAME_H1),
                min_trend_strength=getattr(config, 'MTF_MIN_TREND_STRENGTH', 0.3)
            )
            logger.info("📊 Multi-Timeframe Analysis: ATIVO")
        
        # Configurações híbridas
        self.use_hybrid = getattr(config, 'USE_HYBRID_MODE', True)
        self.hybrid_adx_threshold = getattr(config, 'HYBRID_ADX_THRESHOLD', 20)
        
        # Estatísticas
        self.stats = {
            'trend_signals': 0,
            'mr_signals': 0,
            'ml_blocked': 0,
            'mtf_blocked': 0,
            'executed': 0
        }
    
    def analyze(self, df: pd.DataFrame, open_positions: list, symbol: str = None) -> TradeSignal:
        """
        Análise híbrida completa.
        
        1. Determina estratégia baseado no ADX
        2. Gera sinal
        3. Aplica filtros (ML, MTF)
        4. Retorna sinal final
        """
        # Primeiro, usa Trend Following para obter indicadores
        signal = self.trend_strategy.analyze(df, open_positions)
        
        # Se já posicionado ou dados insuficientes, retorna
        if signal.type == SignalType.HOLD:
            # Verifica se é mercado lateral e pode usar Mean Reversion
            if self.use_hybrid and self.mean_reversion:
                adx = signal.indicators.get('adx', 25)
                if adx < self.hybrid_adx_threshold:
                    mr_signal = self._try_mean_reversion(df, signal.indicators, open_positions)
                    if mr_signal:
                        return mr_signal
            return signal
        
        # Obtém dados do sinal
        signal_type = 'BUY' if signal.type == SignalType.BUY else 'SELL'
        indicators = signal.indicators
        
        # Log da estratégia usada
        adx = indicators.get('adx', 25)
        if adx >= self.hybrid_adx_threshold:
            self.stats['trend_signals'] += 1
            logger.info(f"📈 Estratégia: TREND FOLLOWING (ADX {adx:.0f} >= {self.hybrid_adx_threshold})")
        else:
            self.stats['mr_signals'] += 1
            logger.info(f"🔄 Estratégia: MEAN REVERSION (ADX {adx:.0f} < {self.hybrid_adx_threshold})")
        
        # Aplica filtro ML
        if self.ml_filter:
            ml_result = self._apply_ml_filter(signal_type, indicators)
            if not ml_result['should_trade']:
                self.stats['ml_blocked'] += 1
                logger.warning(f"🤖 ML BLOQUEOU: {ml_result['warnings']}")
                return TradeSignal(
                    SignalType.HOLD,
                    signal.price,
                    comment=f"ML: {ml_result['probability']*100:.0f}% < threshold",
                    indicators=indicators
                )
            else:
                logger.info(f"🤖 ML APROVOU: {ml_result['probability']*100:.0f}% ({ml_result['confidence']})")
        
        # Aplica filtro MTF
        if self.mtf_analyzer and symbol:
            try:
                mtf_result = self._apply_mtf_filter(symbol, signal_type)
                if not mtf_result[0]:
                    self.stats['mtf_blocked'] += 1
                    logger.warning(f"📊 MTF BLOQUEOU: {mtf_result[1]}")
                    return TradeSignal(
                        SignalType.HOLD,
                        signal.price,
                        comment=f"MTF: {mtf_result[1]}",
                        indicators=indicators
                    )
                else:
                    logger.info(f"📊 MTF APROVOU: {mtf_result[1]}")
            except Exception as e:
                logger.error(f"❌ Erro no MTF Filter: {e}")
        
        # Sinal aprovado!
        self.stats['executed'] += 1
        logger.info(f"✅ SINAL APROVADO: {signal.type.name} | Preço: {signal.price:.5f} | SL: {signal.sl:.5f} | TP: {signal.tp:.5f}")
        return signal
    
    def _try_mean_reversion(self, df: pd.DataFrame, indicators: dict, open_positions: list) -> Optional[TradeSignal]:
        """Tenta gerar sinal de Mean Reversion"""
        if not self.mean_reversion or len(open_positions) > 0:
            return None
        
        adx = indicators.get('adx', 25)
        mr_result = self.mean_reversion.analyze(df, adx)
        
        if mr_result['signal'] == 'NONE':
            return None
        
        current_price = df['close'].iloc[-1]
        sl, tp = self.mean_reversion.get_targets(df, mr_result['signal'], current_price)
        
        signal_type = SignalType.BUY if mr_result['signal'] == 'BUY' else SignalType.SELL
        
        # Atualiza indicadores
        indicators['strategy'] = 'MEAN_REVERSION'
        indicators['mr_score'] = mr_result['score']
        indicators['bb_position'] = mr_result['bb_position']
        indicators['zscore'] = mr_result['zscore']
        
        logger.info(f"🔄 MEAN REVERSION: {mr_result['signal']} | Score: {mr_result['score']} | BB: {mr_result['bb_position']}")
        
        return TradeSignal(
            signal_type,
            current_price,
            sl=sl,
            tp=tp,
            comment=f"MR {mr_result['signal']} S{mr_result['score']}",
            indicators=indicators
        )
    
    def _apply_ml_filter(self, signal_type: str, indicators: dict) -> dict:
        """Aplica filtro de Machine Learning"""
        signal_data = {
            'signal_type': signal_type,
            'score': indicators.get('signal_score', 0),
            'rsi': indicators.get('rsi', 50),
            'adx': indicators.get('adx', 20),
            'atr_percentile': indicators.get('atr_percentile', 50),
            'market_structure': indicators.get('market_structure', 'RANGING'),
            'hour': datetime.now().hour
        }
        
        return self.ml_filter.predict_success(signal_data)
    
    def _apply_mtf_filter(self, symbol: str, signal_type: str) -> Tuple[bool, str]:
        """Aplica filtro Multi-Timeframe"""
        block_counter = getattr(self.config, 'MTF_BLOCK_COUNTER_TREND', True)
        
        if not block_counter:
            return True, "MTF filter desativado"
        
        return self.mtf_analyzer.should_trade(symbol, signal_type)
    
    def record_trade_result(self, trade_data: dict):
        """Registra resultado do trade para aprendizado do ML"""
        if self.ml_filter:
            self.ml_filter.record_trade(trade_data)
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do modo híbrido"""
        total = self.stats['trend_signals'] + self.stats['mr_signals']
        return {
            'total_signals': total,
            'trend_following': self.stats['trend_signals'],
            'mean_reversion': self.stats['mr_signals'],
            'ml_blocked': self.stats['ml_blocked'],
            'mtf_blocked': self.stats['mtf_blocked'],
            'executed': self.stats['executed'],
            'block_rate': (self.stats['ml_blocked'] + self.stats['mtf_blocked']) / max(total, 1) * 100
        }
    
    def print_stats(self):
        """Imprime estatísticas"""
        stats = self.get_stats()
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("📊 ESTATÍSTICAS DO MODO HÍBRIDO")
        logger.info(f"   Total de sinais: {stats['total_signals']}")
        logger.info(f"   Trend Following: {stats['trend_following']}")
        logger.info(f"   Mean Reversion: {stats['mean_reversion']}")
        logger.info(f"   Bloqueados ML: {stats['ml_blocked']}")
        logger.info(f"   Bloqueados MTF: {stats['mtf_blocked']}")
        logger.info(f"   Executados: {stats['executed']}")
        logger.info(f"   Taxa de bloqueio: {stats['block_rate']:.1f}%")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
