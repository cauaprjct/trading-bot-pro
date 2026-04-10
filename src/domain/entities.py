from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

class SignalType(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0

@dataclass
class TradeSignal:
    type: SignalType
    price: float
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = datetime.now()

@dataclass
class Position:
    ticket: int
    symbol: str
    type: SignalType
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    comment: str
    time: float = 0.0  # Timestamp de abertura da posição

    @property
    def is_buy(self):
        return self.type == SignalType.BUY
