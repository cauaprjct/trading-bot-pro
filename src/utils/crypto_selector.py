"""
Crypto Selector - Seleciona a melhor oportunidade entre múltiplas criptomoedas

Analisa BTC, ETH, SOL simultaneamente e escolhe a melhor oportunidade
baseado em: score de sinal, probabilidade ML, spread e prioridade.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pandas as pd
from datetime import datetime

from ..domain.entities import TradeSignal, SignalType
from .logger import setup_logger

logger = setup_logger("CryptoSelector")


@dataclass
class CryptoOpportunity:
    """Representa uma oportunidade de trade em uma cripto específica"""
    symbol: str
    name: str
    signal: TradeSignal
    ml_probability: float
    signal_score: int
    spread_ratio: float      # spread_atual / spread_max (menor = melhor)
    priority: int
    combined_score: float
    reason: str
    
    @property
    def is_valid(self) -> bool:
        """Verifica se é uma oportunidade válida"""
        return (
            self.signal.type != SignalType.HOLD and
            self.spread_ratio <= 1.0 and  # Spread dentro do limite
            self.combined_score > 0
        )
    
    def __str__(self) -> str:
        signal_type = self.signal.type.name if self.signal else "NONE"
        return f"{self.symbol}: {signal_type} | Score: {self.signal_score}/9 | ML: {self.ml_probability:.0%} | Combined: {self.combined_score:.2f}"


class CryptoSelector:
    """
    Analisa múltiplas criptomoedas e seleciona a melhor oportunidade.
    
    Critérios de seleção (em ordem):
    1. Sinal válido (não HOLD)
    2. Spread dentro do limite
    3. ML aprovado (se configurado)
    4. Score combinado mais alto
    """
    
    def __init__(self, config, adapter, strategy, ml_filter=None, spread_filter=None):
        self.config = config
        self.adapter = adapter
        self.strategy = strategy
        self.ml_filter = ml_filter
        self.spread_filter = spread_filter
        
        # Pesos para cálculo do score combinado
        self.ml_weight = getattr(config, 'SELECTOR_ML_WEIGHT', 0.5)
        self.score_weight = getattr(config, 'SELECTOR_SCORE_WEIGHT', 0.3)
        self.spread_weight = getattr(config, 'SELECTOR_SPREAD_WEIGHT', 0.2)
        
        # Configurações
        self.min_combined_score = getattr(config, 'SELECTOR_MIN_COMBINED_SCORE', 0.3)
        self.require_ml = getattr(config, 'SELECTOR_REQUIRE_ML_APPROVAL', True)
        
        # Cache de análises
        self._last_analysis: Dict[str, CryptoOpportunity] = {}
        self._last_analysis_time: Optional[datetime] = None
    
    def analyze_asset(self, symbol: str, asset_config: dict) -> CryptoOpportunity:
        """
        Analisa um ativo específico e retorna a oportunidade.
        
        Args:
            symbol: Símbolo do ativo (ex: 'BTCUSD-T')
            asset_config: Configurações específicas do ativo
        
        Returns:
            CryptoOpportunity com os dados da análise
        """
        try:
            # Obtém dados do ativo
            df = self.adapter.get_data(symbol, self.config.TIMEFRAME, n_bars=500)
            if df is None or df.empty:
                return self._create_invalid_opportunity(symbol, asset_config, "Dados indisponíveis")
            
            # Obtém posições abertas neste ativo
            open_positions = self.adapter.get_open_positions(symbol)
            
            # Analisa com a estratégia
            signal = self.strategy.analyze(df, open_positions, symbol)
            
            # Ajusta SL/TP com multiplicadores específicos do ativo
            if signal.type != SignalType.HOLD:
                atr_mult_sl = asset_config.get('atr_mult_sl', 2.5)
                atr_mult_tp = asset_config.get('atr_mult_tp', 5.0)
                
                # Recalcula SL/TP baseado no ATR do ativo
                atr = signal.indicators.get('atr', 0)
                if atr > 0:
                    if signal.type == SignalType.BUY:
                        signal.sl = signal.price - (atr * atr_mult_sl)
                        signal.tp = signal.price + (atr * atr_mult_tp)
                    else:  # SELL
                        signal.sl = signal.price + (atr * atr_mult_sl)
                        signal.tp = signal.price - (atr * atr_mult_tp)
            
            # Obtém score do sinal
            signal_score = signal.indicators.get('signal_score', 0)
            
            # Calcula probabilidade ML
            ml_probability = 0.5  # Padrão neutro
            if self.ml_filter and self.ml_filter.is_ready():
                ml_probability = self._get_ml_probability(signal, symbol)
            
            # Verifica spread
            spread_ratio = self._get_spread_ratio(symbol, asset_config)
            
            # Calcula score combinado
            combined_score = self._calculate_combined_score(
                signal, signal_score, ml_probability, spread_ratio
            )
            
            # Determina razão
            if signal.type == SignalType.HOLD:
                reason = signal.comment or "Aguardando setup"
            elif spread_ratio > 1.0:
                reason = f"Spread alto ({spread_ratio:.1%})"
            elif self.require_ml and ml_probability < self.config.ML_CONFIDENCE_THRESHOLD:
                reason = f"ML baixo ({ml_probability:.0%})"
            else:
                reason = f"✅ Oportunidade válida"
            
            return CryptoOpportunity(
                symbol=symbol,
                name=asset_config.get('name', symbol),
                signal=signal,
                ml_probability=ml_probability,
                signal_score=signal_score,
                spread_ratio=spread_ratio,
                priority=asset_config.get('priority', 99),
                combined_score=combined_score,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"Erro ao analisar {symbol}: {e}")
            return self._create_invalid_opportunity(symbol, asset_config, f"Erro: {e}")
    
    def analyze_all(self) -> List[CryptoOpportunity]:
        """
        Analisa todos os ativos configurados.
        
        Returns:
            Lista de CryptoOpportunity para cada ativo
        """
        opportunities = []
        
        for symbol, asset_config in self.config.CRYPTO_ASSETS.items():
            # Verifica se ativo está habilitado
            if not asset_config.get('enabled', True):
                continue
            
            opp = self.analyze_asset(symbol, asset_config)
            opportunities.append(opp)
            
            # Atualiza cache
            self._last_analysis[symbol] = opp
        
        self._last_analysis_time = datetime.now()
        return opportunities
    
    def select_best(self) -> Optional[CryptoOpportunity]:
        """
        Seleciona a melhor oportunidade entre todos os ativos.
        
        Returns:
            Melhor CryptoOpportunity ou None se não houver oportunidade válida
        """
        opportunities = self.analyze_all()
        
        # Filtra apenas oportunidades válidas
        valid_opportunities = [opp for opp in opportunities if opp.is_valid]
        
        if not valid_opportunities:
            return None
        
        # Filtra por ML se necessário
        if self.require_ml:
            ml_threshold = getattr(self.config, 'ML_CONFIDENCE_THRESHOLD', 0.4)
            valid_opportunities = [
                opp for opp in valid_opportunities 
                if opp.ml_probability >= ml_threshold
            ]
        
        if not valid_opportunities:
            return None
        
        # Filtra por score mínimo
        valid_opportunities = [
            opp for opp in valid_opportunities 
            if opp.combined_score >= self.min_combined_score
        ]
        
        if not valid_opportunities:
            return None
        
        # Ordena por score combinado (maior primeiro)
        valid_opportunities.sort(key=lambda x: (-x.combined_score, x.priority))
        
        return valid_opportunities[0]
    
    def get_analysis_summary(self) -> str:
        """Retorna resumo formatado da última análise"""
        if not self._last_analysis:
            return "Nenhuma análise realizada"
        
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🔍 ANÁLISE MULTI-CRYPTO",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        for symbol, opp in self._last_analysis.items():
            signal_type = opp.signal.type.name if opp.signal else "NONE"
            emoji = "🟢" if signal_type == "BUY" else ("🔴" if signal_type == "SELL" else "⚪")
            
            if opp.is_valid:
                line = f"{emoji} {opp.name}: {signal_type} | Score: {opp.signal_score}/9 | ML: {opp.ml_probability:.0%}"
            else:
                line = f"⚪ {opp.name}: {opp.reason}"
            
            lines.append(line)
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        return "\n".join(lines)
    
    def _get_ml_probability(self, signal: TradeSignal, symbol: str) -> float:
        """Obtém probabilidade do modelo ML"""
        try:
            ind = signal.indicators
            
            # Prepara features
            ml_features = {
                'sma_crossover': 1 if ind.get('sma_fast', 0) > ind.get('sma_slow', 0) else -1,
                'price_vs_sma21': 1 if signal.price > ind.get('sma_slow', 0) else -1,
                'rsi': ind.get('rsi', 50),
                'rsi_zone': 1 if ind.get('rsi', 50) < 30 else (-1 if ind.get('rsi', 50) > 70 else 0),
                'macd_signal': 1 if ind.get('macd', 0) > ind.get('macd_signal', 0) else -1,
                'macd_histogram': ind.get('macd', 0) - ind.get('macd_signal', 0),
                'adx': ind.get('adx', 0),
                'adx_direction': 1 if ind.get('plus_di', 0) > ind.get('minus_di', 0) else -1,
                'atr_percentile': ind.get('atr_percentile', 50),
                'market_structure': ind.get('market_structure', 'RANGING'),
                'bos_type': ind.get('bos_type', 'NONE'),
                'bos_pullback_valid': 1 if ind.get('bos_pullback_valid', False) else 0,
                'in_order_block': 1 if ind.get('in_bullish_ob', False) or ind.get('in_bearish_ob', False) else 0,
                'volume_above_avg': 1,
                'symbol_id': self.config.SYMBOL_ID_MAP.get(symbol, 0),
                'hour': datetime.now().hour
            }
            
            proba, _, _ = self.ml_filter.predict(ml_features, symbol)
            return proba
            
        except Exception as e:
            logger.warning(f"Erro ao obter ML probability: {e}")
            return 0.5
    
    def _get_spread_ratio(self, symbol: str, asset_config: dict) -> float:
        """Calcula razão do spread atual vs máximo permitido"""
        try:
            if self.spread_filter:
                current_spread = self.spread_filter._get_current_spread(symbol)
                if current_spread is not None:
                    max_spread = asset_config.get('spread_max', 10000)
                    return current_spread / max_spread
            return 0.5  # Assume spread OK se não tiver filtro
        except Exception:
            return 0.5
    
    def _calculate_combined_score(
        self, 
        signal: TradeSignal, 
        signal_score: int, 
        ml_probability: float, 
        spread_ratio: float
    ) -> float:
        """
        Calcula score combinado para ranking de oportunidades.
        
        Score = (ML * peso_ml) + (signal_score/9 * peso_score) + ((1-spread_ratio) * peso_spread)
        """
        if signal.type == SignalType.HOLD:
            return 0.0
        
        # Normaliza signal_score para 0-1
        normalized_score = signal_score / 9.0
        
        # Inverte spread_ratio (menor spread = melhor)
        spread_factor = max(0, 1 - spread_ratio)
        
        # Calcula score combinado
        combined = (
            ml_probability * self.ml_weight +
            normalized_score * self.score_weight +
            spread_factor * self.spread_weight
        )
        
        return round(combined, 3)
    
    def _create_invalid_opportunity(
        self, 
        symbol: str, 
        asset_config: dict, 
        reason: str
    ) -> CryptoOpportunity:
        """Cria uma oportunidade inválida (para casos de erro)"""
        return CryptoOpportunity(
            symbol=symbol,
            name=asset_config.get('name', symbol),
            signal=TradeSignal(SignalType.HOLD, 0.0, comment=reason, indicators={}),
            ml_probability=0.0,
            signal_score=0,
            spread_ratio=1.0,
            priority=asset_config.get('priority', 99),
            combined_score=0.0,
            reason=reason
        )
