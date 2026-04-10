"""
🔍 Script para verificar símbolos disponíveis no MT5
Uso: python check_symbols.py
"""

import MetaTrader5 as mt5

def main():
    # Conecta ao MT5
    if not mt5.initialize():
        print("❌ Falha ao conectar ao MT5!")
        print("   Certifique-se que o MT5 está aberto e logado.")
        return
    
    print("✅ Conectado ao MT5!")
    print()
    
    # Info da conta
    account = mt5.account_info()
    if account:
        print(f"📊 Conta: {account.login}")
        print(f"🏦 Corretora: {account.company}")
        print(f"💰 Saldo: ${account.balance:.2f}")
        print()
    
    # Lista TODOS os símbolos disponíveis
    all_symbols = mt5.symbols_get()
    
    print("="*60)
    print(f"🔍 TODOS OS SÍMBOLOS DISPONÍVEIS ({len(all_symbols)} total)")
    print("="*60)
    print()
    
    # Agrupa por categoria
    forex = []
    crypto = []
    indices = []
    metals = []
    stocks = []
    others = []
    
    for s in all_symbols:
        name = s.name
        path = s.path if hasattr(s, 'path') else ""
        
        # Classifica
        if "Crypto" in path or "BTC" in name or "ETH" in name or "SOL" in name:
            crypto.append(s)
        elif "Forex" in path or name in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]:
            forex.append(s)
        elif "Index" in path or "SP500" in name or "NAS" in name or "DAX" in name:
            indices.append(s)
        elif "Metal" in path or "XAU" in name or "XAG" in name:
            metals.append(s)
        elif any(x in name for x in ["AAPL", "GOOGL", "MSFT", "NVDA", "AMD", "TSLA"]):
            stocks.append(s)
        else:
            others.append(s)
    
    def print_category(name, symbols, limit=10):
        if not symbols:
            print(f"\n{name}: Nenhum encontrado ❌")
            return
        
        print(f"\n{name} ({len(symbols)} símbolos):")
        print("-"*50)
        for s in symbols[:limit]:
            tick = mt5.symbol_info_tick(s.name)
            price = tick.bid if tick else 0
            spread = (tick.ask - tick.bid) * 10000 if tick and tick.ask > 0 else 0
            visible = "✅" if s.visible else "❌"
            
            if price > 1000:
                price_str = f"{price:.2f}"
            else:
                price_str = f"{price:.5f}"
            
            print(f"  {visible} {s.name.ljust(12)} | Preço: {price_str.ljust(12)} | Spread: {spread:.1f} pts")
        
        if len(symbols) > limit:
            print(f"  ... e mais {len(symbols) - limit} símbolos")
    
    print_category("💱 FOREX", forex, 10)
    print_category("₿ CRYPTO", crypto, 10)
    print_category("📈 ÍNDICES", indices, 10)
    print_category("🥇 METAIS", metals, 5)
    print_category("📊 AÇÕES", stocks, 10)
    print_category("📦 OUTROS", others, 5)
    
    print()
    print("="*60)
    print("💡 MELHORES PARA SEU BOT (spread baixo + visível):")
    print("="*60)
    
    # Encontra os melhores
    all_tradeable = [s for s in all_symbols if s.visible]
    
    best = []
    for s in all_tradeable:
        tick = mt5.symbol_info_tick(s.name)
        if tick and tick.bid > 0:
            spread = (tick.ask - tick.bid) / tick.bid * 10000  # Spread relativo
            best.append({
                "name": s.name,
                "spread": spread,
                "price": tick.bid
            })
    
    best.sort(key=lambda x: x["spread"])
    
    print("\nTop 10 menor spread:")
    for i, b in enumerate(best[:10], 1):
        print(f"  {i}. {b['name'].ljust(12)} - Spread: {b['spread']:.2f} pts")
    
    mt5.shutdown()

if __name__ == "__main__":
    main()
