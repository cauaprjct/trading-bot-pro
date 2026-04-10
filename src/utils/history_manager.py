"""
Gerenciador de Dados Históricos (OTIMIZADO)
Usa CACHE em memória para evitar leitura repetida de arquivos.
"""
import os
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Optional, Dict
from .logger import setup_logger

logger = setup_logger("HistoryManager")

class HistoryManager:
    def __init__(self, data_dir: str = "historical_data"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self._cache: Dict[str, pd.DataFrame] = {}
        self._cache_loaded: Dict[str, bool] = {}
    
    def _get_cache_key(self, symbol: str, timeframe: int) -> str:
        return f"{symbol}_{timeframe}"
    
    def _get_timeframe_name(self, timeframe: int) -> str:
        names = {
            mt5.TIMEFRAME_M1: "M1", mt5.TIMEFRAME_M5: "M5",
            mt5.TIMEFRAME_M15: "M15", mt5.TIMEFRAME_M30: "M30",
            mt5.TIMEFRAME_H1: "H1", mt5.TIMEFRAME_H4: "H4",
            mt5.TIMEFRAME_D1: "D1", mt5.TIMEFRAME_W1: "W1"
        }
        return names.get(timeframe, f"TF{timeframe}")
    
    def _get_file_path(self, symbol: str, timeframe: int, year_month: str) -> str:
        tf_name = self._get_timeframe_name(timeframe)
        symbol_dir = os.path.join(self.data_dir, symbol.replace("-", "_"))
        if not os.path.exists(symbol_dir):
            os.makedirs(symbol_dir)
        return os.path.join(symbol_dir, f"{tf_name}_{year_month}.csv")
    
    def _load_all_to_cache(self, symbol: str, timeframe: int) -> pd.DataFrame:
        cache_key = self._get_cache_key(symbol, timeframe)
        if self._cache_loaded.get(cache_key, False):
            return self._cache.get(cache_key, pd.DataFrame())
        
        dfs = []
        tf_name = self._get_timeframe_name(timeframe)
        symbol_dir = os.path.join(self.data_dir, symbol.replace("-", "_"))
        
        if os.path.exists(symbol_dir):
            for fn in sorted(os.listdir(symbol_dir)):
                if fn.startswith(f"{tf_name}_") and fn.endswith(".csv"):
                    try:
                        df = pd.read_csv(os.path.join(symbol_dir, fn))
                        df['time'] = pd.to_datetime(df['time'])
                        dfs.append(df)
                    except Exception as e:
                        logger.warning(f"Erro {fn}: {e}")
        
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            combined = combined.drop_duplicates(subset=['time'])
            combined = combined.sort_values('time').reset_index(drop=True)
            self._cache[cache_key] = combined
            self._cache_loaded[cache_key] = True
            logger.info(f"Cache: {symbol} {tf_name} | {len(combined):,} barras")
            return combined
        self._cache_loaded[cache_key] = True
        return pd.DataFrame()

    def download_from_mt5(self, symbol: str, timeframe: int, 
                          start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        try:
            rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
            if rates is None or len(rates) == 0:
                return None
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except Exception as e:
            logger.error(f"Erro download: {e}")
            return None
    
    def save_to_file(self, df: pd.DataFrame, symbol: str, timeframe: int, year_month: str):
        try:
            df.to_csv(self._get_file_path(symbol, timeframe, year_month), index=False)
        except Exception as e:
            logger.error(f"Erro save: {e}")
    
    def load_from_file(self, symbol: str, timeframe: int, year_month: str) -> Optional[pd.DataFrame]:
        fp = self._get_file_path(symbol, timeframe, year_month)
        if not os.path.exists(fp):
            return None
        try:
            df = pd.read_csv(fp)
            df['time'] = pd.to_datetime(df['time'])
            return df
        except:
            return None
    
    def download_and_save_month(self, symbol: str, timeframe: int, 
                                year: int, month: int, force: bool = False) -> bool:
        year_month = f"{year}-{month:02d}"
        fp = self._get_file_path(symbol, timeframe, year_month)
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(seconds=1)
        if start > datetime.now():
            return False
        is_current = (year == datetime.now().year and month == datetime.now().month)
        if end > datetime.now():
            end = datetime.now()
        if os.path.exists(fp) and not force and not is_current:
            return True
        df = self.download_from_mt5(symbol, timeframe, start, end)
        if df is not None and len(df) > 0:
            self.save_to_file(df, symbol, timeframe, year_month)
            return True
        return False
    
    def ensure_history(self, symbol: str, timeframe: int, months: int = 3) -> bool:
        logger.info(f"Verificando: {symbol} {self._get_timeframe_name(timeframe)} {months}m")
        now = datetime.now()
        ok = 0
        for i in range(months):
            target = now - timedelta(days=30*i)
            if self.download_and_save_month(symbol, timeframe, target.year, target.month):
                ok += 1
        logger.info(f"Historico: {ok}/{months} meses")
        return ok > 0

    def get_data(self, symbol: str, timeframe: int, bars: int = 500, 
                 include_live: bool = True) -> pd.DataFrame:
        """OTIMIZADO: Usa cache + apenas 100 barras live do MT5"""
        cached = self._load_all_to_cache(symbol, timeframe)
        
        if cached.empty:
            try:
                rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
                if rates is not None and len(rates) > 0:
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    return df
            except:
                pass
            return pd.DataFrame()
        
        if include_live:
            try:
                rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
                if rates is not None and len(rates) > 0:
                    live = pd.DataFrame(rates)
                    live['time'] = pd.to_datetime(live['time'], unit='s')
                    combined = pd.concat([cached, live], ignore_index=True)
                    combined = combined.drop_duplicates(subset=['time'], keep='last')
                    combined = combined.sort_values('time')
                    self._cache[self._get_cache_key(symbol, timeframe)] = combined
                    if len(combined) > bars:
                        return combined.tail(bars).reset_index(drop=True)
                    return combined.reset_index(drop=True)
            except:
                pass
        
        if len(cached) > bars:
            return cached.tail(bars).reset_index(drop=True)
        return cached.reset_index(drop=True)

    def get_higher_timeframe_trend(self, symbol: str, timeframe: int = None) -> str:
        """Analisa tendencia do H1"""
        if timeframe is None:
            timeframe = mt5.TIMEFRAME_H1
        df = self.get_data(symbol, timeframe, bars=50)
        if df.empty or len(df) < 21:
            return "NEUTRAL"
        df['sma_fast'] = df['close'].rolling(9).mean()
        df['sma_slow'] = df['close'].rolling(21).mean()
        last = df.iloc[-1]
        if pd.isna(last['sma_fast']) or pd.isna(last['sma_slow']):
            return "NEUTRAL"
        if last['sma_fast'] > last['sma_slow']:
            return "UP"
        elif last['sma_fast'] < last['sma_slow']:
            return "DOWN"
        return "NEUTRAL"

    def get_status(self) -> Dict:
        status = {"symbols": {}, "total_files": 0, "total_size_mb": 0}
        if not os.path.exists(self.data_dir):
            return status
        for sd in os.listdir(self.data_dir):
            sp = os.path.join(self.data_dir, sd)
            if os.path.isdir(sp):
                files = [f for f in os.listdir(sp) if f.endswith('.csv')]
                size = sum(os.path.getsize(os.path.join(sp, f)) for f in files)
                status["symbols"][sd] = {"files": len(files), "size_mb": size/(1024*1024)}
                status["total_files"] += len(files)
                status["total_size_mb"] += size/(1024*1024)
        return status

    def print_status(self):
        s = self.get_status()
        logger.info(f"Historico: {s['total_files']} arquivos | {s['total_size_mb']:.2f} MB")
        for sym, info in s["symbols"].items():
            logger.info(f"   {sym}: {info['files']} arquivos ({info['size_mb']:.2f} MB)")
