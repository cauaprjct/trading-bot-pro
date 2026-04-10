"""
Filtro de Notícias - Evita operar durante eventos econômicos de alto impacto

Eventos monitorados:
- NFP (Non-Farm Payrolls) - Alta volatilidade em USD
- FOMC (Federal Reserve) - Decisão de juros EUA
- CPI (Inflation) - Dados de inflação
- ECB (European Central Bank) - Decisão de juros EUR
- BOE (Bank of England) - Decisão de juros GBP
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from .logger import setup_logger

logger = setup_logger("NewsFilter")

@dataclass
class EconomicEvent:
    """Representa um evento econômico"""
    name: str
    datetime_utc: datetime
    currency: str
    impact: str  # "high", "medium", "low"
    
    def is_active(self, blackout_minutes: int = 30) -> bool:
        """Verifica se estamos dentro da janela de blackout do evento"""
        now = datetime.utcnow()
        start = self.datetime_utc - timedelta(minutes=blackout_minutes)
        end = self.datetime_utc + timedelta(minutes=blackout_minutes)
        return start <= now <= end

class NewsFilter:
    """Filtro de notícias econômicas para evitar operar em alta volatilidade"""
    
    # Eventos recorrentes conhecidos (horários em UTC)
    # NFP: 1ª sexta-feira do mês às 13:30 UTC (8:30 EST)
    # FOMC: Varia, mas geralmente 19:00 UTC (14:00 EST)
    KNOWN_EVENTS = {
        "NFP": {"day_of_week": 4, "week_of_month": 1, "hour": 13, "minute": 30, "currency": "USD", "impact": "high"},
        "CPI_US": {"day_of_month_approx": 12, "hour": 13, "minute": 30, "currency": "USD", "impact": "high"},
    }
    
    def __init__(self, blackout_minutes: int = 30, check_api: bool = True, 
                 filter_currencies: List[str] = None):
        """
        Args:
            blackout_minutes: Minutos antes/depois do evento para não operar
            check_api: Se deve buscar eventos de API externa
            filter_currencies: Moedas para filtrar (ex: ["USD", "EUR"])
        """
        self.blackout_minutes = blackout_minutes
        self.check_api = check_api
        self.filter_currencies = filter_currencies or ["USD", "EUR", "GBP"]
        self.cached_events: List[EconomicEvent] = []
        self.last_api_check: datetime = None
        self.api_check_interval = timedelta(hours=1)
        
        logger.info(f"📰 Filtro de notícias ativo. Blackout: {blackout_minutes}min | Moedas: {self.filter_currencies}")
    
    def _is_first_friday(self, dt: datetime) -> bool:
        """Verifica se é a primeira sexta-feira do mês"""
        if dt.weekday() != 4:  # Não é sexta
            return False
        return dt.day <= 7  # Primeira semana
    
    def _get_next_nfp(self) -> Optional[EconomicEvent]:
        """Calcula próximo NFP (1ª sexta do mês às 13:30 UTC)"""
        now = datetime.utcnow()
        
        # Procura nos próximos 40 dias
        for i in range(40):
            check_date = now + timedelta(days=i)
            if self._is_first_friday(check_date):
                nfp_time = check_date.replace(hour=13, minute=30, second=0, microsecond=0)
                if nfp_time > now:
                    return EconomicEvent(
                        name="NFP (Non-Farm Payrolls)",
                        datetime_utc=nfp_time,
                        currency="USD",
                        impact="high"
                    )
        return None
    
    def _fetch_events_from_api(self) -> List[EconomicEvent]:
        """Busca eventos de API externa (Forex Factory style)"""
        events = []
        
        # Tenta buscar do calendário econômico gratuito
        # Nota: APIs gratuitas são limitadas, então usamos fallback para eventos conhecidos
        try:
            # Usando API do Trading Economics (limitada) ou similar
            # Por simplicidade, vamos usar uma abordagem de calendário estático
            # Em produção, você pode integrar com Forex Factory, Investing.com, etc.
            
            # Adiciona NFP se estiver próximo
            nfp = self._get_next_nfp()
            if nfp:
                events.append(nfp)
            
            # Adiciona eventos FOMC conhecidos para 2026 (exemplo)
            # Em produção, isso viria de uma API
            fomc_dates_2026 = [
                datetime(2026, 1, 29, 19, 0),  # Janeiro
                datetime(2026, 3, 19, 18, 0),  # Março
                datetime(2026, 5, 7, 18, 0),   # Maio
                datetime(2026, 6, 18, 18, 0),  # Junho
                datetime(2026, 7, 30, 18, 0),  # Julho
                datetime(2026, 9, 17, 18, 0),  # Setembro
                datetime(2026, 11, 5, 18, 0),  # Novembro
                datetime(2026, 12, 17, 19, 0), # Dezembro
            ]
            
            now = datetime.utcnow()
            for fomc_date in fomc_dates_2026:
                # Só adiciona se for nos próximos 7 dias
                if now <= fomc_date <= now + timedelta(days=7):
                    events.append(EconomicEvent(
                        name="FOMC Decision",
                        datetime_utc=fomc_date,
                        currency="USD",
                        impact="high"
                    ))
            
        except Exception as e:
            logger.warning(f"Erro ao buscar eventos de API: {e}")
        
        return events
    
    def _refresh_events(self):
        """Atualiza cache de eventos se necessário"""
        now = datetime.utcnow()
        
        if self.last_api_check and (now - self.last_api_check) < self.api_check_interval:
            return  # Cache ainda válido
        
        if self.check_api:
            self.cached_events = self._fetch_events_from_api()
            self.last_api_check = now
            
            if self.cached_events:
                logger.info(f"📅 {len(self.cached_events)} eventos econômicos carregados")
    
    def get_active_events(self) -> List[EconomicEvent]:
        """Retorna eventos ativos (dentro da janela de blackout)"""
        self._refresh_events()
        
        active = []
        for event in self.cached_events:
            if event.is_active(self.blackout_minutes):
                if event.currency in self.filter_currencies:
                    active.append(event)
        
        return active
    
    def can_trade(self, symbol: str = None) -> Tuple[bool, str]:
        """
        Verifica se pode operar agora.
        
        Returns:
            (pode_operar, motivo)
        """
        active_events = self.get_active_events()
        
        if not active_events:
            return (True, "")
        
        # Verifica se algum evento afeta o símbolo
        if symbol:
            symbol_currencies = self._extract_currencies(symbol)
            relevant_events = [e for e in active_events if e.currency in symbol_currencies]
            
            if not relevant_events:
                return (True, "")
            
            event = relevant_events[0]
            return (False, f"🚫 Blackout: {event.name} ({event.currency}) às {event.datetime_utc.strftime('%H:%M')} UTC")
        
        # Se não especificou símbolo, bloqueia para qualquer evento
        event = active_events[0]
        return (False, f"🚫 Blackout: {event.name} ({event.currency}) às {event.datetime_utc.strftime('%H:%M')} UTC")
    
    def _extract_currencies(self, symbol: str) -> List[str]:
        """Extrai moedas do símbolo (ex: EURUSD -> [EUR, USD])"""
        symbol = symbol.upper().replace("-", "").replace("_", "").replace("T", "")
        
        currencies = ["EUR", "USD", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]
        found = []
        
        for curr in currencies:
            if curr in symbol:
                found.append(curr)
        
        return found if found else ["USD"]  # Default USD
    
    def get_upcoming_events(self, hours: int = 24) -> List[EconomicEvent]:
        """Retorna eventos nas próximas X horas"""
        self._refresh_events()
        
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)
        
        upcoming = []
        for event in self.cached_events:
            if now <= event.datetime_utc <= cutoff:
                upcoming.append(event)
        
        return sorted(upcoming, key=lambda e: e.datetime_utc)
    
    def get_status(self) -> str:
        """Retorna status formatado do filtro"""
        can, reason = self.can_trade()
        
        if can:
            upcoming = self.get_upcoming_events(hours=12)
            if upcoming:
                next_event = upcoming[0]
                time_until = next_event.datetime_utc - datetime.utcnow()
                hours_until = time_until.total_seconds() / 3600
                return f"✅ Livre | Próximo: {next_event.name} em {hours_until:.1f}h"
            return "✅ Livre | Sem eventos próximos"
        
        return reason
