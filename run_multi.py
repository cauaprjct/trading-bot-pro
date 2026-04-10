#!/usr/bin/env python3
"""
🚀 RUNNER MULTI-ATIVO - Opera múltiplos ativos simultaneamente

Uso: python run_multi.py

Este script:
1. Detecta automaticamente quais ativos estão disponíveis
2. Opera Forex durante a semana
3. Opera Crypto 24/7 (incluindo fins de semana)
4. Gerencia risco total entre todos os ativos
5. 🆕 Usa Ensemble ML (LightGBM + LSTM) para decisões mais robustas
"""

import sys
import os

# Adiciona path do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Substitui config pelo config_multi
import config_multi as config
sys.modules['config'] = config

import time
import threading
from datetime import datetime
import pytz
import numpy as np

from src.infrastructure.mt5_adapter import MT5Adapter
from src.strategies.hybrid_strategy import HybridStrategy
from src.strategies.risk_manager import RiskManager
from src.domain.entities import SignalType
from src.utils.logger import setup_logger
from src.utils.state_manager import StateManager
from src.utils.telegram_notifier import TelegramNotifier
from src.utils.spread_filter import SpreadFilter
from src.utils.multi_ml_filter import MultiMLFilter
from src.utils.deep_ml_filter import DeepMLFilter
from src.utils.ensemble_ml_filter import EnsembleMLFilter  # 🆕 Ensemble

# Som de notificação (Windows)
try:
    import winsound
    SOUND_ENABLED = True
except ImportError:
    SOUND_ENABLED = False

logger = setup_logger("MultiAsset")

def play_sound(sound_type: str):
    """Toca som de notificação."""
    if not SOUND_ENABLED:
        return
    try:
        if sound_type == 'entry':
            winsound.Beep(800, 200)
            winsound.Beep(1000, 200)
        elif sound_type == 'win':
            winsound.Beep(523, 150)
            winsound.Beep(659, 150)
            winsound.Beep(784, 150)
            winsound.Beep(1047, 300)
        elif sound_type == 'loss':
            winsound.Beep(300, 500)
    except Exception:
        pass

class MultiAssetBot:
    """Bot que opera múltiplos ativos simultaneamente."""
    
    def __init__(self):
        self.adapter = None
        self.strategies = {}      # {symbol: strategy}
        self.risk_managers = {}   # {symbol: risk_manager}
        self.spread_filters = {}  # {symbol: spread_filter}
        self.state_manager = None
        self.telegram = None
        self.ensemble_filter = None  # 🆕 EnsembleMLFilter (LightGBM + LSTM)
        self.ml_filter = None     # MultiMLFilter (fallback)
        self.deep_ml_filter = None  # DeepMLFilter (fallback)
        
        # Controle
        self.running = False
        self.last_trade_time = {}  # {symbol: timestamp}
        self.positions_by_asset = {}  # {symbol: [positions]}
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self._last_signal_log = {}  # {symbol: (signal_type, reason, timestamp)} - evita logs repetidos
        self._last_analysis_log = {}  # {symbol: timestamp} - controla log de análise detalhada
        
        # Spinner para feedback visual
        self.spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.cycle_count = 0
        
    def initialize(self) -> bool:
        """Inicializa todos os componentes."""
        logger.info("="*60)
        logger.info("🚀 INICIANDO BOT MULTI-ATIVO v2.0")
        logger.info("="*60)
        
        # 1. Conecta ao MT5
        self.adapter = MT5Adapter(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER
        )
        
        if not self.adapter.connect():
            logger.critical("❌ Falha ao conectar ao MT5!")
            return False
        
        logger.info("✅ Conectado ao MT5")
        
        # 2. Inicializa state manager
        self.state_manager = StateManager(config.STATE_FILE)
        
        # 3. Inicializa Telegram
        self.telegram = TelegramNotifier(
            bot_token=getattr(config, 'TELEGRAM_BOT_TOKEN', ''),
            chat_id=getattr(config, 'TELEGRAM_CHAT_ID', '')
        )
        
        # 4. 🆕 Inicializa Ensemble ML Filter (combina LightGBM + LSTM)
        if getattr(config, 'USE_ENSEMBLE_ML', True):
            self.ensemble_filter = EnsembleMLFilter(
                lgbm_models_dir="models",
                lstm_models_dir="gpu_training_models_production",
                lgbm_weight=getattr(config, 'ENSEMBLE_LGBM_WEIGHT', 0.6),
                lstm_weight=getattr(config, 'ENSEMBLE_LSTM_WEIGHT', 0.4),
                min_ensemble_score=getattr(config, 'ENSEMBLE_MIN_SCORE', 0.42),
                voting_mode=getattr(config, 'ENSEMBLE_VOTING_MODE', 'WEIGHTED'),
                lstm_min_f1=getattr(config, 'DEEP_ML_MIN_F1_TO_USE', 0.15)
            )
            self.ensemble_filter.print_status()
        
        # Fallback: Filtros individuais (se ensemble desabilitado)
        elif getattr(config, 'USE_ML_FILTER', False):
            self.ml_filter = MultiMLFilter(
                models_dir="models",
                min_confidence=getattr(config, 'ML_CONFIDENCE_THRESHOLD', 0.40)
            )
            self.ml_filter.print_status()
        
        # 5. Inicializa estratégias para cada ativo
        active_assets = config.get_active_assets()
        logger.info(f"📊 Ativos ativos: {active_assets}")
        
        for symbol in config.MULTI_ASSETS.keys():
            asset_config = config.get_asset_config(symbol)
            
            # Cria config temporário para o ativo
            temp_config = self._create_asset_config(symbol, asset_config)
            
            # Estratégia
            self.strategies[symbol] = HybridStrategy(temp_config, self.adapter)
            
            # Risk Manager
            self.risk_managers[symbol] = RiskManager(self.adapter, temp_config)
            
            # Spread Filter
            self.spread_filters[symbol] = SpreadFilter(
                max_spread_multiplier=2.0,
                max_spread_absolute=asset_config.get("spread_max", 30),
                history_size=100
            )
            
            self.last_trade_time[symbol] = 0
            self.positions_by_asset[symbol] = []
            
            logger.info(f"  {asset_config['emoji']} {symbol}: Inicializado")
        
        # 🆕 Sincroniza posições existentes no MT5 ao iniciar
        self._sync_initial_positions()
        
        # Notifica início
        self.telegram.send_custom(
            f"🚀 *BOT MULTI-ATIVO INICIADO*\n\n"
            f"📊 Ativos: {len(config.MULTI_ASSETS)}\n"
            f"💰 Capital: R${config.SIMULATED_CAPITAL_BRL:.0f}\n"
            f"🎯 Ativos ativos agora: {', '.join(active_assets)}"
        )
        
        return True
    
    def _create_asset_config(self, symbol: str, asset_config: dict):
        """Cria objeto de config para um ativo específico."""
        class AssetConfig:
            pass
        
        cfg = AssetConfig()
        
        # Copia configs globais
        for attr in dir(config):
            if not attr.startswith('_') and attr.isupper():
                setattr(cfg, attr, getattr(config, attr))
        
        # Sobrescreve com configs do ativo
        cfg.SYMBOL = symbol
        cfg.VOLUME = asset_config.get("volume", 0.05)
        cfg.MAX_LOT_SIZE = asset_config.get("max_volume", 0.10)
        cfg.ATR_MULTIPLIER_SL = asset_config.get("atr_mult_sl", 1.5)
        cfg.ATR_MULTIPLIER_TP = asset_config.get("atr_mult_tp", 3.0)
        cfg.MIN_SIGNAL_SCORE = asset_config.get("min_score", 3)
        cfg.TRAILING_TRIGGER_POINTS = asset_config.get("trailing_trigger", 0.00050)
        cfg.TRAILING_STEP_POINTS = asset_config.get("trailing_step", 0.00030)
        cfg.MAX_SPREAD_ABSOLUTE = asset_config.get("spread_max", 30)
        
        return cfg
    
    def _get_total_positions(self) -> int:
        """Retorna total de posições abertas em todos os ativos."""
        total = 0
        for symbol in config.MULTI_ASSETS.keys():
            positions = self.adapter.get_open_positions(symbol)
            total += len(positions)
        return total
    
    def _sync_positions_with_mt5(self):
        """
        🆕 Sincroniza estado interno com posições reais do MT5.
        Detecta posições fechadas externamente e posições abertas manualmente.
        """
        if not self.state_manager or not self.adapter:
            return
        
        # Coleta todos os tickets de posições abertas no MT5
        all_current_tickets = []
        for symbol in config.MULTI_ASSETS.keys():
            positions = self.adapter.get_open_positions(symbol)
            for pos in positions:
                all_current_tickets.append(pos.ticket)
        
        # Sincroniza com StateManager
        closed_tickets = self.state_manager.sync_positions(all_current_tickets)
        
        # Se alguma posição foi fechada externamente, registra
        if closed_tickets:
            for ticket in closed_tickets:
                # Tenta obter P&L do histórico do MT5
                pnl = self._get_closed_trade_pnl(ticket)
                if pnl is not None:
                    self.daily_pnl += pnl
                    logger.info(f"📝 Trade {ticket} fechado externamente | P&L: ${pnl:.2f}")
                    
                    # Registra no histórico
                    self.state_manager.record_trade({
                        "ticket": ticket,
                        "pnl": pnl,
                        "closed_externally": True
                    })
    
    def _get_closed_trade_pnl(self, ticket: int) -> float:
        """Obtém P&L de um trade fechado do histórico do MT5."""
        try:
            import MetaTrader5 as mt5
            from datetime import datetime, timedelta
            
            # Busca no histórico das últimas 24h
            now = datetime.now()
            history = mt5.history_deals_get(
                now - timedelta(days=1),
                now,
                position=ticket
            )
            
            if history:
                # Soma P&L de todos os deals da posição
                total_pnl = sum(deal.profit + deal.swap + deal.commission for deal in history)
                return total_pnl
            
            return 0.0
        except Exception as e:
            logger.error(f"Erro ao obter P&L do trade {ticket}: {e}")
            return 0.0
    
    def _sync_initial_positions(self):
        """
        🆕 Sincroniza posições existentes no MT5 ao iniciar o bot.
        Detecta posições que já estavam abertas antes do bot iniciar.
        """
        if not self.state_manager or not self.adapter:
            return
        
        logger.info("🔄 Sincronizando posições existentes no MT5...")
        
        total_positions = 0
        positions_by_symbol = {}
        
        for symbol in config.MULTI_ASSETS.keys():
            positions = self.adapter.get_open_positions(symbol)
            if positions:
                positions_by_symbol[symbol] = positions
                total_positions += len(positions)
                
                for pos in positions:
                    # Registra no StateManager se não conhecida
                    if not self.state_manager.is_position_known(pos.ticket):
                        self.state_manager.add_position(pos.ticket)
                        type_str = "BUY" if pos.type == SignalType.BUY else "SELL"
                        logger.info(f"  📝 Posição detectada: {symbol} #{pos.ticket} ({type_str}) @ {pos.price_open:.5f}")
        
        if total_positions > 0:
            logger.info(f"✅ {total_positions} posição(ões) existente(s) sincronizada(s)")
            
            # Mostra resumo por ativo
            for symbol, positions in positions_by_symbol.items():
                asset_config = config.get_asset_config(symbol)
                emoji = asset_config.get("emoji", "📊")
                
                for pos in positions:
                    profit = pos.profit if hasattr(pos, 'profit') else 0
                    profit_emoji = "💚" if profit >= 0 else "💔"
                    type_str = "BUY" if pos.type == SignalType.BUY else "SELL"
                    logger.info(f"  {emoji} {symbol}: {type_str} | Lote: {pos.volume} | {profit_emoji} ${profit:.2f}")
        else:
            logger.info("✅ Nenhuma posição aberta encontrada")
    
    def _can_trade_asset(self, symbol: str) -> tuple:
        """
        Verifica se pode operar o ativo.
        Returns: (can_trade: bool, reason: str)
        """
        asset_config = config.get_asset_config(symbol)
        
        # 1. Ativo habilitado?
        if not asset_config.get("enabled", True):
            return False, "Ativo desabilitado"
        
        # 2. Ativo ativo no momento?
        active_assets = config.get_active_assets()
        if symbol not in active_assets:
            return False, "Fora do horário ideal"
        
        # 3. Limite de posições por ativo
        positions = self.adapter.get_open_positions(symbol)
        max_per_asset = config.MAX_POSITIONS_PER_ASSET
        if len(positions) >= max_per_asset:
            return False, f"Máx posições ({max_per_asset}) atingido"
        
        # 4. Limite total de posições
        total_positions = self._get_total_positions()
        if total_positions >= config.MAX_TOTAL_POSITIONS:
            return False, f"Máx total ({config.MAX_TOTAL_POSITIONS}) atingido"
        
        # 5. Cooldown entre trades
        last_trade = self.last_trade_time.get(symbol, 0)
        cooldown = config.MIN_SECONDS_BETWEEN_TRADES
        if time.time() - last_trade < cooldown:
            remaining = int(cooldown - (time.time() - last_trade))
            return False, f"Cooldown ({remaining}s)"
        
        # 6. Limite diário de trades
        if self.daily_trades >= config.MAX_DAILY_TRADES:
            return False, "Limite diário atingido"
        
        # 7. Limite de perda diária
        max_loss = config.SIMULATED_CAPITAL_USD * (config.MAX_DAILY_LOSS_PERCENT / 100)
        if self.daily_pnl <= -max_loss:
            return False, f"Perda diária máxima atingida"
        
        return True, "OK"
    
    def _check_spread(self, symbol: str) -> tuple:
        """Verifica spread do ativo."""
        spread_filter = self.spread_filters.get(symbol)
        if not spread_filter:
            return True, 0
        
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False, 0
        
        spread = (tick.ask - tick.bid) * 10000  # Em pontos
        
        asset_config = config.get_asset_config(symbol)
        max_spread = asset_config.get("spread_max", 30)
        
        if spread > max_spread:
            return False, spread
        
        return True, spread
    
    def analyze_asset(self, symbol: str) -> dict:
        """
        Analisa um ativo e retorna sinal.
        Returns: {signal, can_trade, reason, ...}
        """
        result = {
            "symbol": symbol,
            "signal": None,
            "can_trade": False,
            "reason": "",
            "spread": 0
        }
        
        # 1. Pode operar?
        can_trade, reason = self._can_trade_asset(symbol)
        if not can_trade:
            result["reason"] = reason
            return result
        
        # 2. Spread OK?
        spread_ok, spread = self._check_spread(symbol)
        result["spread"] = spread
        if not spread_ok:
            result["reason"] = f"Spread alto ({spread:.0f})"
            return result
        
        # 3. Obtém dados
        import MetaTrader5 as mt5
        asset_config = config.get_asset_config(symbol)
        
        # Determina timeframe
        timeframe = mt5.TIMEFRAME_M5
        
        df = self.adapter.get_data(symbol, timeframe, n_bars=200)
        if df is None or len(df) < 50:
            result["reason"] = "Dados insuficientes"
            return result
        
        # 4. Analisa com estratégia
        positions = self.adapter.get_open_positions(symbol)
        strategy = self.strategies.get(symbol)
        
        if not strategy:
            result["reason"] = "Estratégia não inicializada"
            return result
        
        signal = strategy.analyze(df, positions, symbol)
        result["signal"] = signal
        
        if signal.type == SignalType.HOLD:
            result["reason"] = "Sem sinal"
            return result
        
        # 5. 🆕 Filtro Ensemble ML (LightGBM + LSTM combinados)
        if self.ensemble_filter and self.ensemble_filter.is_ready(symbol):
            # Extrai indicadores do sinal para o LightGBM
            indicators = signal.indicators if hasattr(signal, 'indicators') and signal.indicators else {}
            
            # Se não tiver indicadores no sinal, tenta extrair do dataframe
            if not indicators:
                indicators = self._extract_indicators_from_df(df)
            
            # Converte df para lista de candles (para LSTM)
            candles = df.to_dict('records')
            
            # Predição ensemble
            ensemble_score, ensemble_approved, ensemble_reason, details = self.ensemble_filter.predict(
                indicators=indicators,
                symbol=symbol,
                candles=candles
            )
            
            # 🆕 Ajuste por correlação com outros ativos
            other_signals = self._get_other_signals()
            corr_adjustment, corr_reason = self.ensemble_filter.get_correlation_signal(symbol, other_signals)
            if corr_adjustment != 0:
                ensemble_score += corr_adjustment
                ensemble_reason += f" | Corr: {corr_reason}"
            
            result["ensemble_score"] = ensemble_score
            result["ml_proba"] = details.get("lgbm_prob")
            result["deep_ml_proba"] = details.get("lstm_prob")
            result["ensemble_reason"] = ensemble_reason
            
            logger.info(f"🎯 Ensemble {symbol}: {ensemble_reason}")
            
            if not ensemble_approved:
                result["reason"] = ensemble_reason
                result["can_trade"] = False
                return result
        
        # Fallback: Filtros individuais (se ensemble não disponível)
        elif self.ml_filter and self.ml_filter.is_ready(symbol):
            indicators = signal.indicators if hasattr(signal, 'indicators') and signal.indicators else {}
            if not indicators:
                indicators = self._extract_indicators_from_df(df)
            
            ml_proba, ml_approved, ml_reason = self.ml_filter.predict(indicators, symbol)
            result["ml_proba"] = ml_proba
            
            if not ml_approved:
                result["reason"] = ml_reason
                result["can_trade"] = False
                return result
        
        # 6. Sinal válido!
        result["can_trade"] = True
        result["reason"] = "OK"
        
        return result
    
    def _get_other_signals(self) -> dict:
        """
        Coleta sinais recentes dos outros ativos para análise de correlação.
        Returns: {symbol: "BUY"/"SELL"/"HOLD"}
        """
        signals = {}
        import MetaTrader5 as mt5
        
        for symbol in config.MULTI_ASSETS.keys():
            try:
                # Verifica posições abertas
                positions = self.adapter.get_open_positions(symbol)
                if positions:
                    # Se tem posição, usa a direção dela
                    pos = positions[0]
                    if pos.type == 0:  # BUY
                        signals[symbol] = "BUY"
                    else:
                        signals[symbol] = "SELL"
                else:
                    # Sem posição = HOLD
                    signals[symbol] = "HOLD"
            except Exception:
                signals[symbol] = "HOLD"
        
        return signals
    
    def _extract_indicators_from_df(self, df) -> dict:
        """Extrai indicadores do dataframe para o ML filter."""
        if df is None or len(df) < 50:
            return {}
        
        try:
            # Últimos valores
            close = df['close'].iloc[-1]
            
            # SMAs
            sma9 = df['close'].rolling(9).mean().iloc[-1]
            sma21 = df['close'].rolling(21).mean().iloc[-1]
            
            # RSI
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
            rs = gain / loss if loss != 0 else 0
            rsi = 100 - (100 / (1 + rs)) if rs != 0 else 50
            
            # MACD
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            macd_signal = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = (macd_line - macd_signal).iloc[-1]
            
            # ATR
            tr = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift(1)),
                    abs(df['low'] - df['close'].shift(1))
                )
            )
            atr = tr.rolling(14).mean().iloc[-1]
            atr_pct = (tr.rolling(100).apply(lambda x: (x < x.iloc[-1]).sum() / len(x) * 100)).iloc[-1] if len(df) >= 100 else 50
            
            # ADX simplificado
            adx = 25  # Valor padrão
            
            # Volume
            vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
            vol_avg = df[vol_col].rolling(20).mean().iloc[-1] if vol_col in df.columns else 0
            vol_current = df[vol_col].iloc[-1] if vol_col in df.columns else 0
            
            return {
                'sma_crossover': 1 if sma9 > sma21 else (-1 if sma9 < sma21 else 0),
                'price_vs_sma21': 1 if close > sma21 else -1,
                'rsi': rsi,
                'rsi_zone': 1 if rsi < 30 else (-1 if rsi > 70 else 0),
                'macd_signal': 1 if macd_line.iloc[-1] > macd_signal.iloc[-1] else -1,
                'macd_histogram': macd_hist,
                'adx': adx,
                'adx_direction': 1,  # Simplificado
                'atr_percentile': atr_pct if not np.isnan(atr_pct) else 50,
                'market_structure': 0,
                'bos_type': 0,
                'bos_pullback_valid': 0,
                'in_order_block': 0,
                'volume_above_avg': 1 if vol_current > vol_avg else 0,
                # Extras para log detalhado
                'close': close,
                'sma9': sma9,
                'sma21': sma21,
                'atr': atr
            }
        except Exception as e:
            logger.warning(f"Erro ao extrair indicadores: {e}")
            return {}
    
    def _log_detailed_analysis(self, symbol: str, df, signal, result: dict):
        """Loga análise detalhada do mercado como no main.py."""
        asset_config = config.get_asset_config(symbol)
        emoji = asset_config.get("emoji", "📊")
        
        # Extrai indicadores
        ind = self._extract_indicators_from_df(df)
        if not ind:
            return
        
        close = ind.get('close', 0)
        sma9 = ind.get('sma9', 0)
        sma21 = ind.get('sma21', 0)
        rsi = ind.get('rsi', 50)
        atr_pct = ind.get('atr_percentile', 50)
        spread = result.get('spread', 0)
        
        # Tendência
        if sma9 > sma21:
            trend = "📈 ALTA"
            trend_explain = " → média rápida acima da lenta"
        else:
            trend = "📉 BAIXA"
            trend_explain = " → média rápida abaixo da lenta"
        
        # RSI Zone
        if rsi < 30:
            rsi_zone = "🔵 SOBREVENDA"
            rsi_explain = " → pode subir (bom pra comprar)"
        elif rsi > 70:
            rsi_zone = "🔴 SOBRECOMPRA"
            rsi_explain = " → pode cair (bom pra vender)"
        elif rsi < 45:
            rsi_zone = "⚪ NEUTRO"
            rsi_explain = " → tendendo a baixo"
        elif rsi > 55:
            rsi_zone = "⚪ NEUTRO"
            rsi_explain = " → tendendo a alto"
        else:
            rsi_zone = "⚪ NEUTRO"
            rsi_explain = " → mercado indeciso"
        
        # Volatilidade
        if atr_pct < 20:
            vol_status = "📊 Volatilidade BAIXA"
        elif atr_pct > 80:
            vol_status = "📊 Volatilidade ALTA ⚠️"
        else:
            vol_status = f"📊 Volatilidade OK ({atr_pct:.0f}%)"
        
        # Setup status
        setup_status = "🔍 Buscando setup..."
        if rsi < 30:
            setup_status = "🔵 RSI em sobrevenda - possível COMPRA!"
        elif rsi > 70:
            setup_status = "🔴 RSI em sobrecompra - possível VENDA!"
        elif sma9 > sma21 and rsi < 50:
            setup_status = "📈 Alta + RSI baixo - bom pra comprar"
        elif sma9 < sma21 and rsi > 50:
            setup_status = "📉 Baixa + RSI alto - bom pra vender"
        
        # ML status - 🆕 Mostra ensemble score
        ml_status = ""
        if result.get('ensemble_score'):
            ml_status = f"🎯 Ensemble: {result['ensemble_score']:.0%}"
            if result.get('ml_proba'):
                ml_status += f" (LGB:{result['ml_proba']:.0%}"
            if result.get('deep_ml_proba'):
                ml_status += f" LSTM:{result['deep_ml_proba']:.0%})"
            elif result.get('ml_proba'):
                ml_status += ")"
        elif result.get('ml_proba'):
            ml_status = f"🤖 ML: {result['ml_proba']:.1%}"
            if result.get('deep_ml_proba'):
                ml_status += f" | 🧠 LSTM: {result['deep_ml_proba']:.1%}"
        
        # Saldo
        account_info = self.adapter.get_account_info() if self.adapter else {}
        balance_usd = account_info.get('balance', 0)
        balance_brl = balance_usd * getattr(config, 'USD_TO_BRL', 6.10)
        
        # Determina decimais baseado no símbolo
        decimals = 3 if 'JPY' in symbol else 5
        
        # Log formatado
        print()  # Nova linha
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"{emoji} ANÁLISE DE MERCADO | {symbol}")
        logger.info(f"💹 Preço: {close:.{decimals}f} | Tendência: {trend}{trend_explain}")
        logger.info(f"📉 RSI: {rsi:.1f} | Zona: {rsi_zone}{rsi_explain}")
        logger.info(f"📈 SMA9: {sma9:.{decimals}f} | SMA21: {sma21:.{decimals}f}")
        logger.info(f"{vol_status}")
        if spread > 0:
            logger.info(f"💹 Spread: {spread:.1f} pontos")
        if ml_status:
            logger.info(ml_status)
        logger.info(f"💰 Saldo: ${balance_usd:,.2f} (R${balance_brl:,.2f})")
        logger.info(f"📋 Hoje: {self.daily_trades} trades | P&L: ${self.daily_pnl:.2f}")
        logger.info(f"🎯 {setup_status}")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    def execute_trade(self, symbol: str, signal) -> bool:
        """Executa trade para o ativo."""
        asset_config = config.get_asset_config(symbol)
        risk_manager = self.risk_managers.get(symbol)
        
        # Calcula lote
        volume = asset_config.get("volume", 0.05)
        
        # Determina decimais
        decimals = 3 if 'JPY' in symbol else 5
        
        # Log de execução
        emoji = asset_config.get("emoji", "📊")
        order_type = "🟢 BUY" if signal.type == SignalType.BUY else "🔴 SELL"
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"{emoji} EXECUTANDO TRADE | {symbol}")
        logger.info(f"📈 Tipo: {order_type}")
        logger.info(f"📊 Lote: {volume}")
        logger.info(f"🎯 SL: {signal.sl:.{decimals}f} | TP: {signal.tp:.{decimals}f}")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Executa ordem usando execute_order (método correto do MT5Adapter)
        success, ticket = self.adapter.execute_order(
            symbol=symbol,
            signal_type=signal.type,
            volume=volume,
            sl=signal.sl,
            tp=signal.tp,
            comment=f"Multi|{signal.comment[:20] if signal.comment else 'Signal'}"
        )
        
        if success:
            self.last_trade_time[symbol] = time.time()
            self.daily_trades += 1
            
            play_sound('entry')
            
            logger.info(f"✅ ORDEM EXECUTADA! Ticket: {ticket}")
            
            # Calcula valor aproximado em risco (em USD e BRL)
            # Para Forex, 1 lote padrão = 100.000 unidades
            # Mini lote (0.01) = 1.000 unidades
            # Risco = (preço entrada - SL) * lote * 100.000
            pip_value = asset_config.get("pip_value", 0.0001)
            sl_distance = abs(signal.price - signal.sl) if hasattr(signal, 'price') else 0
            
            # Estimativa de risco em USD (aproximado)
            if 'JPY' in symbol:
                risk_usd = sl_distance * volume * 100000 / 100  # Ajuste para pares JPY
            else:
                risk_usd = sl_distance * volume * 100000
            
            risk_brl = risk_usd * getattr(config, 'USD_TO_BRL', 6.10)
            
            # Notifica Telegram com valor em reais
            self.telegram.send_custom(
                f"{emoji} *TRADE EXECUTADO*\n\n"
                f"💹 {symbol}\n"
                f"📈 {order_type}\n"
                f"📊 Lote: {volume}\n"
                f"💰 Risco: ~${risk_usd:.2f} (~R${risk_brl:.2f})\n"
                f"🎯 SL: {signal.sl:.{decimals}f}\n"
                f"🎯 TP: {signal.tp:.{decimals}f}\n"
                f"🎫 Ticket: {ticket}"
            )
            
            return True
        else:
            logger.error(f"❌ Falha ao executar ordem em {symbol}")
        
        return False
    
    def manage_positions(self):
        """Gerencia posições abertas (trailing stop, smart exit)."""
        for symbol in config.MULTI_ASSETS.keys():
            positions = self.adapter.get_open_positions(symbol)
            risk_manager = self.risk_managers.get(symbol)
            
            if not risk_manager:
                continue
            
            for pos in positions:
                # Trailing Stop
                risk_manager.check_trailing_stop(pos)
                
                # Smart Exit
                if getattr(config, 'USE_SMART_EXIT', False):
                    exit_check = risk_manager.check_smart_exit(
                        position=pos,
                        signal_score=5,
                        position_open_time=time.time() - 300,  # Assume 5 min
                        was_negative=pos.profit < 0
                    )
                    
                    if exit_check['should_exit']:
                        asset_config = config.get_asset_config(symbol)
                        emoji = asset_config.get("emoji", "📊")
                        pnl = exit_check['profit']
                        pnl_brl = pnl * getattr(config, 'USD_TO_BRL', 6.10)
                        
                        print()  # Nova linha
                        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        logger.info(f"🧠 SMART EXIT | {symbol}")
                        logger.info(f"📊 Motivo: {exit_check['reason']}")
                        logger.info(f"💰 P&L: ${pnl:.2f} (R${pnl_brl:.2f})")
                        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        
                        if self.adapter.close_position(pos.ticket):
                            self.daily_pnl += pnl
                            
                            # Som de resultado
                            if pnl >= 0:
                                play_sound('win')
                                result_emoji = "💚"
                                result_text = "LUCRO"
                            else:
                                play_sound('loss')
                                result_emoji = "💔"
                                result_text = "PREJUÍZO"
                            
                            logger.info(f"✅ Posição fechada!")
                            logger.info(f"{result_emoji} RESULTADO: {result_text} de ${abs(pnl):.2f}")
                            
                            # Notifica Telegram
                            self.telegram.send_custom(
                                f"{emoji} *POSIÇÃO FECHADA*\n\n"
                                f"💹 {symbol}\n"
                                f"📊 Motivo: {exit_check['reason']}\n"
                                f"{result_emoji} P&L: ${pnl:.2f} (R${pnl_brl:.2f})"
                            )
    
    def run_cycle(self):
        """Executa um ciclo de análise de todos os ativos."""
        import MetaTrader5 as mt5
        
        active_assets = config.get_active_assets()
        
        if not active_assets:
            return
        
        # 🆕 Sincroniza posições com MT5 (detecta posições fechadas/abertas externamente)
        self._sync_positions_with_mt5()
        
        self.cycle_count += 1
        spin = self.spinner[self.cycle_count % len(self.spinner)]
        
        for symbol in active_assets[:config.MAX_CONCURRENT_ASSETS]:
            try:
                # Obtém dados para análise
                df = self.adapter.get_data(symbol, mt5.TIMEFRAME_M5, n_bars=200)
                
                # Analisa
                result = self.analyze_asset(symbol)
                
                # Controle de logs detalhados (a cada 30 segundos por ativo)
                last_analysis = self._last_analysis_log.get(symbol, 0)
                should_log_detailed = time.time() - last_analysis >= 30
                
                if should_log_detailed and df is not None:
                    self._log_detailed_analysis(symbol, df, result.get("signal"), result)
                    self._last_analysis_log[symbol] = time.time()
                else:
                    # Feedback visual compacto entre logs detalhados
                    ind = self._extract_indicators_from_df(df) if df is not None else {}
                    rsi = ind.get('rsi', 50)
                    close = ind.get('close', 0)
                    sma9 = ind.get('sma9', 0)
                    sma21 = ind.get('sma21', 0)
                    
                    trend = "📈" if sma9 > sma21 else "📉"
                    rsi_emoji = "🔵" if rsi < 30 else ("🔴" if rsi > 70 else "⚪")
                    
                    asset_config = config.get_asset_config(symbol)
                    emoji = asset_config.get("emoji", "📊")
                    decimals = 3 if 'JPY' in symbol else 5
                    
                    reason = result.get("reason", "Analisando...")
                    print(f"\r{spin} {emoji} {symbol} {trend} {close:.{decimals}f} | {rsi_emoji} RSI: {rsi:.1f} | {reason} | #{self.cycle_count}", end="", flush=True)
                
                # Executa se tiver sinal
                if result["can_trade"] and result["signal"]:
                    print()  # Nova linha antes do trade
                    play_sound('entry')
                    self.execute_trade(symbol, result["signal"])
                
            except Exception as e:
                logger.error(f"Erro em {symbol}: {e}")
        
        # Gerencia posições
        self.manage_positions()
    
    def print_status(self):
        """Imprime status atual detalhado."""
        active = config.get_active_assets()
        total_pos = self._get_total_positions()
        
        tz = pytz.timezone("America/Sao_Paulo")
        now = datetime.now(tz)
        
        # Saldo
        account_info = self.adapter.get_account_info() if self.adapter else {}
        balance_usd = account_info.get('balance', 0)
        balance_brl = balance_usd * getattr(config, 'USD_TO_BRL', 6.10)
        
        print()  # Nova linha
        logger.info("═"*55)
        logger.info(f"📊 STATUS MULTI-ATIVO | {now.strftime('%H:%M:%S')} BRT")
        logger.info("═"*55)
        logger.info(f"💰 Saldo: ${balance_usd:,.2f} (R${balance_brl:,.2f})")
        logger.info(f"📈 Ativos monitorando: {len(active)} | Posições abertas: {total_pos}")
        logger.info(f"📋 Trades hoje: {self.daily_trades}/{config.MAX_DAILY_TRADES} | P&L: ${self.daily_pnl:.2f}")
        
        # 🆕 Status Ensemble ML
        if self.ensemble_filter:
            stats = self.ensemble_filter.get_stats()
            approved = stats.get('approved', 0)
            rejected = stats.get('rejected', 0)
            unanimous = stats.get('unanimous_approvals', 0)
            total = approved + rejected
            if total > 0:
                rate = approved / total * 100
                logger.info(f"🎯 Ensemble: {approved}✅ {rejected}❌ ({rate:.0f}% aprovação) | {unanimous} unânimes")
        
        # Fallback: Stats individuais
        elif self.ml_filter:
            ml_stats = self.ml_filter.get_stats()
            approved = ml_stats.get('approved', 0)
            rejected = ml_stats.get('rejected', 0)
            total_ml = approved + rejected
            if total_ml > 0:
                rate = approved / total_ml * 100
                logger.info(f"🤖 ML LightGBM: {approved}✅ {rejected}❌ ({rate:.0f}% aprovação)")
        
        # Status por ativo ativo
        logger.info("─"*55)
        logger.info("📊 ATIVOS ATIVOS:")
        for symbol in active:
            positions = self.adapter.get_open_positions(symbol)
            asset_config = config.get_asset_config(symbol)
            emoji = asset_config.get("emoji", "📊")
            desc = asset_config.get("description", "")[:25]
            
            pos_str = f"{len(positions)} pos" if positions else "aguardando"
            pnl_str = ""
            if positions:
                total_pnl = sum(p.profit for p in positions)
                pnl_emoji = "💚" if total_pnl >= 0 else "💔"
                pnl_str = f" | {pnl_emoji} ${total_pnl:.2f}"
            
            logger.info(f"  {emoji} {symbol}: {pos_str}{pnl_str}")
        
        logger.info("═"*55)
    
    def run(self):
        """Loop principal."""
        if not self.initialize():
            return
        
        self.running = True
        cycle_count = 0
        last_signal_log = {}  # {symbol: (signal_type, timestamp)} - evita logs repetidos
        
        logger.info("\n🚀 Bot Multi-Ativo rodando! Ctrl+C para parar.\n")
        
        try:
            while self.running:
                cycle_count += 1
                
                # Verifica conexão
                if not self.adapter.is_connected():
                    logger.warning("⚠️ Reconectando...")
                    if not self.adapter.reconnect(5, 10):
                        break
                
                # Executa ciclo
                self.run_cycle()
                
                # Status a cada 6 ciclos (~60 segundos)
                if cycle_count % 6 == 0:
                    self.print_status()
                
                # Aguarda 10 segundos (igual ao main.py)
                time.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("\n⏹️ Parando bot...")
        
        finally:
            self.running = False
            self.telegram.send_custom(
                f"⏹️ *BOT MULTI-ATIVO PARADO*\n\n"
                f"📊 Trades hoje: {self.daily_trades}\n"
                f"💰 P&L: ${self.daily_pnl:.2f}"
            )
            logger.info("Bot finalizado.")


def main():
    """Função principal."""
    print("\n" + "="*60)
    print("🚀 BOT MULTI-ATIVO - FOREX + CRYPTO")
    print("="*60)
    
    # Mostra ativos configurados
    config.print_all_assets()
    
    # Inicia bot
    bot = MultiAssetBot()
    bot.run()


if __name__ == "__main__":
    main()
