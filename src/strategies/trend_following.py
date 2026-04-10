import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from ..domain.interfaces import IStrategy
from ..domain.entities import TradeSignal, SignalType, Position
from ..utils.logger import setup_logger

logger = setup_logger("Strategy")

class TrendFollowingStrategy(IStrategy):
    """
    Estratégia PRO v2.0 - Sistema de Score de Confiança
    
    Cada sinal recebe uma pontuação de 0-5 baseada em múltiplas confirmações:
    - SMA Crossover (tendência)
    - RSI Momentum (força)
    - MACD Confirmação (momentum)
    - Preço vs SMA (posição)
    - Volume (interesse)
    
    Só executa trades com score >= MIN_SIGNAL_SCORE (padrão: 3)
    """
    
    def __init__(self, fast_period: int, slow_period: int, rsi_period: int, 
                 rsi_upper: int, rsi_lower: int, atr_period: int = 14, 
                 atr_mult_sl: float = 2.0, atr_mult_tp: float = 4.0, 
                 aggressive_mode: bool = False, use_rsi_extreme: bool = False, 
                 rsi_extreme_oversold: int = 25, rsi_extreme_overbought: int = 75,
                 min_signal_score: int = 3, use_macd_filter: bool = True,
                 use_volume_filter: bool = True, rsi_momentum_sell: int = 55,
                 rsi_momentum_buy: int = 45,
                 # Novos parâmetros ADX
                 use_adx_filter: bool = True, adx_period: int = 14,
                 adx_threshold: int = 20, adx_strong: int = 25,
                 # Parâmetros Anti-Stop Hunt
                 use_anti_stop_hunt: bool = True, sl_buffer_pips: int = 5,
                 avoid_round_numbers: bool = True, round_number_buffer_pips: int = 3,
                 use_swing_sl: bool = True,
                 # Parâmetros Filtro de Volatilidade
                 use_volatility_filter: bool = True, atr_percentile_low: int = 20,
                 atr_percentile_high: int = 80, atr_lookback: int = 100,
                 # Parâmetros Market Structure
                 use_market_structure: bool = True, swing_lookback: int = 5,
                 min_swing_points: int = 3, structure_as_filter: bool = True,
                 # Parâmetros BOS + Pullback
                 use_bos_pullback: bool = True, bos_pullback_min: float = 0.3,
                 bos_pullback_max: float = 0.7, bos_expiry_bars: int = 20,
                 bos_as_filter: bool = False,
                 # Parâmetros Order Blocks
                 use_order_blocks: bool = True, ob_lookback: int = 50,
                 ob_min_impulse_atr: float = 1.5, ob_as_filter: bool = False,
                 ob_mitigation_percent: float = 0.5, ob_max_age_bars: int = 100):
        
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.rsi_period = rsi_period
        self.rsi_upper = rsi_upper
        self.rsi_lower = rsi_lower
        self.atr_period = atr_period
        self.atr_mult_sl = atr_mult_sl
        self.atr_mult_tp = atr_mult_tp
        self.aggressive_mode = aggressive_mode
        self.use_rsi_extreme = use_rsi_extreme
        self.rsi_extreme_oversold = rsi_extreme_oversold
        self.rsi_extreme_overbought = rsi_extreme_overbought
        
        # Novos parâmetros PRO v2.0
        self.min_signal_score = min_signal_score
        self.use_macd_filter = use_macd_filter
        self.use_volume_filter = use_volume_filter
        self.rsi_momentum_sell = rsi_momentum_sell  # RSI mínimo para venda
        self.rsi_momentum_buy = rsi_momentum_buy    # RSI máximo para compra
        
        # Parâmetros ADX (Detecção de Tendência vs Range)
        self.use_adx_filter = use_adx_filter
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold  # Mínimo para considerar tendência
        self.adx_strong = adx_strong        # Tendência forte (bonus no score)
        self.adx_ignore_rsi_extreme = getattr(__import__('config'), 'ADX_IGNORE_RSI_EXTREME', 40)  # Só ignora RSI extremo se ADX > este valor
        
        # Parâmetros Anti-Stop Hunt
        self.use_anti_stop_hunt = use_anti_stop_hunt
        self.sl_buffer_pips = sl_buffer_pips
        self.avoid_round_numbers = avoid_round_numbers
        self.round_number_buffer_pips = round_number_buffer_pips
        self.use_swing_sl = use_swing_sl
        
        # Parâmetros Filtro de Volatilidade
        self.use_volatility_filter = use_volatility_filter
        self.atr_percentile_low = atr_percentile_low
        self.atr_percentile_high = atr_percentile_high
        self.atr_lookback = atr_lookback
        
        # Parâmetros Market Structure
        self.use_market_structure = use_market_structure
        self.swing_lookback_struct = swing_lookback  # Renomeado para evitar conflito
        self.min_swing_points = min_swing_points
        self.structure_as_filter = structure_as_filter
        
        # Parâmetros BOS + Pullback
        self.use_bos_pullback = use_bos_pullback
        self.bos_pullback_min = bos_pullback_min
        self.bos_pullback_max = bos_pullback_max
        self.bos_expiry_bars = bos_expiry_bars
        self.bos_as_filter = bos_as_filter
        
        # Parâmetros Order Blocks
        self.use_order_blocks = use_order_blocks
        self.ob_lookback = ob_lookback
        self.ob_min_impulse_atr = ob_min_impulse_atr
        self.ob_as_filter = ob_as_filter
        self.ob_mitigation_percent = ob_mitigation_percent
        self.ob_max_age_bars = ob_max_age_bars
        
        # Estado do BOS (armazena último BOS detectado)
        self._last_bos = None  # {"type": "BULLISH/BEARISH", "price": X, "bar_index": N, "swing_price": Y}
        
        # Lista de Order Blocks ativos
        self._order_blocks = []  # [{"type": "BULLISH/BEARISH", "high": X, "low": Y, "bar_index": N, "strength": Z}]
        
        # MACD padrão
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
        # Volume
        self.volume_period = 20
        
        # Swing lookback para Anti-Stop Hunt
        self.swing_lookback = 20

    def _find_swing_points(self, df: pd.DataFrame, lookback: int = 5) -> tuple:
        """
        Identifica swing highs e swing lows no dataframe.
        
        Um swing high é um ponto onde o high é maior que os N candles anteriores E posteriores.
        Um swing low é um ponto onde o low é menor que os N candles anteriores E posteriores.
        
        Returns:
            (swing_highs, swing_lows) - listas de tuplas (index, price)
        """
        swing_highs = []
        swing_lows = []
        
        if len(df) < lookback * 2 + 1:
            return swing_highs, swing_lows
        
        highs = df['high'].values
        lows = df['low'].values
        
        # Percorre do lookback até len-lookback para ter dados suficientes
        for i in range(lookback, len(df) - lookback):
            # Verifica Swing High
            is_swing_high = True
            for j in range(1, lookback + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.append((i, highs[i]))
            
            # Verifica Swing Low
            is_swing_low = True
            for j in range(1, lookback + 1):
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.append((i, lows[i]))
        
        return swing_highs, swing_lows
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> tuple:
        """
        Analisa a estrutura de mercado baseada em swing points.
        
        Returns:
            (structure, details) - estrutura ("BULLISH", "BEARISH", "RANGING") e detalhes
        """
        swing_highs, swing_lows = self._find_swing_points(df, self.swing_lookback_struct)
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "RANGING", "Swings insuficientes"
        
        # Pega os últimos N swing points
        recent_highs = swing_highs[-self.min_swing_points:] if len(swing_highs) >= self.min_swing_points else swing_highs
        recent_lows = swing_lows[-self.min_swing_points:] if len(swing_lows) >= self.min_swing_points else swing_lows
        
        # Analisa padrão dos highs
        hh_count = 0  # Higher Highs
        lh_count = 0  # Lower Highs
        for i in range(1, len(recent_highs)):
            if recent_highs[i][1] > recent_highs[i-1][1]:
                hh_count += 1
            else:
                lh_count += 1
        
        # Analisa padrão dos lows
        hl_count = 0  # Higher Lows
        ll_count = 0  # Lower Lows
        for i in range(1, len(recent_lows)):
            if recent_lows[i][1] > recent_lows[i-1][1]:
                hl_count += 1
            else:
                ll_count += 1
        
        # Determina estrutura
        total_highs = hh_count + lh_count
        total_lows = hl_count + ll_count
        
        # Estrutura BULLISH: maioria HH e HL
        if total_highs > 0 and total_lows > 0:
            bullish_score = (hh_count / total_highs + hl_count / total_lows) / 2
            bearish_score = (lh_count / total_highs + ll_count / total_lows) / 2
            
            if bullish_score >= 0.6:
                details = f"HH:{hh_count} HL:{hl_count} | Topos e fundos ascendentes"
                return "BULLISH", details
            elif bearish_score >= 0.6:
                details = f"LH:{lh_count} LL:{ll_count} | Topos e fundos descendentes"
                return "BEARISH", details
        
        details = f"HH:{hh_count} LH:{lh_count} | HL:{hl_count} LL:{ll_count}"
        return "RANGING", details
    
    def _get_structure_emoji(self, structure: str) -> str:
        """Retorna emoji para a estrutura"""
        if structure == "BULLISH":
            return "📈"
        elif structure == "BEARISH":
            return "📉"
        else:
            return "📊"
    
    def _detect_bos(self, df: pd.DataFrame, swing_highs: list, swing_lows: list) -> dict:
        """
        Detecta Break of Structure (BOS).
        
        BOS Bullish: Preço fecha acima do último swing high
        BOS Bearish: Preço fecha abaixo do último swing low
        
        Returns:
            {"type": "BULLISH/BEARISH/NONE", "bos_price": X, "swing_price": Y, "bar_index": N}
        """
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {"type": "NONE"}
        
        current_close = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_bar = len(df) - 1
        
        # Último swing high e low (excluindo o mais recente que pode estar se formando)
        last_swing_high = swing_highs[-2] if len(swing_highs) >= 2 else swing_highs[-1]
        last_swing_low = swing_lows[-2] if len(swing_lows) >= 2 else swing_lows[-1]
        
        # BOS Bullish: Fechou acima do último swing high
        if current_close > last_swing_high[1]:
            return {
                "type": "BULLISH",
                "bos_price": current_high,
                "swing_price": last_swing_low[1],  # Swing low para calcular pullback
                "bar_index": current_bar
            }
        
        # BOS Bearish: Fechou abaixo do último swing low
        if current_close < last_swing_low[1]:
            return {
                "type": "BEARISH",
                "bos_price": current_low,
                "swing_price": last_swing_high[1],  # Swing high para calcular pullback
                "bar_index": current_bar
            }
        
        return {"type": "NONE"}
    
    def _check_pullback(self, df: pd.DataFrame, bos: dict) -> dict:
        """
        Verifica se há pullback válido após BOS.
        
        Pullback válido:
        - Preço retornou entre 30% e 70% do movimento
        - Não ultrapassou o ponto de origem
        
        Returns:
            {"valid": True/False, "retracement": X%, "in_zone": True/False}
        """
        if bos["type"] == "NONE":
            return {"valid": False, "retracement": 0, "in_zone": False}
        
        current_close = df['close'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_high = df['high'].iloc[-1]
        
        bos_price = bos["bos_price"]
        swing_price = bos["swing_price"]
        
        # Calcula movimento total
        move = abs(bos_price - swing_price)
        if move == 0:
            return {"valid": False, "retracement": 0, "in_zone": False}
        
        if bos["type"] == "BULLISH":
            # Pullback é quando preço cai após BOS bullish
            retracement = (bos_price - current_low) / move
            in_zone = self.bos_pullback_min <= retracement <= self.bos_pullback_max
            
            # Pullback válido se está na zona e não quebrou o swing low
            valid = in_zone and current_low > swing_price
            
        else:  # BEARISH
            # Pullback é quando preço sobe após BOS bearish
            retracement = (current_high - bos_price) / move
            in_zone = self.bos_pullback_min <= retracement <= self.bos_pullback_max
            
            # Pullback válido se está na zona e não quebrou o swing high
            valid = in_zone and current_high < swing_price
        
        return {
            "valid": valid,
            "retracement": round(retracement * 100, 1),
            "in_zone": in_zone
        }
    
    def _analyze_bos_pullback(self, df: pd.DataFrame) -> dict:
        """
        Analisa BOS + Pullback completo.
        
        Returns:
            {
                "has_bos": True/False,
                "bos_type": "BULLISH/BEARISH/NONE",
                "pullback_valid": True/False,
                "retracement": X%,
                "signal": "BUY/SELL/NONE"
            }
        """
        swing_highs, swing_lows = self._find_swing_points(df, self.swing_lookback_struct)
        
        # Detecta BOS
        bos = self._detect_bos(df, swing_highs, swing_lows)
        
        if bos["type"] == "NONE":
            # Verifica se há BOS anterior ainda válido
            if self._last_bos and self._last_bos["type"] != "NONE":
                bars_since_bos = len(df) - 1 - self._last_bos.get("bar_index", 0)
                if bars_since_bos <= self.bos_expiry_bars:
                    bos = self._last_bos
                else:
                    self._last_bos = None
        else:
            # Novo BOS detectado
            self._last_bos = bos
        
        # Verifica pullback
        pullback = self._check_pullback(df, bos)
        
        # Determina sinal
        signal = "NONE"
        if bos["type"] != "NONE" and pullback["valid"]:
            signal = "BUY" if bos["type"] == "BULLISH" else "SELL"
        
        return {
            "has_bos": bos["type"] != "NONE",
            "bos_type": bos["type"],
            "pullback_valid": pullback["valid"],
            "retracement": pullback["retracement"],
            "in_zone": pullback["in_zone"],
            "signal": signal
        }

    def _detect_order_blocks(self, df: pd.DataFrame, atr_value: float) -> list:
        """
        Detecta Order Blocks no dataframe.
        
        Bullish OB: Último candle de BAIXA antes de impulso de ALTA
        Bearish OB: Último candle de ALTA antes de impulso de BAIXA
        
        Returns:
            Lista de Order Blocks: [{"type", "high", "low", "bar_index", "strength"}]
        """
        order_blocks = []
        
        if len(df) < self.ob_lookback + 5 or atr_value <= 0:
            return order_blocks
        
        current_bar = len(df) - 1
        min_impulse = atr_value * self.ob_min_impulse_atr
        
        # Percorre os candles buscando OBs
        for i in range(self.ob_lookback, 5, -1):
            idx = current_bar - i
            if idx < 1:
                continue
            
            candle = df.iloc[idx]
            is_bearish_candle = candle['close'] < candle['open']
            is_bullish_candle = candle['close'] > candle['open']
            
            # Verifica impulso nos próximos candles
            impulse_bars = min(5, current_bar - idx)
            if impulse_bars < 2:
                continue
            
            future_high = df['high'].iloc[idx+1:idx+1+impulse_bars].max()
            future_low = df['low'].iloc[idx+1:idx+1+impulse_bars].min()
            
            # Bullish OB: Candle de baixa seguido de impulso de alta
            if is_bearish_candle:
                impulse_up = future_high - candle['high']
                if impulse_up >= min_impulse:
                    # Verifica se OB não foi mitigado
                    ob_mid = (candle['high'] + candle['low']) / 2
                    mitigation_level = candle['low'] + (candle['high'] - candle['low']) * self.ob_mitigation_percent
                    
                    # Verifica se preço retornou e tocou o OB
                    mitigated = False
                    for j in range(idx + impulse_bars, current_bar + 1):
                        if df['low'].iloc[j] <= mitigation_level:
                            mitigated = True
                            break
                    
                    if not mitigated:
                        order_blocks.append({
                            "type": "BULLISH",
                            "high": candle['high'],
                            "low": candle['low'],
                            "bar_index": idx,
                            "strength": round(impulse_up / atr_value, 1),
                            "age": current_bar - idx
                        })
            
            # Bearish OB: Candle de alta seguido de impulso de baixa
            if is_bullish_candle:
                impulse_down = candle['low'] - future_low
                if impulse_down >= min_impulse:
                    # Verifica se OB não foi mitigado
                    ob_mid = (candle['high'] + candle['low']) / 2
                    mitigation_level = candle['high'] - (candle['high'] - candle['low']) * self.ob_mitigation_percent
                    
                    # Verifica se preço retornou e tocou o OB
                    mitigated = False
                    for j in range(idx + impulse_bars, current_bar + 1):
                        if df['high'].iloc[j] >= mitigation_level:
                            mitigated = True
                            break
                    
                    if not mitigated:
                        order_blocks.append({
                            "type": "BEARISH",
                            "high": candle['high'],
                            "low": candle['low'],
                            "bar_index": idx,
                            "strength": round(impulse_down / atr_value, 1),
                            "age": current_bar - idx
                        })
        
        # Filtra OBs muito antigos e ordena por proximidade
        order_blocks = [ob for ob in order_blocks if ob["age"] <= self.ob_max_age_bars]
        
        # Limita a 3 OBs de cada tipo (mais recentes)
        bullish_obs = sorted([ob for ob in order_blocks if ob["type"] == "BULLISH"], key=lambda x: x["age"])[:3]
        bearish_obs = sorted([ob for ob in order_blocks if ob["type"] == "BEARISH"], key=lambda x: x["age"])[:3]
        
        return bullish_obs + bearish_obs
    
    def _check_price_in_order_block(self, current_price: float, order_blocks: list, signal_type: str) -> dict:
        """
        Verifica se o preço atual está dentro de um Order Block relevante.
        
        Para BUY: verifica Bullish OBs
        Para SELL: verifica Bearish OBs
        
        Returns:
            {"in_ob": True/False, "ob": order_block ou None, "distance_pips": X}
        """
        target_type = "BULLISH" if signal_type == "BUY" else "BEARISH"
        relevant_obs = [ob for ob in order_blocks if ob["type"] == target_type]
        
        if not relevant_obs:
            return {"in_ob": False, "ob": None, "distance_pips": 0}
        
        for ob in relevant_obs:
            # Verifica se preço está dentro do OB
            if ob["low"] <= current_price <= ob["high"]:
                return {
                    "in_ob": True,
                    "ob": ob,
                    "distance_pips": 0
                }
            
            # Verifica proximidade (dentro de 10 pips)
            if target_type == "BULLISH":
                distance = current_price - ob["high"]
                if 0 < distance <= 0.0010:  # 10 pips acima
                    return {
                        "in_ob": True,
                        "ob": ob,
                        "distance_pips": round(distance * 10000, 1)
                    }
            else:
                distance = ob["low"] - current_price
                if 0 < distance <= 0.0010:  # 10 pips abaixo
                    return {
                        "in_ob": True,
                        "ob": ob,
                        "distance_pips": round(distance * 10000, 1)
                    }
        
        # Retorna o OB mais próximo
        nearest_ob = None
        min_distance = float('inf')
        
        for ob in relevant_obs:
            if target_type == "BULLISH":
                dist = abs(current_price - ob["high"])
            else:
                dist = abs(current_price - ob["low"])
            
            if dist < min_distance:
                min_distance = dist
                nearest_ob = ob
        
        return {
            "in_ob": False,
            "ob": nearest_ob,
            "distance_pips": round(min_distance * 10000, 1) if nearest_ob else 0
        }
    
    def _get_order_blocks_summary(self, order_blocks: list) -> str:
        """Retorna resumo dos Order Blocks para display"""
        if not order_blocks:
            return "Nenhum OB ativo"
        
        bullish = [ob for ob in order_blocks if ob["type"] == "BULLISH"]
        bearish = [ob for ob in order_blocks if ob["type"] == "BEARISH"]
        
        parts = []
        if bullish:
            ob = bullish[0]  # Mais recente
            parts.append(f"🟢 OB @ {ob['low']:.5f}-{ob['high']:.5f}")
        if bearish:
            ob = bearish[0]  # Mais recente
            parts.append(f"🔴 OB @ {ob['low']:.5f}-{ob['high']:.5f}")
        
        return " | ".join(parts) if parts else "Nenhum OB ativo"

    def _calculate_atr_percentile(self, df: pd.DataFrame, current_atr: float) -> tuple:
        """
        Calcula o percentil do ATR atual em relação ao histórico.
        
        Returns:
            (percentile, status) - percentil (0-100) e status descritivo
        """
        if 'atr' not in df.columns or len(df) < self.atr_lookback:
            return 50, "Dados insuficientes"
        
        # Pega os últimos N valores de ATR
        atr_history = df['atr'].tail(self.atr_lookback).dropna()
        
        if len(atr_history) < 10:
            return 50, "Histórico insuficiente"
        
        # Calcula percentil
        values_below = (atr_history < current_atr).sum()
        percentile = (values_below / len(atr_history)) * 100
        
        # Determina status
        if percentile < self.atr_percentile_low:
            status = f"🔵 BAIXA ({percentile:.0f}%) - Mercado parado"
        elif percentile > self.atr_percentile_high:
            status = f"🔴 ALTA ({percentile:.0f}%) - Mercado caótico"
        else:
            status = f"🟢 NORMAL ({percentile:.0f}%)"
        
        return percentile, status

    def _calculate_rsi(self, series, period):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calculate_atr(self, df, period):
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def _calculate_macd(self, series):
        """Calcula MACD, Signal Line e Histograma"""
        ema_fast = series.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = series.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _calculate_volume_sma(self, df, period):
        """Calcula média móvel do volume"""
        if 'tick_volume' in df.columns:
            return df['tick_volume'].rolling(window=period).mean()
        elif 'volume' in df.columns:
            return df['volume'].rolling(window=period).mean()
        return pd.Series([0] * len(df))
    
    def _calculate_adx(self, df, period: int = 14):
        """
        Calcula ADX (Average Directional Index) e DI+/DI-
        
        ADX mede a FORÇA da tendência (não a direção):
        - ADX < 20: Mercado LATERAL (sem tendência)
        - ADX 20-25: Tendência FRACA
        - ADX 25-50: Tendência FORTE
        - ADX > 50: Tendência MUITO FORTE
        
        DI+ e DI- indicam a DIREÇÃO:
        - DI+ > DI-: Tendência de ALTA
        - DI- > DI+: Tendência de BAIXA
        
        Returns:
            (adx, plus_di, minus_di) como Series
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        # +DM e -DM
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_dm = pd.Series(plus_dm, index=df.index)
        minus_dm = pd.Series(minus_dm, index=df.index)
        
        # Smoothed TR, +DM, -DM (usando EMA de Wilder = EMA com alpha = 1/period)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        smooth_plus_dm = plus_dm.ewm(alpha=1/period, adjust=False).mean()
        smooth_minus_dm = minus_dm.ewm(alpha=1/period, adjust=False).mean()
        
        # +DI e -DI
        plus_di = 100 * smooth_plus_dm / atr
        minus_di = 100 * smooth_minus_dm / atr
        
        # DX
        di_sum = plus_di + minus_di
        di_diff = abs(plus_di - minus_di)
        dx = 100 * di_diff / di_sum.replace(0, np.nan)
        
        # ADX (smoothed DX)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        
        return adx, plus_di, minus_di
    
    def _get_adx_status(self, adx_value: float) -> str:
        """Retorna status do ADX"""
        if adx_value < 20:
            return "📊 LATERAL (sem tendência)"
        elif adx_value < 25:
            return "📈 Tendência FRACA"
        elif adx_value < 50:
            return "💪 Tendência FORTE"
        else:
            return "🔥 Tendência MUITO FORTE"
    
    def _is_near_round_number(self, price: float, buffer_pips: int = 3) -> bool:
        """
        Verifica se o preço está próximo de um número redondo.
        Números redondos: X.XX00, X.XX50 (a cada 50 pips)
        """
        # Converte para pips (assume 5 casas decimais)
        price_pips = int(price * 10000)
        
        # Verifica proximidade de X.XX00 (múltiplos de 100 pips)
        remainder_100 = price_pips % 100
        if remainder_100 < buffer_pips or remainder_100 > (100 - buffer_pips):
            return True
        
        # Verifica proximidade de X.XX50 (múltiplos de 50 pips)
        remainder_50 = price_pips % 50
        if remainder_50 < buffer_pips or remainder_50 > (50 - buffer_pips):
            return True
        
        return False
    
    def _adjust_sl_away_from_round(self, sl_price: float, is_buy: bool, buffer_pips: int = 3) -> float:
        """
        Ajusta o SL para ficar longe de números redondos.
        Move o SL para ALÉM do número redondo (mais proteção).
        """
        # Converte para pips
        sl_pips = int(sl_price * 10000)
        pip_value = 0.0001
        
        # Encontra o número redondo mais próximo
        nearest_100 = round(sl_pips / 100) * 100
        nearest_50 = round(sl_pips / 50) * 50
        
        # Escolhe o mais próximo
        dist_100 = abs(sl_pips - nearest_100)
        dist_50 = abs(sl_pips - nearest_50)
        
        if dist_100 <= dist_50 and dist_100 < buffer_pips * 2:
            # Próximo de X.XX00
            if is_buy:
                # SL abaixo do preço, move mais para baixo
                new_sl_pips = nearest_100 - buffer_pips
            else:
                # SL acima do preço, move mais para cima
                new_sl_pips = nearest_100 + buffer_pips
            return new_sl_pips * pip_value
        
        elif dist_50 < buffer_pips * 2:
            # Próximo de X.XX50
            if is_buy:
                new_sl_pips = nearest_50 - buffer_pips
            else:
                new_sl_pips = nearest_50 + buffer_pips
            return new_sl_pips * pip_value
        
        return sl_price
    
    def _find_swing_low(self, df: pd.DataFrame, lookback: int = 20) -> float:
        """Encontra o swing low recente (mínimo local)"""
        if len(df) < lookback:
            return df['low'].min()
        return df['low'].tail(lookback).min()
    
    def _find_swing_high(self, df: pd.DataFrame, lookback: int = 20) -> float:
        """Encontra o swing high recente (máximo local)"""
        if len(df) < lookback:
            return df['high'].max()
        return df['high'].tail(lookback).max()
    
    def _calculate_smart_sl(self, df: pd.DataFrame, current_price: float, 
                            atr_sl: float, is_buy: bool) -> tuple:
        """
        Calcula SL inteligente com proteção anti-stop hunt.
        
        Returns:
            (sl_price, sl_reason) - preço do SL e motivo do ajuste
        """
        pip_value = 0.0001
        buffer = self.sl_buffer_pips * pip_value
        
        if is_buy:
            # SL base (ATR)
            sl_base = current_price - atr_sl
            
            # Adiciona buffer
            sl_with_buffer = sl_base - buffer
            
            # Verifica swing low
            if self.use_swing_sl:
                swing_low = self._find_swing_low(df, self.swing_lookback)
                # Usa o menor entre ATR e swing low (mais proteção)
                if swing_low < sl_with_buffer:
                    sl_with_buffer = swing_low - buffer
            
            # Ajusta para evitar números redondos
            if self.avoid_round_numbers and self._is_near_round_number(sl_with_buffer, self.round_number_buffer_pips):
                sl_final = self._adjust_sl_away_from_round(sl_with_buffer, is_buy, self.round_number_buffer_pips)
                reason = "Anti-Hunt: ajustado de número redondo"
            else:
                sl_final = sl_with_buffer
                reason = f"ATR + {self.sl_buffer_pips} pips buffer"
            
            return sl_final, reason
        
        else:  # SELL
            # SL base (ATR)
            sl_base = current_price + atr_sl
            
            # Adiciona buffer
            sl_with_buffer = sl_base + buffer
            
            # Verifica swing high
            if self.use_swing_sl:
                swing_high = self._find_swing_high(df, self.swing_lookback)
                # Usa o maior entre ATR e swing high (mais proteção)
                if swing_high > sl_with_buffer:
                    sl_with_buffer = swing_high + buffer
            
            # Ajusta para evitar números redondos
            if self.avoid_round_numbers and self._is_near_round_number(sl_with_buffer, self.round_number_buffer_pips):
                sl_final = self._adjust_sl_away_from_round(sl_with_buffer, is_buy, self.round_number_buffer_pips)
                reason = "Anti-Hunt: ajustado de número redondo"
            else:
                sl_final = sl_with_buffer
                reason = f"ATR + {self.sl_buffer_pips} pips buffer"
            
            return sl_final, reason
    
    def _calculate_signal_score(self, df, signal_type: str, market_structure: str = "RANGING", bos_analysis: dict = None, ob_analysis: dict = None) -> Tuple[int, List[str], List[str]]:
        """
        Calcula score de confiança do sinal (0-9)
        
        Returns:
            score: pontuação total
            confirmations: lista de confirmações ativas
            rejections: lista de condições não atendidas
        """
        score = 0
        confirmations = []
        rejections = []
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Valores ADX
        adx_value = last['adx'] if 'adx' in df.columns and not pd.isna(last['adx']) else 0
        plus_di = last['plus_di'] if 'plus_di' in df.columns and not pd.isna(last['plus_di']) else 0
        minus_di = last['minus_di'] if 'minus_di' in df.columns and not pd.isna(last['minus_di']) else 0
        
        # BOS analysis default
        if bos_analysis is None:
            bos_analysis = {"bos_type": "NONE", "pullback_valid": False, "signal": "NONE"}
        
        # OB analysis default
        if ob_analysis is None:
            ob_analysis = {"in_ob": False, "ob": None, "distance_pips": 0}
        
        if signal_type == "SELL":
            # 1. SMA Crossover DOWN
            crossover = prev['sma_fast'] >= prev['sma_slow'] and last['sma_fast'] < last['sma_slow']
            if crossover:
                score += 1
                confirmations.append("✓ SMA9 cruzou abaixo de SMA21")
            else:
                rejections.append("✗ Sem cruzamento de SMA")
            
            # 2. RSI Momentum (> 55 para venda = força vendedora)
            if last['rsi'] > self.rsi_momentum_sell:
                score += 1
                confirmations.append(f"✓ RSI {last['rsi']:.1f} > {self.rsi_momentum_sell} (momentum vendedor)")
            else:
                rejections.append(f"✗ RSI {last['rsi']:.1f} < {self.rsi_momentum_sell} (sem momentum)")
            
            # 3. MACD abaixo da Signal Line
            if self.use_macd_filter and 'macd' in df.columns:
                if last['macd'] < last['macd_signal']:
                    score += 1
                    confirmations.append("✓ MACD abaixo da Signal Line")
                else:
                    rejections.append("✗ MACD acima da Signal Line")
            
            # 4. Preço abaixo da SMA21 (tendência de baixa)
            if last['close'] < last['sma_slow']:
                score += 1
                confirmations.append("✓ Preço abaixo da SMA21 (tendência)")
            else:
                rejections.append("✗ Preço acima da SMA21")
            
            # 5. Volume acima da média
            if self.use_volume_filter and 'volume_sma' in df.columns:
                current_vol = df['tick_volume'].iloc[-1] if 'tick_volume' in df.columns else 0
                if current_vol > last['volume_sma'] * 1.1:  # 10% acima da média
                    score += 1
                    confirmations.append("✓ Volume acima da média")
                else:
                    rejections.append("✗ Volume abaixo da média")
            
            # 6. ADX forte + DI- > DI+ (tendência de baixa confirmada)
            if self.use_adx_filter and adx_value >= self.adx_strong:
                if minus_di > plus_di:
                    score += 1
                    confirmations.append(f"✓ ADX {adx_value:.0f} forte + DI- > DI+ (tendência baixa)")
                else:
                    rejections.append(f"✗ ADX {adx_value:.0f} mas DI+ > DI- (direção oposta)")
            elif self.use_adx_filter:
                rejections.append(f"✗ ADX {adx_value:.0f} < {self.adx_strong} (tendência fraca)")
            
            # 7. Market Structure BEARISH (LH + LL)
            if self.use_market_structure:
                if market_structure == "BEARISH":
                    score += 1
                    confirmations.append("✓ Estrutura BEARISH (LH + LL)")
                elif market_structure == "BULLISH":
                    rejections.append("✗ Estrutura BULLISH (contra o sinal)")
                else:
                    rejections.append("✗ Estrutura indefinida (RANGING)")
            
            # 8. BOS + Pullback BEARISH
            if self.use_bos_pullback:
                if bos_analysis["bos_type"] == "BEARISH" and bos_analysis["pullback_valid"]:
                    score += 1
                    confirmations.append(f"✓ BOS Bearish + Pullback ({bos_analysis['retracement']:.0f}%)")
                elif bos_analysis["bos_type"] == "BEARISH":
                    rejections.append(f"✗ BOS Bearish sem pullback válido")
                else:
                    rejections.append("✗ Sem BOS Bearish")
            
            # 9. Order Block BEARISH
            if self.use_order_blocks:
                if ob_analysis["in_ob"] and ob_analysis["ob"] and ob_analysis["ob"]["type"] == "BEARISH":
                    score += 1
                    ob = ob_analysis["ob"]
                    if ob_analysis["distance_pips"] == 0:
                        confirmations.append(f"✓ Preço em Bearish OB ({ob['low']:.5f}-{ob['high']:.5f})")
                    else:
                        confirmations.append(f"✓ Próximo de Bearish OB ({ob_analysis['distance_pips']:.0f} pips)")
                else:
                    rejections.append("✗ Sem Order Block Bearish")
        
        elif signal_type == "BUY":
            # 1. SMA Crossover UP
            crossover = prev['sma_fast'] <= prev['sma_slow'] and last['sma_fast'] > last['sma_slow']
            if crossover:
                score += 1
                confirmations.append("✓ SMA9 cruzou acima de SMA21")
            else:
                rejections.append("✗ Sem cruzamento de SMA")
            
            # 2. RSI Momentum (< 45 para compra = força compradora)
            if last['rsi'] < self.rsi_momentum_buy:
                score += 1
                confirmations.append(f"✓ RSI {last['rsi']:.1f} < {self.rsi_momentum_buy} (momentum comprador)")
            else:
                rejections.append(f"✗ RSI {last['rsi']:.1f} > {self.rsi_momentum_buy} (sem momentum)")
            
            # 3. MACD acima da Signal Line
            if self.use_macd_filter and 'macd' in df.columns:
                if last['macd'] > last['macd_signal']:
                    score += 1
                    confirmations.append("✓ MACD acima da Signal Line")
                else:
                    rejections.append("✗ MACD abaixo da Signal Line")
            
            # 4. Preço acima da SMA21 (tendência de alta)
            if last['close'] > last['sma_slow']:
                score += 1
                confirmations.append("✓ Preço acima da SMA21 (tendência)")
            else:
                rejections.append("✗ Preço abaixo da SMA21")
            
            # 5. Volume acima da média
            if self.use_volume_filter and 'volume_sma' in df.columns:
                current_vol = df['tick_volume'].iloc[-1] if 'tick_volume' in df.columns else 0
                if current_vol > last['volume_sma'] * 1.1:
                    score += 1
                    confirmations.append("✓ Volume acima da média")
                else:
                    rejections.append("✗ Volume abaixo da média")
            
            # 6. ADX forte + DI+ > DI- (tendência de alta confirmada)
            if self.use_adx_filter and adx_value >= self.adx_strong:
                if plus_di > minus_di:
                    score += 1
                    confirmations.append(f"✓ ADX {adx_value:.0f} forte + DI+ > DI- (tendência alta)")
                else:
                    rejections.append(f"✗ ADX {adx_value:.0f} mas DI- > DI+ (direção oposta)")
            elif self.use_adx_filter:
                rejections.append(f"✗ ADX {adx_value:.0f} < {self.adx_strong} (tendência fraca)")
            
            # 7. Market Structure BULLISH (HH + HL)
            if self.use_market_structure:
                if market_structure == "BULLISH":
                    score += 1
                    confirmations.append("✓ Estrutura BULLISH (HH + HL)")
                elif market_structure == "BEARISH":
                    rejections.append("✗ Estrutura BEARISH (contra o sinal)")
                else:
                    rejections.append("✗ Estrutura indefinida (RANGING)")
            
            # 8. BOS + Pullback BULLISH
            if self.use_bos_pullback:
                if bos_analysis["bos_type"] == "BULLISH" and bos_analysis["pullback_valid"]:
                    score += 1
                    confirmations.append(f"✓ BOS Bullish + Pullback ({bos_analysis['retracement']:.0f}%)")
                elif bos_analysis["bos_type"] == "BULLISH":
                    rejections.append(f"✗ BOS Bullish sem pullback válido")
                else:
                    rejections.append("✗ Sem BOS Bullish")
            
            # 9. Order Block BULLISH
            if self.use_order_blocks:
                if ob_analysis["in_ob"] and ob_analysis["ob"] and ob_analysis["ob"]["type"] == "BULLISH":
                    score += 1
                    ob = ob_analysis["ob"]
                    if ob_analysis["distance_pips"] == 0:
                        confirmations.append(f"✓ Preço em Bullish OB ({ob['low']:.5f}-{ob['high']:.5f})")
                    else:
                        confirmations.append(f"✓ Próximo de Bullish OB ({ob_analysis['distance_pips']:.0f} pips)")
                else:
                    rejections.append("✗ Sem Order Block Bullish")
        
        return score, confirmations, rejections
    
    def _get_score_label(self, score: int) -> str:
        """Retorna label do score"""
        if score >= 9:
            return "🔥 SINAL PERFEITO (9/9)"
        elif score >= 8:
            return "💪 SINAL MUITO FORTE (8/9)"
        elif score >= 7:
            return "👍 SINAL FORTE (7/9)"
        elif score >= 6:
            return "✅ SINAL BOM (6/9)"
        elif score >= 5:
            return "⚠️ SINAL MÉDIO (5/9)"
        elif score >= 4:
            return "❌ SINAL FRACO (4/9)"
        else:
            return "🚫 SINAL MUITO FRACO (<4/9)"

    def analyze(self, df: pd.DataFrame, open_positions: List[Position]) -> TradeSignal:
        # Inicializa com valores vazios para evitar erro
        empty_indicators = {"rsi": 0, "sma_fast": 0, "sma_slow": 0, "atr": 0, "macd": 0, "signal_score": 0, "adx": 0, "plus_di": 0, "minus_di": 0}

        if df.empty or len(df) < max(self.slow_period, self.atr_period, self.macd_slow, self.adx_period) + 5:
            return TradeSignal(SignalType.HOLD, 0.0, comment="Dados insuficientes", indicators=empty_indicators)

        # Cálculos de Indicadores Básicos
        df['sma_fast'] = df['close'].rolling(window=self.fast_period).mean()
        df['sma_slow'] = df['close'].rolling(window=self.slow_period).mean()
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        df['atr'] = self._calculate_atr(df, self.atr_period)
        
        # Novos Indicadores PRO v2.0
        df['macd'], df['macd_signal'], df['macd_hist'] = self._calculate_macd(df['close'])
        df['volume_sma'] = self._calculate_volume_sma(df, self.volume_period)
        
        # ADX - Detecção de Tendência vs Range
        df['adx'], df['plus_di'], df['minus_di'] = self._calculate_adx(df, self.adx_period)

        last = df.iloc[-1]
        prev = df.iloc[-2]
        current_price = last['close']
        atr_value = last['atr']
        adx_value = last['adx'] if not pd.isna(last['adx']) else 0
        plus_di = last['plus_di'] if not pd.isna(last['plus_di']) else 0
        minus_di = last['minus_di'] if not pd.isna(last['minus_di']) else 0
        
        # Calcula percentil de volatilidade
        atr_percentile, atr_vol_status = self._calculate_atr_percentile(df, atr_value)
        
        # Analisa estrutura de mercado
        market_structure, structure_details = self._analyze_market_structure(df)
        structure_emoji = self._get_structure_emoji(market_structure)
        
        # Analisa BOS + Pullback
        bos_analysis = self._analyze_bos_pullback(df)
        
        # Detecta Order Blocks
        order_blocks = []
        ob_analysis_buy = {"in_ob": False, "ob": None, "distance_pips": 0}
        ob_analysis_sell = {"in_ob": False, "ob": None, "distance_pips": 0}
        ob_summary = "Nenhum OB ativo"
        
        if self.use_order_blocks:
            order_blocks = self._detect_order_blocks(df, atr_value)
            ob_analysis_buy = self._check_price_in_order_block(current_price, order_blocks, "BUY")
            ob_analysis_sell = self._check_price_in_order_block(current_price, order_blocks, "SELL")
            ob_summary = self._get_order_blocks_summary(order_blocks)
        
        # Snapshot dos indicadores
        indicators_snapshot = {
            "rsi": round(last['rsi'], 2),
            "sma_fast": round(last['sma_fast'], 5),
            "sma_slow": round(last['sma_slow'], 5),
            "atr": round(atr_value, 5),
            "atr_percentile": round(atr_percentile, 0),
            "macd": round(last['macd'], 5),
            "macd_signal": round(last['macd_signal'], 5),
            "signal_score": 0,
            "adx": round(adx_value, 1),
            "plus_di": round(plus_di, 1),
            "minus_di": round(minus_di, 1),
            "market_structure": market_structure,
            "structure_details": structure_details,
            "bos_type": bos_analysis["bos_type"],
            "bos_pullback_valid": bos_analysis["pullback_valid"],
            "bos_retracement": bos_analysis["retracement"],
            "order_blocks": len(order_blocks),
            "ob_summary": ob_summary,
            "in_bullish_ob": ob_analysis_buy["in_ob"],
            "in_bearish_ob": ob_analysis_sell["in_ob"]
        }

        # Se já posicionado, retorna HOLD com indicadores atuais
        if len(open_positions) > 0:
            return TradeSignal(SignalType.HOLD, current_price, comment="Já posicionado", indicators=indicators_snapshot)

        # Validar ATR (evitar divisão por zero ou valores absurdos)
        if pd.isna(atr_value) or atr_value <= 0:
            return TradeSignal(SignalType.HOLD, current_price, comment="ATR inválido", indicators=indicators_snapshot)
        
        # --- FILTRO DE VOLATILIDADE: Bloqueia em extremos ---
        if self.use_volatility_filter:
            if atr_percentile < self.atr_percentile_low:
                return TradeSignal(
                    SignalType.HOLD, 
                    current_price, 
                    comment=f"Volatilidade {atr_vol_status}",
                    indicators=indicators_snapshot
                )
            elif atr_percentile > self.atr_percentile_high:
                return TradeSignal(
                    SignalType.HOLD, 
                    current_price, 
                    comment=f"Volatilidade {atr_vol_status}",
                    indicators=indicators_snapshot
                )
        
        # --- FILTRO ADX: Bloqueia trades em mercado lateral ---
        if self.use_adx_filter and adx_value < self.adx_threshold:
            adx_status = self._get_adx_status(adx_value)
            return TradeSignal(
                SignalType.HOLD, 
                current_price, 
                comment=f"ADX {adx_value:.1f} < {self.adx_threshold} | {adx_status}",
                indicators=indicators_snapshot
            )

        # Definição de SL e TP Dinâmicos via ATR
        sl_dist = atr_value * self.atr_mult_sl
        tp_dist = atr_value * self.atr_mult_tp
        
        # Distância mínima de stops (evita erro "Invalid stops" da corretora)
        # Detecta se é par JPY (preço > 100) ou par normal (preço < 10)
        if current_price > 100:
            # Par JPY (ex: USDJPY ~157) - pip = 0.01
            MIN_STOP_DISTANCE = 0.200  # 20 pips para JPY (spread pode ser ~10 pips)
        else:
            # Par normal (ex: EURUSD ~1.16) - pip = 0.0001
            MIN_STOP_DISTANCE = 0.00150  # 15 pips
        
        if sl_dist < MIN_STOP_DISTANCE:
            sl_dist = MIN_STOP_DISTANCE
            tp_dist = MIN_STOP_DISTANCE * 2  # Mantém ratio 1:2
        
        # --- ANTI-STOP HUNT: Calcula SL inteligente ---
        sl_reason_buy = ""
        sl_reason_sell = ""
        if self.use_anti_stop_hunt:
            # Pré-calcula SL para BUY e SELL
            sl_buy, sl_reason_buy = self._calculate_smart_sl(df, current_price, sl_dist, is_buy=True)
            sl_sell, sl_reason_sell = self._calculate_smart_sl(df, current_price, sl_dist, is_buy=False)
        else:
            sl_buy = current_price - sl_dist
            sl_sell = current_price + sl_dist

        # --- MODO AGRESSIVO (APENAS PARA TESTES!) ---
        if self.aggressive_mode:
            if current_price > prev['close']:
                logger.info(f"🔥 MODO AGRESSIVO: Preço subiu! COMPRANDO! RSI: {last['rsi']:.2f}")
                return TradeSignal(
                    SignalType.BUY, 
                    current_price, 
                    sl=sl_buy,
                    tp=current_price + tp_dist,
                    comment="TESTE AGRESSIVO",
                    indicators=indicators_snapshot
                )
            elif current_price < prev['close']:
                logger.info(f"🔥 MODO AGRESSIVO: Preço caiu! VENDENDO! RSI: {last['rsi']:.2f}")
                return TradeSignal(
                    SignalType.SELL, 
                    current_price, 
                    sl=sl_sell,
                    tp=current_price - tp_dist,
                    comment="TESTE AGRESSIVO",
                    indicators=indicators_snapshot
                )
            return TradeSignal(SignalType.HOLD, current_price, comment="Sem movimento", indicators=indicators_snapshot)

        # --- ESTRATÉGIA PRO v2.1 (PRODUÇÃO) ---
        
        # Detecta cruzamento de médias
        crossover_buy = prev['sma_fast'] <= prev['sma_slow'] and last['sma_fast'] > last['sma_slow']
        crossover_sell = prev['sma_fast'] >= prev['sma_slow'] and last['sma_fast'] < last['sma_slow']
        
        # 1. Sinal de COMPRA com Score
        if crossover_buy:
            # Verifica estrutura de mercado como filtro
            if self.use_market_structure and self.structure_as_filter:
                if market_structure == "BEARISH":
                    logger.warning(f"🚫 Market Structure: Sinal de COMPRA bloqueado - Estrutura BEARISH")
                    return TradeSignal(SignalType.HOLD, current_price, 
                                       comment=f"Estrutura BEARISH contra BUY", indicators=indicators_snapshot)
            
            score, confirmations, rejections = self._calculate_signal_score(df, "BUY", market_structure, bos_analysis, ob_analysis_buy)
            indicators_snapshot["signal_score"] = score
            score_label = self._get_score_label(score)
            
            # Log Anti-Stop Hunt
            if self.use_anti_stop_hunt and sl_reason_buy:
                logger.info(f"🛡️ Anti-Stop Hunt: {sl_reason_buy}")
            
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"📊 ANÁLISE DE SINAL DE COMPRA")
            logger.info(f"📈 {score_label}")
            for conf in confirmations:
                logger.info(f"   {conf}")
            for rej in rejections:
                logger.info(f"   {rej}")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            if score >= self.min_signal_score:
                logger.info(f"✅ Score {score}/9 >= {self.min_signal_score} - EXECUTANDO COMPRA!")
                # Gera comment simples sem caracteres especiais
                simple_comment = f"Buy S{score}"
                
                return TradeSignal(
                    SignalType.BUY, 
                    current_price, 
                    sl=sl_buy,
                    tp=current_price + tp_dist,
                    comment=simple_comment,
                    indicators=indicators_snapshot
                )
            else:
                logger.warning(f"❌ Score {score}/9 < {self.min_signal_score} - SINAL REJEITADO!")
                return TradeSignal(SignalType.HOLD, current_price, 
                                   comment=f"Sinal fraco ({score}/9)", indicators=indicators_snapshot)

        # 2. Sinal de VENDA com Score
        if crossover_sell:
            # Verifica estrutura de mercado como filtro
            if self.use_market_structure and self.structure_as_filter:
                if market_structure == "BULLISH":
                    logger.warning(f"🚫 Market Structure: Sinal de VENDA bloqueado - Estrutura BULLISH")
                    return TradeSignal(SignalType.HOLD, current_price, 
                                       comment=f"Estrutura BULLISH contra SELL", indicators=indicators_snapshot)
            
            score, confirmations, rejections = self._calculate_signal_score(df, "SELL", market_structure, bos_analysis, ob_analysis_sell)
            indicators_snapshot["signal_score"] = score
            score_label = self._get_score_label(score)
            
            # Log Anti-Stop Hunt
            if self.use_anti_stop_hunt and sl_reason_sell:
                logger.info(f"🛡️ Anti-Stop Hunt: {sl_reason_sell}")
            
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"📊 ANÁLISE DE SINAL DE VENDA")
            logger.info(f"📉 {score_label}")
            for conf in confirmations:
                logger.info(f"   {conf}")
            for rej in rejections:
                logger.info(f"   {rej}")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            if score >= self.min_signal_score:
                logger.info(f"✅ Score {score}/9 >= {self.min_signal_score} - EXECUTANDO VENDA!")
                
                # Gera comment simples sem caracteres especiais
                simple_comment = f"Sell S{score}"
                
                return TradeSignal(
                    SignalType.SELL, 
                    current_price, 
                    sl=sl_sell,
                    tp=current_price - tp_dist,
                    comment=simple_comment,
                    indicators=indicators_snapshot
                )
            else:
                logger.warning(f"❌ Score {score}/9 < {self.min_signal_score} - SINAL REJEITADO!")
                return TradeSignal(SignalType.HOLD, current_price, 
                                   comment=f"Sinal fraco ({score}/9)", indicators=indicators_snapshot)

        # --- ENTRADA POR RSI EXTREMO (mantido como opção) ---
        # REGRA DE OURO: NUNCA use RSI extremo contra tendência forte!
        # Se ADX > 25 e DI+ > DI-, o mercado está em ALTA forte - RSI pode ficar em sobrecompra por horas
        # Se ADX > 25 e DI- > DI+, o mercado está em BAIXA forte - RSI pode ficar em sobrevenda por horas
        if self.use_rsi_extreme:
            adx_val = last.get('adx', 0)
            plus_di = last.get('plus_di', 0)
            minus_di = last.get('minus_di', 0)
            
            # Detecta tendência MUITO forte (só ignora RSI se ADX > adx_ignore_rsi_extreme)
            # Antes era 25, agora é 40 por padrão - permite mais entradas em RSI extremo
            strong_uptrend = adx_val > self.adx_ignore_rsi_extreme and plus_di > minus_di
            strong_downtrend = adx_val > self.adx_ignore_rsi_extreme and minus_di > plus_di
            
            # Compra em sobrevenda extrema (mas NÃO se tendência de baixa MUITO forte)
            if last['rsi'] < self.rsi_extreme_oversold:
                if strong_downtrend:
                    logger.warning(f"⚠️ RSI {last['rsi']:.1f} em sobrevenda, mas ADX {adx_val:.0f} + DI- dominante = TENDÊNCIA DE BAIXA MUITO FORTE! Ignorando RSI extremo.")
                else:
                    score, confirmations, rejections = self._calculate_signal_score(df, "BUY", market_structure, bos_analysis, ob_analysis_buy)
                    # RSI extremo adiciona +1 ao score
                    score += 1
                    confirmations.append(f"✓ RSI EXTREMO {last['rsi']:.1f} (sobrevenda)")
                    indicators_snapshot["signal_score"] = score
                    
                    if score >= self.min_signal_score:
                        logger.info(f"🔵 RSI EXTREMO + Score {score}/9 - COMPRANDO!")
                        return TradeSignal(
                            SignalType.BUY, 
                            current_price, 
                            sl=sl_buy,
                            tp=current_price + tp_dist,
                            comment=f"RSI{int(last['rsi'])} Buy S{score}",
                            indicators=indicators_snapshot
                        )
            
            # Venda em sobrecompra extrema (mas NÃO se tendência de alta MUITO forte)
            if last['rsi'] > self.rsi_extreme_overbought:
                if strong_uptrend:
                    logger.warning(f"⚠️ RSI {last['rsi']:.1f} em sobrecompra, mas ADX {adx_val:.0f} + DI+ dominante = TENDÊNCIA DE ALTA MUITO FORTE! Ignorando RSI extremo.")
                else:
                    score, confirmations, rejections = self._calculate_signal_score(df, "SELL", market_structure, bos_analysis, ob_analysis_sell)
                    # RSI extremo adiciona +1 ao score
                    score += 1
                    confirmations.append(f"✓ RSI EXTREMO {last['rsi']:.1f} (sobrecompra)")
                    indicators_snapshot["signal_score"] = score
                    
                    if score >= self.min_signal_score:
                        logger.info(f"🔴 RSI EXTREMO + Score {score}/9 - VENDENDO!")
                        return TradeSignal(
                            SignalType.SELL, 
                            current_price, 
                            sl=sl_sell,
                            tp=current_price - tp_dist,
                            comment=f"RSI{int(last['rsi'])} Sell S{score}",
                            indicators=indicators_snapshot
                        )

        return TradeSignal(SignalType.HOLD, current_price, comment="Aguardando setup", indicators=indicators_snapshot)
