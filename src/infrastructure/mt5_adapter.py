import MetaTrader5 as mt5
import pandas as pd
import time
from typing import List, Optional
from ..domain.interfaces import IExchangeAdapter
from ..domain.entities import SignalType, Position
from ..utils.logger import setup_logger

logger = setup_logger("MT5Adapter")

class MT5Adapter(IExchangeAdapter):
    def __init__(self, login=None, password=None, server=None):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self._last_connection_check = 0
        self._connection_check_interval = 30  # Verifica conexão a cada 30s

    def connect(self) -> bool:
        """Estabelece conexão com o terminal MetaTrader 5"""
        try:
            # Se credenciais não forem fornecidas, tenta inicializar sem elas (pega a sessão ativa)
            if not self.login or not self.password:
                init_result = mt5.initialize()
            else:
                init_result = mt5.initialize(login=self.login, password=self.password, server=self.server)

            if not init_result:
                logger.error(f"Falha na inicialização do MT5: {mt5.last_error()}")
                self.connected = False
                return False
            
            # Verifica se está conectado ao servidor da corretora
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                logger.error("Não foi possível obter informações do terminal.")
                return False

            logger.info(f"Conectado ao MT5. Conta: {mt5.account_info().login}, Servidor: {mt5.account_info().server}")
            self.connected = True
            self._last_connection_check = time.time()
            return True
        except Exception as e:
            logger.critical(f"Erro crítico na conexão: {e}")
            return False

    def is_connected(self) -> bool:
        """Verifica se ainda está conectado ao MT5"""
        # Evita verificar muito frequentemente
        if time.time() - self._last_connection_check < self._connection_check_interval:
            return self.connected
        
        self._last_connection_check = time.time()
        
        try:
            # Tenta obter info da conta como teste de conexão
            account_info = mt5.account_info()
            if account_info is None:
                self.connected = False
                return False
            
            # Verifica se terminal está conectado ao servidor
            terminal_info = mt5.terminal_info()
            if terminal_info is None or not terminal_info.connected:
                self.connected = False
                return False
            
            self.connected = True
            return True
        except Exception as e:
            logger.warning(f"Erro ao verificar conexão: {e}")
            self.connected = False
            return False

    def reconnect(self, max_attempts: int = 5, base_delay: int = 10) -> bool:
        """Tenta reconectar ao MT5 com backoff exponencial"""
        logger.warning("🔄 Conexão perdida! Iniciando reconexão...")
        
        # Primeiro, tenta desconectar limpo
        self.disconnect()
        
        for attempt in range(1, max_attempts + 1):
            delay = base_delay * (2 ** (attempt - 1))  # Backoff exponencial: 10, 20, 40, 80, 160s
            delay = min(delay, 300)  # Máximo 5 minutos
            
            logger.info(f"🔄 Tentativa {attempt}/{max_attempts} de reconexão...")
            
            if self.connect():
                logger.info(f"✅ Reconectado com sucesso na tentativa {attempt}!")
                return True
            
            if attempt < max_attempts:
                logger.warning(f"❌ Falha na tentativa {attempt}. Aguardando {delay}s...")
                time.sleep(delay)
        
        logger.critical(f"❌ Falha ao reconectar após {max_attempts} tentativas!")
        return False

    def disconnect(self):
        """Desconecta do MT5 de forma limpa"""
        try:
            mt5.shutdown()
            self.connected = False
            logger.info("Desconectado do MT5.")
        except Exception as e:
            logger.warning(f"Erro ao desconectar: {e}")

    def get_data(self, symbol: str, timeframe, n_bars: int = 100) -> pd.DataFrame:
        if not self.connected: self.connect()
        
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_bars)
        if rates is None:
            logger.warning(f"Não foi possível obter dados para {symbol}")
            return pd.DataFrame()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_tick_info(self, symbol: str) -> dict:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {}
        return {"bid": tick.bid, "ask": tick.ask, "last": tick.last}

    def get_symbol_info(self, symbol: str) -> dict:
        """Retorna informações do símbolo (digits, point, etc.)"""
        info = mt5.symbol_info(symbol)
        if info is None:
            return {}
        return {
            "digits": info.digits,
            "point": info.point,
            "trade_tick_size": info.trade_tick_size,
            "trade_tick_value": info.trade_tick_value,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "trade_stops_level": info.trade_stops_level,
            "spread": info.spread
        }

    def get_open_positions(self, symbol: str = None) -> List[Position]:
        if not self.connected: self.connect()
        
        if symbol:
            mt5_positions = mt5.positions_get(symbol=symbol)
        else:
            mt5_positions = mt5.positions_get()

        if mt5_positions is None:
            return []

        positions = []
        for p in mt5_positions:
            pos_type = SignalType.BUY if p.type == mt5.POSITION_TYPE_BUY else SignalType.SELL
            positions.append(Position(
                ticket=p.ticket,
                symbol=p.symbol,
                type=pos_type,
                volume=p.volume,
                price_open=p.price_open,
                sl=p.sl,
                tp=p.tp,
                profit=p.profit,
                comment=p.comment,
                time=p.time  # Timestamp de abertura
            ))
        return positions

    def get_account_info(self) -> dict:
        info = mt5.account_info()
        if info is None: return {}
        return {
            "balance": info.balance,
            "equity": info.equity,
            "profit": info.profit
        }

    def execute_order(self, symbol: str, signal_type: SignalType, volume: float, sl: float = 0.0, tp: float = 0.0, comment: str = "") -> tuple:
        """Executa ordem e retorna (sucesso, ticket)"""
        if not self.connected: self.connect()
        
        # Verifica se o símbolo existe e está disponível
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"❌ Símbolo '{symbol}' NÃO EXISTE no MT5!")
            logger.error(f"   Verifique o nome correto do símbolo na sua corretora.")
            return (False, None)
        
        if not symbol_info.visible:
            # Tenta tornar visível
            if not mt5.symbol_select(symbol, True):
                logger.error(f"❌ Não foi possível selecionar o símbolo '{symbol}'")
                return (False, None)
        
        # Define tipo de ordem e preço
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"❌ Não foi possível obter cotação para '{symbol}'")
            return (False, None)
            
        if signal_type == SignalType.BUY:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        elif signal_type == SignalType.SELL:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            return (False, None)

        # Monta requisição
        # Tenta descobrir o filling mode correto
        filling_mode = mt5.ORDER_FILLING_FOK # Padrão mais comum
        if symbol_info:
             # Verifica quais modos são suportados pelo símbolo
             # filling_mode flags: 1 (FOK), 2 (IOC)
             filling_mode = mt5.ORDER_FILLING_FOK # Default
             
             # Tenta usar o que estiver disponível
             filling_flags = symbol_info.filling_mode
             
             if filling_flags == 1: # Somente FOK
                 filling_mode = mt5.ORDER_FILLING_FOK
             elif filling_flags == 2: # Somente IOC
                 filling_mode = mt5.ORDER_FILLING_IOC
             elif filling_flags == 3: # FOK e IOC
                 filling_mode = mt5.ORDER_FILLING_FOK # Prefere FOK
             else:
                 # Se for 0 ou outro, tenta ORDER_FILLING_RETURN (padrão exchange)
                 filling_mode = mt5.ORDER_FILLING_RETURN
        
        # Sanitiza o comment - MT5 só aceita ASCII básico e tem limite de 31 caracteres
        # Remove TUDO que não seja letra, número ou espaço
        try:
            # Força encoding ASCII, remove caracteres inválidos
            comment_str = str(comment).encode('ascii', 'ignore').decode('ascii')
            # Remove TODOS os caracteres especiais - só permite letras, números e espaço
            safe_comment = ''.join(c for c in comment_str if c.isalnum() or c == ' ')
            # Remove espaços duplos
            while '  ' in safe_comment:
                safe_comment = safe_comment.replace('  ', ' ')
            # Limita a 20 caracteres para garantir (MT5 é sensível)
            safe_comment = safe_comment[:20].strip()
        except:
            safe_comment = ""
        
        # Fallback simples se ficar vazio ou muito curto
        if len(safe_comment) < 3:
            safe_comment = "Bot"
        
        logger.debug(f"Comment sanitizado: {safe_comment}")
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 20240101, # Ideal vir do config
            "comment": safe_comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        # Envia ordem
        result = mt5.order_send(request)
        
        # Verifica se result é None (erro de conexão ou símbolo inválido)
        if result is None:
            last_error = mt5.last_error()
            logger.error(f"❌ order_send retornou None! Erro MT5: {last_error}")
            logger.error(f"   Verifique: 1) MT5 conectado? 2) Símbolo '{symbol}' existe? 3) Conta tem permissão?")
            return (False, None)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Erro ao enviar ordem ({symbol}, {signal_type.name}): {result.comment} (Retcode: {result.retcode})")
            return (False, None)
        
        logger.info(f"Ordem EXECUTADA com sucesso: {signal_type.name} {volume} lots em {price}. Ticket: {result.order}")
        return (True, result.order)

    def modify_position(self, ticket: int, sl: float, tp: float) -> bool:
        """Modifica SL e TP de uma posição aberta"""
        # Busca a posição para validar
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.warning(f"Posição {ticket} não encontrada para modificação.")
            return False
        
        position = positions[0]
        symbol = position.symbol
        
        # Pega info do símbolo para validar distância mínima
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"Não foi possível obter info do símbolo {symbol}")
            return False
        
        # Distância mínima de stops (STOP_LEVEL) em pontos
        stop_level = symbol_info.trade_stops_level
        point = symbol_info.point
        min_distance = stop_level * point
        
        # Se stop_level é 0, usa um mínimo seguro (10 pips)
        if min_distance == 0:
            # Para USDJPY (3 dígitos), 10 pips = 0.100
            # Para EURUSD (5 dígitos), 10 pips = 0.00100
            if symbol_info.digits == 3:
                min_distance = 0.100  # 10 pips para pares JPY
            else:
                min_distance = 0.00100  # 10 pips para outros pares
        
        # Pega preço atual
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.error(f"Não foi possível obter tick de {symbol}")
            return False
        
        current_price = tick.bid if position.type == 0 else tick.ask  # BUY usa bid, SELL usa ask
        
        # Valida distância do SL
        sl_distance = abs(current_price - sl)
        if sl_distance < min_distance:
            # SL muito perto, não modifica (silenciosamente)
            return False
        
        # Valida distância do TP
        tp_distance = abs(current_price - tp)
        if tp_distance < min_distance:
            # TP muito perto, não modifica (silenciosamente)
            return False
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": round(sl, symbol_info.digits),
            "tp": round(tp, symbol_info.digits),
        }
        
        result = mt5.order_send(request)
        if result is None:
            logger.error(f"Falha ao modificar posição {ticket}: order_send retornou None")
            return False
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Falha ao modificar posição {ticket}: {result.comment}")
            return False
            
        logger.info(f"Posição {ticket} modificada. Novo SL: {sl}, Novo TP: {tp}")
        return True

    def close_position(self, ticket: int) -> bool:
        # Lógica para fechar posição específica pelo ticket
        # No MT5, fechar é abrir uma ordem contrária com o mesmo volume
        # Simplificação: Fechamento via trade_action_deal com posição oposta
        # Nota: Uma implementação completa requereria buscar a posição para saber o volume e tipo.
        
        # Busca a posição para pegar detalhes
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.warning(f"Posição {ticket} não encontrada para fechamento.")
            return False
        
        position = positions[0]
        symbol = position.symbol
        volume = position.volume
        
        # Tipo contrário
        order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(symbol).ask

        # Detecta o filling mode suportado pelo símbolo
        symbol_info = mt5.symbol_info(symbol)
        filling_mode = mt5.ORDER_FILLING_IOC  # Padrão mais compatível
        
        if symbol_info is not None:
            # Valores: FOK=1, IOC=2, RETURN=3 (bits no filling_mode)
            if symbol_info.filling_mode & 1:  # FOK
                filling_mode = mt5.ORDER_FILLING_FOK
            elif symbol_info.filling_mode & 2:  # IOC
                filling_mode = mt5.ORDER_FILLING_IOC
            else:
                filling_mode = mt5.ORDER_FILLING_RETURN

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "position": ticket, # Importante para fechar a posição específica
            "price": price,
            "deviation": 20,
            "magic": 20240101,
            "comment": "Close Position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Erro ao fechar posição {ticket}: {result.comment}")
            return False
            
        logger.info(f"Posição {ticket} FECHADA com sucesso.")
        return True

    def close_all_positions(self, symbol: str) -> bool:
        positions = self.get_open_positions(symbol)
        success = True
        for pos in positions:
            if not self.close_position(pos.ticket):
                success = False
        return success

    def get_closed_trade_info(self, ticket: int) -> dict:
        """Busca informações de um trade fechado no histórico do MT5"""
        try:
            from datetime import datetime, timedelta
            
            # Busca deals (execuções) das últimas 24h
            today = datetime.now()
            from_date = today - timedelta(days=1)
            
            # Busca todos os deals
            deals = mt5.history_deals_get(from_date, today)
            if deals is None or len(deals) == 0:
                logger.warning(f"Nenhum deal encontrado no histórico para ticket {ticket}")
                return None
            
            # Procura deals relacionados a este position_id
            entry_deal = None
            exit_deal = None
            total_profit = 0
            
            for deal in deals:
                if deal.position_id == ticket:
                    if deal.entry == mt5.DEAL_ENTRY_IN:
                        entry_deal = deal
                    elif deal.entry == mt5.DEAL_ENTRY_OUT:
                        exit_deal = deal
                        total_profit = deal.profit + deal.commission + deal.swap
            
            if exit_deal:
                trade_type = "SELL" if exit_deal.type == mt5.DEAL_TYPE_SELL else "BUY"
                # Se fechou com SELL, a posição original era BUY e vice-versa
                original_type = "BUY" if trade_type == "SELL" else "SELL"
                
                result = {
                    "ticket": ticket,
                    "symbol": exit_deal.symbol,
                    "type": original_type,
                    "volume": exit_deal.volume,
                    "entry_price": entry_deal.price if entry_deal else 0,
                    "exit_price": exit_deal.price,
                    "pnl": total_profit,
                    "commission": exit_deal.commission,
                    "swap": exit_deal.swap,
                    "exit_time": datetime.fromtimestamp(exit_deal.time).isoformat()
                }
                
                logger.info(f"📝 Trade fechado encontrado: {original_type} | P&L: ${total_profit:.2f}")
                return result
            
            logger.warning(f"Deal de saída não encontrado para ticket {ticket}")
            return None
            
        except Exception as e:
            logger.warning(f"Erro ao buscar info do trade {ticket}: {e}")
            return None
