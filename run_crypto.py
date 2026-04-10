#!/usr/bin/env python3
"""
🪙 Run Crypto - Bot Unificado para Trading de Criptomoedas

Analisa BTC, ETH e SOL simultaneamente e executa ordem
no ativo com melhor oportunidade.

Uso:
    python run_crypto.py
"""

import sys
import os
import time
import winsound
from datetime import datetime

# Adiciona diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config_crypto as config
from src.infrastructure.mt5_adapter import MT5Adapter
from src.strategies.hybrid_strategy import HybridStrategy
from src.strategies.risk_manager import RiskManager
from src.utils.state_manager import StateManager
from src.utils.telegram_notifier import TelegramNotifier
from src.utils.spread_filter import SpreadFilter
from src.utils.ml_filter import MLFilter
from src.utils.auto_trainer import UniversalAutoTrainer
from src.utils.crypto_selector import CryptoSelector
from src.utils.logger import setup_logger
from src.domain.entities import SignalType

logger = setup_logger("CryptoBot")


def play_sound(sound_type: str):
    """Toca som de notificação."""
    try:
        sounds = {
            'entry': (800, 200),
            'win': (1000, 300),
            'loss': (400, 300),
            'alert': (600, 150)
        }
        freq, duration = sounds.get(sound_type, (500, 100))
        winsound.Beep(freq, duration)
    except:
        pass


def main():
    """Loop principal do bot multi-crypto."""
    
    logger.info("=" * 60)
    logger.info("🪙 CRYPTO BOT v1.0 - Multi-Asset Trading")
    logger.info("=" * 60)
    logger.info(f"   Ativos: {', '.join(config.CRYPTO_ASSETS.keys())}")
    logger.info(f"   Timeframe: M1")
    logger.info(f"   Modo: {'AGRESSIVO' if config.AGGRESSIVE_MODE else 'NORMAL'}")
    logger.info("=" * 60)
    
    # 1. Conecta ao MT5
    adapter = MT5Adapter(config)
    if not adapter.connect():
        logger.error("❌ Falha ao conectar ao MT5!")
        return
    
    logger.info("✅ Conectado ao MT5")
    
    # 2. Auto-treina modelo universal
    if config.ML_AUTO_TRAIN:
        logger.info("🤖 Iniciando Auto-Trainer Universal...")
        
        symbols = list(config.CRYPTO_ASSETS.keys())
        auto_trainer = UniversalAutoTrainer(
            symbols=symbols,
            timeframe=config.TIMEFRAME,
            history_months=config.HISTORY_MONTHS
        )
        
        success, model_path, threshold = auto_trainer.run(adapter)
        
        if success:
            config.ML_MODEL_PATH = model_path
            config.ML_CONFIDENCE_THRESHOLD = threshold
            logger.info(f"✅ Modelo universal pronto: {model_path}")
        else:
            logger.warning("⚠️ Auto-treino falhou, usando configuração padrão")
    
    # 3. Inicializa componentes
    
    # ML Filter
    ml_filter = None
    if config.USE_ML_FILTER:
        project_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(project_dir, config.ML_MODEL_PATH)
        
        if os.path.exists(model_path):
            ml_filter = MLFilter(
                model_path=model_path,
                min_confidence=config.ML_CONFIDENCE_THRESHOLD
            )
            logger.info(f"🤖 ML Filter ATIVO - Threshold: {config.ML_CONFIDENCE_THRESHOLD:.0%}")
        else:
            logger.warning(f"⚠️ Modelo ML não encontrado: {model_path}")
    
    # Spread Filter
    spread_filter = None
    if config.USE_SPREAD_FILTER:
        spread_filter = SpreadFilter(
            max_spread_multiplier=config.MAX_SPREAD_MULTIPLIER,
            max_spread_absolute=config.MAX_SPREAD_ABSOLUTE,
            history_size=config.SPREAD_HISTORY_SIZE
        )
        logger.info("💹 Spread Filter ATIVO")
    
    # Strategy (usa config padrão, será ajustado por ativo)
    strategy = HybridStrategy(config, adapter)
    
    # Crypto Selector
    crypto_selector = CryptoSelector(
        config=config,
        adapter=adapter,
        strategy=strategy,
        ml_filter=ml_filter,
        spread_filter=spread_filter
    )
    logger.info("🔍 Crypto Selector ATIVO")
    
    # Risk Manager
    risk_manager = RiskManager(adapter, config)
    
    # State Manager
    state_manager = StateManager(config.STATE_FILE)
    
    # Telegram
    telegram = TelegramNotifier(
        bot_token=config.TELEGRAM_BOT_TOKEN,
        chat_id=config.TELEGRAM_CHAT_ID
    )
    
    # Notifica início
    telegram.notify_bot_started(
        symbol="MULTI-CRYPTO",
        mode="HÍBRIDO v3.0",
        filters_config={
            'risk_percent': config.RISK_PER_TRADE_PERCENT,
            'assets': list(config.CRYPTO_ASSETS.keys())
        }
    )
    
    # 4. Parâmetros do loop
    max_positions = config.MAX_OPEN_POSITIONS
    cooldown_seconds = config.MIN_SECONDS_BETWEEN_TRADES
    heartbeat_interval = config.HEARTBEAT_INTERVAL
    
    last_log_time = time.time() - heartbeat_interval - 1
    last_trade_time = state_manager.get_last_trade_time()
    cycle_count = 0
    
    # Tracking de posições
    position_open_times = {}
    position_scores = {}
    position_symbols = {}
    
    logger.info("=" * 60)
    logger.info("🚀 BOT INICIADO - Monitorando BTC, ETH, SOL")
    logger.info("=" * 60)
    
    # 5. Loop principal
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    try:
        while True:
            cycle_count += 1
            spin = spinner[cycle_count % len(spinner)]
            
            # Verifica posições abertas em TODOS os ativos
            all_positions = []
            for symbol in config.CRYPTO_ASSETS.keys():
                positions = adapter.get_open_positions(symbol)
                all_positions.extend(positions)
            
            # Se tem posição aberta, monitora
            if len(all_positions) >= max_positions:
                pos = all_positions[0]
                profit_emoji = "💚" if pos.profit >= 0 else "💔"
                profit_brl = pos.profit * config.USD_TO_BRL
                
                if time.time() - last_log_time > heartbeat_interval:
                    print()
                    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    logger.info(f"📊 MONITORANDO POSIÇÃO: {pos.symbol}")
                    pos_type = "🟢 COMPRADO" if pos.is_buy else "🔴 VENDIDO"
                    logger.info(f"{pos_type} | Entrada: {pos.price_open:.5f}")
                    logger.info(f"{profit_emoji} P&L: ${pos.profit:.2f} (R${profit_brl:.2f})")
                    logger.info(f"🎯 SL: {pos.sl:.5f} | TP: {pos.tp:.5f}")
                    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    last_log_time = time.time()
                else:
                    print(f"\r{spin} {pos.symbol} | {profit_emoji} ${pos.profit:.2f} | Ciclo #{cycle_count}", end="", flush=True)
                
                # Verifica trailing stop
                risk_manager.check_trailing_stop(pos)
                
                time.sleep(10)
                continue
            
            # Verifica cooldown
            time_since_last = time.time() - last_trade_time
            if last_trade_time > 0 and time_since_last < cooldown_seconds:
                remaining = int(cooldown_seconds - time_since_last)
                print(f"\r{spin} Cooldown: {remaining}s | Ciclo #{cycle_count}", end="", flush=True)
                time.sleep(10)
                continue
            
            # Analisa todos os ativos e seleciona o melhor
            best_opportunity = crypto_selector.select_best()
            
            # Log de heartbeat
            if time.time() - last_log_time > heartbeat_interval:
                print()
                logger.info(crypto_selector.get_analysis_summary())
                
                if best_opportunity:
                    logger.info(f"🎯 SELECIONADO: {best_opportunity.symbol}")
                    logger.info(f"   Score: {best_opportunity.combined_score:.2f} | ML: {best_opportunity.ml_probability:.0%}")
                else:
                    logger.info("⏳ Aguardando oportunidade...")
                
                # Info de saldo
                account = adapter.get_account_info()
                balance_usd = account.get('balance', 0)
                balance_brl = balance_usd * config.USD_TO_BRL
                logger.info(f"💰 Saldo: ${balance_usd:,.2f} (R${balance_brl:,.2f})")
                logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                last_log_time = time.time()
            else:
                if best_opportunity:
                    print(f"\r{spin} 🎯 {best_opportunity.symbol} | Score: {best_opportunity.combined_score:.2f} | Ciclo #{cycle_count}", end="", flush=True)
                else:
                    print(f"\r{spin} 🔍 Analisando... | Ciclo #{cycle_count}", end="", flush=True)
            
            # Executa se tiver oportunidade válida
            if best_opportunity and best_opportunity.is_valid:
                opp = best_opportunity
                signal = opp.signal
                symbol = opp.symbol
                asset_config = config.CRYPTO_ASSETS[symbol]
                
                # Verifica spread específico do ativo
                if spread_filter:
                    spread_filter.update_spread(symbol)
                    can_trade, spread_reason = spread_filter.can_trade(symbol)
                    # Usa spread_max específico do ativo
                    current_spread = spread_filter._get_current_spread(symbol)
                    if current_spread and current_spread > asset_config['spread_max']:
                        logger.warning(f"💹 Spread alto para {symbol}: {current_spread} > {asset_config['spread_max']}")
                        time.sleep(10)
                        continue
                
                print()
                logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"🎯 EXECUTANDO ORDEM: {symbol}")
                logger.info(f"   Tipo: {signal.type.name}")
                logger.info(f"   Score: {opp.signal_score}/9 | ML: {opp.ml_probability:.0%}")
                logger.info(f"   Combined: {opp.combined_score:.2f}")
                logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # Calcula volume
                sl_dist = abs(signal.price - signal.sl)
                volume = risk_manager.calculate_lot_size(symbol, sl_dist)
                
                # Limita ao max_lot do ativo
                max_lot = asset_config.get('max_lot', config.MAX_LOT_SIZE)
                min_lot = asset_config.get('min_lot', 0.01)
                volume = max(min_lot, min(volume, max_lot))
                
                # Executa ordem
                success, ticket = adapter.execute_order(
                    symbol=symbol,
                    signal_type=signal.type,
                    volume=volume,
                    sl=signal.sl,
                    tp=signal.tp,
                    comment=f"Crypto {signal.type.name} S{opp.signal_score}"
                )
                
                if success and ticket:
                    last_trade_time = time.time()
                    state_manager.set_last_trade_time(last_trade_time)
                    state_manager.add_position(ticket)
                    
                    position_open_times[ticket] = time.time()
                    position_scores[ticket] = opp.signal_score
                    position_symbols[ticket] = symbol
                    
                    play_sound('entry')
                    
                    logger.info(f"✅ ORDEM EXECUTADA!")
                    logger.info(f"   Ticket: {ticket}")
                    logger.info(f"   Volume: {volume}")
                    logger.info(f"   Cooldown: {cooldown_seconds}s")
                    
                    # Notifica Telegram
                    account = adapter.get_account_info()
                    telegram.notify_order_executed(
                        order_type=signal.type.name,
                        symbol=symbol,
                        price=signal.price,
                        volume=volume,
                        sl=signal.sl,
                        tp=signal.tp,
                        ticket=ticket,
                        balance_usd=account.get('balance', 0),
                        usd_to_brl=config.USD_TO_BRL,
                        signal_score=opp.signal_score
                    )
                else:
                    logger.error(f"❌ Falha ao executar ordem!")
            
            time.sleep(10)
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Bot parado pelo usuário")
        telegram.notify_bot_stopped("Parado pelo usuário")
    
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        telegram.notify_error("Erro Fatal", str(e))
        raise


if __name__ == "__main__":
    main()
