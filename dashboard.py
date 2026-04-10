"""
Dashboard Web - Interface visual para monitorar o bot

Uso:
    python dashboard.py              # Inicia na porta 5000
    python dashboard.py --port 8080  # Porta customizada

Acesse: http://localhost:5000
"""

import argparse
import json
from datetime import datetime
from flask import Flask, render_template_string, jsonify
import MetaTrader5 as mt5
import config
from src.utils.state_manager import StateManager
from src.utils.logger import setup_logger

logger = setup_logger("Dashboard")

app = Flask(__name__)

# HTML Template embutido (evita criar pasta templates)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 B3 Trading Bot Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 30px; font-size: 2em; }
        h1 span { color: #00d4ff; }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 {
            font-size: 1em;
            color: #888;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        .status-online { background: #00c853; color: #000; }
        .status-offline { background: #ff1744; color: #fff; }
        .status-positioned { background: #ff9100; color: #000; }
        
        .big-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #00d4ff;
        }
        .big-number.positive { color: #00c853; }
        .big-number.negative { color: #ff1744; }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .metric-row:last-child { border-bottom: none; }
        .metric-label { color: #888; }
        .metric-value { font-weight: bold; }
        
        .trade-list { max-height: 300px; overflow-y: auto; }
        .trade-item {
            display: flex;
            justify-content: space-between;
            padding: 10px;
            margin: 5px 0;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
        }
        .trade-win { border-left: 3px solid #00c853; }
        .trade-loss { border-left: 3px solid #ff1744; }
        
        .indicator-bar {
            height: 8px;
            background: #333;
            border-radius: 4px;
            margin-top: 5px;
            overflow: hidden;
        }
        .indicator-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }
        .rsi-fill { background: linear-gradient(90deg, #ff1744, #ffeb3b, #00c853); }
        
        .refresh-info {
            text-align: center;
            color: #666;
            font-size: 0.8em;
            margin-top: 20px;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .live-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #00c853;
            border-radius: 50%;
            margin-right: 5px;
            animation: pulse 1s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 B3 Trading Bot <span>Dashboard</span></h1>
        
        <div class="grid">
            <!-- Status Card -->
            <div class="card">
                <h2>📡 Status</h2>
                <div id="status-content">
                    <p><span class="live-dot"></span> Carregando...</p>
                </div>
            </div>
            
            <!-- Preço Card -->
            <div class="card">
                <h2>💰 Preço Atual</h2>
                <div class="big-number" id="current-price">--</div>
                <p id="symbol-name">{{ symbol }}</p>
            </div>
            
            <!-- P&L Card -->
            <div class="card">
                <h2>📈 P&L do Dia</h2>
                <div class="big-number" id="daily-pnl">$0.00</div>
            </div>
            
            <!-- Saldo Card -->
            <div class="card">
                <h2>💵 Saldo</h2>
                <div class="big-number" id="balance">--</div>
            </div>
        </div>
        
        <div class="grid">
            <!-- Indicadores Card -->
            <div class="card">
                <h2>📊 Indicadores</h2>
                <div class="metric-row">
                    <span class="metric-label">RSI (14)</span>
                    <span class="metric-value" id="rsi-value">--</span>
                </div>
                <div class="indicator-bar">
                    <div class="indicator-fill rsi-fill" id="rsi-bar" style="width: 50%"></div>
                </div>
                <div class="metric-row">
                    <span class="metric-label">SMA 9</span>
                    <span class="metric-value" id="sma-fast">--</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">SMA 21</span>
                    <span class="metric-value" id="sma-slow">--</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Tendência</span>
                    <span class="metric-value" id="trend">--</span>
                </div>
            </div>
            
            <!-- Métricas Card -->
            <div class="card">
                <h2>📈 Performance</h2>
                <div class="metric-row">
                    <span class="metric-label">Total Trades</span>
                    <span class="metric-value" id="total-trades">0</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Win Rate</span>
                    <span class="metric-value" id="win-rate">0%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Profit Factor</span>
                    <span class="metric-value" id="profit-factor">0</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Max Drawdown</span>
                    <span class="metric-value" id="max-drawdown">$0</span>
                </div>
            </div>
            
            <!-- Posições Card -->
            <div class="card">
                <h2>📋 Posições Abertas</h2>
                <div id="positions-list">
                    <p style="color: #666;">Nenhuma posição aberta</p>
                </div>
            </div>
        </div>
        
        <!-- Histórico de Trades -->
        <div class="card">
            <h2>📜 Últimos Trades</h2>
            <div class="trade-list" id="trades-list">
                <p style="color: #666;">Nenhum trade registrado</p>
            </div>
        </div>
        
        <p class="refresh-info">Atualização automática a cada 5 segundos | <span id="last-update">--</span></p>
    </div>
    
    <script>
        function updateDashboard() {
            fetch('/api/data')
                .then(response => response.json())
                .then(data => {
                    // Status
                    const statusHtml = `
                        <p><span class="live-dot"></span> 
                        <span class="status-badge ${data.mt5_connected ? 'status-online' : 'status-offline'}">
                            MT5: ${data.mt5_connected ? 'Conectado' : 'Desconectado'}
                        </span>
                        <span class="status-badge ${data.positions_count > 0 ? 'status-positioned' : 'status-online'}">
                            ${data.positions_count > 0 ? 'Posicionado' : 'Livre'}
                        </span>
                        </p>
                    `;
                    document.getElementById('status-content').innerHTML = statusHtml;
                    
                    // Preço
                    document.getElementById('current-price').textContent = data.current_price.toFixed(5);
                    
                    // P&L
                    const pnlEl = document.getElementById('daily-pnl');
                    pnlEl.textContent = (data.daily_pnl >= 0 ? '+' : '') + '$' + data.daily_pnl.toFixed(2);
                    pnlEl.className = 'big-number ' + (data.daily_pnl >= 0 ? 'positive' : 'negative');
                    
                    // Saldo
                    document.getElementById('balance').textContent = '$' + data.balance.toFixed(2);
                    
                    // Indicadores
                    document.getElementById('rsi-value').textContent = data.rsi.toFixed(1);
                    document.getElementById('rsi-bar').style.width = data.rsi + '%';
                    document.getElementById('sma-fast').textContent = data.sma_fast.toFixed(5);
                    document.getElementById('sma-slow').textContent = data.sma_slow.toFixed(5);
                    document.getElementById('trend').textContent = data.sma_fast > data.sma_slow ? '📈 ALTISTA' : '📉 BAIXISTA';
                    
                    // Métricas
                    document.getElementById('total-trades').textContent = data.metrics.total_trades;
                    document.getElementById('win-rate').textContent = data.metrics.win_rate.toFixed(1) + '%';
                    document.getElementById('profit-factor').textContent = data.metrics.profit_factor.toFixed(2);
                    document.getElementById('max-drawdown').textContent = '$' + data.metrics.max_drawdown.toFixed(2);
                    
                    // Posições
                    if (data.positions.length > 0) {
                        let posHtml = '';
                        data.positions.forEach(p => {
                            posHtml += `<div class="trade-item">
                                <span>${p.type} ${p.volume} @ ${p.price.toFixed(5)}</span>
                                <span>P&L: $${p.profit.toFixed(2)}</span>
                            </div>`;
                        });
                        document.getElementById('positions-list').innerHTML = posHtml;
                    } else {
                        document.getElementById('positions-list').innerHTML = '<p style="color: #666;">Nenhuma posição aberta</p>';
                    }
                    
                    // Trades
                    if (data.recent_trades.length > 0) {
                        let tradesHtml = '';
                        data.recent_trades.forEach(t => {
                            const isWin = t.pnl >= 0;
                            tradesHtml += `<div class="trade-item ${isWin ? 'trade-win' : 'trade-loss'}">
                                <span>${t.type} @ ${t.exit_price}</span>
                                <span style="color: ${isWin ? '#00c853' : '#ff1744'}">${isWin ? '+' : ''}$${t.pnl.toFixed(2)}</span>
                            </div>`;
                        });
                        document.getElementById('trades-list').innerHTML = tradesHtml;
                    }
                    
                    // Timestamp
                    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                })
                .catch(err => console.error('Erro ao atualizar:', err));
        }
        
        // Atualiza a cada 5 segundos
        updateDashboard();
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"""

def get_mt5_data():
    """Coleta dados do MT5"""
    data = {
        "mt5_connected": False,
        "current_price": 0.0,
        "balance": 0.0,
        "rsi": 50.0,
        "sma_fast": 0.0,
        "sma_slow": 0.0,
        "positions": [],
        "positions_count": 0
    }
    
    try:
        if not mt5.initialize():
            return data
        
        data["mt5_connected"] = True
        
        # Saldo
        account = mt5.account_info()
        if account:
            data["balance"] = account.balance
        
        # Preço atual
        tick = mt5.symbol_info_tick(config.SYMBOL)
        if tick:
            data["current_price"] = tick.bid
        
        # Posições
        positions = mt5.positions_get(symbol=config.SYMBOL)
        if positions:
            data["positions_count"] = len(positions)
            for p in positions:
                data["positions"].append({
                    "type": "BUY" if p.type == 0 else "SELL",
                    "volume": p.volume,
                    "price": p.price_open,
                    "profit": p.profit
                })
        
        # Indicadores (calcula dos dados)
        rates = mt5.copy_rates_from_pos(config.SYMBOL, config.TIMEFRAME, 0, 50)
        if rates is not None and len(rates) > 0:
            import pandas as pd
            df = pd.DataFrame(rates)
            
            # SMA
            data["sma_fast"] = df['close'].rolling(config.SMA_FAST).mean().iloc[-1]
            data["sma_slow"] = df['close'].rolling(config.SMA_SLOW).mean().iloc[-1]
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(config.RSI_PERIOD).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(config.RSI_PERIOD).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            data["rsi"] = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
        
        mt5.shutdown()
        
    except Exception as e:
        logger.error(f"Erro ao coletar dados MT5: {e}")
    
    return data

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML, symbol=config.SYMBOL)

@app.route('/api/data')
def api_data():
    """API endpoint para dados do dashboard"""
    
    # Dados do MT5
    mt5_data = get_mt5_data()
    
    # Dados do StateManager
    state_manager = StateManager(getattr(config, 'STATE_FILE', 'bot_state.json'))
    daily_stats = state_manager.get_daily_stats()
    metrics = state_manager.get_performance_metrics()
    recent_trades = state_manager.get_trades_history(limit=10)
    
    response = {
        **mt5_data,
        "daily_pnl": daily_stats.get("pnl", 0),
        "metrics": {
            "total_trades": metrics.total_trades,
            "win_rate": metrics.win_rate,
            "profit_factor": metrics.profit_factor if metrics.profit_factor != float('inf') else 0,
            "max_drawdown": metrics.max_drawdown
        },
        "recent_trades": recent_trades[-10:][::-1]  # Últimos 10, mais recente primeiro
    }
    
    return jsonify(response)

def main():
    parser = argparse.ArgumentParser(description='Dashboard do B3 Trading Bot')
    parser.add_argument('--port', type=int, default=5000, help='Porta do servidor')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host (0.0.0.0 para rede)')
    
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("🖥️  B3 Trading Bot - Dashboard")
    print("="*50)
    print(f"📡 Acesse: http://localhost:{args.port}")
    print(f"📡 Na rede: http://<seu-ip>:{args.port}")
    print("="*50 + "\n")
    
    app.run(host=args.host, port=args.port, debug=False)

if __name__ == "__main__":
    main()
