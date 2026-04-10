"""
🎯 Ensemble ML Filter - Combina LightGBM + LSTM para decisões mais robustas

Estratégia:
- LightGBM: Bom em features tabulares, rápido, precision ~50%
- LSTM: Captura padrões temporais, F1 ~30%
- Ensemble: Combina os dois para reduzir falsos positivos

Modos de votação:
- UNANIMOUS: Ambos devem aprovar (mais conservador)
- MAJORITY: Pelo menos um aprova com alta confiança
- WEIGHTED: Score ponderado baseado nas métricas de cada modelo
"""
import numpy as np
from typing import Dict, Tuple, Optional, List
from .logger import setup_logger
from .multi_ml_filter import MultiMLFilter
from .deep_ml_filter import DeepMLFilter

logger = setup_logger("EnsembleML")


class EnsembleMLFilter:
    """
    Combina múltiplos modelos ML para decisões mais robustas.
    """
    
    def __init__(
        self,
        lgbm_models_dir: str = "models",
        lstm_models_dir: str = "gpu_training_models_production",
        lgbm_weight: float = 0.6,  # LightGBM tem precision melhor
        lstm_weight: float = 0.4,  # LSTM como filtro adicional
        min_ensemble_score: float = 0.45,  # Score mínimo combinado
        voting_mode: str = "WEIGHTED",  # UNANIMOUS, MAJORITY, WEIGHTED
        lstm_min_f1: float = 0.15,  # F1 mínimo para usar LSTM (baixei de 0.20)
    ):
        self.lgbm_weight = lgbm_weight
        self.lstm_weight = lstm_weight
        self.min_ensemble_score = min_ensemble_score
        self.voting_mode = voting_mode
        self.lstm_min_f1 = lstm_min_f1
        
        # Inicializa filtros individuais
        self.lgbm_filter = MultiMLFilter(
            models_dir=lgbm_models_dir,
            min_confidence=0.40
        )
        
        self.lstm_filter = DeepMLFilter(
            models_dir=lstm_models_dir,
            min_confidence=0.50,
            seq_length=20
        )
        
        # Estatísticas
        self._stats = {
            "predictions": 0,
            "approved": 0,
            "rejected": 0,
            "unanimous_approvals": 0,
            "lgbm_only_approvals": 0,
            "lstm_only_approvals": 0,
            "by_symbol": {}
        }
        
        # Cache de correlações entre pares (atualizado para seus 7 pares)
        self.correlations = {
            # Correlações positivas fortes
            ("EURUSD", "GBPUSD"): 0.85,   # Alta correlação positiva
            ("EURUSD", "AUDUSD"): 0.65,   # Correlação moderada
            ("GBPUSD", "AUDUSD"): 0.60,   # Correlação moderada
            
            # Correlações com JPY (geralmente movem juntos contra USD)
            ("USDJPY", "EURJPY"): 0.75,   # Alta correlação
            ("USDJPY", "GBPJPY"): 0.70,   # Alta correlação
            ("EURJPY", "GBPJPY"): 0.80,   # Muito alta correlação
            
            # Correlações negativas (USD de lados opostos)
            ("EURUSD", "USDCAD"): -0.70,  # Correlação negativa
            ("GBPUSD", "USDCAD"): -0.65,  # Correlação negativa
            ("AUDUSD", "USDCAD"): -0.55,  # Correlação moderada negativa
            
            # Correlações cruzadas
            ("EURUSD", "USDJPY"): -0.30,  # Fraca correlação negativa
            ("GBPUSD", "USDJPY"): -0.25,  # Fraca correlação negativa
        }
        
        logger.info(f"🎯 Ensemble ML inicializado: {voting_mode} mode")
        logger.info(f"   Pesos: LightGBM {lgbm_weight:.0%} | LSTM {lstm_weight:.0%}")
        logger.info(f"   Score mínimo: {min_ensemble_score:.0%}")
    
    def is_ready(self, symbol: str = None) -> bool:
        """Verifica se pelo menos um modelo está disponível."""
        lgbm_ready = self.lgbm_filter.is_ready(symbol)
        lstm_ready = self.lstm_filter.is_ready(symbol, min_f1=self.lstm_min_f1)
        return lgbm_ready or lstm_ready
    
    def _get_model_weight(self, symbol: str, model_type: str) -> float:
        """Retorna peso ajustado baseado nas métricas do modelo."""
        if model_type == "lgbm":
            model_data = self.lgbm_filter.get_model_for_symbol(symbol)
            if model_data:
                precision = model_data.get('metrics', {}).get('precision', 0.5)
                # Ajusta peso baseado na precision (0.4-0.6 -> 0.8-1.2x)
                return self.lgbm_weight * (0.8 + precision * 0.8)
        else:  # lstm
            if symbol.upper() in self.lstm_filter.models:
                metrics = self.lstm_filter.models[symbol.upper()].get('metrics', {})
                f1 = metrics.get('f1', 0.25)
                # Ajusta peso baseado no F1 (0.15-0.35 -> 0.6-1.4x)
                return self.lstm_weight * (0.6 + f1 * 4)
        
        return self.lgbm_weight if model_type == "lgbm" else self.lstm_weight
    
    def predict(
        self,
        indicators: Dict,
        symbol: str,
        candles: List[Dict] = None
    ) -> Tuple[float, bool, str, Dict]:
        """
        Prediz usando ensemble de modelos.
        
        Args:
            indicators: Dict com indicadores para LightGBM
            symbol: Símbolo do ativo
            candles: Lista de candles para LSTM
            
        Returns:
            (score_ensemble, aprovado, motivo, detalhes)
        """
        symbol = symbol.upper()
        self._stats["predictions"] += 1
        
        if symbol not in self._stats["by_symbol"]:
            self._stats["by_symbol"][symbol] = {
                "predictions": 0, "approved": 0, "rejected": 0
            }
        self._stats["by_symbol"][symbol]["predictions"] += 1
        
        details = {
            "lgbm_prob": None,
            "lgbm_approved": None,
            "lstm_prob": None,
            "lstm_approved": None,
            "ensemble_score": None,
            "voting_result": None
        }
        
        # 1. Predição LightGBM
        lgbm_prob, lgbm_approved, lgbm_reason = 0.5, True, "N/A"
        lgbm_weight = 0
        
        if self.lgbm_filter.is_ready(symbol):
            lgbm_prob, lgbm_approved, lgbm_reason = self.lgbm_filter.predict(indicators, symbol)
            lgbm_weight = self._get_model_weight(symbol, "lgbm")
            details["lgbm_prob"] = lgbm_prob
            details["lgbm_approved"] = lgbm_approved
        
        # 2. Predição LSTM
        lstm_prob, lstm_approved, lstm_reason = 0.5, True, "N/A"
        lstm_weight = 0
        
        if self.lstm_filter.is_ready(symbol, min_f1=self.lstm_min_f1) and candles:
            lstm_prob, lstm_approved, lstm_reason = self.lstm_filter.predict(symbol, candles)
            lstm_weight = self._get_model_weight(symbol, "lstm")
            details["lstm_prob"] = lstm_prob
            details["lstm_approved"] = lstm_approved
        
        # 3. Calcula score ensemble
        total_weight = lgbm_weight + lstm_weight
        if total_weight > 0:
            ensemble_score = (lgbm_prob * lgbm_weight + lstm_prob * lstm_weight) / total_weight
        else:
            ensemble_score = 0.5
        
        details["ensemble_score"] = ensemble_score
        
        # 4. Decisão baseada no modo de votação
        if self.voting_mode == "UNANIMOUS":
            # Ambos devem aprovar
            approved = lgbm_approved and lstm_approved
            if approved:
                self._stats["unanimous_approvals"] += 1
            voting_result = "UNANIMOUS" if approved else "VETOED"
            
        elif self.voting_mode == "MAJORITY":
            # Pelo menos um aprova com alta confiança (>60%)
            high_conf_lgbm = lgbm_approved and lgbm_prob >= 0.60
            high_conf_lstm = lstm_approved and lstm_prob >= 0.60
            approved = high_conf_lgbm or high_conf_lstm or (lgbm_approved and lstm_approved)
            voting_result = "MAJORITY" if approved else "MINORITY"
            
        else:  # WEIGHTED
            # Score ponderado deve passar do threshold
            approved = ensemble_score >= self.min_ensemble_score
            voting_result = f"SCORE {ensemble_score:.0%}"
        
        details["voting_result"] = voting_result
        
        # 5. Atualiza estatísticas
        if approved:
            self._stats["approved"] += 1
            self._stats["by_symbol"][symbol]["approved"] += 1
            
            if lgbm_approved and lstm_approved:
                self._stats["unanimous_approvals"] += 1
            elif lgbm_approved:
                self._stats["lgbm_only_approvals"] += 1
            else:
                self._stats["lstm_only_approvals"] += 1
        else:
            self._stats["rejected"] += 1
            self._stats["by_symbol"][symbol]["rejected"] += 1
        
        # 6. Monta razão
        reason_parts = []
        if details["lgbm_prob"] is not None:
            emoji = "✅" if lgbm_approved else "❌"
            reason_parts.append(f"LGB:{lgbm_prob:.0%}{emoji}")
        if details["lstm_prob"] is not None:
            emoji = "✅" if lstm_approved else "❌"
            reason_parts.append(f"LSTM:{lstm_prob:.0%}{emoji}")
        
        reason_parts.append(f"→ {ensemble_score:.0%}")
        reason = " | ".join(reason_parts)
        
        if approved:
            reason = f"🎯 Ensemble APROVOU: {reason}"
        else:
            reason = f"🚫 Ensemble REJEITOU: {reason}"
        
        return ensemble_score, approved, reason, details
    
    def get_correlation_signal(self, symbol: str, other_signals: Dict[str, str]) -> Tuple[float, str]:
        """
        Verifica se há divergência com pares correlacionados.
        
        Lógica:
        - Se pares correlacionados positivamente têm sinais iguais → confirma (+0.05)
        - Se pares correlacionados positivamente têm sinais opostos → alerta (0)
        - Se pares correlacionados negativamente têm sinais opostos → confirma (+0.05)
        
        Args:
            symbol: Símbolo atual
            other_signals: {symbol: "BUY"/"SELL"/"HOLD"} dos outros ativos
            
        Returns:
            (adjustment, reason) - adjustment é -0.05 a +0.10
        """
        symbol = symbol.upper()
        adjustment = 0.0
        reasons = []
        confirmations = 0
        
        for (pair1, pair2), corr in self.correlations.items():
            related_symbol = None
            if symbol == pair1:
                related_symbol = pair2
            elif symbol == pair2:
                related_symbol = pair1
            
            if related_symbol and related_symbol in other_signals:
                other_signal = other_signals[related_symbol]
                
                if other_signal == "HOLD":
                    continue
                
                # Correlação positiva: sinais iguais confirmam
                if corr > 0.5:
                    # Se o par correlacionado tem posição, é uma confirmação
                    confirmations += 1
                    reasons.append(f"{related_symbol}:{other_signal}")
                    adjustment += 0.03
                
                # Correlação negativa: sinais opostos confirmam
                elif corr < -0.5:
                    confirmations += 1
                    reasons.append(f"{related_symbol}:{other_signal}(inv)")
                    adjustment += 0.02
        
        # Limita ajuste
        adjustment = min(adjustment, 0.10)
        
        if confirmations > 0:
            reason = f"+{confirmations} corr: {', '.join(reasons[:2])}"
        else:
            reason = ""
        
        return adjustment, reason
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas detalhadas."""
        total = self._stats["predictions"]
        return {
            **self._stats,
            "approval_rate": self._stats["approved"] / total if total > 0 else 0,
            "unanimous_rate": self._stats["unanimous_approvals"] / total if total > 0 else 0,
            "lgbm_stats": self.lgbm_filter.get_stats(),
            "lstm_stats": self.lstm_filter.get_stats()
        }
    
    def print_status(self):
        """Imprime status do ensemble."""
        print("\n" + "="*60)
        print("🎯 STATUS DO ENSEMBLE ML")
        print("="*60)
        print(f"Modo: {self.voting_mode} | Score mínimo: {self.min_ensemble_score:.0%}")
        print(f"Pesos: LightGBM {self.lgbm_weight:.0%} | LSTM {self.lstm_weight:.0%}")
        print()
        
        # Stats LightGBM
        print("📊 LightGBM:")
        for symbol, data in self.lgbm_filter.models.items():
            metrics = data.get('metrics', {})
            precision = metrics.get('precision', 0)
            print(f"   {symbol}: Precision {precision:.1%}")
        
        print()
        
        # Stats LSTM
        print("🧠 LSTM:")
        for symbol, data in self.lstm_filter.models.items():
            metrics = data.get('metrics', {})
            f1 = metrics.get('f1', 0)
            status = "✅" if f1 >= self.lstm_min_f1 else "⚠️"
            print(f"   {symbol}: F1 {f1:.1%} {status}")
        
        print("="*60 + "\n")
