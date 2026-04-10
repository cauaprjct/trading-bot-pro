"""
🤖 Treina Modelos ML para TODOS os Ativos
Cria um modelo LightGBM otimizado para cada par de moedas.

Uso: python train_all_models.py
"""

import os
import sys

# Ativos para treinar
ASSETS = [
    "GBPUSD",
    "EURUSD",
    "USDCAD", 
    "USDJPY",
    "EURJPY",
    "GBPJPY",
    "AUDUSD",
]

def main():
    print("="*60)
    print("🤖 TREINAMENTO DE MODELOS ML - MULTI-ATIVO")
    print("="*60)
    print()
    
    # Importa o trainer
    from train_ml_model import MLTrainer
    
    success = 0
    failed = 0
    models = {}
    
    for symbol in ASSETS:
        print()
        print(f"{'='*60}")
        print(f"📊 Treinando modelo para {symbol}...")
        print(f"{'='*60}")
        
        try:
            trainer = MLTrainer(symbol=symbol, timeframe="M5")
            model_path = trainer.run()
            
            if model_path:
                success += 1
                models[symbol] = model_path
                print(f"✅ {symbol}: Modelo salvo!")
            else:
                failed += 1
                print(f"❌ {symbol}: Falha no treino")
                
        except Exception as e:
            failed += 1
            print(f"❌ {symbol}: Erro - {e}")
    
    # Resumo
    print()
    print("="*60)
    print("📊 RESUMO DO TREINAMENTO")
    print("="*60)
    print()
    print(f"✅ Sucesso: {success} modelos")
    print(f"❌ Falha: {failed} modelos")
    print()
    
    if models:
        print("📁 Modelos criados:")
        for symbol, path in models.items():
            print(f"  {symbol}: {path}")
    
    print()
    print("="*60)
    print("✅ Treinamento concluído!")
    print("   Agora rode: python run_multi.py")
    print("="*60)


if __name__ == "__main__":
    main()
