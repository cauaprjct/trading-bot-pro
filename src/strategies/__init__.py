"""
Strategies Module - B3 Trading Bot PRO v3.0

Estratégias disponíveis:
- TrendFollowingStrategy: Estratégia principal (SMA + RSI + MACD + Smart Money)
- MeanReversionStrategy: Para mercados laterais (Bollinger Bands + Z-Score)
- HybridStrategy: Combina Trend Following + Mean Reversion automaticamente
- MLSignalFilter: Filtro de Machine Learning para sinais
- MultiTimeframeAnalyzer: Confirmação com timeframe maior
- RiskManager: Gerenciamento de risco e Smart Exit
"""

from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .ml_signal_filter import MLSignalFilter
from .multi_timeframe import MultiTimeframeAnalyzer
from .hybrid_strategy import HybridStrategy
from .risk_manager import RiskManager

__all__ = [
    'TrendFollowingStrategy',
    'MeanReversionStrategy',
    'MLSignalFilter',
    'MultiTimeframeAnalyzer',
    'HybridStrategy',
    'RiskManager'
]
