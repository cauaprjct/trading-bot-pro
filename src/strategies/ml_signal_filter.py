"""
ML Signal Filter - Filtro de Machine Learning para sinais

Usa um modelo simples (Random Forest ou Logistic Regression) para
prever a probabilidade de sucesso de um sinal.

Features usadas:
- RSI, MACD, ADX, ATR percentile
- Market Structure, BOS, Order Blocks
- Hora do dia, dia da semana
- Volatilidade, Spread

O modelo é treinado com histórico de trades do próprio bot.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import os
from ..utils.logger import setup_logger

logger = setup_logger("MLFilter")


class MLSignalFilter:
    """
    Filtro de Machine Learning para avaliar qualidade dos sinais.
    
    Usa estatísticas históricas para calcular probabilidade de sucesso.
    Não requer bibliotecas externas de ML - usa abordagem estatística simples.
    """
    
    def __init__(
        self,
        history_file: str = "ml_trade_history.json",
        min_samples: int = 20,
        confidence_threshold: float = 0.55,
        use_time_filter: bool = True,
        use_volatility_filter: bool = True
    ):
        self.history_file = history_file
        self.min_samples = min_samples
        self.confidence_threshold = confidence_threshold
        self.use_time_filter = use_time_filter
        self.use_volatility_filter = use_volatility_filter
        
        # Histórico de trades para aprendizado
        self.trade_history: List[Dict] = []
        
        # Estatísticas por feature
        self.stats = {
            'by_hour': {},      # Win rate por hora
            'by_rsi_zone': {},  # Win rate por zona de RSI
            'by_adx_zone': {},  # Win rate por zona de ADX
            'by_structure': {}, # Win rate por estrutura de mercado
            'by_score': {},     # Win rate por score
            'by_volatility': {} # Win rate por volatilidade
        }
        
        self._load_history()
    
    def _load_history(self):
        """Carrega histórico de trades"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.trade_history = data.get('trades', [])
                    self.stats = data.get('stats', self.stats)
                logger.info(f"📊 ML Filter: {len(self.trade_history)} trades carregados")
        except Exception as e:
            logger.warning(f"Erro ao carregar histórico ML: {e}")
    
    def _save_history(self):
        """Salva histórico de trades"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump({
                    'trades': self.trade_history[-1000:],  # Mantém últimos 1000
                    'stats': self.stats
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Erro ao salvar histórico ML: {e}")
    
    def _get_rsi_zone(self, rsi: float) -> str:
        """Classifica RSI em zonas"""
        if rsi < 30:
            return 'oversold'
        elif rsi < 45:
            return 'low'
        elif rsi < 55:
            return 'neutral'
        elif rsi < 70:
            return 'high'
        else:
            return 'overbought'
    
    def _get_adx_zone(self, adx: float) -> str:
        """Classifica ADX em zonas"""
        if adx < 15:
            return 'very_weak'
        elif adx < 20:
            return 'weak'
        elif adx < 25:
            return 'moderate'
        elif adx < 40:
            return 'strong'
        else:
            return 'very_strong'
    
    def _get_volatility_zone(self, atr_percentile: float) -> str:
        """Classifica volatilidade em zonas"""
        if atr_percentile < 20:
            return 'very_low'
        elif atr_percentile < 40:
            return 'low'
        elif atr_percentile < 60:
            return 'normal'
        elif atr_percentile < 80:
            return 'high'
        else:
            return 'very_high'
    
    def record_trade(self, trade_data: Dict):
        """
        Registra resultado de um trade para aprendizado.
        
        trade_data deve conter:
        - signal_type: 'BUY' ou 'SELL'
        - score: int (score do sinal)
        - rsi: float
        - adx: float
        - atr_percentile: float
        - market_structure: str
        - hour: int
        - result: 'WIN' ou 'LOSS'
        - profit: float
        """
        # Adiciona timestamp
        trade_data['timestamp'] = datetime.now().isoformat()
        
        # Adiciona zonas
        trade_data['rsi_zone'] = self._get_rsi_zone(trade_data.get('rsi', 50))
        trade_data['adx_zone'] = self._get_adx_zone(trade_data.get('adx', 20))
        trade_data['volatility_zone'] = self._get_volatility_zone(trade_data.get('atr_percentile', 50))
        
        self.trade_history.append(trade_data)
        
        # Atualiza estatísticas
        self._update_stats(trade_data)
        
        # Salva
        self._save_history()
        
        logger.info(f"📊 ML: Trade registrado - {trade_data['result']} | Score: {trade_data.get('score', 0)}")
    
    def _update_stats(self, trade: Dict):
        """Atualiza estatísticas com novo trade"""
        is_win = trade['result'] == 'WIN'
        
        # Por hora
        hour = str(trade.get('hour', 0))
        if hour not in self.stats['by_hour']:
            self.stats['by_hour'][hour] = {'wins': 0, 'total': 0}
        self.stats['by_hour'][hour]['total'] += 1
        if is_win:
            self.stats['by_hour'][hour]['wins'] += 1
        
        # Por zona de RSI
        rsi_zone = trade.get('rsi_zone', 'neutral')
        if rsi_zone not in self.stats['by_rsi_zone']:
            self.stats['by_rsi_zone'][rsi_zone] = {'wins': 0, 'total': 0}
        self.stats['by_rsi_zone'][rsi_zone]['total'] += 1
        if is_win:
            self.stats['by_rsi_zone'][rsi_zone]['wins'] += 1
        
        # Por zona de ADX
        adx_zone = trade.get('adx_zone', 'moderate')
        if adx_zone not in self.stats['by_adx_zone']:
            self.stats['by_adx_zone'][adx_zone] = {'wins': 0, 'total': 0}
        self.stats['by_adx_zone'][adx_zone]['total'] += 1
        if is_win:
            self.stats['by_adx_zone'][adx_zone]['wins'] += 1
        
        # Por estrutura
        structure = trade.get('market_structure', 'RANGING')
        if structure not in self.stats['by_structure']:
            self.stats['by_structure'][structure] = {'wins': 0, 'total': 0}
        self.stats['by_structure'][structure]['total'] += 1
        if is_win:
            self.stats['by_structure'][structure]['wins'] += 1
        
        # Por score
        score = str(trade.get('score', 0))
        if score not in self.stats['by_score']:
            self.stats['by_score'][score] = {'wins': 0, 'total': 0}
        self.stats['by_score'][score]['total'] += 1
        if is_win:
            self.stats['by_score'][score]['wins'] += 1
        
        # Por volatilidade
        vol_zone = trade.get('volatility_zone', 'normal')
        if vol_zone not in self.stats['by_volatility']:
            self.stats['by_volatility'][vol_zone] = {'wins': 0, 'total': 0}
        self.stats['by_volatility'][vol_zone]['total'] += 1
        if is_win:
            self.stats['by_volatility'][vol_zone]['wins'] += 1
    
    def _get_win_rate(self, category: str, key: str) -> float:
        """Retorna win rate para uma categoria/chave"""
        stats = self.stats.get(category, {}).get(key, {'wins': 0, 'total': 0})
        if stats['total'] < 3:  # Mínimo de amostras
            return 0.5  # Retorna 50% se dados insuficientes
        return stats['wins'] / stats['total']
    
    def predict_success(self, signal_data: Dict) -> Dict:
        """
        Prevê probabilidade de sucesso do sinal.
        
        signal_data deve conter:
        - signal_type: 'BUY' ou 'SELL'
        - score: int
        - rsi: float
        - adx: float
        - atr_percentile: float
        - market_structure: str
        - hour: int (opcional)
        
        Returns:
            {
                'probability': float (0-1),
                'confidence': str ('HIGH', 'MEDIUM', 'LOW'),
                'should_trade': bool,
                'factors': list of str,
                'warnings': list of str
            }
        """
        result = {
            'probability': 0.5,
            'confidence': 'LOW',
            'should_trade': True,
            'factors': [],
            'warnings': []
        }
        
        # Se não tem histórico suficiente, retorna neutro
        if len(self.trade_history) < self.min_samples:
            result['warnings'].append(f"Histórico insuficiente ({len(self.trade_history)}/{self.min_samples})")
            return result
        
        probabilities = []
        weights = []
        
        # 1. Win rate por score (peso alto)
        score = str(signal_data.get('score', 0))
        wr_score = self._get_win_rate('by_score', score)
        probabilities.append(wr_score)
        weights.append(3.0)
        if wr_score > 0.6:
            result['factors'].append(f"✓ Score {score} tem {wr_score*100:.0f}% win rate")
        elif wr_score < 0.4:
            result['warnings'].append(f"⚠️ Score {score} tem apenas {wr_score*100:.0f}% win rate")
        
        # 2. Win rate por hora (peso médio)
        if self.use_time_filter:
            hour = str(signal_data.get('hour', datetime.now().hour))
            wr_hour = self._get_win_rate('by_hour', hour)
            probabilities.append(wr_hour)
            weights.append(2.0)
            if wr_hour > 0.6:
                result['factors'].append(f"✓ Hora {hour}h tem {wr_hour*100:.0f}% win rate")
            elif wr_hour < 0.4:
                result['warnings'].append(f"⚠️ Hora {hour}h tem apenas {wr_hour*100:.0f}% win rate")
        
        # 3. Win rate por RSI zone (peso médio)
        rsi_zone = self._get_rsi_zone(signal_data.get('rsi', 50))
        wr_rsi = self._get_win_rate('by_rsi_zone', rsi_zone)
        probabilities.append(wr_rsi)
        weights.append(2.0)
        
        # 4. Win rate por ADX zone (peso médio)
        adx_zone = self._get_adx_zone(signal_data.get('adx', 20))
        wr_adx = self._get_win_rate('by_adx_zone', adx_zone)
        probabilities.append(wr_adx)
        weights.append(2.0)
        
        # 5. Win rate por estrutura (peso alto)
        structure = signal_data.get('market_structure', 'RANGING')
        wr_struct = self._get_win_rate('by_structure', structure)
        probabilities.append(wr_struct)
        weights.append(2.5)
        if wr_struct > 0.6:
            result['factors'].append(f"✓ Estrutura {structure} tem {wr_struct*100:.0f}% win rate")
        
        # 6. Win rate por volatilidade (peso baixo)
        if self.use_volatility_filter:
            vol_zone = self._get_volatility_zone(signal_data.get('atr_percentile', 50))
            wr_vol = self._get_win_rate('by_volatility', vol_zone)
            probabilities.append(wr_vol)
            weights.append(1.5)
        
        # Calcula probabilidade ponderada
        if probabilities:
            weighted_sum = sum(p * w for p, w in zip(probabilities, weights))
            total_weight = sum(weights)
            result['probability'] = weighted_sum / total_weight
        
        # Determina confiança
        if result['probability'] >= 0.65:
            result['confidence'] = 'HIGH'
        elif result['probability'] >= 0.55:
            result['confidence'] = 'MEDIUM'
        else:
            result['confidence'] = 'LOW'
        
        # Decide se deve operar
        result['should_trade'] = result['probability'] >= self.confidence_threshold
        
        if not result['should_trade']:
            result['warnings'].append(f"Probabilidade {result['probability']*100:.0f}% < {self.confidence_threshold*100:.0f}%")
        
        logger.info(f"🤖 ML Prediction: {result['probability']*100:.0f}% ({result['confidence']}) - Trade: {result['should_trade']}")
        
        return result
    
    def get_best_hours(self, min_trades: int = 5) -> List[Tuple[int, float]]:
        """Retorna as melhores horas para operar"""
        best = []
        for hour, stats in self.stats['by_hour'].items():
            if stats['total'] >= min_trades:
                wr = stats['wins'] / stats['total']
                best.append((int(hour), wr))
        return sorted(best, key=lambda x: x[1], reverse=True)
    
    def get_stats_summary(self) -> str:
        """Retorna resumo das estatísticas"""
        total_trades = len(self.trade_history)
        if total_trades == 0:
            return "Sem dados de histórico"
        
        wins = sum(1 for t in self.trade_history if t.get('result') == 'WIN')
        overall_wr = wins / total_trades
        
        lines = [
            f"📊 ML Stats Summary",
            f"Total trades: {total_trades}",
            f"Win rate geral: {overall_wr*100:.1f}%",
            "",
            "Melhores horas:"
        ]
        
        best_hours = self.get_best_hours()[:3]
        for hour, wr in best_hours:
            lines.append(f"  {hour}h: {wr*100:.0f}%")
        
        return "\n".join(lines)
