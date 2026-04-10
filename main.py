import time
import pytz
from datetime import datetime, time as dt_time
import config
from src.infrastructure.mt5_adapter import MT5Adapter
from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.hybrid_strategy import HybridStrategy
from src.strategies.risk_manager import RiskManager
from src.domain.entities import SignalType
from src.utils.logger import setup_logger
from src.utils.state_manager import StateManager
from src.utils.telegram_notifier import TelegramNotifier
from src.utils.news_filter import NewsFilter
from src.utils.history_manager import HistoryManager
from src.utils.session_filter import SessionFilter
from src.utils.spread_filter import SpreadFilter
from src.utils.ml_filter import MLFilter

# Som de notificação (Windows)
try:
    import winsound
    SOUND_ENABLED = True
except ImportError:
    SOUND_ENABLED = False

logger = setup_logger("Main")

def play_sound(sound_type: str):
    """
    Toca som de notificação.
    sound_type: 'entry' (entrada), 'win' (lucro), 'loss' (perda)
    """
    if not SOUND_ENABLED:
        return
    
    try:
        if sound_type == 'entry':
            # Som de entrada - beep curto
            winsound.Beep(800, 200)  # 800Hz por 200ms
            winsound.Beep(1000, 200)  # 1000Hz por 200ms
        elif sound_type == 'win':
            # Som de vitória - melodia alegre
            winsound.Beep(523, 150)  # Dó
            winsound.Beep(659, 150)  # Mi
            winsound.Beep(784, 150)  # Sol
            winsound.Beep(1047, 300) # Dó alto
        elif sound_type == 'loss':
            # Som de perda - tom grave
            winsound.Beep(300, 500)  # Tom grave longo
    except Exception:
        pass  # Ignora erros de som

def is_market_open():
    """Verifica se está dentro do horário operacional definido no config."""
    now = datetime.now().time()
    return config.START_TIME <= now <= config.END_TIME

def should_force_exit():
    """Verifica se passou do horário limite para zeragem forçada."""
    now = datetime.now().time()
    return now >= config.FORCE_EXIT_TIME

def apply_conservative_mode():
    """Aplica configurações do modo conservador se ativo."""
    if not getattr(config, 'CONSERVATIVE_MODE', False):
        # Verifica se é modo demo/treino
        if getattr(config, 'DEMO_TRAINING_MODE', False):
            logger.info("🔥 MODO TURBO DEMO ATIVO - Usando configs do config.py!")
            logger.info(f"⚡ Cooldown: {config.MIN_SECONDS_BETWEEN_TRADES}s | Max Lote: {config.MAX_LOT_SIZE} | Posições: {config.MAX_OPEN_POSITIONS}")
        return
    
    logger.warning("🛡️ MODO CONSERVADOR ATIVO - Configurações de proteção aplicadas")
    
    # Sobrescreve configurações para modo seguro
    config.VOLUME = 0.01
    config.MAX_LOT_SIZE = 0.01
    config.MAX_OPEN_POSITIONS = 1
    config.MIN_SECONDS_BETWEEN_TRADES = 1800  # 30 minutos
    config.ATR_MULTIPLIER_SL = 1.0
    config.ATR_MULTIPLIER_TP = 2.0
    config.USE_RSI_EXTREME_ENTRY = False
    config.AGGRESSIVE_MODE = False
    
    capital = getattr(config, 'INITIAL_CAPITAL', 20.0)
    max_loss = getattr(config, 'MAX_DAILY_LOSS_PERCENT', 25.0)
    max_trades = getattr(config, 'MAX_DAILY_TRADES', 5)
    
    logger.info(f"💰 Capital: ${capital} | Max perda/dia: {max_loss}% | Max trades/dia: {max_trades}")

def main():
    logger.info(">>> Iniciando B3 Trading Bot PRO 2.1 <<<")
    
    # Aplica modo conservador se ativo
    apply_conservative_mode()
    
    # 1. Inicialização de Dependências
    try:
        adapter = MT5Adapter(
            login=config.MT5_LOGIN, 
            password=config.MT5_PASSWORD, 
            server=config.MT5_SERVER
        )
        
        if not adapter.connect():
            logger.critical("Não foi possível conectar ao MT5. Encerrando.")
            return

        risk_manager = RiskManager(adapter, config)
        
        # Inicializa gerenciador de estado
        state_file = getattr(config, 'STATE_FILE', 'bot_state.json')
        state_manager = StateManager(state_file)
        
        # Inicializa notificador Telegram
        telegram = TelegramNotifier(
            bot_token=getattr(config, 'TELEGRAM_BOT_TOKEN', ''),
            chat_id=getattr(config, 'TELEGRAM_CHAT_ID', '')
        )
        
        # Inicializa filtro de notícias
        news_filter = None
        if getattr(config, 'USE_NEWS_FILTER', False):
            news_filter = NewsFilter(
                blackout_minutes=getattr(config, 'NEWS_BLACKOUT_MINUTES', 30),
                filter_currencies=getattr(config, 'NEWS_FILTER_CURRENCIES', ["USD", "EUR", "GBP"])
            )
        
        # Inicializa filtro de sessão (Killzones)
        session_filter = None
        if getattr(config, 'USE_SESSION_FILTER', False):
            session_filter = SessionFilter(
                london_start=getattr(config, 'KILLZONE_LONDON_START', dt_time(5, 0)),
                london_end=getattr(config, 'KILLZONE_LONDON_END', dt_time(7, 0)),
                ny_start=getattr(config, 'KILLZONE_NY_START', dt_time(10, 0)),
                ny_end=getattr(config, 'KILLZONE_NY_END', dt_time(12, 0)),
                avoid_open_minutes=getattr(config, 'AVOID_SESSION_OPEN_MINUTES', 30)
            )
            logger.info(f"🎯 Filtro de Sessão ATIVO - Killzones: Londres 05:00-07:00 | NY 10:00-12:00")
        
        # Inicializa filtro de spread
        spread_filter = None
        if getattr(config, 'USE_SPREAD_FILTER', False):
            spread_filter = SpreadFilter(
                max_spread_multiplier=getattr(config, 'MAX_SPREAD_MULTIPLIER', 2.0),
                max_spread_absolute=getattr(config, 'MAX_SPREAD_ABSOLUTE', 30),
                history_size=getattr(config, 'SPREAD_HISTORY_SIZE', 100)
            )
            logger.info(f"💹 Filtro de Spread ATIVO - Máx: {getattr(config, 'MAX_SPREAD_ABSOLUTE', 30)} pontos ou 2x média")
        
        # Inicializa filtro ML (LightGBM)
        ml_filter = None
        if getattr(config, 'USE_ML_FILTER', False):
            import os
            model_path = getattr(config, 'ML_MODEL_PATH', 'models/btcusd_t_lgbm.pkl')
            # Ajusta caminho relativo ao diretório do projeto
            if not os.path.isabs(model_path):
                project_dir = os.path.dirname(os.path.abspath(__file__))
                model_path = os.path.join(project_dir, model_path)
            
            ml_confidence = getattr(config, 'ML_CONFIDENCE_THRESHOLD', 0.60)
            ml_filter = MLFilter(model_path=model_path, min_confidence=ml_confidence)
            
            if ml_filter.is_ready():
                logger.info(f"🤖 ML Filter ATIVO - Modelo: {os.path.basename(model_path)}")
                logger.info(f"   Threshold: {ml_confidence:.0%} | Features: {len(ml_filter.feature_names)}")
            else:
                logger.warning(f"⚠️ ML Filter: Modelo não encontrado em {model_path}")
                logger.warning(f"   Execute: python train_ml_model.py --symbol {config.SYMBOL}")
                if not getattr(config, 'ML_FALLBACK_TO_SCORE', True):
                    ml_filter = None
        
        # Inicializa gerenciador de histórico
        history_manager = None
        if getattr(config, 'USE_HISTORY_MANAGER', False):
            history_manager = HistoryManager()
            logger.info("📊 Verificando e baixando histórico...")
            history_manager.ensure_history(config.SYMBOL, config.TIMEFRAME, 
                                          getattr(config, 'HISTORY_MONTHS', 3))
            # Também baixa H1 para filtro multi-timeframe
            if getattr(config, 'USE_MTF_FILTER', False):
                import MetaTrader5 as mt5
                history_manager.ensure_history(config.SYMBOL, mt5.TIMEFRAME_H1, 
                                              getattr(config, 'HISTORY_MONTHS', 3))
            history_manager.print_status()

        # Passa o flag de modo agressivo para a estratégia
        aggressive = getattr(config, 'AGGRESSIVE_MODE', False)
        
        # Verifica se deve usar modo híbrido (v3.0)
        use_hybrid = getattr(config, 'USE_HYBRID_MODE', False)
        
        if use_hybrid:
            # Usa HybridStrategy (Trend Following + Mean Reversion + ML + MTF)
            strategy = HybridStrategy(config, adapter)
            logger.info("🚀 Modo HÍBRIDO v3.0 ATIVO!")
            logger.info("   📈 Trend Following (ADX >= 20)")
            logger.info("   🔄 Mean Reversion (ADX < 20)")
            if getattr(config, 'USE_ML_FILTER', False):
                logger.info("   🤖 ML Signal Filter: ON")
            if getattr(config, 'USE_MTF_ANALYSIS', False):
                logger.info("   📊 Multi-Timeframe (H1): ON")
        else:
            # Usa TrendFollowingStrategy original
            strategy = TrendFollowingStrategy(
                fast_period=config.SMA_FAST,
                slow_period=config.SMA_SLOW,
                rsi_period=config.RSI_PERIOD,
                rsi_upper=config.RSI_OVERBOUGHT,
                rsi_lower=config.RSI_OVERSOLD,
                atr_period=config.ATR_PERIOD,
                atr_mult_sl=config.ATR_MULTIPLIER_SL,
                atr_mult_tp=config.ATR_MULTIPLIER_TP,
                aggressive_mode=aggressive,
                use_rsi_extreme=getattr(config, 'USE_RSI_EXTREME_ENTRY', False),
                rsi_extreme_oversold=getattr(config, 'RSI_EXTREME_OVERSOLD', 25),
                rsi_extreme_overbought=getattr(config, 'RSI_EXTREME_OVERBOUGHT', 75),
                # Novos parâmetros PRO v2.0
                min_signal_score=getattr(config, 'MIN_SIGNAL_SCORE', 3),
                use_macd_filter=getattr(config, 'USE_MACD_FILTER', True),
                use_volume_filter=getattr(config, 'USE_VOLUME_FILTER', True),
                rsi_momentum_sell=getattr(config, 'RSI_MOMENTUM_SELL', 55),
                rsi_momentum_buy=getattr(config, 'RSI_MOMENTUM_BUY', 45),
                # Parâmetros ADX (Detecção de Tendência vs Range)
                use_adx_filter=getattr(config, 'USE_ADX_FILTER', True),
                adx_period=getattr(config, 'ADX_PERIOD', 14),
                adx_threshold=getattr(config, 'ADX_THRESHOLD', 20),
                adx_strong=getattr(config, 'ADX_STRONG', 25),
                # Parâmetros Anti-Stop Hunt
                use_anti_stop_hunt=getattr(config, 'USE_ANTI_STOP_HUNT', True),
                sl_buffer_pips=getattr(config, 'SL_BUFFER_PIPS', 5),
                avoid_round_numbers=getattr(config, 'AVOID_ROUND_NUMBERS', True),
                round_number_buffer_pips=getattr(config, 'ROUND_NUMBER_BUFFER_PIPS', 3),
                use_swing_sl=getattr(config, 'USE_SWING_SL', True),
                # Parâmetros Filtro de Volatilidade
                use_volatility_filter=getattr(config, 'USE_VOLATILITY_FILTER', True),
                atr_percentile_low=getattr(config, 'ATR_PERCENTILE_LOW', 20),
                atr_percentile_high=getattr(config, 'ATR_PERCENTILE_HIGH', 80),
                atr_lookback=getattr(config, 'ATR_LOOKBACK', 100),
                # Parâmetros Market Structure
                use_market_structure=getattr(config, 'USE_MARKET_STRUCTURE', True),
                swing_lookback=getattr(config, 'SWING_LOOKBACK', 5),
                min_swing_points=getattr(config, 'MIN_SWING_POINTS', 3),
                structure_as_filter=getattr(config, 'STRUCTURE_AS_FILTER', True),
                # Parâmetros BOS + Pullback (Smart Money)
                use_bos_pullback=getattr(config, 'USE_BOS_PULLBACK', True),
                bos_pullback_min=getattr(config, 'BOS_PULLBACK_MIN', 0.3),
                bos_pullback_max=getattr(config, 'BOS_PULLBACK_MAX', 0.7),
                bos_expiry_bars=getattr(config, 'BOS_EXPIRY_BARS', 20),
                bos_as_filter=getattr(config, 'BOS_AS_FILTER', False),
                # Parâmetros Order Blocks (Smart Money)
                use_order_blocks=getattr(config, 'USE_ORDER_BLOCKS', True),
                ob_lookback=getattr(config, 'OB_LOOKBACK', 50),
                ob_min_impulse_atr=getattr(config, 'OB_MIN_IMPULSE_ATR', 1.5),
                ob_as_filter=getattr(config, 'OB_AS_FILTER', False),
                ob_mitigation_percent=getattr(config, 'OB_MITIGATION_PERCENT', 0.5),
                ob_max_age_bars=getattr(config, 'OB_MAX_AGE_BARS', 100)
            )
        
        # Log de configuração
        if use_hybrid:
            mode_str = "🚀 HÍBRIDO PRO v3.0"
        elif aggressive:
            mode_str = "🔥 AGRESSIVO (TESTE)"
        else:
            mode_str = "📊 TÉCNICO PRO v2.1"
        rsi_extreme_str = f"RSI Extremo: <{getattr(config, 'RSI_EXTREME_OVERSOLD', 25)} / >{getattr(config, 'RSI_EXTREME_OVERBOUGHT', 75)}" if getattr(config, 'USE_RSI_EXTREME_ENTRY', False) else "RSI Extremo: OFF"
        min_score = getattr(config, 'MIN_SIGNAL_SCORE', 3)
        adx_status = f"ADX: ON (min={getattr(config, 'ADX_THRESHOLD', 20)})" if getattr(config, 'USE_ADX_FILTER', True) else "ADX: OFF"
        logger.info(f"Modo: {mode_str}")
        if use_hybrid:
            logger.info(f"Estratégia: Hybrid (TrendFollowing + MeanReversion + ML + MTF)")
        else:
            logger.info(f"Estratégia: TrendFollowing PRO (SMA {config.SMA_FAST}/{config.SMA_SLOW} + RSI + MACD + Volume + ADX)")
        logger.info(f"Sistema de Score: Mínimo {min_score}/9 confirmações para entrar")
        logger.info(f"Filtros: MACD={'ON' if getattr(config, 'USE_MACD_FILTER', True) else 'OFF'} | Volume={'ON' if getattr(config, 'USE_VOLUME_FILTER', True) else 'OFF'} | {adx_status}")
        anti_hunt_status = f"Anti-Hunt: ON (+{getattr(config, 'SL_BUFFER_PIPS', 5)} pips)" if getattr(config, 'USE_ANTI_STOP_HUNT', True) else "Anti-Hunt: OFF"
        logger.info(f"RSI Momentum: Compra<{getattr(config, 'RSI_MOMENTUM_BUY', 45)} | Venda>{getattr(config, 'RSI_MOMENTUM_SELL', 55)} | {rsi_extreme_str}")
        logger.info(f"🛡️ {anti_hunt_status} | Evita números redondos: {'ON' if getattr(config, 'AVOID_ROUND_NUMBERS', True) else 'OFF'}")
        vol_filter_status = f"Volatilidade: ON ({getattr(config, 'ATR_PERCENTILE_LOW', 20)}-{getattr(config, 'ATR_PERCENTILE_HIGH', 80)}%)" if getattr(config, 'USE_VOLATILITY_FILTER', True) else "Volatilidade: OFF"
        logger.info(f"📊 {vol_filter_status}")
        struct_status = "Market Structure: ON (filtra contra-tendência)" if getattr(config, 'USE_MARKET_STRUCTURE', True) else "Market Structure: OFF"
        logger.info(f"📐 {struct_status}")
        bos_status = f"BOS+Pullback: ON ({int(getattr(config, 'BOS_PULLBACK_MIN', 0.3)*100)}-{int(getattr(config, 'BOS_PULLBACK_MAX', 0.7)*100)}% retração)" if getattr(config, 'USE_BOS_PULLBACK', True) else "BOS+Pullback: OFF"
        logger.info(f"🎯 {bos_status}")
        ob_status = f"Order Blocks: ON (impulso > {getattr(config, 'OB_MIN_IMPULSE_ATR', 1.5)}x ATR)" if getattr(config, 'USE_ORDER_BLOCKS', True) else "Order Blocks: OFF"
        logger.info(f"📦 {ob_status}")
        logger.info(f"Risk Manager: Risco {config.RISK_PER_TRADE_PERCENT}% | Max Lote: {getattr(config, 'MAX_LOT_SIZE', 'N/A')} | Trailing: {'ON' if config.USE_TRAILING_STOP else 'OFF'}")
        logger.info(f"Limites: Max Posições={getattr(config, 'MAX_OPEN_POSITIONS', 1)} | Cooldown={getattr(config, 'MIN_SECONDS_BETWEEN_TRADES', 0)}s")
        logger.info(f"Monitorando ativo: {config.SYMBOL}")
        logger.info(state_manager.get_stats_summary())
        
        # Mostra métricas de performance se houver histórico
        history = state_manager.get_trades_history()
        if history:
            logger.info(state_manager.get_performance_summary())
        
        # Notifica início via Telegram com filtros Smart Money
        filters_config = {
            'session_filter': getattr(config, 'USE_SESSION_FILTER', False),
            'spread_filter': getattr(config, 'USE_SPREAD_FILTER', False),
            'adx_filter': getattr(config, 'USE_ADX_FILTER', False),
            'anti_stop_hunt': getattr(config, 'USE_ANTI_STOP_HUNT', False),
            'volatility_filter': getattr(config, 'USE_VOLATILITY_FILTER', False),
            'market_structure': getattr(config, 'USE_MARKET_STRUCTURE', False),
            'bos_pullback': getattr(config, 'USE_BOS_PULLBACK', False),
            'order_blocks': getattr(config, 'USE_ORDER_BLOCKS', False)
        }
        telegram.notify_bot_started(config.SYMBOL, mode_str, filters_config)

    except Exception as e:
        logger.critical(f"Erro na inicialização: {e}")
        return

    # 2. Loop Principal
    last_log_time = time.time() - 61  # Força primeiro log imediato
    last_trade_time = state_manager.get_last_trade_time()  # Recupera do estado salvo
    cycle_count = 0  # Contador de ciclos para feedback visual
    
    # Parâmetros de segurança
    max_positions = getattr(config, 'MAX_OPEN_POSITIONS', 1)
    cooldown_seconds = getattr(config, 'MIN_SECONDS_BETWEEN_TRADES', 60)
    heartbeat_interval = getattr(config, 'HEARTBEAT_INTERVAL', 30)
    
    # Parâmetros de reconexão
    max_reconnect = getattr(config, 'MAX_RECONNECT_ATTEMPTS', 5)
    reconnect_delay = getattr(config, 'RECONNECT_DELAY_SECONDS', 10)
    
    # Parâmetros do modo conservador
    conservative_mode = getattr(config, 'CONSERVATIVE_MODE', False)
    initial_capital = getattr(config, 'INITIAL_CAPITAL', 100.0)
    max_daily_loss_pct = getattr(config, 'MAX_DAILY_LOSS_PERCENT', 25.0)
    max_daily_trades = getattr(config, 'MAX_DAILY_TRADES', 10)
    daily_limit_hit = False  # Flag para parar o bot
    
    # Parâmetros da saída inteligente
    use_smart_exit = getattr(config, 'USE_SMART_EXIT', False)
    position_open_times = {}  # {ticket: timestamp} - rastreia quando cada posição foi aberta
    position_scores = {}      # {ticket: score} - rastreia o score do sinal que abriu a posição
    position_was_negative = {} # {ticket: bool} - rastreia se posição já esteve negativa
    
    # Controle de notificações Telegram (a cada 1 minuto)
    last_telegram_update = 0
    telegram_update_interval = 60  # segundos
    
    # Recupera posições existentes do MT5 para Smart Exit funcionar após reinício
    if use_smart_exit:
        existing_positions = adapter.get_open_positions(config.SYMBOL)
        for pos in existing_positions:
            if pos.ticket not in position_open_times:
                # Usa o tempo de abertura real da posição do MT5
                position_open_times[pos.ticket] = pos.time  # timestamp de abertura
                position_scores[pos.ticket] = 5  # Score padrão (não sabemos o original)
                position_was_negative[pos.ticket] = pos.profit < 0
                logger.info(f"🧠 Smart Exit: Recuperada posição {pos.ticket} | P&L: ${pos.profit:.2f}")
    
    # Spinner para feedback visual
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    while True:
        try:
            # --- Verificação de Mudança de Sessão (Bot 24h) ---
            # Se estiver rodando via run_24h.py, verifica se mudou de sessão
            if hasattr(config, 'get_current_session'):
                try:
                    from config_24h import get_current_session, get_session_config, get_current_symbol
                    current_session = get_current_session()
                    session_config = get_session_config(current_session)
                    new_symbol = session_config["symbol"]
                    
                    # Se o símbolo mudou, atualiza as configurações
                    if new_symbol != config.SYMBOL:
                        logger.info(f"🔄 MUDANÇA DE SESSÃO: {config.SYMBOL} → {new_symbol}")
                        logger.info(f"📍 Nova sessão: {session_config['name']}")
                        
                        # Fecha posições abertas no símbolo antigo antes de trocar
                        old_positions = adapter.get_open_positions(config.SYMBOL)
                        if old_positions:
                            logger.info(f"⚠️ Fechando {len(old_positions)} posição(ões) em {config.SYMBOL} antes de trocar...")
                            for pos in old_positions:
                                adapter.close_position(pos.ticket)
                        
                        # Atualiza configurações
                        config.SYMBOL = new_symbol
                        config.MIN_SIGNAL_SCORE = session_config["min_signal_score"]
                        config.USE_TRAILING_STOP = session_config["use_trailing_stop"]
                        config.TRAILING_TRIGGER_POINTS = session_config["trailing_trigger"]
                        config.TRAILING_STEP_POINTS = session_config["trailing_step"]
                        
                        # Notifica via Telegram
                        telegram.send_message(
                            f"🔄 *MUDANÇA DE SESSÃO*\n\n"
                            f"📍 {session_config['name']}\n"
                            f"💹 Par: {new_symbol}\n"
                            f"📊 Score mínimo: {session_config['min_signal_score']}/9\n"
                            f"🎚️ Qualidade: {session_config['quality']}"
                        )
                        
                        logger.info(f"💹 Agora operando: {config.SYMBOL}")
                        logger.info(f"📊 Score mínimo: {config.MIN_SIGNAL_SCORE}/9")
                except ImportError:
                    pass  # Não está rodando via run_24h.py
            
            # --- Verificação de Limites Diários (Modo Conservador) ---
            if conservative_mode and not daily_limit_hit:
                # Verifica limite de perda
                loss_hit, loss_pct = state_manager.check_daily_loss_limit(initial_capital, max_daily_loss_pct)
                if loss_hit:
                    daily_limit_hit = True
                    msg = f"🛑 LIMITE DE PERDA ATINGIDO! Perda: {loss_pct:.1f}% | Bot pausado até amanhã."
                    logger.critical(msg)
                    telegram.notify_error("Limite de Perda", msg)
                    print(f"\n{msg}")
                    print("Bot entrará em modo de espera. Reinicie amanhã ou desative CONSERVATIVE_MODE.")
                
                # Verifica limite de trades
                if state_manager.check_daily_trade_limit(max_daily_trades):
                    daily_limit_hit = True
                    msg = f"🛑 LIMITE DE TRADES ATINGIDO! {max_daily_trades} trades hoje. Bot pausado."
                    logger.warning(msg)
                    telegram.notify_error("Limite de Trades", msg)
            
            if daily_limit_hit:
                # Fica em modo de espera, só monitora
                time.sleep(60)
                continue
            
            # --- Verificação de Conexão ---
            if not adapter.is_connected():
                print()  # Nova linha
                logger.warning("⚠️ Conexão com MT5 perdida!")
                telegram.notify_error("Conexão Perdida", "Iniciando reconexão...")
                
                if not adapter.reconnect(max_reconnect, reconnect_delay):
                    logger.critical("❌ Impossível reconectar. Encerrando bot.")
                    telegram.notify_bot_stopped("Falha na reconexão")
                    break
                
                # Reconectou com sucesso
                telegram.notify_reconnection(True, 1)
                continue

            # Verifica Horário de Encerramento Forçado
            if should_force_exit():
                open_positions = adapter.get_open_positions(config.SYMBOL)
                if open_positions:
                    logger.warning("⏰ Horário limite! Forçando zeragem de posições.")
                    adapter.close_all_positions(config.SYMBOL)
                else:
                    logger.info("Mercado fechado. Aguardando próximo dia...")
                
                time.sleep(60)
                continue

            # Verifica Horário Operacional
            if not is_market_open():
                logger.info("Fora do horário operacional. Aguardando...")
                time.sleep(60)
                continue

            # --- Ciclo de Trading ---
            cycle_count += 1
            spin = spinner[cycle_count % len(spinner)]
            
            # 1. Coleta de Dados (usa histórico local + MT5 live)
            if history_manager:
                df = history_manager.get_data(config.SYMBOL, config.TIMEFRAME, bars=500)
            else:
                df = adapter.get_data(config.SYMBOL, config.TIMEFRAME, n_bars=100)
            open_positions = adapter.get_open_positions(config.SYMBOL)
            
            # DEBUG: Log das posições abertas
            if open_positions:
                logger.info(f"🔍 DEBUG: Posições abertas: {[p.ticket for p in open_positions]}")
            
            # Sincroniza estado com posições reais do MT5
            current_tickets = [p.ticket for p in open_positions]
            closed_tickets = state_manager.sync_positions(current_tickets)
            
            # Registra trades fechados no histórico
            for ticket in closed_tickets:
                # Busca informações do trade fechado no histórico do MT5
                trade_info = adapter.get_closed_trade_info(ticket)
                if trade_info:
                    state_manager.record_trade(trade_info)
                    # Notifica via Telegram
                    telegram.notify_position_closed(
                        trade_info.get('symbol', config.SYMBOL),
                        trade_info.get('pnl', 0),
                        ticket,
                        usd_to_brl=getattr(config, 'USD_TO_BRL', 6.10)
                    )

            # 1.5 Gerenciamento de Posições Abertas (Trailing Stop + Smart Exit)
            for pos in open_positions:
                risk_manager.check_trailing_stop(pos)
                
                # 🧠 SAÍDA INTELIGENTE
                if use_smart_exit:
                    ticket = pos.ticket
                    open_time = position_open_times.get(ticket, time.time())
                    score = position_scores.get(ticket, 5)
                    
                    # Rastreia se já esteve negativo
                    if pos.profit < 0:
                        position_was_negative[ticket] = True
                    
                    # Verifica se deve sair
                    exit_check = risk_manager.check_smart_exit(
                        position=pos,
                        signal_score=score,
                        position_open_time=open_time,
                        was_negative=position_was_negative.get(ticket, False)
                    )
                    
                    if exit_check['should_exit']:
                        pnl_usd = exit_check['profit']
                        pnl_brl = pnl_usd * getattr(config, 'USD_TO_BRL', 6.10)
                        
                        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        logger.info(f"🧠 SMART EXIT ATIVADO!")
                        logger.info(f"📊 Motivo: {exit_check['reason']}")
                        logger.info(f"💰 P&L: ${pnl_usd:.2f} (R${pnl_brl:.2f})")
                        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        
                        # Fecha a posição
                        if adapter.close_position(ticket):
                            emoji = "💚" if pnl_usd >= 0 else "💔"
                            resultado = "LUCRO" if pnl_usd >= 0 else "PREJUÍZO"
                            logger.info(f"✅ Posição {ticket} fechada com sucesso!")
                            logger.info(f"{emoji} RESULTADO: {resultado} de ${abs(pnl_usd):.2f} (R${abs(pnl_brl):.2f})")
                            
                            # 🔊 Som de resultado
                            if pnl_usd >= 0:
                                play_sound('win')
                            else:
                                play_sound('loss')
                            
                            # Limpa rastreamento
                            position_open_times.pop(ticket, None)
                            position_scores.pop(ticket, None)
                            position_was_negative.pop(ticket, None)
                            
                            # Atualiza estatísticas
                            pnl = exit_check['profit']
                            state_manager.record_trade({
                                'symbol': config.SYMBOL,
                                'ticket': ticket,
                                'pnl': pnl,
                                'type': 'smart_exit',
                                'reason': exit_check['reason']
                            })
                            
                            # Notifica Telegram
                            telegram.notify_position_closed(
                                config.SYMBOL,
                                pnl,
                                ticket,
                                usd_to_brl=getattr(config, 'USD_TO_BRL', 6.10),
                                close_reason=exit_check['reason']
                            )
                        else:
                            logger.error(f"❌ Falha ao fechar posição {ticket}")

            # 2. Verificar limite de posições ANTES de analisar
            # DEBUG: Log do número de posições
            logger.info(f"🔍 DEBUG: open_positions = {len(open_positions)} | max_positions = {max_positions}")
            
            if len(open_positions) >= max_positions:
                # Apenas log de heartbeat, sem analisar novos sinais
                if time.time() - last_log_time > heartbeat_interval:
                    # Chama analyze com symbol se for HybridStrategy
                    if use_hybrid:
                        signal = strategy.analyze(df, open_positions, config.SYMBOL)
                    else:
                        signal = strategy.analyze(df, open_positions)
                    ind = signal.indicators
                    sma9 = ind.get('sma_fast', 0)
                    sma21 = ind.get('sma_slow', 0)
                    trend = "📈 ALTA" if sma9 > sma21 else "📉 BAIXA"
                    rsi_val = ind.get('rsi', 0)
                    rsi_zone = "🔵 SOBREVENDA" if rsi_val < 30 else ("🔴 SOBRECOMPRA" if rsi_val > 70 else "⚪ NEUTRO")
                    
                    # Info da posição aberta
                    pos = open_positions[0]
                    pos_type = "🟢 COMPRADO" if pos.is_buy else "🔴 VENDIDO"
                    pos_profit = pos.profit
                    pos_profit_brl = pos_profit * getattr(config, 'USD_TO_BRL', 6.10)
                    profit_emoji = "💚" if pos_profit >= 0 else "💔"
                    
                    print()
                    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    logger.info(f"📊 MONITORANDO POSIÇÃO ABERTA")
                    logger.info(f"� Preço: {signal.price:.5f} | Tendência: {trend}")
                    logger.info(f"�📉 RSI: {rsi_val:.1f} | Zona: {rsi_zone}")
                    logger.info(f"{pos_type} | Entrada: {pos.price_open:.5f} | {profit_emoji} P&L: ${pos_profit:.2f} (R${pos_profit_brl:.2f})")
                    logger.info(f"🎯 SL: {pos.sl:.5f} | TP: {pos.tp:.5f}")
                    
                    # Status da saída inteligente
                    if use_smart_exit:
                        ticket = pos.ticket
                        score = position_scores.get(ticket, 5)
                        open_time = position_open_times.get(ticket, time.time())
                        minutes_open = (time.time() - open_time) / 60
                        was_neg = position_was_negative.get(ticket, False)
                        
                        if pos_profit >= 0:
                            if was_neg:
                                smart_status = f"🔄 RECUPEROU! Pronto para sair com lucro"
                            else:
                                smart_status = f"✅ No lucro - aguardando melhor momento"
                        else:
                            wait_max = getattr(config, 'SMART_EXIT_WAIT_NEGATIVE_MINUTES', 30)
                            smart_status = f"⏳ Aguardando recuperação ({minutes_open:.0f}/{wait_max}min)"
                        
                        logger.info(f"🧠 Smart Exit: Score {score}/9 | {smart_status}")
                        
                        # Envia atualização no Telegram a cada 1 minuto
                        if time.time() - last_telegram_update >= telegram_update_interval:
                            pos_type = "BUY" if pos.is_buy else "SELL"
                            telegram.notify_position_update(
                                symbol=config.SYMBOL,
                                pos_type=pos_type,
                                entry_price=pos.price_open,
                                current_price=signal.price,
                                pnl_usd=pos_profit,
                                sl=pos.sl,
                                tp=pos.tp,
                                usd_to_brl=getattr(config, 'USD_TO_BRL', 6.10),
                                score=score,
                                minutes_open=minutes_open,
                                smart_status=smart_status
                            )
                            last_telegram_update = time.time()
                    
                    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    last_log_time = time.time()
                else:
                    # Feedback visual entre heartbeats
                    if use_hybrid:
                        signal = strategy.analyze(df, open_positions, config.SYMBOL)
                    else:
                        signal = strategy.analyze(df, open_positions)
                    ind = signal.indicators
                    pos = open_positions[0]
                    profit_emoji = "💚" if pos.profit >= 0 else "💔"
                    profit_brl = pos.profit * getattr(config, 'USD_TO_BRL', 6.10)
                    trend = "📈" if ind.get('sma_fast', 0) > ind.get('sma_slow', 0) else "📉"
                    print(f"\r{spin} {trend} {signal.price:.5f} | RSI: {ind.get('rsi', 0):.1f} | {profit_emoji} ${pos.profit:.2f} (R${profit_brl:.2f}) | #{cycle_count}", end="", flush=True)
                time.sleep(10)
                continue

            # 3. Verificar cooldown entre operações
            time_since_last_trade = time.time() - last_trade_time
            if last_trade_time > 0 and time_since_last_trade < cooldown_seconds:
                remaining = int(cooldown_seconds - time_since_last_trade)
                # Feedback visual do cooldown
                print(f"\r{spin} Cooldown: {remaining}s restantes | Ciclo #{cycle_count}", end="", flush=True)
                time.sleep(10)
                continue

            # 4. Análise da Estratégia
            if use_hybrid:
                signal = strategy.analyze(df, open_positions, config.SYMBOL)
            else:
                signal = strategy.analyze(df, open_positions)
            
            # DEBUG: Log do sinal retornado
            logger.info(f"🔍 DEBUG Main: Sinal retornado: {signal.type.name} | Preço: {signal.price:.5f}")

            # Log de "Heartbeat" (Sinal de Vida)
            if time.time() - last_log_time > heartbeat_interval:
                ind = signal.indicators
                rsi_val = ind.get('rsi', 0)
                sma9 = ind.get('sma_fast', 0)
                sma21 = ind.get('sma_slow', 0)
                adx_val = ind.get('adx', 0)
                plus_di = ind.get('plus_di', 0)
                minus_di = ind.get('minus_di', 0)
                atr_pct = ind.get('atr_percentile', 50)
                market_struct = ind.get('market_structure', 'RANGING')
                struct_details = ind.get('structure_details', '')
                
                trend = "📈 ALTA" if sma9 > sma21 else "📉 BAIXA"
                
                # RSI com explicação
                if rsi_val < 30:
                    rsi_zone = "🔵 SOBREVENDA"
                    rsi_explain = " → caiu muito, pode subir (bom pra comprar)"
                elif rsi_val > 70:
                    rsi_zone = "🔴 SOBRECOMPRA"
                    rsi_explain = " → subiu muito, pode cair (bom pra vender)"
                elif rsi_val < 40:
                    rsi_zone = "⚪ NEUTRO"
                    rsi_explain = " → tendendo a baixo, pode comprar"
                elif rsi_val > 60:
                    rsi_zone = "⚪ NEUTRO"
                    rsi_explain = " → tendendo a alto, pode vender"
                else:
                    rsi_zone = "⚪ NEUTRO"
                    rsi_explain = " → mercado indeciso"
                
                # Status do ADX com explicação
                if adx_val < 20:
                    adx_status = f"📊 ADX {adx_val:.0f} - LATERAL (sem tendência)"
                    adx_explain = " → mercado parado, evitar trades"
                elif adx_val < 25:
                    adx_status = f"📈 ADX {adx_val:.0f} - Tendência FRACA"
                    adx_explain = " → tendência começando, cuidado"
                elif adx_val < 50:
                    di_dir = "↑ DI+" if plus_di > minus_di else "↓ DI-"
                    adx_status = f"💪 ADX {adx_val:.0f} - Tendência FORTE ({di_dir})"
                    adx_explain = " → bom momento pra operar!"
                else:
                    di_dir = "↑ DI+" if plus_di > minus_di else "↓ DI-"
                    adx_status = f"🔥 ADX {adx_val:.0f} - Tendência MUITO FORTE ({di_dir})"
                    adx_explain = " → tendência forte, aproveitar!"
                
                # Status da Volatilidade (ATR Percentil) com explicação
                if atr_pct < 20:
                    vol_status = f"🔵 Volatilidade BAIXA ({atr_pct:.0f}%) → mercado calmo, movimentos pequenos"
                elif atr_pct > 80:
                    vol_status = f"🔴 Volatilidade ALTA ({atr_pct:.0f}%) → mercado agitado, cuidado com stops"
                else:
                    vol_status = f"🟢 Volatilidade NORMAL ({atr_pct:.0f}%) → condições ideais"
                
                # Status da Estrutura de Mercado com explicação
                if market_struct == "BULLISH":
                    struct_status = f"📈 Estrutura BULLISH (HH+HL) → topos e fundos subindo, tendência de alta"
                elif market_struct == "BEARISH":
                    struct_status = f"📉 Estrutura BEARISH (LH+LL) → topos e fundos caindo, tendência de baixa"
                else:
                    struct_status = f"📊 Estrutura RANGING → mercado sem direção clara"
                
                # Status do BOS + Pullback com explicação
                bos_type = ind.get('bos_type', 'NONE')
                bos_pullback = ind.get('bos_pullback_valid', False)
                bos_retrace = ind.get('bos_retracement', 0)
                if bos_type != "NONE":
                    bos_emoji = "🟢" if bos_type == "BULLISH" else "🔴"
                    if bos_pullback:
                        pullback_str = f"✓ Pullback {bos_retrace:.0f}% → preço voltou, bom ponto de entrada!"
                    else:
                        pullback_str = f"⏳ Aguardando pullback → esperar preço voltar"
                    bos_status = f"{bos_emoji} BOS {bos_type} | {pullback_str}"
                else:
                    bos_status = "⚪ Sem BOS ativo → sem rompimento recente"
                
                # Status dos Order Blocks com explicação
                ob_count = ind.get('order_blocks', 0)
                ob_summary = ind.get('ob_summary', 'Nenhum OB ativo')
                in_bullish_ob = ind.get('in_bullish_ob', False)
                in_bearish_ob = ind.get('in_bearish_ob', False)
                if in_bullish_ob:
                    ob_status = f"📦 {ob_summary} ⬅️ PREÇO EM OB DE COMPRA! Zona de suporte"
                elif in_bearish_ob:
                    ob_status = f"📦 {ob_summary} ⬅️ PREÇO EM OB DE VENDA! Zona de resistência"
                elif ob_count > 0:
                    ob_status = f"📦 {ob_summary} → zonas de interesse próximas"
                else:
                    ob_status = "📦 Sem Order Blocks ativos"
                
                # Status do filtro de notícias
                news_status = "✅ Livre"
                if news_filter:
                    can_trade, news_reason = news_filter.can_trade(config.SYMBOL)
                    if not can_trade:
                        news_status = f"🚫 {news_reason}"
                # Status do filtro de sessão
                session_status = "✅ Livre"
                if session_filter:
                    session_status = session_filter.get_session_status()
                
                # Status do spread
                spread_status = ""
                if spread_filter:
                    spread_filter.update_spread(config.SYMBOL)  # Atualiza histórico
                    spread_status = spread_filter.get_spread_status(config.SYMBOL)
                
                # Informações de saldo em USD e BRL
                account_info = adapter.get_account_info()
                balance_usd = account_info.get('balance', 0)
                profit_usd = account_info.get('profit', 0)
                
                usd_to_brl = getattr(config, 'USD_TO_BRL', 6.10)
                balance_brl = balance_usd * usd_to_brl
                
                # Avaliação de performance
                daily_stats = state_manager.get_daily_stats()
                daily_pnl = daily_stats.get('pnl', 0)
                win_rate = daily_stats.get('win_rate', 0)
                trades_count = daily_stats.get('trades_count', 0)
                
                if trades_count == 0:
                    performance = "⏳ Aguardando trades"
                elif win_rate >= 60:
                    performance = "🏆 Excelente!"
                elif win_rate >= 50:
                    performance = "👍 Bom"
                else:
                    performance = "⚠️ Melhorar"
                
                # Verifica se há setup próximo
                setup_status = "🔍 Buscando setup..."
                if rsi_val < 30:
                    setup_status = "🔵 RSI em sobrevenda - possível COMPRA em breve!"
                elif rsi_val > 70:
                    setup_status = "🔴 RSI em sobrecompra - possível VENDA em breve!"
                elif sma9 > sma21 and rsi_val < 50:
                    setup_status = "📈 Alta + RSI baixo - bom momento pra comprar"
                elif sma9 < sma21 and rsi_val > 50:
                    setup_status = "📉 Baixa + RSI alto - bom momento pra vender"
                
                # Explicação da tendência
                trend_explain = ""
                if sma9 > sma21:
                    trend_explain = " → média rápida acima da lenta = subindo"
                else:
                    trend_explain = " → média rápida abaixo da lenta = caindo"
                
                # Explicação das SMAs
                sma_diff = abs(sma9 - sma21)
                if sma_diff < 0.001:
                    sma_explain = " → médias muito próximas, possível reversão"
                else:
                    sma_explain = ""
                
                print()  # Nova linha antes do log
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"🔎 ANÁLISE DE MERCADO | {config.SYMBOL}")
                logger.info(f"💹 Preço: {signal.price:.5f} | Tendência: {trend}{trend_explain}")
                logger.info(f"📉 RSI: {rsi_val:.1f} | Zona: {rsi_zone}{rsi_explain}")
                logger.info(f"📈 SMA9: {sma9:.5f} | SMA21: {sma21:.5f}{sma_explain}")
                logger.info(f"{adx_status}{adx_explain}")
                logger.info(f"{vol_status}")
                logger.info(f"{struct_status}")
                logger.info(f"🎯 {bos_status}")
                logger.info(f"{ob_status}")
                logger.info(f"💰 Saldo: ${balance_usd:,.2f} (R${balance_brl:,.2f})")
                logger.info(f"📰 Notícias: {news_status}")
                logger.info(f"⏰ Sessão: {session_status}")
                if spread_status:
                    logger.info(f"💹 {spread_status}")
                logger.info(f"📋 Hoje: {trades_count} trades | W/L: {daily_stats.get('wins', 0)}/{daily_stats.get('losses', 0)} | P&L: ${daily_pnl:.2f}")
                logger.info(f"🎯 {setup_status}")
                logger.info(f"📈 Performance: {performance}")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                last_log_time = time.time()
            else:
                # Feedback visual entre heartbeats
                ind = signal.indicators
                rsi_val = ind.get('rsi', 0)
                trend = "📈" if ind.get('sma_fast', 0) > ind.get('sma_slow', 0) else "📉"
                rsi_emoji = "🔵" if rsi_val < 30 else ("🔴" if rsi_val > 70 else "⚪")
                print(f"\r{spin} {trend} {signal.price:.5f} | {rsi_emoji} RSI: {rsi_val:.1f} | 🔍 Buscando... | #{cycle_count}", end="", flush=True)

            # 5. Execução
            if signal.type != SignalType.HOLD:
                # Verifica filtro de sessão (Killzones) antes de operar
                if session_filter:
                    can_trade_session, session_reason = session_filter.can_trade(config.SYMBOL)
                    if not can_trade_session:
                        if time.time() - last_log_time > heartbeat_interval:
                            logger.warning(f"⏰ {session_reason}")
                            logger.info(f"📊 Status: {session_filter.get_session_status()}")
                        time.sleep(10)
                        continue
                
                # Verifica filtro de spread antes de operar
                if spread_filter:
                    can_trade_spread, spread_reason = spread_filter.can_trade(config.SYMBOL)
                    if not can_trade_spread:
                        if time.time() - last_log_time > heartbeat_interval:
                            logger.warning(f"💹 {spread_reason}")
                        time.sleep(10)
                        continue
                
                # Verifica filtro de notícias antes de operar
                if news_filter:
                    can_trade, news_reason = news_filter.can_trade(config.SYMBOL)
                    if not can_trade:
                        logger.warning(f"📰 {news_reason}")
                        time.sleep(10)
                        continue
                
                # Verifica filtro multi-timeframe (H1 deve concordar com M1)
                if history_manager and getattr(config, 'USE_MTF_FILTER', False):
                    h1_trend = history_manager.get_higher_timeframe_trend(config.SYMBOL)
                    
                    # BUY só se H1 está em alta, SELL só se H1 está em baixa
                    if signal.type == SignalType.BUY and h1_trend == "DOWN":
                        logger.warning(f"🚫 MTF Filter: Sinal de COMPRA bloqueado - H1 em BAIXA")
                        logger.info(f"   ↳ Explicação: Gráfico de 1 hora ainda caindo, comprar agora seria contra a tendência maior")
                        time.sleep(10)
                        continue
                    elif signal.type == SignalType.SELL and h1_trend == "UP":
                        logger.warning(f"🚫 MTF Filter: Sinal de VENDA bloqueado - H1 em ALTA")
                        logger.info(f"   ↳ Explicação: Gráfico de 1 hora ainda subindo, vender agora seria contra a tendência maior")
                        time.sleep(10)
                        continue
                    else:
                        logger.info(f"✅ MTF Filter: H1 confirma tendência ({h1_trend})")
                
                # 🤖 FILTRO ML (LightGBM) - Verifica probabilidade de sucesso
                if ml_filter and ml_filter.is_ready():
                    ind = signal.indicators
                    
                    # Prepara features para o modelo
                    ml_features = {
                        'sma_crossover': 1 if ind.get('sma_fast', 0) > ind.get('sma_slow', 0) else -1,
                        'price_vs_sma21': 1 if signal.price > ind.get('sma_slow', 0) else -1,
                        'rsi': ind.get('rsi', 50),
                        'rsi_zone': 1 if ind.get('rsi', 50) < 30 else (-1 if ind.get('rsi', 50) > 70 else 0),
                        'macd_signal': 1 if ind.get('macd', 0) > ind.get('macd_signal', 0) else -1,
                        'macd_histogram': ind.get('macd', 0) - ind.get('macd_signal', 0),
                        'adx': ind.get('adx', 0),
                        'adx_direction': 1 if ind.get('plus_di', 0) > ind.get('minus_di', 0) else -1,
                        'atr_percentile': ind.get('atr_percentile', 50),
                        'market_structure': ind.get('market_structure', 'RANGING'),
                        'bos_type': ind.get('bos_type', 'NONE'),
                        'bos_pullback_valid': 1 if ind.get('bos_pullback_valid', False) else 0,
                        'in_order_block': 1 if ind.get('in_bullish_ob', False) or ind.get('in_bearish_ob', False) else 0,
                        'volume_above_avg': 1  # Assume volume ok se chegou aqui
                    }
                    
                    ml_proba, ml_approved, ml_reason = ml_filter.predict(ml_features)
                    
                    if getattr(config, 'ML_LOG_PREDICTIONS', True):
                        logger.info(f"🤖 ML Filter: {ml_proba:.1%} probabilidade de sucesso")
                    
                    if not ml_approved:
                        logger.warning(f"🤖 {ml_reason}")
                        logger.info(f"   ↳ Sinal rejeitado pelo modelo ML - aguardando melhor oportunidade")
                        time.sleep(10)
                        continue
                    else:
                        logger.info(f"✅ {ml_reason}")
                
                print()  # Nova linha antes do log de execução
                current_price = signal.price
                sl_price = signal.sl
                tp_price = signal.tp
                
                # Cálculo da distância do SL em pontos
                sl_dist_points = abs(current_price - sl_price)
                
                # Calcular Lote Dinâmico (com limite de segurança)
                volume = risk_manager.calculate_lot_size(config.SYMBOL, sl_dist_points)
                
                # Calcula valores em dinheiro para o log
                usd_to_brl = getattr(config, 'USD_TO_BRL', 6.10)
                account_info = adapter.get_account_info()
                balance_usd = account_info.get('balance', 0)
                balance_brl = balance_usd * usd_to_brl
                
                # Calcula risco e lucro potencial
                # Para USDJPY: 1 pip = 0.01, valor por pip ≈ $6.25 por lote
                # Para EURUSD: 1 pip = 0.0001, valor por pip = $10 por lote
                symbol_info = adapter.get_symbol_info(config.SYMBOL)
                if symbol_info and symbol_info.get('digits', 5) == 3:
                    # Par JPY (3 casas decimais)
                    pips_sl = abs(current_price - sl_price) * 100  # 0.01 = 1 pip
                    pips_tp = abs(tp_price - current_price) * 100
                    valor_por_pip = volume * 6.25  # Aproximado para USDJPY
                else:
                    # Par normal (5 casas decimais)
                    pips_sl = abs(current_price - sl_price) * 10000  # 0.0001 = 1 pip
                    pips_tp = abs(tp_price - current_price) * 10000
                    valor_por_pip = volume * 10  # $10 por pip por lote
                
                risco_usd = pips_sl * valor_por_pip
                lucro_usd = pips_tp * valor_por_pip
                risco_brl = risco_usd * usd_to_brl
                lucro_brl = lucro_usd * usd_to_brl
                
                # Log detalhado da operação
                op_type = "🟢 COMPRA" if signal.type.name == "BUY" else "🔴 VENDA"
                acao = "subir" if signal.type.name == "BUY" else "cair"
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"🎯 SINAL DETECTADO!")
                logger.info(f"{op_type} | {config.SYMBOL}")
                logger.info(f"💡 Apostando que o preço vai {acao}")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"💰 QUANTO ESTOU APOSTANDO:")
                logger.info(f"   📦 Volume: {volume} lotes")
                logger.info(f"   💵 Saldo: ${balance_usd:,.2f} (R${balance_brl:,.2f})")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"📍 PREÇOS:")
                logger.info(f"   💹 Entrada: {current_price:.5f}")
                logger.info(f"   🛡️ Stop Loss: {sl_price:.5f} ({pips_sl:.1f} pips)")
                logger.info(f"   🎯 Take Profit: {tp_price:.5f} ({pips_tp:.1f} pips)")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"⚠️ RISCO vs RETORNO:")
                logger.info(f"   ❌ Se PERDER: -${risco_usd:.2f} (-R${risco_brl:.2f})")
                logger.info(f"   ✅ Se GANHAR: +${lucro_usd:.2f} (+R${lucro_brl:.2f})")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"📝 Motivo: {signal.comment}")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                success, ticket = adapter.execute_order(
                    symbol=config.SYMBOL,
                    signal_type=signal.type,
                    volume=volume,
                    sl=sl_price,
                    tp=tp_price,
                    comment=signal.comment
                )
                
                if success and ticket:
                    last_trade_time = time.time()
                    state_manager.set_last_trade_time(last_trade_time)
                    state_manager.add_position(ticket)
                    
                    # Rastreia tempo de abertura e score para saída inteligente
                    position_open_times[ticket] = time.time()
                    ind = signal.indicators
                    signal_score = ind.get('signal_score', 0)
                    position_scores[ticket] = signal_score
                    position_was_negative[ticket] = False
                    
                    # 🔊 Som de entrada
                    play_sound('entry')
                    
                    logger.info(f"✅ ORDEM EXECUTADA COM SUCESSO!")
                    logger.info(f"🎫 Ticket: {ticket}")
                    logger.info(f"⏱️ Cooldown de {cooldown_seconds}s iniciado")
                    
                    # Log da saída inteligente
                    if use_smart_exit:
                        logger.info(f"🧠 Smart Exit ATIVO: Score {signal_score}/9 | Aguardando lucro para sair")
                    
                    logger.info(state_manager.get_stats_summary())
                    
                    # Notifica via Telegram com score e Smart Money info
                    account_info = adapter.get_account_info()
                    ind = signal.indicators
                    signal_score = ind.get('signal_score', 0)
                    
                    # Prepara Smart Money info para Telegram
                    smart_money_info = {
                        'market_structure': ind.get('market_structure', 'RANGING'),
                        'bos_type': ind.get('bos_type', 'NONE'),
                        'bos_pullback_valid': ind.get('bos_pullback_valid', False),
                        'in_order_block': ind.get('in_bullish_ob', False) or ind.get('in_bearish_ob', False),
                        'ob_type': 'BULLISH' if ind.get('in_bullish_ob', False) else ('BEARISH' if ind.get('in_bearish_ob', False) else ''),
                        'adx': ind.get('adx', 0),
                        'session': session_filter.get_session_status() if session_filter else ''
                    }
                    
                    telegram.notify_order_executed(
                        order_type=signal.type.name,
                        symbol=config.SYMBOL,
                        price=current_price,
                        volume=volume,
                        sl=sl_price,
                        tp=tp_price,
                        ticket=ticket,
                        balance_usd=account_info.get('balance', 0),
                        usd_to_brl=getattr(config, 'USD_TO_BRL', 6.10),
                        signal_score=signal_score,
                        smart_money_info=smart_money_info
                    )
                else:
                    logger.error(f"❌ Falha ao executar ordem!")

            # Aguarda próximo ciclo
            time.sleep(10)

        except KeyboardInterrupt:
            logger.info("Bot paralisado pelo usuário.")
            telegram.notify_bot_stopped("Parado pelo usuário")
            break
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
            telegram.notify_error("Erro no Loop", str(e))
            time.sleep(5)

if __name__ == "__main__":
    main()
