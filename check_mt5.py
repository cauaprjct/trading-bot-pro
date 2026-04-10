import MetaTrader5 as mt5
import time

print("🔍 Iniciando diagnóstico do MetaTrader 5...")

if not mt5.initialize():
    print(f"❌ Falha ao conectar no MT5: {mt5.last_error()}")
    print("⚠️ Certifique-se de que o MetaTrader 5 Desktop está ABERTO e logado.")
    quit()

print("✅ Conexão com o Terminal estabelecida!")

# Info da Conta
account = mt5.account_info()
if account:
    print(f"\n👤 Conta: {account.login}")
    print(f"🏢 Servidor: {account.server}")
    print(f"💰 Saldo: {account.balance} {account.currency}")
    print(f"🚦 AlgoTrading Habilitado? {'SIM' if mt5.terminal_info().trade_allowed else 'NÃO (Habilite o botão AlgoTrading no MT5!)'}")
else:
    print("❌ Não foi possível ler os dados da conta.")

# Verificação de Ativos
print("\n🔎 Verificando ativos disponíveis...")
symbols = mt5.symbols_get()
symbol_names = [s.name for s in symbols] if symbols else []

target_b3 = ["WINJ24", "WINM24", "WINQ24", "WINV24", "WINZ24", "WDOJ24"] # Exemplos
found_b3 = [s for s in target_b3 if s in symbol_names]

if found_b3:
    print(f"✅ Ativos B3 encontrados: {found_b3}")
    print(f"ℹ️ Configure um desses no seu 'config.py'.")
elif "EURUSD" in symbol_names:
    print("⚠️ NENHUM ativo da B3 (WIN/WDO) foi encontrado nesta conta.")
    print("✅ Mas encontrei ativos de FOREX (EURUSD, etc).")
    print("💡 DIAGNÓSTICO: Você criou uma conta 'MetaQuotes' ou 'Admirals' (Gringa).")
    print("   -> Para testar o bot AGORA: Mude 'SYMBOL' no config.py para 'EURUSD'.")
    print("   -> Para operar B3: Você precisa abrir conta demo na XP, Rico, Genial, etc.")
else:
    print("❌ Nenhum ativo conhecido encontrado. Verifique a 'Observação do Mercado' no MT5.")

print("\n🏁 Diagnóstico concluído.")
mt5.shutdown()
