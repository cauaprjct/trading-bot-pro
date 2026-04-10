from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Optional
from .entities import TradeSignal, SignalType, Position

class IExchangeAdapter(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def get_data(self, symbol: str, timeframe, n_bars: int) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_tick_info(self, symbol: str) -> dict:
        """Retorna informações de preço atual (bid/ask) e especificações do contrato"""
        pass

    @abstractmethod
    def get_open_positions(self, symbol: str = None) -> List[Position]:
        pass

    @abstractmethod
    def get_account_info(self) -> dict:
        pass

    @abstractmethod
    def execute_order(self, symbol: str, signal_type: SignalType, volume: float, sl: float = 0.0, tp: float = 0.0, comment: str = "") -> bool:
        pass
    
    @abstractmethod
    def close_position(self, ticket: int) -> bool:
        pass
        
    @abstractmethod
    def close_all_positions(self, symbol: str) -> bool:
        pass

class IStrategy(ABC):
    @abstractmethod
    def analyze(self, data: pd.DataFrame, open_positions: List[Position]) -> TradeSignal:
        pass
