import MetaTrader5 as mt5
import math
from ..utils.logger import setup_logger

logger = setup_logger("RiskManager")

class RiskManager:
    def __init__(self, exchange_adapter, config):
        self.adapter = exchange_adapter
        self.config = config

    def calculate_lot_size(self, symbol: str, sl_points: float) -> float:
        """
        Calcula o tamanho do lote baseado no risco percentual da conta.
        Fórmula: Lote = (Saldo * Risco%) / (StopLoss_Pontos * Valor_Do_Ponto)
        
        IMPORTANTE: Aplica limite máximo de lotes para segurança!
        Em modo conservador, usa lote fixo.
        """
        # Modo conservador: lote fixo
        if getattr(self.config, 'CONSERVATIVE_MODE', False):
            fixed_lot = getattr(self.config, 'FIXED_LOT_SIZE', 0.01)
            logger.info(f"🛡️ Modo Conservador: Lote fixo {fixed_lot}")
            return fixed_lot
        
        if sl_points <= 0:
            logger.warning("SL Points inválido para cálculo de lote. Usando volume fixo.")
            return self.config.VOLUME

        account = self.adapter.get_account_info()
        balance = account.get('balance', 0)
        
        if balance <= 0:
            logger.warning("Saldo inválido. Usando volume fixo.")
            return self.config.VOLUME

        risk_money = balance * (self.config.RISK_PER_TRADE_PERCENT / 100)
        
        # Obtém informações do símbolo
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"Não foi possível obter info do símbolo {symbol}")
            return self.config.VOLUME
            
        # Valor monetário de 1 ponto de variação para 1.0 lote
        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size
        
        if tick_size == 0 or tick_value == 0:
            logger.warning("tick_size ou tick_value inválido. Usando volume fixo.")
            return self.config.VOLUME

        # Quanto dinheiro perde se o preço andar sl_points com 1.0 lote?
        loss_per_1_lot = (sl_points / tick_size) * tick_value
        
        if loss_per_1_lot == 0:
            logger.warning("loss_per_1_lot = 0. Usando volume fixo.")
            return self.config.VOLUME
            
        lot_size = risk_money / loss_per_1_lot
        
        # Normalizar lote (step de volume)
        step_vol = symbol_info.volume_step
        lot_size = math.floor(lot_size / step_vol) * step_vol
        
        # Respeitar limites do símbolo
        lot_size = max(lot_size, symbol_info.volume_min)
        lot_size = min(lot_size, symbol_info.volume_max)
        
        # SEGURANÇA: Aplicar limite máximo configurado
        max_lot = getattr(self.config, 'MAX_LOT_SIZE', 1.0)
        if lot_size > max_lot:
            logger.warning(f"⚠️ Lote calculado ({lot_size:.2f}) excede MAX_LOT_SIZE ({max_lot}). Limitando.")
            lot_size = max_lot
        
        logger.info(f"📊 Risco: Saldo=${balance:.2f} | Arriscando ${risk_money:.2f} ({self.config.RISK_PER_TRADE_PERCENT:.1f}%) | Lote={lot_size:.2f}")
        return float(f"{lot_size:.2f}")

    def check_trailing_stop(self, position) -> bool:
        """
        Verifica e move o Trailing Stop se necessário.
        Retorna True se modificou.
        """
        if not self.config.USE_TRAILING_STOP:
            return False
            
        symbol = position.symbol
        ticket = position.ticket
        price_current = mt5.symbol_info_tick(symbol).bid if position.type == 1 else mt5.symbol_info_tick(symbol).ask # Se BUY (1), usa BID pra fechar. Se SELL, usa ASK.
        # Correção: type 0 é BUY, 1 é SELL no MT5 constants, mas na nossa Entity mapeamos.
        # Vamos usar a lógica direta do preço.
        
        # Pega preço atual do mercado
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return False
        
        current_sl = position.sl
        open_price = position.price_open
        
        # Lógica para COMPRA (BUY)
        if position.is_buy: # Assumindo property is_buy na Entity
            market_price = tick.bid
            # Se o lucro já superou o gatilho (Trigger)
            if market_price > (open_price + self.config.TRAILING_TRIGGER_POINTS):
                # Novo Stop proposto: Preço Atual - Degrau (Step)
                # Ou Preço Atual - Trigger (para garantir distância mínima)
                # Vamos usar: Novo SL = Preço Atual - Trigger
                proposed_sl = market_price - self.config.TRAILING_TRIGGER_POINTS
                
                # Só move se for PRA CIMA (Proteger mais) e maior que o SL atual + um passo minimo
                if proposed_sl > (current_sl + self.config.TRAILING_STEP_POINTS):
                    return self.adapter.modify_position(ticket, sl=proposed_sl, tp=position.tp)

        # Lógica para VENDA (SELL)
        else:
            market_price = tick.ask
            # Se o preço caiu abaixo da entrada (lucro)
            if market_price < (open_price - self.config.TRAILING_TRIGGER_POINTS):
                proposed_sl = market_price + self.config.TRAILING_TRIGGER_POINTS
                
                # Só move se for PRA BAIXO (Proteger mais) e menor que o SL atual
                if current_sl == 0 or proposed_sl < (current_sl - self.config.TRAILING_STEP_POINTS):
                    return self.adapter.modify_position(ticket, sl=proposed_sl, tp=position.tp)
                    
        return False

    def check_smart_exit(self, position, signal_score: int = 5, position_open_time: float = None, was_negative: bool = False) -> dict:
        """
        Verifica se deve sair da posição usando lógica inteligente.
        
        Retorna:
        {
            'should_exit': bool,
            'reason': str,
            'profit': float
        }
        
        Lógica:
        1. Se lucro >= mínimo configurado → SAIR
        2. Se estava negativo e voltou positivo → SAIR (recuperação)
        3. Se negativo por muito tempo → SAIR (timeout)
        4. Se perda > X% do capital → SAIR (emergência)
        5. Se score alto e lucro bom → deixar correr até TP
        """
        if not getattr(self.config, 'USE_SMART_EXIT', False):
            return {'should_exit': False, 'reason': 'Smart Exit desativado', 'profit': 0}
        
        import time
        
        profit = position.profit
        min_profit_usd = getattr(self.config, 'SMART_EXIT_MIN_PROFIT_USD', 0.50)
        wait_negative_min = getattr(self.config, 'SMART_EXIT_WAIT_NEGATIVE_MINUTES', 30)
        emergency_loss_pct = getattr(self.config, 'SMART_EXIT_EMERGENCY_LOSS_PERCENT', 30)
        high_confidence = getattr(self.config, 'SMART_EXIT_HIGH_CONFIDENCE_SCORE', 7)
        take_on_recovery = getattr(self.config, 'SMART_EXIT_TAKE_PROFIT_ON_RECOVERY', True)
        
        # Pega saldo da conta
        account = self.adapter.get_account_info()
        balance = account.get('balance', 10000)
        
        # Se usando capital simulado
        if getattr(self.config, 'USE_SIMULATED_CAPITAL', False):
            balance = getattr(self.config, 'SIMULATED_CAPITAL_USD', 25.0)
        
        result = {
            'should_exit': False,
            'reason': '',
            'profit': profit
        }
        
        # 1. EMERGÊNCIA: Perda muito grande (% do capital)
        if profit < 0:
            loss_percent = abs(profit) / balance * 100
            if loss_percent >= emergency_loss_pct:
                result['should_exit'] = True
                result['reason'] = f'🚨 EMERGÊNCIA: Perda de {loss_percent:.1f}% do capital!'
                logger.warning(result['reason'])
                return result
        
        # 2. Se score ALTO e no lucro → deixa correr até TP
        if signal_score >= high_confidence and profit > 0:
            result['reason'] = f'💪 Score alto ({signal_score}/9) - deixando correr até TP'
            return result
        
        # 3. Se no LUCRO e >= mínimo → SAIR
        if profit >= min_profit_usd:
            result['should_exit'] = True
            result['reason'] = f'✅ Lucro de ${profit:.2f} >= mínimo ${min_profit_usd:.2f}'
            logger.info(f"🎯 SMART EXIT: {result['reason']}")
            return result
        
        # 4. Se estava negativo e voltou positivo → SAIR (recuperação)
        # IMPORTANTE: Só sai se JÁ ESTEVE negativo antes (was_negative=True)
        if take_on_recovery and was_negative and profit > 0:
            result['should_exit'] = True
            result['reason'] = f'🔄 Recuperação! Estava negativo, agora ${profit:.2f}'
            logger.info(f"🎯 SMART EXIT: {result['reason']}")
            return result
        
        # 5. Se negativo por muito tempo → SAIR (timeout)
        if profit < 0 and position_open_time:
            minutes_open = (time.time() - position_open_time) / 60
            if minutes_open >= wait_negative_min:
                result['should_exit'] = True
                result['reason'] = f'⏰ Timeout: {minutes_open:.0f}min negativo (max: {wait_negative_min}min)'
                logger.warning(f"🎯 SMART EXIT: {result['reason']}")
                return result
            else:
                result['reason'] = f'⏳ Aguardando recuperação ({minutes_open:.0f}/{wait_negative_min}min)'
        
        # 6. Se negativo mas dentro do tempo → ESPERAR
        if profit < 0:
            result['reason'] = f'⏳ P&L negativo (${profit:.2f}), aguardando voltar ao positivo...'
        
        return result
