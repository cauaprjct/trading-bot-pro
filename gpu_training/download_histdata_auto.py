"""
📥 HistData.com Auto Downloader - Usa Playwright para baixar automaticamente
Baixa dados M1 de 2023-2025 para todos os 7 símbolos Forex.

Uso: python gpu_training/download_histdata_auto.py
"""
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright
import time

# Configuração
SYMBOLS = ["eurusd", "gbpusd", "usdjpy", "usdcad", "audusd", "eurjpy", "gbpjpy"]
YEARS = [2023, 2024, 2025]
OUTPUT_DIR = Path("gpu_training/historical_data_raw")

# URL base
BASE_URL = "https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes"


async def download_file(page, symbol: str, year: int, download_path: Path) -> bool:
    """Baixa um arquivo específico."""
    url = f"{BASE_URL}/{symbol}/{year}"
    
    print(f"  📥 Acessando {symbol.upper()} {year}...")
    
    try:
        await page.goto(url, timeout=30000)
        await asyncio.sleep(2)  # Espera carregar
        
        # Procura o link de download
        download_link = page.get_by_role("link", name=f"HISTDATA_COM_ASCII_{symbol.upper()}_M1_{year}.zip")
        
        if await download_link.count() == 0:
            print(f"  ❌ Link não encontrado para {symbol.upper()} {year}")
            return False
        
        # Configura download
        async with page.expect_download(timeout=120000) as download_info:
            await download_link.click()
        
        download = await download_info.value
        
        # Salva o arquivo
        filename = f"HISTDATA_COM_ASCII_{symbol.upper()}_M1_{year}.zip"
        filepath = download_path / filename
        await download.save_as(filepath)
        
        size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"  ✅ {filename} ({size_mb:.1f} MB)")
        return True
        
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False


async def main():
    print("="*60)
    print("📥 HISTDATA.COM AUTO DOWNLOADER")
    print("="*60)
    print(f"Símbolos: {', '.join(s.upper() for s in SYMBOLS)}")
    print(f"Anos: {', '.join(str(y) for y in YEARS)}")
    print(f"Total: {len(SYMBOLS) * len(YEARS)} arquivos")
    print("="*60)
    
    # Cria diretórios
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for symbol in SYMBOLS:
        (OUTPUT_DIR / symbol.upper()).mkdir(exist_ok=True)
    
    async with async_playwright() as p:
        print("\n🚀 Iniciando browser...")
        browser = await p.chromium.launch(headless=False)  # headless=False para ver
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        
        # Aceita cookies se aparecer
        try:
            await page.goto("https://www.histdata.com", timeout=15000)
            accept_btn = page.get_by_role("button", name="ACCEPT")
            if await accept_btn.count() > 0:
                await accept_btn.click()
                print("✅ Cookies aceitos")
        except:
            pass
        
        results = {"ok": 0, "fail": 0}
        
        for symbol in SYMBOLS:
            print(f"\n📊 {symbol.upper()}")
            download_path = OUTPUT_DIR / symbol.upper()
            
            for year in YEARS:
                # Verifica se já existe
                filename = f"HISTDATA_COM_ASCII_{symbol.upper()}_M1_{year}.zip"
                filepath = download_path / filename
                
                if filepath.exists():
                    size_mb = filepath.stat().st_size / (1024 * 1024)
                    print(f"  ⏭️ {filename} já existe ({size_mb:.1f} MB)")
                    results["ok"] += 1
                    continue
                
                success = await download_file(page, symbol, year, download_path)
                if success:
                    results["ok"] += 1
                else:
                    results["fail"] += 1
                
                # Pausa entre downloads
                await asyncio.sleep(3)
        
        await browser.close()
    
    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO")
    print("="*60)
    print(f"✅ Sucesso: {results['ok']}")
    print(f"❌ Falha: {results['fail']}")
    
    if results["ok"] > 0:
        print(f"\n📁 Arquivos salvos em: {OUTPUT_DIR.absolute()}")
        print("\n🔄 Próximo passo:")
        print("   python gpu_training/convert_histdata.py")


if __name__ == "__main__":
    asyncio.run(main())
