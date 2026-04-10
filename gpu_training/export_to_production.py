"""
📦 Export to Production - Converte modelos GPU para produção
Exporta modelos PyTorch para formato leve compatível com o bot.
"""
import os
import sys
import argparse
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime
import json

import torch
import torch.nn as nn

print("="*60)
print("📦 EXPORTAÇÃO DE MODELOS PARA PRODUÇÃO")
print("="*60)


class ProductionModel:
    """Wrapper para modelo em produção."""
    
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.model = None
        self.feature_names = []
        self.scaler_mean = None
        self.scaler_scale = None
        self.threshold = 0.5
        
        self._load_model()
    
    def _load_model(self):
        """Carrega modelo PyTorch."""
        # weights_only=False necessário para carregar numpy arrays (scaler)
        checkpoint = torch.load(self.model_path, map_location='cpu', weights_only=False)
        
        self.feature_names = checkpoint['feature_names']
        self.scaler_mean = checkpoint['scaler_mean']
        self.scaler_scale = checkpoint['scaler_scale']
        self.metrics = checkpoint.get('metrics', {})
        self.threshold = checkpoint.get('threshold', 0.5)
        
        # Recria arquitetura do modelo
        model_type = checkpoint.get('model_type', 'lstm')
        input_size = len(self.feature_names)
        
        if model_type == 'lstm':
            self.model = self._create_lstm(input_size)
        else:
            self.model = self._create_transformer(input_size)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
    
    def _create_lstm(self, input_size: int) -> nn.Module:
        """Cria modelo LSTM - deve corresponder à arquitetura de treino."""
        class LSTMModel(nn.Module):
            def __init__(self, input_size):
                super().__init__()
                # IMPORTANTE: hidden_size=128 para corresponder ao treino!
                self.lstm = nn.LSTM(input_size, 128, 2, batch_first=True, dropout=0.3)
                self.fc = nn.Sequential(
                    nn.Linear(128, 32),
                    nn.ReLU(),
                    nn.Dropout(0.3),
                    nn.Linear(32, 1)
                )
            
            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                return self.fc(lstm_out[:, -1, :]).squeeze()
        
        return LSTMModel(input_size)
    
    def _create_transformer(self, input_size: int) -> nn.Module:
        """Cria modelo Transformer - deve corresponder à arquitetura de treino."""
        class TransformerModel(nn.Module):
            def __init__(self, input_size):
                super().__init__()
                self.input_proj = nn.Linear(input_size, 128)
                encoder_layer = nn.TransformerEncoderLayer(128, 8, 512, 0.2, batch_first=True)
                self.transformer = nn.TransformerEncoder(encoder_layer, 4)
                self.fc = nn.Sequential(
                    nn.Linear(128, 64),
                    nn.ReLU(),
                    nn.Dropout(0.2),
                    nn.Linear(64, 1)
                )
            
            def forward(self, x):
                x = self.input_proj(x)
                x = self.transformer(x)
                return self.fc(x[:, -1, :]).squeeze()
        
        return TransformerModel(input_size)
    
    def predict(self, features: np.ndarray) -> float:
        """Faz predição."""
        # Normaliza
        features_norm = (features - self.scaler_mean) / (self.scaler_scale + 1e-10)
        
        # Converte para tensor
        x = torch.tensor(features_norm, dtype=torch.float32).unsqueeze(0)
        
        # Predição
        with torch.no_grad():
            logits = self.model(x)
            prob = torch.sigmoid(logits).item()
        
        return prob
    
    def export_to_onnx(self, output_path: Path, seq_length: int = 60):
        """Exporta para ONNX (mais rápido em produção)."""
        dummy_input = torch.randn(1, seq_length, len(self.feature_names))
        
        torch.onnx.export(
            self.model,
            dummy_input,
            output_path,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )
        
        print(f"   ✅ ONNX exportado: {output_path}")
    
    def export_to_pickle(self, output_path: Path):
        """Exporta para pickle (compatível com bot atual)."""
        # Cria versão simplificada para LightGBM-like interface
        export_data = {
            'model_state_dict': self.model.state_dict(),  # Salva state_dict, não o modelo
            'feature_names': self.feature_names,
            'scaler_mean': self.scaler_mean,
            'scaler_scale': self.scaler_scale,
            'threshold': self.threshold,
            'metrics': self.metrics,
            'model_type': 'deep_learning',
            'trained_at': datetime.now().isoformat()
        }
        
        with open(output_path, 'wb') as f:
            pickle.dump(export_data, f)
        
        print(f"   ✅ Pickle exportado: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Exporta modelos para produção')
    parser.add_argument('--input-dir', default='models', help='Pasta com modelos .pt')
    parser.add_argument('--output-dir', default='models', help='Pasta de saída')
    parser.add_argument('--format', default='pickle', choices=['pickle', 'onnx', 'both'], help='Formato de saída')
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not input_dir.exists():
        print(f"❌ Pasta não encontrada: {input_dir}")
        return
    
    # Procura modelos .pt
    model_files = list(input_dir.glob("*.pt"))
    
    if not model_files:
        print(f"❌ Nenhum modelo .pt encontrado em {input_dir}")
        return
    
    print(f"\n📁 Encontrados {len(model_files)} modelos")
    
    for model_file in model_files:
        print(f"\n📊 Processando {model_file.name}...")
        
        try:
            prod_model = ProductionModel(model_file)
            
            # Nome base
            base_name = model_file.stem  # ex: eurusd_lstm
            
            # Exporta
            if args.format in ['pickle', 'both']:
                pickle_path = output_dir / f"{base_name}_deep.pkl"
                prod_model.export_to_pickle(pickle_path)
            
            if args.format in ['onnx', 'both']:
                onnx_path = output_dir / f"{base_name}.onnx"
                prod_model.export_to_onnx(onnx_path)
            
            # Mostra métricas
            metrics = prod_model.metrics
            if metrics:
                print(f"   📈 Métricas: F1={metrics.get('f1', 0):.3f} "
                      f"Precision={metrics.get('precision', 0):.3f} "
                      f"Recall={metrics.get('recall', 0):.3f}")
        
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    print(f"\n{'='*60}")
    print(f"✅ Exportação concluída!")
    print(f"   Modelos salvos em: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
