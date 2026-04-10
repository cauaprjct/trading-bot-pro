# Bot para GBP/USD-T
import sys
sys.path.insert(0, '.')

# Substitui o config antes de importar main
import config_gbpusd as config
sys.modules['config'] = config

from main import main

if __name__ == "__main__":
    print("🚀 Iniciando bot GBP/USD-T...")
    main()
