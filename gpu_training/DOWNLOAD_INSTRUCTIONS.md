# 📥 Instruções para Download de Dados Históricos

## ⚠️ IMPORTANTE: Limitações das Fontes

| Fonte | Limite | Viável para 2-3 anos? |
|-------|--------|----------------------|
| MT5 MetaQuotes-Demo | ~6 meses M5 | ❌ Não |
| Myfxbook | ~1000 data points/timeframe | ❌ Não (M1 = 16h) |
| Dukascopy API | Ilimitado (mas lento) | ✅ Sim (~2-4h) |
| HistData.com | Anos inteiros | ✅ Sim (manual, ~30min) |

---

## Opção 1: HistData.com (RECOMENDADO - Mais Rápido)

O HistData.com permite baixar anos inteiros de dados M1 em poucos cliques.

### Links Diretos por Símbolo:

| Símbolo | Link 2023 | Link 2024 | Link 2025 |
|---------|-----------|-----------|-----------|
| EUR/USD | [2023](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurusd/2023) | [2024](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurusd/2024) | [2025](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurusd/2025) |
| GBP/USD | [2023](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/gbpusd/2023) | [2024](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/gbpusd/2024) | [2025](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/gbpusd/2025) |
| USD/JPY | [2023](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/usdjpy/2023) | [2024](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/usdjpy/2024) | [2025](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/usdjpy/2025) |
| USD/CAD | [2023](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/usdcad/2023) | [2024](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/usdcad/2024) | [2025](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/usdcad/2025) |
| AUD/USD | [2023](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/audusd/2023) | [2024](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/audusd/2024) | [2025](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/audusd/2025) |
| EUR/JPY | [2023](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurjpy/2023) | [2024](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurjpy/2024) | [2025](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurjpy/2025) |
| GBP/JPY | [2023](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/gbpjpy/2023) | [2024](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/gbpjpy/2024) | [2025](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/gbpjpy/2025) |

### Passo a Passo:

1. **Clique em cada link** acima (ou acesse https://www.histdata.com/download-free-forex-data/)

2. **Na página**, clique no botão **"Download"** (arquivo ZIP ~50-100MB)

3. **Organize os arquivos**:
```
gpu_training/historical_data_raw/
├── EURUSD/
│   ├── DAT_ASCII_EURUSD_M1_2023.csv (ou .zip)
│   ├── DAT_ASCII_EURUSD_M1_2024.csv
│   └── DAT_ASCII_EURUSD_M1_2025.csv
├── GBPUSD/
│   └── ...
└── ...
```

4. **Execute o conversor**:
```bash
python gpu_training/convert_histdata.py
```

**Tempo estimado**: ~15-30 minutos para baixar tudo manualmente (21 arquivos).

---

## Opção 2: Dukascopy API (Automático - Deixa Rodando)

Se preferir não baixar manualmente, use o script Dukascopy (funciona, mas demora):

```bash
# Download completo - 3 anos, 7 símbolos (~2-4 horas)
python gpu_training/download_dukascopy.py --years 3 --workers 20

# Ou baixe apenas 1 ano para teste rápido (~30-60 min)
python gpu_training/download_dukascopy.py --years 1 --workers 20

# Baixar apenas alguns símbolos específicos
python gpu_training/download_dukascopy.py --years 3 --workers 20 --symbols EURUSD GBPUSD
```

**Tempo estimado**: 
- 1 ano, 7 símbolos: ~30-60 minutos
- 3 anos, 7 símbolos: ~2-4 horas

**Dica**: Execute em background e vá fazer outra coisa:
```bash
# Windows PowerShell
Start-Process -NoNewWindow python -ArgumentList "gpu_training/download_dukascopy.py --years 3 --workers 20"
```

---

## Opção 3: Usar Dados do MT5 (Já Disponíveis)

Os dados já copiados do MT5 (~6 meses) estão em:
```
gpu_training/historical_data/
```

Para treinar com esses dados:
```bash
python gpu_training/prepare_data.py --validate
python gpu_training/run_full_pipeline.py --skip-download
```

---

## Verificar Dados

Após baixar, verifique:
```bash
python gpu_training/prepare_data.py --validate
```

Saída esperada:
```
✅ EURUSD: 150,000+ candles M5 (~500+ dias)
✅ GBPUSD: 150,000+ candles M5 (~500+ dias)
...
```

---

## Próximos Passos

Após ter os dados:
```bash
# 1. Preparar dados
python gpu_training/prepare_data.py

# 2. Executar pipeline completo
python gpu_training/run_full_pipeline.py \
    --symbols EURUSD GBPUSD USDJPY USDCAD AUDUSD EURJPY GBPJPY \
    --model lstm \
    --epochs 100
```
