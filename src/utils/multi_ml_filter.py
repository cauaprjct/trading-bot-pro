"""
🤖 Multi ML Filter - Gerencia múltiplos modelos ML (um por ativo)
"""
import os
import pickle
import numpy as np
from typing import Dict, Optional, Tuple
from .logger import setup_logger

logger = setup_logger("MultiMLFilter")


class MultiMLFilter:
    """
    Gerencia múltiplos modelos ML, um para cada ativo.
    Carrega automaticamente o modelo correto baseado no símbolo.
    """
    
    def __init__(self, models_dir: str = "models", min_confidence: float = 0.40):
        """
        Args:
            models_dir: Pasta onde estão os modelos .pkl
            min_confidence: Probabilidade mínima padrão (pode ser sobrescrita por ativo)
        """
        self.models_dir = models_dir
        self.min_confidence = min_confidence
        self.models = {}  # {symbol: model_data}
        self._stats = {"predictions": 0, "approved": 0, "rejected": 0, "by_symbol": {}}
        
        # Carrega todos os modelos disponíveis
        self._load_all_models()
    
    def _load_all_models(self):
        """Carrega todos os modelos da pasta."""
        if not os.path.exists(self.models_dir):
            logger.warning(f"⚠️ Pasta de modelos não encontrada: {self.models_dir}")
            return
        
        for filename in os.listdir(self.models_dir):
            if filename.endswith("_lgbm.pkl"):
                # Extrai símbolo do nome do arquivo (ex: gbpusd_lgbm.pkl -> GBPUSD)
                symbol = filename.replace("_lgbm.pkl", "").upper()
                filepath = os.path.join(self.models_dir, filename)
                
                try:
                    with open(filepath, 'rb') as f:
                        data = pickle.load(f)
                    
                    self.models[symbol] = {
                        'model': data['model'],
                        'feature_names': data['feature_names'],
                        'threshold': data.get('threshold', self.min_confidence),
                        'metrics': data.get('metrics', {})
                    }
                    
                    self._stats["by_symbol"][symbol] = {"predictions": 0, "approved": 0, "rejected": 0}
                    
                    logger.info(f"✅ Modelo carregado: {symbol} (threshold: {data.get('threshold', self.min_confidence):.0%})")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao carregar {filename}: {e}")
        
        logger.info(f"🤖 {len(self.models)} modelos ML carregados")
    
    def is_ready(self, symbol: str = None) -> bool:
        """Verifica se há modelo disponível."""
        if symbol:
            return symbol.upper() in self.models
        return len(self.models) > 0
    
    def get_model_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Retorna dados do modelo para o símbolo."""
        return self.models.get(symbol.upper())
    
    def extract_features(self, indicators: Dict, feature_names: list) -> Optional[np.ndarray]:
        """Extrai features dos indicadores."""
        try:
            features = []
            for name in feature_names:
                value = indicators.get(name, 0)
                
                if isinstance(value, bool):
                    value = 1 if value else 0
                elif isinstance(value, str):
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
    
    def predict(self, indicators: Dict, symbol: str) -> Tuple[float, bool, str]:
        """
        Prediz probabilidade de sucesso usando o modelo específico do ativo.
        
        Args:
            indicators: Dict com indicadores da estratégia
            symbol: Símbolo do ativo (ex: "GBPUSD")
            
        Returns:
            (probabilidade, aprovado, motivo)
        """
        self._stats["predictions"] += 1
        symbol_upper = symbol.upper()
        
        # Inicializa stats do símbolo se não existir
        if symbol_upper not in self._stats["by_symbol"]:
            self._stats["by_symbol"][symbol_upper] = {"predictions": 0, "approved": 0, "rejected": 0}
        self._stats["by_symbol"][symbol_upper]["predictions"] += 1
        
        # Busca modelo do ativo
        model_data = self.get_model_for_symbol(symbol_upper)
        
        if not model_data:
            # Fallback: tenta modelo genérico ou aprova
            logger.debug(f"Modelo não encontrado para {symbol_upper} - aprovando")
            return 0.5, True, f"Sem modelo para {symbol_upper}"
        
        model = model_data['model']
        feature_names = model_data['feature_names']
        threshold = model_data['threshold']
        
        # Extrai features
        features = self.extract_features(indicators, feature_names)
        if features is None:
            return 0.5, True, "Features inválidas"
        
        try:
            # Predição
            proba = model.predict_proba(features)[0][1]
            approved = proba >= threshold
            
            if approved:
                self._stats["approved"] += 1
                self._stats["by_symbol"][symbol_upper]["approved"] += 1
                reason = f"ML {symbol_upper}: {proba:.1%} >= {threshold:.0%} ✅"
            else:
                self._stats["rejected"] += 1
                self._stats["by_symbol"][symbol_upper]["rejected"] += 1
                reason = f"ML {symbol_upper}: {proba:.1%} < {threshold:.0%} ❌"
            
            return proba, approved, reason
            
        except Exception as e:
            logger.warning(f"Erro na predição ML para {symbol_upper}: {e}")
            return 0.5, True, f"Erro ML: {e}"
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de uso."""
        total = self._stats["predictions"]
        if total == 0:
            return self._stats
        
        return {
            **self._stats,
            "approval_rate": self._stats["approved"] / total if total > 0 else 0,
            "rejection_rate": self._stats["rejected"] / total if total > 0 else 0
        }
    
    def print_status(self):
        """Imprime status dos modelos."""
        print("\n" + "="*50)
        print("🤖 STATUS DOS MODELOS ML")
        print("="*50)
        
        for symbol, data in self.models.items():
            metrics = data.get('metrics', {})
            threshold = data.get('threshold', 0.4)
            precision = metrics.get('precision', 0)
            
            print(f"  {symbol}: Threshold {threshold:.0%} | Precision {precision:.1%}")
        
        print("="*50 + "\n")
