import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from .logger import setup_logger
from .performance_metrics import PerformanceMetrics

logger = setup_logger("StateManager")

class StateManager:
    """Gerencia persistência de estado do bot em arquivo JSON"""
    
    def __init__(self, state_file: str = "bot_state.json", initial_balance: float = 100000.0):
        self.state_file = state_file
        self.initial_balance = initial_balance
        self.state: Dict[str, Any] = self._default_state()
        self._load_state()
    
    def _default_state(self) -> Dict[str, Any]:
        """Retorna estado padrão/inicial"""
        return {
            "last_updated": None,
            "open_positions": [],  # Lista de tickets
            "last_trade_time": 0,
            "last_trade_ticket": None,
            "trades_history": [],  # Histórico de trades fechados
            "daily_stats": {
                "date": str(date.today()),
                "trades_count": 0,
                "wins": 0,
                "losses": 0,
                "pnl": 0.0
            }
        }
    
    def _load_state(self) -> bool:
        """Carrega estado do arquivo"""
        if not os.path.exists(self.state_file):
            logger.info(f"Arquivo de estado não encontrado. Criando novo: {self.state_file}")
            self._save_state()
            return False
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            
            # Valida e mescla com estado padrão
            default = self._default_state()
            for key in default:
                if key not in loaded:
                    loaded[key] = default[key]
            
            self.state = loaded
            
            # Verifica se é um novo dia - reseta stats
            if self.state["daily_stats"]["date"] != str(date.today()):
                logger.info("🌅 Novo dia detectado! Resetando estatísticas diárias.")
                self._reset_daily_stats()
            
            logger.info(f"📂 Estado carregado: {len(self.state['open_positions'])} posições conhecidas")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao ler arquivo de estado: {e}. Criando novo.")
            self.state = self._default_state()
            self._save_state()
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar estado: {e}")
            return False
    
    def _save_state(self) -> bool:
        """Salva estado no arquivo"""
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            
            # Backup do arquivo anterior
            if os.path.exists(self.state_file):
                backup_file = f"{self.state_file}.bak"
                try:
                    os.replace(self.state_file, backup_file)
                except:
                    pass
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
            return False
    
    def _reset_daily_stats(self):
        """Reseta estatísticas diárias"""
        self.state["daily_stats"] = {
            "date": str(date.today()),
            "trades_count": 0,
            "wins": 0,
            "losses": 0,
            "pnl": 0.0
        }
        self._save_state()
    
    # --- Métodos Públicos ---
    
    def get_last_trade_time(self) -> float:
        """Retorna timestamp da última operação"""
        return self.state.get("last_trade_time", 0)
    
    def set_last_trade_time(self, timestamp: float):
        """Atualiza timestamp da última operação"""
        self.state["last_trade_time"] = timestamp
        self._save_state()
    
    def add_position(self, ticket: int):
        """Registra nova posição aberta"""
        if ticket not in self.state["open_positions"]:
            self.state["open_positions"].append(ticket)
            self.state["last_trade_ticket"] = ticket
            self.state["daily_stats"]["trades_count"] += 1
            self._save_state()
            logger.info(f"📝 Posição {ticket} registrada no estado")
    
    def remove_position(self, ticket: int, pnl: float = 0.0):
        """Remove posição fechada e atualiza stats"""
        if ticket in self.state["open_positions"]:
            self.state["open_positions"].remove(ticket)
            
            # Atualiza estatísticas
            self.state["daily_stats"]["pnl"] += pnl
            if pnl >= 0:
                self.state["daily_stats"]["wins"] += 1
            else:
                self.state["daily_stats"]["losses"] += 1
            
            self._save_state()
            logger.info(f"📝 Posição {ticket} removida do estado (P&L: {pnl:.2f})")
    
    def is_position_known(self, ticket: int) -> bool:
        """Verifica se posição já é conhecida pelo bot"""
        return ticket in self.state["open_positions"]
    
    def get_known_positions(self) -> List[int]:
        """Retorna lista de tickets conhecidos"""
        return self.state["open_positions"].copy()
    
    def sync_positions(self, current_tickets: List[int]) -> List[int]:
        """Sincroniza estado com posições reais do MT5. Retorna tickets fechados."""
        known = set(self.state["open_positions"])
        current = set(current_tickets)
        
        # Posições que fecharam (estavam no estado mas não estão mais no MT5)
        closed = known - current
        for ticket in closed:
            logger.info(f"🔄 Posição {ticket} foi fechada")
            self.state["open_positions"].remove(ticket)
        
        # Posições novas (estão no MT5 mas não no estado - abertas manualmente?)
        new = current - known
        for ticket in new:
            logger.info(f"🔄 Posição {ticket} detectada (aberta externamente?)")
            self.state["open_positions"].append(ticket)
        
        if closed or new:
            self._save_state()
        
        return list(closed)  # Retorna tickets que foram fechados
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do dia"""
        stats = self.state["daily_stats"].copy()
        total = stats["wins"] + stats["losses"]
        stats["win_rate"] = (stats["wins"] / total * 100) if total > 0 else 0
        return stats
    
    def check_daily_loss_limit(self, initial_capital: float, max_loss_percent: float) -> Tuple[bool, float]:
        """
        Verifica se atingiu limite de perda diária.
        
        Returns:
            (limite_atingido, perda_atual_percent)
        """
        stats = self.get_daily_stats()
        daily_pnl = stats.get("pnl", 0)
        
        if daily_pnl >= 0:
            return (False, 0.0)
        
        loss_percent = abs(daily_pnl) / initial_capital * 100
        limit_hit = loss_percent >= max_loss_percent
        
        return (limit_hit, loss_percent)
    
    def check_daily_trade_limit(self, max_trades: int) -> bool:
        """Verifica se atingiu limite de trades diários"""
        stats = self.get_daily_stats()
        return stats.get("trades_count", 0) >= max_trades
    
    def get_stats_summary(self) -> str:
        """Retorna resumo formatado das estatísticas"""
        s = self.get_daily_stats()
        return f"📊 Trades: {s['trades_count']} | W/L: {s['wins']}/{s['losses']} ({s['win_rate']:.0f}%) | P&L: ${s['pnl']:.2f}"
    
    # --- Métodos de Histórico e Métricas ---
    
    def record_trade(self, trade_data: Dict[str, Any]):
        """Registra um trade fechado no histórico"""
        trade_data["recorded_at"] = datetime.now().isoformat()
        self.state["trades_history"].append(trade_data)
        
        # Atualiza estatísticas diárias
        pnl = trade_data.get('pnl', 0)
        self.state["daily_stats"]["trades_count"] += 1
        self.state["daily_stats"]["pnl"] += pnl
        
        if pnl > 0:
            self.state["daily_stats"]["wins"] += 1
        elif pnl < 0:
            self.state["daily_stats"]["losses"] += 1
        # Se pnl == 0, é breakeven, não conta como win nem loss
        
        # Limita histórico a 1000 trades (evita arquivo muito grande)
        if len(self.state["trades_history"]) > 1000:
            self.state["trades_history"] = self.state["trades_history"][-1000:]
        
        self._save_state()
        
        result = "WIN ✅" if pnl > 0 else ("LOSS ❌" if pnl < 0 else "BREAKEVEN ➖")
        logger.info(f"📝 Trade registrado: {result} | P&L: ${pnl:.2f}")
    
    def get_trades_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """Retorna histórico de trades"""
        history = self.state.get("trades_history", [])
        if limit:
            return history[-limit:]
        return history
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Retorna objeto com métricas de performance calculadas"""
        return PerformanceMetrics(self.state.get("trades_history", []), self.initial_balance)
    
    def get_performance_summary(self) -> str:
        """Retorna resumo de performance de uma linha"""
        metrics = self.get_performance_metrics()
        return metrics.get_summary()
    
    def get_performance_report(self) -> str:
        """Retorna relatório completo de performance"""
        metrics = self.get_performance_metrics()
        return metrics.get_full_report()
    
    def clear_history(self):
        """Limpa histórico de trades (use com cuidado!)"""
        self.state["trades_history"] = []
        self._save_state()
        logger.warning("⚠️ Histórico de trades limpo!")
