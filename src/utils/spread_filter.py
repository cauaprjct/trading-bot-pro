"""
Spread Filter - Filtro de Spread

Evita trades quando o spread está alto, indicando:
- Baixa liquidez
- Alta volatilidade
- Maior chance de manipulação
- Maior slippage

Para EURUSD:
- Spread normal: 5-15 pontos (0.5-1.5 pips)
- Spread alto: > 30 pontos (> 3 pips)

No MT5, spread é em PONTOS (não pips):
- 1 pip = 10 pontos para pares com 5 casas decimais (EURUSD, GBPUSD)
- 1 pip = 1 ponto para pares com 3 casas decimais (USDJPY)
"""

from collections import deque
from typing import Tuple, Optional
from datetime import datetime
import MetaTrader5 as mt5


class SpreadFilter:
    """
    Filtro de spread para evitar trades em momentos de baixa liquidez.
    """
    
    def __init__(
        self,
        max_spread_multiplier: float = 2.0,  # Bloqueia se spread > 2x média
        max_spread_absolute: int = 30,        # Bloqueia se spread > 30 pontos (3 pips)
        history_size: int = 100,              # Tamanho do histórico para média
        min_samples: int = 10                 # Mínimo de amostras antes de usar média
    ):
        self.max_spread_multiplier = max_spread_multiplier
        self.max_spread_absolute = max_spread_absolute
        self.history_size = history_size
        self.min_samples = min_samples
        
        # Histórico de spreads por símbolo
        self._spread_history: dict[str, deque] = {}
        
    def _get_history(self, symbol: str) -> deque:
        """Retorna ou cria histórico para o símbolo"""
        if symbol not in self._spread_history:
            self._spread_history[symbol] = deque(maxlen=self.history_size)
        return self._spread_history[symbol]
    
    def _get_current_spread(self, symbol: str) -> Optional[int]:
        """Obtém spread atual do MT5 em pontos"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return None
            return symbol_info.spread
        except Exception:
            return None
    
    def _get_spread_in_pips(self, spread_points: int, symbol: str) -> float:
        """Converte spread de pontos para pips"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return spread_points / 10  # Assume 5 casas decimais
            
            # Número de casas decimais
            digits = symbol_info.digits
            
            # Para 5 casas (EURUSD): 1 pip = 10 pontos
            # Para 3 casas (USDJPY): 1 pip = 10 pontos também
            # Para 2 casas: 1 pip = 1 ponto
            if digits >= 4:
                return spread_points / 10
            else:
                return spread_points
        except Exception:
            return spread_points / 10
    
    def update_spread(self, symbol: str) -> int:
        """
        Atualiza histórico com spread atual.
        Retorna o spread atual em pontos.
        """
        spread = self._get_current_spread(symbol)
        if spread is not None:
            history = self._get_history(symbol)
            history.append(spread)
        return spread or 0
    
    def get_average_spread(self, symbol: str) -> float:
        """Retorna spread médio do símbolo"""
        history = self._get_history(symbol)
        if len(history) == 0:
            return 0
        return sum(history) / len(history)
    
    def can_trade(self, symbol: str) -> Tuple[bool, str]:
        """
        Verifica se pode operar baseado no spread atual.
        
        Returns:
            (True, "motivo") se pode operar
            (False, "motivo") se não pode
        """
        # Obtém spread atual
        current_spread = self._get_current_spread(symbol)
        if current_spread is None:
            return True, "⚠️ Spread indisponível"
        
        # Atualiza histórico
        self.update_spread(symbol)
        
        # Converte para pips para exibição
        spread_pips = self._get_spread_in_pips(current_spread, symbol)
        
        # 1. Verifica limite absoluto
        if current_spread > self.max_spread_absolute:
            return False, f"🚫 Spread MUITO ALTO: {spread_pips:.1f} pips (máx: {self._get_spread_in_pips(self.max_spread_absolute, symbol):.1f})"
        
        # 2. Verifica vs média (se tiver amostras suficientes)
        history = self._get_history(symbol)
        if len(history) >= self.min_samples:
            avg_spread = self.get_average_spread(symbol)
            avg_pips = self._get_spread_in_pips(avg_spread, symbol)
            
            if current_spread > avg_spread * self.max_spread_multiplier:
                return False, f"🚫 Spread ALTO: {spread_pips:.1f} pips (média: {avg_pips:.1f}, máx: {avg_pips * self.max_spread_multiplier:.1f})"
        
        # Spread OK
        return True, f"✅ Spread OK: {spread_pips:.1f} pips"
    
    def get_spread_status(self, symbol: str) -> str:
        """Retorna status formatado do spread"""
        current_spread = self._get_current_spread(symbol)
        if current_spread is None:
            return "Spread: N/A"
        
        spread_pips = self._get_spread_in_pips(current_spread, symbol)
        history = self._get_history(symbol)
        
        if len(history) >= self.min_samples:
            avg_spread = self.get_average_spread(symbol)
            avg_pips = self._get_spread_in_pips(avg_spread, symbol)
            
            # Classifica o spread
            ratio = current_spread / avg_spread if avg_spread > 0 else 1
            if ratio <= 1.2:
                status = "🟢 Normal"
            elif ratio <= 1.5:
                status = "🟡 Elevado"
            elif ratio <= 2.0:
                status = "🟠 Alto"
            else:
                status = "🔴 Muito Alto"
            
            return f"{status} | Spread: {spread_pips:.1f} pips (média: {avg_pips:.1f})"
        else:
            samples = len(history)
            return f"⏳ Coletando dados ({samples}/{self.min_samples}) | Spread: {spread_pips:.1f} pips"
    
    def get_stats(self, symbol: str) -> dict:
        """Retorna estatísticas do spread"""
        history = self._get_history(symbol)
        current = self._get_current_spread(symbol) or 0
        
        if len(history) == 0:
            return {
                "current": current,
                "average": 0,
                "min": 0,
                "max": 0,
                "samples": 0
            }
        
        return {
            "current": current,
            "average": sum(history) / len(history),
            "min": min(history),
            "max": max(history),
            "samples": len(history)
        }


# Função de conveniência
def create_spread_filter(
    max_spread_multiplier: float = 2.0,
    max_spread_absolute: int = 30,
    history_size: int = 100
) -> SpreadFilter:
    """Cria um SpreadFilter com configurações padrão ou customizadas"""
    return SpreadFilter(
        max_spread_multiplier=max_spread_multiplier,
        max_spread_absolute=max_spread_absolute,
        history_size=history_size
    )
