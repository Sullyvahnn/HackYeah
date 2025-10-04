#!/usr/bin/env python3
"""
Scraper dla całej Małopolski z AI filterem (Ollama)

Użycie:
  python run_malopolska.py              # Pełny scraping
  python run_malopolska.py --quick      # Szybki test (20 artykułów)
  python run_malopolska.py --police     # Tylko strony policji
  python run_malopolska.py --help       # Pomoc
"""
import sys
import os
import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importy spider'ów
try:
    from agent.crime_news_scrapper.malopolska_crime_spider import MalopolskaCrimeSpider
except ImportError as e:
    print(f"Błąd importu: {e}")
    print("Upewnij się, że struktura katalogów jest poprawna:")
    print("  agent/crime_news_scrapper/malopolska_crime_spider.py")
    sys.exit(1)

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def check_ollama():
    """Sprawdza czy Ollama działa"""
    import requests
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = [m['name'] for m in response.json()['models']]
            logger.info(f"Ollama działa! Dostępne modele: {', '.join(models)}")
            return True
    except requests.exceptions.ConnectionError:
        logger.error("Ollama nie działa!")
        logger.error("Uruchom w osobnym terminalu: ollama serve")
        logger.error("Instalacja: https://ollama.com/download")
        return False
    except Exception as e:
        logger.error(f"Błąd sprawdzania Ollama: {e}")
        return False


def run_scraping(mode='full'):
    """
    Uruchamia scraping według trybu:
    - full: Wszystkie źródła (150 artykułów, 100 stron)
    - quick: Szybki test (20 artykułów, 15 stron)
    - police: Tylko policja (30 artykułów, 25 stron)
    """
    
    # Sprawdź Ollama
    if not check_ollama():
        return
    
    # Utwórz katalogi
    os.makedirs("data/malopolska", exist_ok=True)
    
    settings = get_project_settings()
    
    # Podstawowe ustawienia Scrapy
    settings.set('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    settings.set('ROBOTSTXT_OBEY', False)
    settings.set('COOKIES_ENABLED', False)
    settings.set('CONCURRENT_REQUESTS', 2)
    settings.set('LOG_LEVEL', 'INFO')
    
    # Nadpisz ustawienia według trybu
    if mode == 'quick':
        settings.set('CLOSESPIDER_ITEMCOUNT', 20)
        settings.set('CLOSESPIDER_PAGECOUNT', 15)
        settings.set('DOWNLOAD_DELAY', 1.0)
        logger.info("TRYB: Szybki test (20 artykułów, 15 stron)")
        
    elif mode == 'police':
        settings.set('CLOSESPIDER_ITEMCOUNT', 30)
        settings.set('CLOSESPIDER_PAGECOUNT', 25)
        settings.set('DOWNLOAD_DELAY', 1.0)
        logger.info("TRYB: Tylko strony policji")
        
    else:
        settings.set('CLOSESPIDER_ITEMCOUNT', 150)
        settings.set('CLOSESPIDER_PAGECOUNT', 100)
        settings.set('DOWNLOAD_DELAY', 2.0)
        logger.info("TRYB: Pełny scraping Małopolski (150 artykułów)")
    
    process = CrawlerProcess(settings)
    
    # Uruchom spider
    process.crawl(MalopolskaCrimeSpider)
    
    print("\n" + "="*70)
    print("ROZPOCZYNAM SCRAPING MAŁOPOLSKI...")
    print("="*70)
    print(f"Źródła: TVN24, NaszeMiasto, Fakt, Policja")
    print(f"AI: Ollama (lokalny LLM - ZERO limitów)")
    print("="*70 + "\n")
    
    try:
        process.start()
    except KeyboardInterrupt:
        logger.warning("\nPrzerwano przez użytkownika (Ctrl+C)")
        return
    except Exception as e:
        logger.error(f"Błąd podczas scrapowania: {e}")
        return
    
    print("\n" + "="*70)
    print("SCRAPING ZAKOŃCZONY!")
    print("="*70)
    print("\nSprawdź wyniki:")
    print("  - data/malopolska/events_*.jsonl")
    print("  - data/crime_data.db")
    print("  - data/ollama_cache.json (cache AI)")
    print("\nTIP: Uruchom dashboard: streamlit run dashboard.py")
    print("="*70 + "\n")


def show_help():
    """Wyświetla pomoc"""
    print(__doc__)
    print("\nOpcje:")
    print("  --quick, -q     Szybki test (20 artykułów, ~2 min)")
    print("  --police, -p    Tylko strony policji (30 artykułów)")
    print("  --help, -h      Ta pomoc")
    print("\nPrzykłady:")
    print("  python run_malopolska.py")
    print("  python run_malopolska.py --quick")
    print("  python run_malopolska.py --police")
    print("\nWymagania:")
    print("  1. Zainstaluj Ollama: https://ollama.com/download")
    print("  2. Pobierz model: ollama pull llama3.2:3b-instruct-q4_K_M")
    print("  3. Uruchom serwer: ollama serve")
    print("  4. Uruchom scraper: python run_malopolska.py")


if __name__ == "__main__":
    # Parsuj argumenty
    mode = 'full'
    
    if '--quick' in sys.argv or '-q' in sys.argv:
        mode = 'quick'
    elif '--police' in sys.argv or '-p' in sys.argv:
        mode = 'police'
    elif '--help' in sys.argv or '-h' in sys.argv:
        show_help()
        sys.exit(0)
    
    run_scraping(mode)