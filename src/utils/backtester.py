import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from ..domain.entities import SignalType, TradeSignal
from .performance_metrics import PerformanceMetrics
from .logger import setup_logger

logger = setup_logger("Backtester")

@dataclass
class BacktestTrade:
    """Representa um trade no backtest"""
    entry_time: datetime
    exit_time: datetime = None
    type: str = ""  # "BUY" ou "SELL"
    entry_price: float = 0.0
    exit_price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    volume: float = 1.0
    pnl: float = 0.0
    exit_reason: str = ""  # "TP", "SL", "SIGNAL", "END"
    
    def to_dict(self) -> dict:
        return {
            "entry_time": str(self.entry_time),
            "exit_time": str(self.exit_time),
            "type": self.type,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "sl": self.sl,
            "tp": self.tp,
            "volume": self.volume,
            "pnl": self.pnl,
            "exit_reason": self.exit_reason
        }

@dataclass
class BacktestResult:
    """Resultado do backtest"""
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    initial_balance: float = 100000.0
    final_balance: float = 0.0
    total_bars: int = 0
    start_date: datetime = None
    end_date: datetime = None
    
    def get_metrics(self) -> PerformanceMetrics:
        trades_dict = [t.to_dict() for t in self.trades]
        return PerformanceMetrics(trades_dict, self.initial_balance)

class Backtester:
    """Engine de backtesting para estratégias de trading"""
    
    def __init__(self, strategy, initial_balance: float = 100000.0, 
                 risk_per_trade: float = 1.0, max_lot: float = 1.0,
                 commission_per_lot: float = 0.0, spread_points: float = 0.0):
        """
        Args:
            strategy: Instância da estratégia (TrendFollowingStrategy)
            initial_balance: Capital inicial
            risk_per_trade: Risco % por trade
            max_lot: Lote máximo
            commission_per_lot: Comissão por lote
            spread_points: Spread em pontos
        """
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.max_lot = max_lot
        self.commission = commission_per_lot
        self.spread = spread_points
        
        # Estado do backtest
        self.balance = initial_balance
        self.equity_curve = [initial_balance]
        self.trades: List[BacktestTrade] = []
        self.current_position: Optional[BacktestTrade] = None
    
    def _calculate_lot_size(self, sl_distance: float, tick_value: float = 10.0) -> float:
        """Calcula tamanho do lote baseado no risco"""
        if sl_distance <= 0:
            return 0.01
        
        risk_amount = self.balance * (self.risk_per_trade / 100)
        lot_size = risk_amount / (sl_distance * tick_value * 10000)  # Ajuste para forex
        lot_size = min(lot_size, self.max_lot)
        lot_size = max(lot_size, 0.01)
        return round(lot_size, 2)
    
    def _calculate_pnl(self, trade: BacktestTrade) -> float:
        """Calcula P&L de um trade"""
        if trade.type == "BUY":
            pips = (trade.exit_price - trade.entry_price) * 10000
        else:  # SELL
            pips = (trade.entry_price - trade.exit_price) * 10000
        
        # P&L = pips * valor_pip * lotes - comissão
        pnl = pips * 10 * trade.volume - (self.commission * trade.volume * 2)
        return round(pnl, 2)
    
    def _check_sl_tp(self, trade: BacktestTrade, high: float, low: float) -> tuple:
        """Verifica se SL ou TP foi atingido. Retorna (hit, price, reason)"""
        if trade.type == "BUY":
            # Para BUY: SL é abaixo, TP é acima
            if low <= trade.sl:
                return (True, trade.sl, "SL")
            if high >= trade.tp:
                return (True, trade.tp, "TP")
        else:  # SELL
            # Para SELL: SL é acima, TP é abaixo
            if high >= trade.sl:
                return (True, trade.sl, "SL")
            if low <= trade.tp:
                return (True, trade.tp, "TP")
        
        return (False, 0, "")
    
    def run(self, df: pd.DataFrame, symbol: str = "EURUSD") -> BacktestResult:
        """
        Executa o backtest nos dados fornecidos.
        
        Args:
            df: DataFrame com colunas: time, open, high, low, close, tick_volume
            symbol: Símbolo para log
        
        Returns:
            BacktestResult com trades e métricas
        """
        logger.info(f"🔬 Iniciando backtest: {symbol}")
        logger.info(f"📊 Período: {df['time'].iloc[0]} até {df['time'].iloc[-1]}")
        logger.info(f"📈 Total de barras: {len(df)}")
        
        self.balance = self.initial_balance
        self.equity_curve = [self.initial_balance]
        self.trades = []
        self.current_position = None
        
        # Precisa de dados suficientes para os indicadores
        min_bars = max(self.strategy.slow_period, self.strategy.atr_period) + 10
        
        for i in range(min_bars, len(df)):
            # Dados até o momento atual (sem olhar o futuro)
            current_data = df.iloc[:i+1].copy()
            current_bar = df.iloc[i]
            current_time = current_bar['time']
            
            # Se tem posição aberta, verifica SL/TP
            if self.current_position:
                hit, price, reason = self._check_sl_tp(
                    self.current_position,
                    current_bar['high'],
                    current_bar['low']
                )
                
                if hit:
                    self._close_position(price, current_time, reason)
            
            # Se não tem posição, analisa estratégia
            if not self.current_position:
                # Simula lista vazia de posições abertas
                signal = self.strategy.analyze(current_data, [])
                
                if signal.type != SignalType.HOLD:
                    self._open_position(signal, current_time)
            
            # Atualiza equity curve
            self.equity_curve.append(self.balance)
        
        # Fecha posição aberta no final
        if self.current_position:
            final_price = df.iloc[-1]['close']
            self._close_position(final_price, df.iloc[-1]['time'], "END")
        
        # Monta resultado
        result = BacktestResult(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_balance=self.initial_balance,
            final_balance=self.balance,
            total_bars=len(df),
            start_date=df['time'].iloc[0],
            end_date=df['time'].iloc[-1]
        )
        
        logger.info(f"✅ Backtest concluído: {len(self.trades)} trades")
        return result
    
    def _open_position(self, signal: TradeSignal, time: datetime):
        """Abre uma posição"""
        sl_distance = abs(signal.price - signal.sl)
        volume = self._calculate_lot_size(sl_distance)
        
        # Aplica spread na entrada
        entry_price = signal.price
        if signal.type == SignalType.BUY:
            entry_price += self.spread / 10000
        else:
            entry_price -= self.spread / 10000
        
        self.current_position = BacktestTrade(
            entry_time=time,
            type=signal.type.name,
            entry_price=entry_price,
            sl=signal.sl,
            tp=signal.tp,
            volume=volume
        )
    
    def _close_position(self, price: float, time: datetime, reason: str):
        """Fecha a posição atual"""
        if not self.current_position:
            return
        
        self.current_position.exit_time = time
        self.current_position.exit_price = price
        self.current_position.exit_reason = reason
        self.current_position.pnl = self._calculate_pnl(self.current_position)
        
        # Atualiza saldo
        self.balance += self.current_position.pnl
        
        # Salva trade
        self.trades.append(self.current_position)
        self.current_position = None
    
    def print_report(self, result: BacktestResult):
        """Imprime relatório do backtest"""
        metrics = result.get_metrics()
        
        print("\n" + "="*60)
        print("           🔬 RELATÓRIO DE BACKTEST")
        print("="*60)
        print(f"Período: {result.start_date} até {result.end_date}")
        print(f"Total de barras: {result.total_bars}")
        print(f"Capital inicial: ${result.initial_balance:,.2f}")
        print(f"Capital final: ${result.final_balance:,.2f}")
        print(f"Retorno: {((result.final_balance/result.initial_balance)-1)*100:.2f}%")
        print("="*60)
        print(metrics.get_full_report())
        
        # Lista últimos trades
        if result.trades:
            print("\n📋 Últimos 10 trades:")
            print("-"*60)
            for trade in result.trades[-10:]:
                emoji = "✅" if trade.pnl >= 0 else "❌"
                print(f"{emoji} {trade.type} | Entry: {trade.entry_price:.5f} | "
                      f"Exit: {trade.exit_price:.5f} | P&L: ${trade.pnl:.2f} | {trade.exit_reason}")
