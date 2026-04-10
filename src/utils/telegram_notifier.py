import requests
from typing import Optional, List, Dict
from datetime import datetime
from .logger import setup_logger

logger = setup_logger("Telegram")

class TelegramNotifier:
    """Envia notificações para o Telegram - Smart Money Edition v2.3"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        self.base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else None
        
        if not self.enabled:
            logger.info("📱 Telegram não configurado. Notificações desativadas.")
        else:
            logger.info("📱 Telegram configurado. Notificações ativadas.")
    
    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Envia mensagem para o Telegram"""
        if not self.enabled:
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram API error: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.warning("Telegram timeout - mensagem não enviada")
            return False
        except Exception as e:
            logger.warning(f"Erro ao enviar Telegram: {e}")
            return False
    
    # --- Métodos de Notificação Específicos ---
    
    def notify_bot_started(self, symbol: str, mode: str, filters_config: dict = None):
        """Notifica que o bot iniciou com informações Smart Money"""
        
        # Filtros ativos
        filters_text = ""
        if filters_config:
            filters_text = "\n🎯 <b>Filtros Smart Money:</b>\n"
            if filters_config.get('session_filter', False):
                filters_text += "✅ Killzones (Londres/NY)\n"
            if filters_config.get('spread_filter', False):
                filters_text += "✅ Spread Filter\n"
            if filters_config.get('adx_filter', False):
                filters_text += "✅ ADX Filter\n"
            if filters_config.get('anti_stop_hunt', False):
                filters_text += "✅ Anti-Stop Hunt\n"
            if filters_config.get('volatility_filter', False):
                filters_text += "✅ Volatility Filter\n"
            if filters_config.get('market_structure', False):
                filters_text += "✅ Market Structure\n"
            if filters_config.get('bos_pullback', False):
                filters_text += "✅ BOS + Pullback\n"
            if filters_config.get('order_blocks', False):
                filters_text += "✅ Order Blocks\n"
        
        msg = f"""
🤖 <b>Bot PRO 2.3 - Smart Money Edition</b>

📊 Ativo: <code>{symbol}</code>
⚙️ Modo: {mode}
📈 Score: Mínimo 3/9 confirmações
{filters_text}
🕐 Iniciado: {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
    
    def notify_bot_stopped(self, reason: str = "Manual"):
        """Notifica que o bot parou"""
        msg = f"""
🛑 <b>Bot Parado</b>

📝 Motivo: {reason}
🕐 Hora: {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
    
    def notify_order_executed(self, order_type: str, symbol: str, price: float, 
                              volume: float, sl: float, tp: float, ticket: int,
                              balance_usd: float = 0, usd_to_brl: float = 6.10,
                              signal_score: int = 0, confirmations: list = None,
                              smart_money_info: dict = None):
        """Notifica ordem executada com informações claras em português"""
        emoji = "🟢" if order_type == "BUY" else "🔴"
        acao = "COMPRA" if order_type == "BUY" else "VENDA"
        direcao = "SUBIR" if order_type == "BUY" else "CAIR"
        balance_brl = balance_usd * usd_to_brl
        
        # Detecta se é par JPY (3 casas decimais) ou normal (5 casas)
        is_jpy = "JPY" in symbol
        
        if is_jpy:
            # Par JPY: 1 pip = 0.01
            pips_risco = abs(price - sl) * 100
            pips_lucro = abs(tp - price) * 100
            valor_por_pip = volume * 6.25  # Aproximado para USDJPY
        else:
            # Par normal: 1 pip = 0.0001
            pips_risco = abs(price - sl) * 10000
            pips_lucro = abs(tp - price) * 10000
            valor_por_pip = volume * 10
        
        risco_usd = pips_risco * valor_por_pip
        lucro_usd = pips_lucro * valor_por_pip
        risco_brl = risco_usd * usd_to_brl
        lucro_brl = lucro_usd * usd_to_brl
        
        # Score label
        if signal_score >= 7:
            score_label = "🔥 SINAL FORTE"
        elif signal_score >= 5:
            score_label = "👍 SINAL BOM"
        elif signal_score >= 3:
            score_label = "✅ SINAL OK"
        else:
            score_label = "⚠️ SINAL FRACO"
        
        msg = f"""
{emoji} <b>NOVA APOSTA - {acao}</b>

🎯 <b>O QUE O BOT FEZ:</b>
Apostou que {symbol} vai {direcao}
Score: {signal_score}/9 - {score_label}

💰 <b>QUANTO APOSTOU:</b>
Volume: <b>{volume} lotes</b>
Saldo atual: ${balance_usd:,.2f} (R${balance_brl:,.2f})

📍 <b>PREÇOS:</b>
• Entrou em: <code>{price:.5f}</code>
• Stop Loss: <code>{sl:.5f}</code> ({pips_risco:.0f} pips)
• Take Profit: <code>{tp:.5f}</code> ({pips_lucro:.0f} pips)

⚠️ <b>SE PERDER:</b>
-${risco_usd:.2f} (-R${risco_brl:.2f})

✅ <b>SE GANHAR:</b>
+${lucro_usd:.2f} (+R${lucro_brl:.2f})

🎫 Ticket: {ticket}
🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
    
    def notify_position_closed(self, symbol: str, pnl: float, ticket: int, 
                               usd_to_brl: float = 6.10, close_reason: str = None):
        """Notifica posição fechada com explicação clara"""
        ganhou = pnl >= 0
        emoji = "✅" if ganhou else "❌"
        
        pnl_brl = pnl * usd_to_brl
        
        if ganhou:
            resultado = "VOCÊ GANHOU!"
            pnl_str = f"+${pnl:.2f}"
            pnl_brl_str = f"+R${pnl_brl:.2f}"
            mensagem_extra = "🎉 Parabéns! O bot acertou essa!"
        else:
            resultado = "VOCÊ PERDEU"
            pnl_str = f"-${abs(pnl):.2f}"
            pnl_brl_str = f"-R${abs(pnl_brl):.2f}"
            mensagem_extra = "😔 Faz parte do jogo. Nem sempre dá certo."
        
        # Motivo do fechamento em português
        reason_text = ""
        if close_reason:
            if "TP" in close_reason or "Take" in close_reason:
                reason_text = "\n📝 Fechou porque: Bateu o alvo de lucro (Take Profit)"
            elif "SL" in close_reason or "Stop" in close_reason:
                reason_text = "\n📝 Fechou porque: Bateu o limite de perda (Stop Loss)"
            elif "Trailing" in close_reason:
                reason_text = "\n📝 Fechou porque: Trailing Stop protegeu o lucro"
            else:
                reason_text = f"\n📝 Motivo: {close_reason}"
        
        msg = f"""
{emoji} <b>APOSTA FECHADA - {resultado}</b>

� {symbol}

💰 <b>RESULTADO:</b>
<b>{pnl_str}</b> (<b>{pnl_brl_str}</b>)

{mensagem_extra}{reason_text}

🎫 Ticket: {ticket}
🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
    
    def notify_error(self, error_type: str, details: str):
        """Notifica erro crítico"""
        msg = f"""
⚠️ <b>ERRO: {error_type}</b>

📝 {details}
🕐 Hora: {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
    
    def notify_signal_rejected(self, signal_type: str, symbol: str, price: float,
                               score: int, min_score: int, rejections: list = None,
                               blocked_by: str = None):
        """Notifica sinal rejeitado por score baixo ou filtro Smart Money"""
        emoji = "🟢" if signal_type == "BUY" else "🔴"
        acao = "COMPRA" if signal_type == "BUY" else "VENDA"
        
        # Motivos da rejeição
        rej_text = ""
        if rejections:
            rej_text = "\n❌ <b>O que faltou:</b>\n"
            for r in rejections[:5]:
                rej_text += f"• {r.replace('✗ ', '')}\n"
        
        # Filtro que bloqueou
        blocked_text = ""
        if blocked_by:
            blocked_text = f"\n🚫 <b>Bloqueado por:</b> {blocked_by}\n"
        
        msg = f"""
🚫 <b>SINAL REJEITADO</b>

{emoji} Sinal de {acao} em {symbol}
💹 Preço: {price:.5f}

📊 <b>Score: {score}/9</b> (mínimo: {min_score})
{blocked_text}{rej_text}
💡 <b>Por que não entrou:</b>
O bot usa 9 confirmações Smart Money.
Só entra quando tem {min_score}+ confirmações.

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
    
    def notify_filter_blocked(self, signal_type: str, symbol: str, price: float,
                              filter_name: str, filter_reason: str):
        """Notifica quando um filtro Smart Money bloqueou o trade"""
        emoji = "🟢" if signal_type == "BUY" else "🔴"
        acao = "COMPRA" if signal_type == "BUY" else "VENDA"
        
        msg = f"""
🛡️ <b>FILTRO SMART MONEY ATIVO</b>

{emoji} Sinal de {acao} em {symbol}
💹 Preço: {price:.5f}

🚫 <b>Bloqueado por:</b> {filter_name}
📝 {filter_reason}

💡 Isso protege você de trades ruins!

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
    
    def notify_reconnection(self, success: bool, attempt: int):
        """Notifica tentativa de reconexão"""
        if success:
            msg = f"🔄 <b>Reconectado</b> com sucesso na tentativa {attempt}"
        else:
            msg = f"❌ <b>Falha na reconexão</b> - tentativa {attempt}"
        return self._send_message(msg)
    
    def notify_daily_report(self, stats: dict, metrics_summary: str = ""):
        """Envia relatório diário"""
        
        # Performance emoji
        win_rate = stats.get('win_rate', 0)
        if stats.get('trades_count', 0) == 0:
            perf_emoji = "⏳ Sem trades"
        elif win_rate >= 60:
            perf_emoji = "🏆 Excelente!"
        elif win_rate >= 50:
            perf_emoji = "👍 Bom"
        else:
            perf_emoji = "⚠️ Precisa melhorar"
        
        pnl = stats.get('pnl', 0)
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        
        msg = f"""
📊 <b>Relatório Diário - Smart Money Bot</b>

📅 Data: {stats.get('date', datetime.now().strftime('%Y-%m-%d'))}

📈 <b>Resultados:</b>
🔢 Trades: {stats.get('trades_count', 0)}
✅ Wins: {stats.get('wins', 0)}
❌ Losses: {stats.get('losses', 0)}
📊 Win Rate: {win_rate:.1f}%
💰 P&L: {pnl_str}

{perf_emoji}

{metrics_summary}

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
    
    def send_custom(self, message: str):
        """Envia mensagem customizada"""
        return self._send_message(message)
    
    def notify_status_update(self, price: float, trend: str, rsi: float, 
                             balance_usd: float, profit_usd: float,
                             positions_count: int, max_positions: int,
                             cooldown_remaining: int, daily_stats: dict,
                             next_action: str, usd_to_brl: float = 6.10,
                             smart_money_status: dict = None):
        """Envia atualização de status com Smart Money info"""
        
        # Emojis de tendência e RSI
        trend_emoji = "📈" if trend == "UP" else "📉"
        rsi_emoji = "🔵" if rsi < 30 else ("🔴" if rsi > 70 else "⚪")
        
        # Valores em BRL
        balance_brl = balance_usd * usd_to_brl
        profit_brl = profit_usd * usd_to_brl
        
        # Status de posição
        if positions_count > 0:
            pos_status = f"🟠 POSICIONADO ({positions_count}/{max_positions})"
        else:
            pos_status = "🟢 LIVRE"
        
        # Cooldown
        if cooldown_remaining > 0:
            cooldown_str = f"⏱️ Cooldown: {cooldown_remaining}s"
        else:
            cooldown_str = "✅ Pronto para operar"
        
        # Stats do dia
        wins = daily_stats.get('wins', 0)
        losses = daily_stats.get('losses', 0)
        pnl = daily_stats.get('pnl', 0)
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        
        # Performance emoji
        win_rate = daily_stats.get('win_rate', 0)
        if daily_stats.get('trades_count', 0) == 0:
            perf_emoji = "⏳"
        elif win_rate >= 60:
            perf_emoji = "🏆"
        elif win_rate >= 50:
            perf_emoji = "👍"
        else:
            perf_emoji = "⚠️"
        
        # Smart Money status
        sm_text = ""
        if smart_money_status:
            sm_text = "\n🎯 <b>Smart Money:</b>\n"
            
            # ADX
            adx = smart_money_status.get('adx', 0)
            if adx >= 25:
                sm_text += f"💪 ADX {adx:.0f} (forte)\n"
            elif adx >= 20:
                sm_text += f"📈 ADX {adx:.0f}\n"
            else:
                sm_text += f"📊 ADX {adx:.0f} (lateral)\n"
            
            # Structure
            structure = smart_money_status.get('market_structure', 'RANGING')
            struct_emoji = "📈" if structure == "BULLISH" else ("📉" if structure == "BEARISH" else "📊")
            sm_text += f"{struct_emoji} Estrutura: {structure}\n"
            
            # BOS
            bos = smart_money_status.get('bos_type', 'NONE')
            if bos != "NONE":
                bos_emoji = "🟢" if bos == "BULLISH" else "🔴"
                sm_text += f"{bos_emoji} BOS: {bos}\n"
            
            # Order Blocks
            ob_count = smart_money_status.get('order_blocks', 0)
            if ob_count > 0:
                sm_text += f"📦 {ob_count} Order Blocks ativos\n"
            
            # Session
            session = smart_money_status.get('session', '')
            if session:
                sm_text += f"⏰ {session}\n"
        
        msg = f"""
📊 <b>STATUS</b> [{datetime.now().strftime('%H:%M:%S')}]

{trend_emoji} Preço: <code>{price:.5f}</code> | RSI: {rsi:.1f} {rsi_emoji}
💰 ${balance_usd:,.0f} (R${balance_brl:,.0f})
💵 Lucro aberto: ${profit_usd:,.2f} (R${profit_brl:,.2f})

{pos_status}
{cooldown_str}
{sm_text}
📊 Hoje: {wins}W/{losses}L | {pnl_str} {perf_emoji}
⏳ {next_action}
"""
        return self._send_message(msg)
    
    def notify_smart_money_analysis(self, symbol: str, price: float,
                                    indicators: dict, session_status: str = ""):
        """Envia análise completa Smart Money"""
        
        # Tendência
        sma_fast = indicators.get('sma_fast', 0)
        sma_slow = indicators.get('sma_slow', 0)
        trend = "📈 ALTA" if sma_fast > sma_slow else "📉 BAIXA"
        
        # RSI
        rsi = indicators.get('rsi', 50)
        if rsi < 30:
            rsi_status = "🔵 SOBREVENDA"
        elif rsi > 70:
            rsi_status = "🔴 SOBRECOMPRA"
        else:
            rsi_status = "⚪ NEUTRO"
        
        # ADX
        adx = indicators.get('adx', 0)
        if adx >= 25:
            adx_status = f"💪 FORTE ({adx:.0f})"
        elif adx >= 20:
            adx_status = f"📈 Tendência ({adx:.0f})"
        else:
            adx_status = f"📊 LATERAL ({adx:.0f})"
        
        # Volatilidade
        atr_pct = indicators.get('atr_percentile', 50)
        if atr_pct < 20:
            vol_status = f"🔵 BAIXA ({atr_pct:.0f}%)"
        elif atr_pct > 80:
            vol_status = f"🔴 ALTA ({atr_pct:.0f}%)"
        else:
            vol_status = f"🟢 NORMAL ({atr_pct:.0f}%)"
        
        # Market Structure
        structure = indicators.get('market_structure', 'RANGING')
        if structure == "BULLISH":
            struct_status = "📈 BULLISH (HH+HL)"
        elif structure == "BEARISH":
            struct_status = "📉 BEARISH (LH+LL)"
        else:
            struct_status = "📊 RANGING"
        
        # BOS
        bos_type = indicators.get('bos_type', 'NONE')
        bos_pullback = indicators.get('bos_pullback_valid', False)
        if bos_type != "NONE":
            bos_emoji = "🟢" if bos_type == "BULLISH" else "🔴"
            pullback_str = "✓ Pullback válido" if bos_pullback else "⏳ Aguardando pullback"
            bos_status = f"{bos_emoji} {bos_type} | {pullback_str}"
        else:
            bos_status = "⚪ Sem BOS ativo"
        
        # Order Blocks
        ob_summary = indicators.get('ob_summary', 'Nenhum OB ativo')
        in_bullish_ob = indicators.get('in_bullish_ob', False)
        in_bearish_ob = indicators.get('in_bearish_ob', False)
        if in_bullish_ob or in_bearish_ob:
            ob_status = f"📦 {ob_summary} ⬅️ PREÇO EM OB!"
        else:
            ob_status = f"📦 {ob_summary}"
        
        msg = f"""
🎯 <b>ANÁLISE SMART MONEY</b>

📊 {symbol} @ {price:.5f}

<b>Indicadores:</b>
{trend} | RSI: {rsi:.1f} {rsi_status}
ADX: {adx_status}
Volatilidade: {vol_status}

<b>Smart Money:</b>
Estrutura: {struct_status}
BOS: {bos_status}
{ob_status}

<b>Sessão:</b>
{session_status if session_status else "N/A"}

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)

    def notify_position_update(self, symbol: str, pos_type: str, entry_price: float,
                               current_price: float, pnl_usd: float, sl: float, tp: float,
                               usd_to_brl: float = 6.10, score: int = 0, 
                               minutes_open: float = 0, smart_status: str = ""):
        """Notifica atualização de posição aberta (a cada 1 min)"""
        emoji = "🟢" if pos_type == "BUY" else "🔴"
        tipo = "COMPRADO" if pos_type == "BUY" else "VENDIDO"
        
        pnl_brl = pnl_usd * usd_to_brl
        profit_emoji = "💚" if pnl_usd >= 0 else "💔"
        
        # Distância do SL e TP em pips
        is_jpy = "JPY" in symbol
        multiplier = 100 if is_jpy else 10000
        
        if pos_type == "BUY":
            dist_sl = (current_price - sl) * multiplier
            dist_tp = (tp - current_price) * multiplier
        else:
            dist_sl = (sl - current_price) * multiplier
            dist_tp = (current_price - tp) * multiplier
        
        msg = f"""
{emoji} <b>POSIÇÃO ABERTA - {tipo}</b>

📊 {symbol}
⏱️ Aberta há {minutes_open:.0f} minutos

💹 <b>Preços:</b>
• Entrada: <code>{entry_price:.5f}</code>
• Atual: <code>{current_price:.5f}</code>
• SL: <code>{sl:.5f}</code> ({dist_sl:.1f} pips)
• TP: <code>{tp:.5f}</code> ({dist_tp:.1f} pips)

{profit_emoji} <b>P&L Atual:</b>
<b>${pnl_usd:.2f}</b> (<b>R${pnl_brl:.2f}</b>)

🎯 Score: {score}/9
{smart_status}

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        return self._send_message(msg)
