"""
🤖 ML Filter - Filtro de Machine Learning para Sinais de Trading
Usa LightGBM para prever probabilidade de sucesso do trade.

LEVE E OTIMIZADO:
- Treino: ~30 segundos (offline, uma vez)
- Inferência: <1ms por predição
- RAM: ~10MB
"""
import os
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from .logger import setup_logger

logger = setup_logger("MLFilter")

class MLFilter:
    """
    Filtro ML que aprende quais combinações de indicadores geram trades lucrativos.
    
    Substitui o score fixo 9/9 por uma probabilidade dinâmica baseada em dados reais.
    """
    
    def __init__(self, model_path: str = None, min_confidence: float = 0.60):
        """
        Args:
            model_path: Caminho para o modelo treinado (.pkl)
            min_confidence: Probabilidade mínima para aprovar trade (0.0-1.0)
        """
        self.model = None
        self.feature_names = None
        self.min_confidence = min_confidence
        self.model_path = model_path
        self._stats = {"predictions": 0, "approved": 0, "rejected": 0}
        
        # Carrega modelo se existir
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def load_model(self, path: str) -> bool:
        """Carrega modelo treinado do disco."""
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
            
            self.model = data['model']
            self.feature_names = data['feature_names']
            self.min_confidence = data.get('threshold', self.min_confidence)
            
            logger.info(f"🤖 Modelo ML carregado: {path}")
            logger.info(f"   Features: {len(self.feature_names)} | Threshold: {self.min_confidence:.0%}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar modelo ML: {e}")
            return False
    
    def is_ready(self) -> bool:
        """Verifica se o modelo está pronto para uso."""
        return self.model is not None and self.feature_names is not None
    
    def extract_features(self, indicators: Dict) -> Optional[np.ndarray]:
        """
        Extrai features dos indicadores para predição.
        
        Args:
            indicators: Dict com indicadores da estratégia
            
        Returns:
            Array numpy com features ou None se faltar dados
        """
        if not self.feature_names:
            return None
        
        try:
            features = []
            for name in self.feature_names:
                value = indicators.get(name, 0)
                
                # Converte booleanos e strings
                if isinstance(value, bool):
                    value = 1 if value else 0
                elif isinstance(value, str):
                    # Converte estruturas de mercado
                    if value == "BULLISH":
                        value = 1
                    elif value == "BEARISH":
                        value = -1
                    else:
                        value = 0
                elif value is None or (isinstance(value, float) and np.isnan(value)):
                    value = 0
                
                features.append(float(value))
            
            return np.array(features).reshape(1, -1)
            
        except Exception as e:
            logger.warning(f"Erro ao extrair features: {e}")
            return None
    
    def predict(self, indicators: Dict, symbol: str = None) -> Tuple[float, bool, str]:
        """
        Prediz probabilidade de sucesso do trade.
        
        Args:
            indicators: Dict com indicadores da estratégia
            symbol: Símbolo do ativo (para modelo universal)
            
        Returns:
            (probabilidade, aprovado, motivo)
        """
        self._stats["predictions"] += 1
        
        # Se modelo não está pronto, aprova tudo (fallback)
        if not self.is_ready():
            return 0.5, True, "Modelo não carregado - usando score padrão"
        
        # Adiciona symbol_id se necessário (para modelo universal)
        if symbol and 'symbol_id' in self.feature_names:
            # Tenta obter mapeamento do modelo
            symbol_map = getattr(self, '_symbol_map', {
                'BTCUSD-T': 0, 'ETHUSD-T': 1, 'SOLUSD-T': 2
            })
            indicators['symbol_id'] = symbol_map.get(symbol, 0)
        
        # Adiciona hora se necessário
        if 'hour' in self.feature_names and 'hour' not in indicators:
            from datetime import datetime
            indicators['hour'] = datetime.now().hour
        
        # Extrai features
        features = self.extract_features(indicators)
        if features is None:
            return 0.5, True, "Features inválidas - usando score padrão"
        
        try:
            # Predição
            proba = self.model.predict_proba(features)[0][1]
            approved = proba >= self.min_confidence
            
            if approved:
                self._stats["approved"] += 1
                reason = f"ML aprovou: {proba:.1%} >= {self.min_confidence:.0%}"
            else:
                self._stats["rejected"] += 1
                reason = f"ML rejeitou: {proba:.1%} < {self.min_confidence:.0%}"
            
            return proba, approved, reason
            
        except Exception as e:
            logger.warning(f"Erro na predição ML: {e}")
            return 0.5, True, f"Erro ML: {e}"
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de uso."""
        total = self._stats["predictions"]
        if total == 0:
            return self._stats
        
        return {
            **self._stats,
            "approval_rate": self._stats["approved"] / total,
            "rejection_rate": self._stats["rejected"] / total
        }
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Retorna importância de cada feature (se disponível)."""
        if not self.is_ready():
            return {}
        
        try:
            importances = self.model.feature_importances_
            return dict(zip(self.feature_names, importances))
        except:
            return {}


# Features padrão que a estratégia já calcula
DEFAULT_FEATURES = [
    # Tendência
    'sma_crossover',      # 1 se SMA9 > SMA21, -1 se <, 0 se =
    'price_vs_sma21',     # 1 se preço > SMA21, -1 se <
    
    # Momentum
    'rsi',                # Valor RSI (0-100)
    'rsi_zone',           # 1=sobrevenda, -1=sobrecompra, 0=neutro
    'macd_signal',        # 1 se MACD > Signal, -1 se <
    'macd_histogram',     # Valor do histograma
    
    # Força da tendência
    'adx',                # Valor ADX (0-100)
    'adx_direction',      # 1 se DI+ > DI-, -1 se <
    
    # Volatilidade
    'atr_percentile',     # Percentil ATR (0-100)
    
    # Smart Money
    'market_structure',   # 1=BULLISH, -1=BEARISH, 0=RANGING
    'bos_type',           # 1=BULLISH, -1=BEARISH, 0=NONE
    'bos_pullback_valid', # 1 se pullback válido, 0 se não
    'in_order_block',     # 1 se em OB, 0 se não
    
    # Volume
    'volume_above_avg',   # 1 se volume > média, 0 se não
]
