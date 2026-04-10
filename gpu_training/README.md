# 🚀 GPU Training - Trading Bot ML

Treinamento intensivo com GPU H100/H200 para modelos de trading.

## 📥 PASSO 1: Obter Dados Históricos (2-3 anos)

A instância GPU (Linux) **NÃO tem MT5**. Escolha uma das opções:

### Opção A: Download Automático via Dukascopy API (Recomendado)
```bash
# Na instância GPU ou Windows, execute:
python gpu_training/download_dukascopy.py --years 3 --workers 8

# Isso baixa ~3 anos de dados tick e converte para M5
# Tempo estimado: ~30-60 min para 7 símbolos
```

### Opção B: Download Manual do HistData.com
1. Acesse: https://www.histdata.com/download-free-forex-data/
2. Para cada símbolo (EURUSD, GBPUSD, USDJPY, USDCAD, AUDUSD, EURJPY, GBPJPY):
   - Clique no símbolo
   - Selecione "ASCII" e "1-Minute Bar Quotes"
   - Baixe os anos: 2023, 2024, 2025
3. Extraia os ZIPs em `gpu_training/historical_data_raw/SYMBOL/`
4. Execute o conversor:
```bash
python gpu_training/convert_histdata.py
```

### Opção C: Copiar dados do MT5 (Windows)
```bash
# No Windows, compacte a pasta:
# Clique direito em 'historical_data' > Enviar para > Pasta compactada

# Na instância GPU, descompacte:
unzip historical_data.zip
```

### Verificar dados:
```bash
python gpu_training/prepare_data.py --validate
```

## Requisitos
```bash
pip install -r gpu_training/requirements.txt
```

## Arquivos
| Arquivo | Descrição |
|---------|-----------|
| `download_dukascopy.py` | **Baixa dados históricos via API Dukascopy** |
| `download_histdata.py` | Baixa dados via MT5 (se disponível) |
| `convert_histdata.py` | Converte dados do HistData.com |
| `prepare_data.py` | Verifica e valida dados históricos |
| `generate_labels_gpu.py` | Simula trades com diferentes parâmetros |
| `train_deep_model.py` | Treina LSTM/Transformer (compatível com bot) |
| `optimize_hyperparams.py` | Otimização Bayesiana com Optuna |
| `run_full_pipeline.py` | Executa todo o pipeline |
| `export_to_production.py` | Exporta modelos para o bot |

## Como usar

### Opção 1: Pipeline Completo (Recomendado)
```bash
# Verifica dados primeiro
python gpu_training/prepare_data.py --validate

# Executa pipeline completo
python gpu_training/run_full_pipeline.py \
    --symbols EURUSD GBPUSD USDJPY USDCAD AUDUSD EURJPY GBPJPY \
    --model lstm \
    --epochs 100 \
    --optuna-trials 200 \
    --skip-download
```

### Opção 2: Passo a Passo
```bash
# 1. Simular trades com diferentes parâmetros
python gpu_training/generate_labels_gpu.py --symbols EURUSD GBPUSD

# 2. Otimizar hiperparâmetros (opcional, ~2h)
python gpu_training/optimize_hyperparams.py --symbol EURUSD --trials 500

# 3. Treinar modelo LSTM
python gpu_training/train_deep_model.py --model lstm --epochs 100

# 4. Exportar para produção
python gpu_training/export_to_production.py --format pickle
```

### Opção 3: Só Treinar (Mais Rápido)
```bash
# Treina direto com dados existentes
python gpu_training/train_deep_model.py \
    --data-dir historical_data \
    --symbols EURUSD GBPUSD USDJPY \
    --model lstm \
    --epochs 50
```

## Estimativa de tempo (H100)
| Etapa | Tempo |
|-------|-------|
| Verificação de dados | ~1 min |
| Simulação de trades | ~10 min |
| Otimização (500 trials) | ~2 horas |
| Treino LSTM (100 epochs) | ~30 min |
| **Total** | **~3 horas** |

## Compatibilidade com o Bot

Os modelos treinados usam as **mesmas 14 features** do LightGBM:
- `sma_crossover`, `price_vs_sma21`
- `rsi`, `rsi_zone`
- `macd_signal`, `macd_histogram`
- `adx`, `adx_direction`
- `atr_percentile`
- `market_structure`, `bos_type`, `bos_pullback_valid`
- `in_order_block`, `volume_above_avg`

Isso garante que os modelos deep learning funcionem como **drop-in replacement** para os modelos LightGBM existentes.

## Após o Treinamento

1. Copie os modelos `.pkl` de volta para o Windows:
```bash
# Na instância, os modelos estarão em:
gpu_training/output/models/*.pt

# Exporte para pickle:
python gpu_training/export_to_production.py

# Copie para o Windows na pasta 'models/'
```

2. O bot vai usar automaticamente os novos modelos!
