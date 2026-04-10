#!/usr/bin/env python3
"""
🚀 Run Full Pipeline - Executa todo o pipeline de treinamento GPU
Script principal que orquestra todo o processo.
"""
import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
import json

print("="*70)
print("🚀 PIPELINE COMPLETO DE TREINAMENTO GPU")
print("="*70)
print(f"⏰ Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

def run_command(cmd: list, description: str) -> bool:
    """Executa comando e retorna sucesso."""
    print(f"\n{'='*60}")
    print(f"📌 {description}")
    print(f"{'='*60}")
    print(f"   Comando: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✅ {description} - CONCLUÍDO")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} - FALHOU (código {e.returncode})")
        return False
    except FileNotFoundError:
        print(f"\n❌ Comando não encontrado: {cmd[0]}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Pipeline completo de treinamento GPU')
    parser.add_argument('--data-dir', default='historical_data', help='Pasta com dados')
    parser.add_argument('--output-dir', default='gpu_training/output', help='Pasta de saída')
    parser.add_argument('--symbols', nargs='+', default=['EURUSD', 'GBPUSD', 'USDJPY'], help='Símbolos')
    parser.add_argument('--years', type=int, default=2, help='Anos de histórico')
    parser.add_argument('--model', default='lstm', choices=['lstm', 'transformer'], help='Tipo de modelo')
    parser.add_argument('--epochs', type=int, default=100, help='Épocas de treino')
    parser.add_argument('--optuna-trials', type=int, default=100, help='Trials de otimização')
    parser.add_argument('--skip-download', action='store_true', help='Pula download de dados')
    parser.add_argument('--skip-simulation', action='store_true', help='Pula simulação de trades')
    parser.add_argument('--skip-optimization', action='store_true', help='Pula otimização')
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    symbols_str = ' '.join(args.symbols)
    
    print(f"📋 Configuração:")
    print(f"   Símbolos: {args.symbols}")
    print(f"   Anos de histórico: {args.years}")
    print(f"   Modelo: {args.model}")
    print(f"   Épocas: {args.epochs}")
    print(f"   Trials Optuna: {args.optuna_trials}")
    
    results = {
        'start_time': datetime.now().isoformat(),
        'config': vars(args),
        'steps': {}
    }
    
    # Step 1: Download histórico estendido
    if not args.skip_download:
        success = run_command([
            sys.executable, 'gpu_training/download_extended_history.py',
            '--years', str(args.years),
            '--symbols', *args.symbols,
            '--output', 'historical_data_extended'
        ], "Download de Histórico Estendido")
        results['steps']['download'] = success
        
        if success:
            args.data_dir = 'historical_data_extended'
    
    # Step 2: Simulação de trades GPU
    if not args.skip_simulation:
        success = run_command([
            sys.executable, 'gpu_training/generate_labels_gpu.py',
            '--data-dir', args.data_dir,
            '--output-dir', str(output_dir / 'simulations'),
            '--symbols', *args.symbols
        ], "Simulação de Trades GPU")
        results['steps']['simulation'] = success
    
    # Step 3: Otimização de hiperparâmetros (para cada símbolo)
    if not args.skip_optimization:
        for symbol in args.symbols:
            success = run_command([
                sys.executable, 'gpu_training/optimize_hyperparams.py',
                '--data-dir', args.data_dir,
                '--output-dir', str(output_dir / 'optimization'),
                '--symbol', symbol,
                '--trials', str(args.optuna_trials)
            ], f"Otimização de Hiperparâmetros - {symbol}")
            results['steps'][f'optimization_{symbol}'] = success
    
    # Step 4: Treinamento do modelo final
    success = run_command([
        sys.executable, 'gpu_training/train_deep_model.py',
        '--data-dir', args.data_dir,
        '--output-dir', str(output_dir / 'models'),
        '--model', args.model,
        '--symbols', *args.symbols,
        '--epochs', str(args.epochs)
    ], f"Treinamento do Modelo {args.model.upper()}")
    results['steps']['training'] = success
    
    # Salva resultados
    results['end_time'] = datetime.now().isoformat()
    
    results_file = output_dir / 'pipeline_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Resumo
    print(f"\n{'='*70}")
    print("📊 RESUMO DO PIPELINE")
    print(f"{'='*70}")
    
    total_steps = len(results['steps'])
    successful_steps = sum(1 for v in results['steps'].values() if v)
    
    for step, success in results['steps'].items():
        status = "✅" if success else "❌"
        print(f"   {status} {step}")
    
    print(f"\n   Total: {successful_steps}/{total_steps} etapas concluídas")
    print(f"   Resultados salvos em: {results_file}")
    print(f"\n⏰ Fim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    
    # Instruções finais
    if successful_steps == total_steps:
        print(f"\n🎉 Pipeline concluído com sucesso!")
        print(f"\n📁 Modelos treinados em: {output_dir / 'models'}")
        print(f"\n💡 Para usar os modelos no bot:")
        print(f"   1. Copie os arquivos .pt para a pasta 'models/'")
        print(f"   2. Atualize o config para usar os novos modelos")
    else:
        print(f"\n⚠️ Algumas etapas falharam. Verifique os logs acima.")


if __name__ == "__main__":
    main()
