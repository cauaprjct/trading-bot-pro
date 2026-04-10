from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TradeRecord:
    """Registro de um trade fechado"""
    ticket: int
    symbol: str
    type: str  # "BUY" ou "SELL"
    volume: float
    entry_price: float
    exit_price: float
    pnl: float
    entry_time: str
    exit_time: str
    duration_seconds: int = 0

class PerformanceMetrics:
    """Calcula métricas de performance de trading"""
    
    def __init__(self, trades: List[Dict[str, Any]], initial_balance: float = 100000.0):
        self.trades = trades
        self.initial_balance = initial_balance
        self._calculate_all()
    
    def _calculate_all(self):
        """Calcula todas as métricas"""
        if not self.trades:
            self._set_empty_metrics()
            return
        
        # Separa wins e losses
        wins = [t for t in self.trades if t.get('pnl', 0) > 0]
        losses = [t for t in self.trades if t.get('pnl', 0) < 0]
        breakeven = [t for t in self.trades if t.get('pnl', 0) == 0]
        
        # Valores de P&L
        all_pnl = [t.get('pnl', 0) for t in self.trades]
        win_pnl = [t.get('pnl', 0) for t in wins]
        loss_pnl = [t.get('pnl', 0) for t in losses]
        
        # Métricas básicas
        self.total_trades = len(self.trades)
        self.winning_trades = len(wins)
        self.losing_trades = len(losses)
        self.breakeven_trades = len(breakeven)
        
        # Win Rate
        self.win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        # P&L
        self.total_pnl = sum(all_pnl)
        self.gross_profit = sum(win_pnl) if win_pnl else 0
        self.gross_loss = abs(sum(loss_pnl)) if loss_pnl else 0
        
        # Profit Factor
        self.profit_factor = (self.gross_profit / self.gross_loss) if self.gross_loss > 0 else float('inf')
        
        # Médias
        self.avg_win = (sum(win_pnl) / len(win_pnl)) if win_pnl else 0
        self.avg_loss = (sum(loss_pnl) / len(loss_pnl)) if loss_pnl else 0
        self.avg_trade = (sum(all_pnl) / len(all_pnl)) if all_pnl else 0
        
        # Risk/Reward Ratio (média de ganho / média de perda)
        self.risk_reward = (self.avg_win / abs(self.avg_loss)) if self.avg_loss != 0 else float('inf')
        
        # Maior ganho e maior perda
        self.largest_win = max(win_pnl) if win_pnl else 0
        self.largest_loss = min(loss_pnl) if loss_pnl else 0
        
        # Expectancy (Expectativa matemática por trade)
        # E = (Win% * Avg Win) - (Loss% * Avg Loss)
        win_prob = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        loss_prob = self.losing_trades / self.total_trades if self.total_trades > 0 else 0
        self.expectancy = (win_prob * self.avg_win) + (loss_prob * self.avg_loss)
        
        # Drawdown
        self._calculate_drawdown(all_pnl)
        
        # Streaks
        self._calculate_streaks()
        
        # Return on Investment
        self.roi = (self.total_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0
    
    def _calculate_drawdown(self, pnl_list: List[float]):
        """Calcula max drawdown"""
        if not pnl_list:
            self.max_drawdown = 0
            self.max_drawdown_pct = 0
            return
        
        # Simula equity curve
        equity = self.initial_balance
        peak = equity
        max_dd = 0
        max_dd_pct = 0
        
        for pnl in pnl_list:
            equity += pnl
            if equity > peak:
                peak = equity
            
            dd = peak - equity
            dd_pct = (dd / peak * 100) if peak > 0 else 0
            
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        
        self.max_drawdown = max_dd
        self.max_drawdown_pct = max_dd_pct
        self.final_equity = equity
    
    def _calculate_streaks(self):
        """Calcula sequências de wins/losses"""
        if not self.trades:
            self.current_streak = 0
            self.max_win_streak = 0
            self.max_loss_streak = 0
            return
        
        current = 0
        max_win = 0
        max_loss = 0
        
        for t in self.trades:
            pnl = t.get('pnl', 0)
            if pnl > 0:
                if current >= 0:
                    current += 1
                else:
                    current = 1
                max_win = max(max_win, current)
            elif pnl < 0:
                if current <= 0:
                    current -= 1
                else:
                    current = -1
                max_loss = max(max_loss, abs(current))
            # breakeven não altera streak
        
        self.current_streak = current
        self.max_win_streak = max_win
        self.max_loss_streak = max_loss
    
    def _set_empty_metrics(self):
        """Define métricas vazias quando não há trades"""
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.breakeven_trades = 0
        self.win_rate = 0
        self.total_pnl = 0
        self.gross_profit = 0
        self.gross_loss = 0
        self.profit_factor = 0
        self.avg_win = 0
        self.avg_loss = 0
        self.avg_trade = 0
        self.risk_reward = 0
        self.largest_win = 0
        self.largest_loss = 0
        self.expectancy = 0
        self.max_drawdown = 0
        self.max_drawdown_pct = 0
        self.final_equity = self.initial_balance
        self.current_streak = 0
        self.max_win_streak = 0
        self.max_loss_streak = 0
        self.roi = 0
    
    def get_summary(self) -> str:
        """Retorna resumo de uma linha"""
        streak_icon = "🔥" if self.current_streak > 0 else ("❄️" if self.current_streak < 0 else "➖")
        return f"📊 {self.total_trades} trades | WR: {self.win_rate:.0f}% | PF: {self.profit_factor:.2f} | P&L: ${self.total_pnl:.2f} {streak_icon}{abs(self.current_streak)}"
    
    def get_full_report(self) -> str:
        """Retorna relatório completo formatado"""
        pf_str = f"{self.profit_factor:.2f}" if self.profit_factor != float('inf') else "∞"
        rr_str = f"{self.risk_reward:.2f}" if self.risk_reward != float('inf') else "∞"
        
        streak_str = f"+{self.current_streak}" if self.current_streak > 0 else str(self.current_streak)
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    📊 RELATÓRIO DE PERFORMANCE               ║
╠══════════════════════════════════════════════════════════════╣
║  RESUMO GERAL                                                ║
║  ├─ Total de Trades: {self.total_trades:<8}                          ║
║  ├─ Wins/Losses/BE:  {self.winning_trades}/{self.losing_trades}/{self.breakeven_trades:<20}              ║
║  ├─ Win Rate:        {self.win_rate:.1f}%{'':<25}             ║
║  └─ ROI:             {self.roi:.2f}%{'':<24}             ║
╠══════════════════════════════════════════════════════════════╣
║  RESULTADOS FINANCEIROS                                      ║
║  ├─ P&L Total:       ${self.total_pnl:>10.2f}                        ║
║  ├─ Lucro Bruto:     ${self.gross_profit:>10.2f}                        ║
║  ├─ Perda Bruta:     ${self.gross_loss:>10.2f}                        ║
║  ├─ Maior Ganho:     ${self.largest_win:>10.2f}                        ║
║  └─ Maior Perda:     ${self.largest_loss:>10.2f}                        ║
╠══════════════════════════════════════════════════════════════╣
║  MÉTRICAS DE QUALIDADE                                       ║
║  ├─ Profit Factor:   {pf_str:<10}                              ║
║  ├─ Risk/Reward:     {rr_str:<10}                              ║
║  ├─ Expectancy:      ${self.expectancy:>10.2f}                        ║
║  ├─ Média por Win:   ${self.avg_win:>10.2f}                        ║
║  └─ Média por Loss:  ${self.avg_loss:>10.2f}                        ║
╠══════════════════════════════════════════════════════════════╣
║  RISCO                                                       ║
║  ├─ Max Drawdown:    ${self.max_drawdown:>10.2f} ({self.max_drawdown_pct:.1f}%)              ║
║  ├─ Equity Final:    ${self.final_equity:>10.2f}                        ║
║  └─ Streak Atual:    {streak_str:<10} (Max W:{self.max_win_streak} L:{self.max_loss_streak})       ║
╚══════════════════════════════════════════════════════════════╝
"""
        return report
