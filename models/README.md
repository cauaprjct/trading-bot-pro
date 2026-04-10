# 🤖 Modelos ML - Trading Bot

Esta pasta contém os modelos treinados de Machine Learning.

## Como Treinar

```bash
# Treina modelo para BTCUSD
python train_ml_model.py --symbol BTCUSD-T

# Treina para outro símbolo
python train_ml_model.py --symbol EURUSD-T
```

## Arquivos Gerados

- `btcusd_t_lgbm.pkl` - Modelo LightGBM para BTCUSD
- `eurusd_t_lgbm.pkl` - Modelo LightGBM para EURUSD

## Recursos

- **Tamanho:** ~1-2 MB por modelo
- **RAM:** ~10 MB durante uso
- **Inferência:** <1ms por predição

## Retreino

Recomenda-se retreinar o modelo:
- A cada 1-2 semanas
- Após mudanças significativas no mercado
- Se a taxa de acerto cair abaixo de 50%
