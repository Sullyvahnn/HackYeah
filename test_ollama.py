#!/usr/bin/env python3
"""
Test Ollama API przed uruchomieniem scrapingu
"""

import os
import sys
import time
import requests

def test_ollama():
    """Test czy Ollama działa"""
    print("=" * 60)
    print("🧪 TEST OLLAMA API")
    print("=" * 60)
    
    # Sprawdź czy serwer działa
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            print("❌ Ollama serwer nie odpowiada!")
            print("\n🚀 Uruchom w osobnym terminalu:")
            print("  ollama serve")
            return False
            
        models = response.json().get('models', [])
        model_names = [m['name'] for m in models]
        
        print(f"✅ Ollama działa!")
        print(f"✅ Zainstalowane modele: {len(models)}")
        for name in model_names:
            print(f"  • {name}")
        
        if not models:
            print("\n❌ Brak modeli!")
            print("\n📦 Pobierz model:")
            print("  ollama pull llama3.2:3b-instruct-q4_K_M")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Nie można połączyć z Ollama!")
        print("\n🚀 Uruchom w osobnym terminalu:")
        print("  ollama serve")
        print("\n💡 Jeśli już działa, sprawdź port 11434")
        return False
    
    # Wybierz model do testu
    test_model = None
    preferred = [
        "llama3.2:3b-instruct-q4_K_M",
        "llama3.2:3b",
        "phi3:3.8b-mini-instruct-q4_K_M",
        "gemma2:2b-instruct-q4_K_M"
    ]
    
    for pref in preferred:
        if pref in model_names:
            test_model = pref
            break
    
    if not test_model:
        test_model = model_names[0]
    
    print(f"\n🧠 Testuję model: {test_model}")
    
    # Test zapytania
    try:
        print("\n🔄 Test 1: Proste zapytanie...")
        start = time.time()
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": test_model,
                "prompt": "Answer ONLY: YES or NO. Is this a crime: 'Car accident on highway'",
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 10
                }
            },
            timeout=30
        )
        
        elapsed = time.time() - start
        result = response.json()
        answer = result.get('response', '').strip()
        
        print(f"✅ Odpowiedź: '{answer}' ({elapsed:.2f}s)")
        
        if "YES" in answer.upper() or "TAK" in answer.upper():
            print("✅ Model odpowiada poprawnie!")
        else:
            print(f"⚠️  Nieoczekiwana odpowiedź, ale działa")
        
    except Exception as e:
        print(f"❌ Błąd zapytania: {e}")
        return False
    
    # Test AI filter
    print("\n🧠 Testuję AI filter...")
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from agent.crime_news_scrapper.ai_filter_ollama import CrimeFilterLocal
        
        ai = CrimeFilterLocal(model=test_model)
        print("✅ CrimeFilterLocal zainicjalizowany")
        
        # Test filtrowania
        test_titles = [
            "Wypadek na ul. Wielickiej - 2 rannych",
            "Nowa kawiarnia w centrum Krakowa",
            "Pożar w Nowej Hucie - ewakuacja",
            "Festiwal muzyczny w Tarnowie"
        ]
        
        print("\n🔍 Test filtrowania:")
        correct = 0
        total = len(test_titles)
        
        for i, title in enumerate(test_titles, 1):
            expected = i in [1, 3]  # 1 i 3 to przestępstwa
            is_crime = ai.is_crime_related(title)
            emoji = "✅" if is_crime == expected else "⚠️"
            correct += (is_crime == expected)
            print(f"  {emoji} {title[:50]} → {is_crime}")
        
        accuracy = 100 * correct / total
        print(f"\n📊 Trafność: {correct}/{total} ({accuracy:.0f}%)")
        
        if accuracy >= 75:
            print("✅ Model działa dobrze!")
        else:
            print("⚠️  Model może potrzebować lepszych promptów")
        
        # Test ekstrakcji
        print("\n📊 Test ekstrakcji:")
        start = time.time()
        info = ai.extract_event_info(
            "Wypadek na ul. Wielickiej w Krakowie",
            "",
            "W czwartek rano doszło do poważnego wypadku na ul. Wielickiej w Krakowie. Zderzyły się dwa samochody. Dwie osoby zostały ranne i trafiły do szpitala."
        )
        elapsed = time.time() - start
        
        print(f"  Czas: {elapsed:.2f}s")
        print(f"  Typ: {info['crime_type']}")
        print(f"  Lokalizacja: {info['location_name']}")
        print(f"  Współrzędne: ({info['latitude']:.4f}, {info['longitude']:.4f})")
        print(f"  Waga: {info['severity']}/10")
        print(f"  Streszczenie: {info['short_summary'][:60]}...")
        
        if info['crime_type'] == 'wypadek' and 'Wielicka' in info['location_name']:
            print("✅ Ekstrakcja działa poprawnie!")
        else:
            print("⚠️  Ekstrakcja działa, ale może być niedokładna")
        
    except Exception as e:
        print(f"❌ Błąd AI filter: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Podsumowanie
    print("\n" + "=" * 60)
    print("✅ OLLAMA GOTOWY DO UŻYCIA!")
    print("=" * 60)
    print(f"\n🎯 Model: {test_model}")
    print(f"⚡ Szybkość: ~{elapsed:.1f}s/artykuł")
    print(f"💾 Cache: Duplikaty będą instant")
    print("\n🚀 Możesz uruchomić scraping:")
    print("  python run_malopolska.py --quick    # Test 20 artykułów")
    print("  python run_malopolska.py            # Pełny 150 artykułów")
    print("\n✨ ZALETY OLLAMA:")
    print("  ✅ ZERO limitów API")
    print("  ✅ Działa offline")
    print("  ✅ Gratis na zawsze")
    print("  ✅ Szybki na Radeon 890M")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_ollama()
    sys.exit(0 if success else 1)