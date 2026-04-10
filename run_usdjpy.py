# Bot para USD/JPY-T
import sys
sys.path.insert(0, '.')

# Substitui o config antes de importar main
import config_usdjpy as config
sys.modules['config'] = config

from main import main

if __name__ == "__main__":
    print("🚀 Iniciando bot USD/JPY-T...")
    main()
