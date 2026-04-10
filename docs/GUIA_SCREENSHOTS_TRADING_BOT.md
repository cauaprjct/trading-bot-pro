# 📸 GUIA COMPLETO DE SCREENSHOTS - Trading Bot PRO 4.0

**Objetivo:** Capturar screenshots profissionais para publicação no GitHub e LinkedIn  
**Data:** 10/04/2026

---

## 🎯 SCREENSHOTS OBRIGATÓRIOS (8 essenciais)

### 1. ⭐ Terminal de Treinamento (PRIORIDADE MÁXIMA)
**Arquivo:** `trading_bot/resultado.txt`  
**Como fazer:**
1. Abra o arquivo `resultado.txt` no VS Code ou Notepad++
2. Ajuste o zoom para ficar legível (Ctrl + Scroll)
3. Capture a tela mostrando:
   - ✅ Cabeçalho "TREINAMENTO DE MODELOS ML - MULTI-ATIVO"
   - ✅ Seção de um ativo completa (ex: GBPUSD):
     - 📊 Total de candles (36,241)
     - 📅 Período (Jul/2025 - Jan/2026)
     - 🟢 Wins/Losses (38.1% / 61.9%)
     - 📊 Métricas (Precision: 51.8%, F1: 40.9%)
     - 🎯 Threshold ótimo: 40%
   - ✅ Resumo final com os 7 modelos

**Legenda para LinkedIn:**
```
🧠 Treinamento dos 7 modelos ML - cada ativo tem seu próprio modelo otimizado

36.000+ candles por ativo | Precision 47-57% | F1 Score 16-42%
Período: 6 meses (Jul/2025 - Jan/2026)

#MachineLearning #AlgoTrading #Python
```

---

### 2. ⭐ Estrutura do Projeto (VS Code)
**Como fazer:**
1. Abra a pasta `trading_bot` no VS Code
2. Expanda as pastas principais:
   - `src/` (domain, infrastructure, strategies, utils)
   - `models/` (7 arquivos .pkl)
   - `gpu_training/` (modelos LSTM)
   - `historical_data/` (dados históricos)
3. Capture a sidebar do Explorer mostrando a estrutura

**OU use o comando tree:**
```bash
cd trading_bot
tree /F /A > estrutura.txt
```

**Legenda para LinkedIn:**
```
🏗️ Arquitetura modular - Clean Architecture aplicada

Cada componente tem sua responsabilidade:
• domain/ - Regras de negócio
• infrastructure/ - Adaptadores (MT5)
• strategies/ - Estratégias de trading
• utils/ - Filtros ML e utilitários

#CleanCode #SoftwareArchitecture #Python
```

---

### 3. ⭐ Tabela de Ativos (README.md)
**Arquivo:** `trading_bot/README.md`  
**Como fazer:**
1. Abra o README.md
2. Role até a seção "💱 ATIVOS CONFIGURADOS"
3. Capture a tabela mostrando os 7 pares Forex:
   - Ativo | Emoji | Spread Máx | Horário BRT | Lote

**Legenda para LinkedIn:**
```
💱 Multi-asset: 7 pares operando simultaneamente

Cada ativo tem configurações otimizadas:
• Spread máximo permitido
• Horários ideais de operação
• Lote específico
• Gestão de risco independente

#Forex #Trading #RiskManagement
```

---

### 4. ⭐ Métricas de Performance (resultado.txt)
**Como fazer:**
1. Abra `resultado.txt`
2. Capture a seção "📊 RESUMO DO TREINAMENTO"
3. Mostre a lista dos 7 modelos com seus caminhos

**OU crie uma tabela visual:**
Abra Excel/Google Sheets e crie:

| Ativo | Precision | F1 Score | Threshold |
|-------|-----------|----------|-----------|
| GBPUSD | 51.8% | 40.9% | 40% |
| EURUSD | 50.8% | 35.5% | 40% |
| USDCAD | 48.6% | 42.9% | 40% |
| USDJPY | 52.0% | 45.2% | 40% |
| EURJPY | 47.3% | 40.5% | 40% |
| GBPJPY | 51.1% | 33.4% | 40% |
| AUDUSD | 57.2% | 42.5% | 40% |

**Legenda para LinkedIn:**
```
📊 Cada modelo foi otimizado individualmente

Não existe "one size fits all" em trading:
• AUDUSD: Melhor precision (57.2%)
• USDJPY: Melhor F1 Score (45.2%)
• Threshold adaptativo por ativo

#DataScience #ModelOptimization #ML
```

---

### 5. ⭐ Sistema de Score 9/9 (BOT_BEHAVIOR.md)
**Arquivo:** `trading_bot/BOT_BEHAVIOR.md`  
**Como fazer:**
1. Abra o arquivo BOT_BEHAVIOR.md
2. Capture a seção "🎯 Sistema de Score 9/9"
3. Mostre a tabela com as 9 confirmações:
   - SMA Crossover
   - RSI Momentum
   - MACD
   - Preço vs SMA21
   - Volume
   - ADX + DI
   - Market Structure
   - BOS + Pullback
   - Order Block

**Legenda para LinkedIn:**
```
🎯 9 confirmações antes de cada trade

Como traders profissionais, não entramos em qualquer sinal:
✓ Indicadores técnicos (SMA, RSI, MACD)
✓ Força da tendência (ADX)
✓ Smart Money Concepts (Order Blocks, BOS)
✓ Estrutura de mercado (HH/HL/LH/LL)

Score mínimo: 4/9 | Ideal: 7+/9

#SmartMoney #ICT #TradingStrategy
```

---

### 6. ⭐ Config Multi-Asset (config_multi.py)
**Arquivo:** `trading_bot/config_multi.py`  
**Como fazer:**
1. Abra `config_multi.py`
2. Capture a seção `MULTI_ASSETS` mostrando 2-3 ativos completos
3. Destaque as configurações:
   - volume, spread_max, atr_mult_sl, atr_mult_tp
   - best_hours, emoji

**Legenda para LinkedIn:**
```
⚙️ Cada ativo tem configurações otimizadas

GBPUSD:
• Spread máx: 10 pips
• Horário: 4h-18h BRT
• Lote: 0.05 (~$0.35/pip)
• SL: ~5 pips | TP: ~10 pips

Configurações baseadas em:
• Liquidez do par
• Volatilidade histórica
• Sessões de trading

#ConfigurationManagement #Optimization
```

---

### 7. ⭐ Ensemble ML Filter (código)
**Arquivo:** `trading_bot/src/utils/ensemble_ml_filter.py`  
**Como fazer:**
1. Abra o arquivo `ensemble_ml_filter.py`
2. Capture a função principal que combina LightGBM + LSTM
3. Mostre o código do weighted voting

**Legenda para LinkedIn:**
```
🧠 Ensemble ML: LightGBM (85%) + LSTM (15%)

Combina dois tipos de Machine Learning:
• LightGBM: Rápido, precision ~50%
• LSTM: Captura padrões temporais, F1 ~30%

Weighted voting: Score mínimo 28%

Por que ensemble?
✓ Mais robusto que modelo único
✓ Combina pontos fortes de cada modelo
✓ Reduz falsos positivos

#EnsembleLearning #LightGBM #LSTM
```

---

### 8. ⭐ GPU Training README
**Arquivo:** `trading_bot/gpu_training/README.md`  
**Como fazer:**
1. Se existir, abra o README da pasta gpu_training
2. Capture informações sobre:
   - Pipeline de treinamento
   - Uso de GPU H100
   - 3 anos de dados históricos
   - Otimização bayesiana (Optuna)

**OU crie um screenshot do terminal mostrando:**
```bash
python run_full_pipeline.py --symbols EURUSD GBPUSD --epochs 100
```

**Legenda para LinkedIn:**
```
🚀 Pipeline completo de treinamento em GPU H100

• 3 anos de dados históricos (Dukascopy API)
• Otimização bayesiana (Optuna)
• 100 epochs por modelo
• Exportação automática para produção

Tempo de treino: ~3 horas (7 modelos)

#GPU #DeepLearning #MLOps #H100
```

---

## 📸 SCREENSHOTS OPCIONAIS (Bônus)

### 9. Dashboard Web (se tiver)
Se você tem o `dashboard.py` funcionando:
```bash
python dashboard.py
```
Capture a interface web mostrando métricas em tempo real.

---

### 10. Telegram Notifications
Se você tem notificações Telegram configuradas, capture:
- Notificação de trade executado
- Notificação de trade fechado com lucro
- Alertas do bot

---

### 11. Terminal do Bot Rodando
Execute o bot em modo demo:
```bash
python run_multi.py
```
Capture o terminal mostrando:
- Conexão com MT5
- Carregamento dos modelos
- Análise de mercado em tempo real
- Heartbeat (sinal de vida)

---

### 12. Gráfico MT5 com Indicadores
Abra o MetaTrader 5 e:
1. Adicione os indicadores (SMA9, SMA21, RSI, MACD)
2. Marque Order Blocks no gráfico
3. Capture um exemplo de setup perfeito

---

## 🎨 DICAS DE CAPTURA

### Ferramentas Recomendadas
- **Windows:** Snipping Tool (Win + Shift + S)
- **Lightshot:** https://app.prntscr.com/
- **ShareX:** https://getsharex.com/ (melhor para edição)

### Qualidade
- ✅ Resolução mínima: 1920x1080
- ✅ Formato: PNG (melhor qualidade)
- ✅ Zoom: Ajuste para texto legível
- ✅ Tema: Dark mode (mais profissional)

### Edição
- ✅ Adicione setas/círculos destacando pontos importantes
- ✅ Use cores: Verde (sucesso), Vermelho (alerta), Azul (info)
- ✅ Adicione texto explicativo se necessário
- ✅ Mantenha limpo e profissional

### Organização
Salve os screenshots com nomes descritivos:
```
trading-bot-01-treinamento.png
trading-bot-02-estrutura.png
trading-bot-03-ativos.png
trading-bot-04-metricas.png
trading-bot-05-score-9-9.png
trading-bot-06-config.png
trading-bot-07-ensemble.png
trading-bot-08-gpu-training.png
```

---

## 📱 FORMATO PARA LINKEDIN

### Carrossel (10 slides)
Crie um carrossel no Canva com:
1. Capa (título + logo)
2. Screenshot 1 (Treinamento)
3. Screenshot 2 (Estrutura)
4. Screenshot 3 (Ativos)
5. Screenshot 4 (Métricas)
6. Screenshot 5 (Score 9/9)
7. Screenshot 6 (Config)
8. Screenshot 7 (Ensemble)
9. Screenshot 8 (GPU Training)
10. Call to Action (GitHub link)

**Dimensões:** 1080x1080px (quadrado)

### Post Único
Se preferir post único, use:
- Screenshot mais impactante (Treinamento ou Métricas)
- Adicione texto overlay com números principais
- Dimensões: 1200x628px (landscape)

---

## 🚀 PRÓXIMOS PASSOS

Depois de capturar os screenshots:

1. ✅ Organize em uma pasta `screenshots/`
2. ✅ Edite se necessário (setas, destaques)
3. ✅ Crie o repositório no GitHub
4. ✅ Adicione screenshots no README.md
5. ✅ Publique no LinkedIn (use POST 2 - Storytelling)
6. ✅ Responda comentários nas primeiras 2 horas

---

## 📊 CHECKLIST FINAL

Antes de publicar, verifique:

- [ ] 8 screenshots obrigatórios capturados
- [ ] Qualidade boa (legível, profissional)
- [ ] Nomes de arquivo organizados
- [ ] README.md do GitHub atualizado
- [ ] Post LinkedIn escrito (use POSTS_LINKEDIN_FINAL.md)
- [ ] Hashtags preparadas
- [ ] Horário de publicação definido (8h-10h ou 18h-20h)

---

**Boa sorte com as capturas! 🚀**

Se precisar de ajuda com algum screenshot específico, me avise!
