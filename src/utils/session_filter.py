"""
Session Filter - Filtro de Sessão (Killzones)

Só permite trades durante os horários de maior liquidez e menor manipulação.
Baseado em conceitos de Smart Money / ICT.

Killzones (horário de Brasília - BRT):
- London Killzone: 05:00 - 07:00 (melhor liquidez europeia)
- NY Killzone: 10:00 - 12:00 (overlap Londres/NY - maior volume)

Horários a EVITAR:
- Abertura de Londres (04:00 - 04:30) - alta manipulação
- Abertura de NY (09:30 - 10:00) - alta manipulação  
- Fechamento de Londres (13:00 - 14:00) - reversões falsas
- Sessão Asiática (20:00 - 04:00) - baixa liquidez para EURUSD
"""

from datetime import datetime, time
from typing import Tuple
import pytz

class SessionFilter:
    """
    Filtro de sessão baseado em Killzones.
    Só permite trades nos horários de maior probabilidade de sucesso.
    """
    
    def __init__(
        self,
        # Killzone de Londres (BRT)
        london_start: time = time(5, 0),
        london_end: time = time(7, 0),
        # Killzone de NY (BRT)
        ny_start: time = time(10, 0),
        ny_end: time = time(12, 0),
        # Minutos para evitar após abertura de sessão
        avoid_open_minutes: int = 30,
        # Timezone
        timezone: str = "America/Sao_Paulo"
    ):
        self.london_start = london_start
        self.london_end = london_end
        self.ny_start = ny_start
        self.ny_end = ny_end
        self.avoid_open_minutes = avoid_open_minutes
        self.tz = pytz.timezone(timezone)
        
        # Horários de abertura das sessões (para evitar)
        self.london_open = time(4, 0)   # 04:00 BRT
        self.ny_open = time(9, 30)      # 09:30 BRT
        self.london_close = time(13, 0) # 13:00 BRT
        
    def _time_to_minutes(self, t: time) -> int:
        """Converte time para minutos desde meia-noite"""
        return t.hour * 60 + t.minute
    
    def _is_in_range(self, current: time, start: time, end: time) -> bool:
        """Verifica se horário atual está dentro do range"""
        current_min = self._time_to_minutes(current)
        start_min = self._time_to_minutes(start)
        end_min = self._time_to_minutes(end)
        
        # Range normal (não cruza meia-noite)
        if start_min <= end_min:
            return start_min <= current_min <= end_min
        # Range que cruza meia-noite
        else:
            return current_min >= start_min or current_min <= end_min
    
    def _is_near_session_open(self, current: time) -> Tuple[bool, str]:
        """
        Verifica se está próximo da abertura de uma sessão (alta manipulação)
        """
        current_min = self._time_to_minutes(current)
        
        # Abertura de Londres (04:00 - 04:30 BRT)
        london_open_min = self._time_to_minutes(self.london_open)
        if london_open_min <= current_min < london_open_min + self.avoid_open_minutes:
            remaining = (london_open_min + self.avoid_open_minutes) - current_min
            return True, f"Abertura de Londres (aguardar {remaining} min)"
        
        # Abertura de NY (09:30 - 10:00 BRT)
        ny_open_min = self._time_to_minutes(self.ny_open)
        if ny_open_min <= current_min < ny_open_min + self.avoid_open_minutes:
            remaining = (ny_open_min + self.avoid_open_minutes) - current_min
            return True, f"Abertura de NY (aguardar {remaining} min)"
        
        # Fechamento de Londres (13:00 - 14:00 BRT) - reversões falsas
        london_close_min = self._time_to_minutes(self.london_close)
        if london_close_min <= current_min < london_close_min + 60:
            remaining = (london_close_min + 60) - current_min
            return True, f"Fechamento de Londres (aguardar {remaining} min)"
        
        return False, ""
    
    def _is_asian_session(self, current: time) -> bool:
        """
        Verifica se está na sessão asiática (baixa liquidez para EURUSD)
        Sessão Asiática: 20:00 - 04:00 BRT
        """
        current_min = self._time_to_minutes(current)
        asian_start = self._time_to_minutes(time(20, 0))
        asian_end = self._time_to_minutes(time(4, 0))
        
        # Cruza meia-noite
        return current_min >= asian_start or current_min < asian_end
    
    def is_in_killzone(self, current: time = None) -> Tuple[bool, str]:
        """
        Verifica se está em uma killzone (horário ideal para operar)
        
        Returns:
            (True, "London Killzone") se está em killzone
            (False, "") se não está
        """
        if current is None:
            current = datetime.now(self.tz).time()
        
        hour = current.hour
        
        # Detecta se é config Asian (começa às 19:00)
        is_asian_config = self.london_start.hour >= 19
        
        if is_asian_config:
            # Sessão Asiática - períodos específicos
            if 19 <= hour < 21:
                return True, "🌅 Sydney Warmup (19:00-21:00)"
            elif 21 <= hour <= 23:
                return True, "🎯 Tokyo Killzone (21:00-00:00)"
            elif 0 <= hour < 4:
                return True, "🌙 Tokyo Late (00:00-04:00)"
            elif 4 <= hour < 5:
                return True, "⏰ London Prep (04:00-05:00)"
            return False, ""
        
        # Config padrão London/NY
        # Killzone 1 (London)
        if self._is_in_range(current, self.london_start, self.london_end):
            return True, f"London Killzone ({self.london_start.strftime('%H:%M')}-{self.london_end.strftime('%H:%M')})"
        
        # Killzone 2 (NY)
        if self._is_in_range(current, self.ny_start, self.ny_end):
            return True, f"NY Killzone ({self.ny_start.strftime('%H:%M')}-{self.ny_end.strftime('%H:%M')})"
        
        return False, ""
    
    def can_trade(self, symbol: str = None) -> Tuple[bool, str]:
        """
        Verifica se pode operar no momento atual.
        
        Returns:
            (True, "Motivo") se pode operar
            (False, "Motivo") se não pode
        """
        now = datetime.now(self.tz)
        current = now.time()
        
        # 1. Verifica se está próximo de abertura de sessão (EVITAR)
        # Só verifica se as killzones são as padrão (London/NY)
        if self.london_start.hour < 20:  # Não é Asian config
            near_open, open_reason = self._is_near_session_open(current)
            if near_open:
                return False, f"🚫 {open_reason} - Alta manipulação"
        
        # 2. Verifica se está na sessão asiática (EVITAR para EURUSD/GBPUSD)
        # Só bloqueia se NÃO estiver configurado para Asian Killzone
        if symbol and ("EUR" in symbol or "GBP" in symbol):
            if self.london_start.hour < 20:  # Não é Asian config
                if self._is_asian_session(current):
                    return False, "🌙 Sessão Asiática - Baixa liquidez para EUR/GBP"
        
        # 3. Verifica se está em uma killzone (IDEAL)
        in_killzone, killzone_name = self.is_in_killzone(current)
        if in_killzone:
            return True, f"✅ {killzone_name}"
        
        # 4. Fora de killzone mas não em horário perigoso
        # Permite operar mas com aviso
        hour = current.hour
        
        # Se é config Asian, horários aceitáveis são diferentes
        if self.london_start.hour >= 20:
            # Asian config - horários aceitáveis fora de killzone
            if 19 <= hour <= 23 or 0 <= hour < 2:
                return True, "⚠️ Fora de Killzone (Sessão Asiática ativa)"
            return False, f"🚫 Fora de Killzone ({hour}:00 BRT) - Baixa probabilidade"
        
        # Horários aceitáveis fora de killzone (config padrão London/NY)
        if 7 <= hour < 9:
            return True, "⚠️ Fora de Killzone (Londres ativa)"
        elif 12 <= hour < 13:
            return True, "⚠️ Fora de Killzone (NY ativa)"
        elif 14 <= hour < 17:
            return True, "⚠️ Fora de Killzone (NY tarde)"
        
        # Horários ruins
        return False, f"🚫 Fora de Killzone ({hour}:00 BRT) - Baixa probabilidade"
    
    def get_next_killzone(self) -> Tuple[str, int]:
        """
        Retorna a próxima killzone e quantos minutos faltam.
        
        Returns:
            (nome_killzone, minutos_restantes)
        """
        now = datetime.now(self.tz)
        current = now.time()
        current_min = self._time_to_minutes(current)
        hour = current.hour
        
        # Detecta se é config Asian
        is_asian_config = self.london_start.hour >= 19
        
        if is_asian_config:
            # Próximos períodos asiáticos
            if hour < 19:
                # Antes de Sydney
                sydney_min = self._time_to_minutes(time(19, 0))
                return "🌅 Sydney Warmup", sydney_min - current_min
            elif 19 <= hour < 21:
                # Em Sydney, próximo é Tokyo KZ
                tokyo_min = self._time_to_minutes(time(21, 0))
                return "🎯 Tokyo Killzone", tokyo_min - current_min
            elif 21 <= hour <= 23:
                # Em Tokyo KZ, próximo é Tokyo Late (meia-noite)
                return "🌙 Tokyo Late", (24 * 60 - current_min)
            elif 0 <= hour < 4:
                # Em Tokyo Late, próximo é London Prep
                prep_min = self._time_to_minutes(time(4, 0))
                return "⏰ London Prep", prep_min - current_min
            elif 4 <= hour < 5:
                # Em London Prep, próximo é London KZ (bot diurno)
                london_min = self._time_to_minutes(time(5, 0))
                return "London Killzone (bot diurno)", london_min - current_min
            else:
                # Após 05:00, próximo é Sydney (19:00)
                sydney_min = self._time_to_minutes(time(19, 0))
                return "🌅 Sydney Warmup", sydney_min - current_min
        
        # Config padrão London/NY
        kz1_name = "London Killzone"
        
        killzones = [
            (kz1_name, self.london_start),
            ("NY Killzone", self.ny_start),
        ]
        
        for name, start in killzones:
            start_min = self._time_to_minutes(start)
            if start_min > 0 and current_min < start_min:
                return name, start_min - current_min
        
        # Próxima é a primeira killzone do dia seguinte
        first_kz_min = self._time_to_minutes(self.london_start)
        if first_kz_min == 0:
            first_kz_min = self._time_to_minutes(self.ny_start)
        minutes_until = (24 * 60 - current_min) + first_kz_min
        return f"{kz1_name} (amanhã)", minutes_until
    
    def get_session_status(self) -> str:
        """
        Retorna status formatado da sessão atual.
        """
        now = datetime.now(self.tz)
        current = now.time()
        
        can_trade, reason = self.can_trade()
        in_killzone, killzone_name = self.is_in_killzone(current)
        
        if in_killzone:
            return f"🎯 {killzone_name} - HORÁRIO IDEAL"
        elif can_trade:
            return f"⚠️ {reason}"
        else:
            next_kz, minutes = self.get_next_killzone()
            hours = minutes // 60
            mins = minutes % 60
            return f"{reason} | Próxima: {next_kz} em {hours}h{mins}m"


# Função de conveniência para uso rápido
def create_session_filter(
    london_start: time = time(5, 0),
    london_end: time = time(7, 0),
    ny_start: time = time(10, 0),
    ny_end: time = time(12, 0),
    avoid_open_minutes: int = 30
) -> SessionFilter:
    """Cria um SessionFilter com configurações padrão ou customizadas"""
    return SessionFilter(
        london_start=london_start,
        london_end=london_end,
        ny_start=ny_start,
        ny_end=ny_end,
        avoid_open_minutes=avoid_open_minutes
    )
