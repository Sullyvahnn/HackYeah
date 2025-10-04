#!/usr/bin/env python3
"""
Skrypt testowy dla Cyklu 1: Scrapowanie i Filtracja
Uruchom z folderu src/: python test_cycle1.py
"""

import os
import sys

# Dodaj src/ do PYTHONPATH
sys.path.insert(0, os.path.dirname(__file__))

def test_database():
    """Test 1: Sprawdź czy baza danych działa"""
    print("="*60)
    print("TEST 1: Inicjalizacja bazy danych")
    print("="*60)
    
    from agent.db import initialize_db_manager
    
    db_manager = initialize_db_manager('data/crime_data.db')
    stats = db_manager.get_statistics()
    
    print(f"✅ Baza danych działa!")
    print(f"   Wszystkie artykuły: {stats['total_articles']}")
    print(f"   Przetworzone: {stats['processed']}")
    print(f"   Oczekujące: {stats['pending']}")
    print()
    
    return db_manager

def test_ai_filter():
    """Test 2: Sprawdź czy filtr AI działa"""
    print("="*60)
    print("TEST 2: Filtr AI")
    print("="*60)
    
    from agent.crime_news_scrapper.ai_filter import CrimeFilter
    
    print("Ładuję model AI...")
    filter_ai = CrimeFilter()
    
    # Testowe artykuły
    test_cases = [
        ("Złodziej ukradł samochód na ulicy Długiej w Krakowie", True),
        ("Pogoda na weekend: ciepło i słonecznie", False),
        ("Policja zatrzymała sprawcę rozboju w centrum miasta", True),
        ("Nowy salon piękności otwarto na Rynku", False),
    ]
    
    print("\n🧪 Testuję klasyfikację:\n")
    for title, expected in test_cases:
        result = filter_ai.is_crime_related(title)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{title[:50]}...' → {result}")
    
    print()
    return filter_ai

def run_spider():
    """Test 3: Uruchom spider"""
    print("="*60)
    print("TEST 3: Uruchomienie Spider")
    print("="*60)
    print("Uruchamiam scrapy spider...")
    print("UWAGA: To może potrwać kilka minut!\n")
    
    # Uruchom scrapy z linii komend
    os.system("cd src && scrapy crawl crime_news -s CLOSESPIDER_PAGECOUNT=3")

def check_results(db_manager):
    """Test 4: Sprawdź zapisane artykuły"""
    print("\n" + "="*60)
    print("TEST 4: Wyniki w bazie danych")
    print("="*60)
    
    stats = db_manager.get_statistics()
    print(f"📊 Statystyki:")
    print(f"   Wszystkie artykuły: {stats['total_articles']}")
    print(f"   Przetworzone: {stats['processed']}")
    print(f"   Oczekujące na AI: {stats['pending']}")
    
    # Pokaż przykładowe artykuły
    unprocessed = db_manager.get_unprocessed_articles(limit=5)
    
    if unprocessed:
        print(f"\n📰 Przykładowe artykuły do przetworzenia:\n")
        for i, article in enumerate(unprocessed, 1):
            print(f"{i}. [{article['source']}] {article['title']}")
            print(f"   Długość tekstu: {len(article['raw_text'])} znaków")
            print(f"   URL: {article['url'][:80]}...")
            print()
    else:
        print("\n⚠️ Brak nieprzetworzonych artykułów w bazie!")
    
    print("="*60)

if __name__ == "__main__":
    print("\n🚀 URUCHAMIAM TESTY CYKLU 1\n")
    
    try:
        # Test 1: Baza danych
        db_manager = test_database()
        
        # Test 2: Filtr AI
        test_ai_filter()
        
        # Test 3: Spider (można pominąć dla szybkiego testu)
        response = input("Czy uruchomić spider? (może potrwać ~2-3 min) [t/N]: ")
        if response.lower() == 't':
            run_spider()
            
            # Test 4: Wyniki
            check_results(db_manager)
        else:
            print("\n⏭️ Pomijam uruchomienie spider")
            print("💡 Aby uruchomić ręcznie: cd src && scrapy crawl crime_news")
        
        print("\n✅ TESTY ZAKOŃCZONE!")
        
    except Exception as e:
        print(f"\n❌ BŁĄD: {e}")
        import traceback
        traceback.print_exc()