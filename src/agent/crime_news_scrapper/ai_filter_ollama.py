import logging
import json
import os
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CrimeFilterLocal:
    """
    Używa LOKALNEGO Ollama (Bielik 11B/Llama 3.2)
    
    INSTALACJA:
    1. Pobierz Ollama: https://ollama.com/download
    2. Zainstaluj model: ollama pull bielik:11b-v2.3-instruct-q4_K_M
       (lub: ollama pull llama3.2:3b-instruct-q4_K_M - szybszy)
    3. Uruchom: ollama serve
    """
    
    def __init__(self, model="llama3.2:3b-instruct-q4_K_M"):
        logger.info("=== Inicjalizuję Ollama (lokalny LLM - AMD GPU) ===")
        
        self.model = model
        self.api_url = "http://localhost:11434/api/generate"
        
        # Dla AMD iGPU - mniejsze modele są lepsze
        logger.info("Dla Radeon 890M zalecane: llama3.2:3b lub phi3:3.8b")
        
        # Sprawdź czy Ollama działa
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [m['name'] for m in response.json()['models']]
            
            if self.model not in models:
                logger.warning(f"Model {self.model} nie jest zainstalowany!")
                logger.info("Zainstaluj: ollama pull bielik:11b-v2.3-instruct-q4_K_M")
                logger.info("Dostępne: " + ", ".join(models))
                
                # Fallback na dostępny model
                if models:
                    self.model = models[0]
                    logger.info(f"Używam: {self.model} (fallback)")
            else:
                logger.info(f"Model: {self.model}")
                
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Ollama nie działa!\n"
                "Uruchom w terminalu: ollama serve\n"
                "Instalacja: https://ollama.com/download"
            )
        
        logger.info("ZERO limitów API!")
        logger.info("Działa offline")
        
        # Cache
        self.filter_cache = {}
        self.extract_cache = {}
        self.cache_file = "data/ollama_cache.json"
        self._load_cache()
        
        # Geokoder z cache
        self.geolocator = Nominatim(user_agent="krakow_crime_ollama", timeout=10)
        self.geocode_cache = {}
        logger.info(f"Cache: {len(self.filter_cache)} filtrów, {len(self.geocode_cache)} lokalizacji")


    def _load_cache(self):
        """Wczytaj cache"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.filter_cache = cache_data.get('filter', {})
                    self.extract_cache = cache_data.get('extract', {})
                    self.geocode_cache = cache_data.get('geocode', {})
            except Exception as e:
                logger.warning(f"Błąd ładowania cache: {e}")

    def _save_cache(self):
        """Zapisz cache"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'filter': self.filter_cache,
                    'extract': self.extract_cache,
                    'geocode': self.geocode_cache
                }, f, ensure_ascii=False, indent=2)
            logger.info("Cache Ollama zapisany.")
        except Exception as e:
            logger.error(f"Błąd zapisu cache: {e}")

    def ask_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """Wysyła zapytanie do lokalnego Ollama"""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3, # Poprawiona temperatura
                        "num_predict": max_tokens,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                logger.error(f"Ollama error: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"Błąd Ollama: {e}")
            return ""

    def is_crime_related(self, title: str, teaser: str = "", content: str = "") -> bool:
        """
        FILTR: Czy artykuł dotyczy przestępstwa/zagrożenia?
        + Cache
        """
        # KLUCZ CACHE NA CAŁYM TYTULE (Poprawiono)
        cache_key = str(hash(title)) 
        
        # Sprawdź cache
        if cache_key in self.filter_cache:
            logger.debug(f"Cache hit: {title[:40]}...")
            return self.filter_cache[cache_key]
        
        # Generowanie tekstu do zapytania
        text_to_analyze = " ".join([title, teaser, content[:200]]).strip()
        
        prompt = f"""You are filtering news for a crime and safety map.

Article title: "{text_to_analyze}"

Does this describe **ANY** of these situations in the Małopolska region:
- **Wszelkie formy przemocy lub przestępstw**: kradzież, oszustwo, pobicie, groźby, handel, narkotyki.
- **Wypadki lub incydenty związane z transportem**: wypadki drogowe, kolejowe, kolizje, ucieczki.
- **Zagrożenia naturalne lub awarie**: pożar, powódź, wybuch, alarm bombowy, katastrofa budowlana.
- **Działania Służb**: interwencja Policji, akcja Straży Pożarnej, poszukiwania zaginionych osób.

Answer ONLY: YES or NO

Answer:"""

        response = self.ask_llm(prompt, max_tokens=10)
        is_crime = "TAK" in response.upper()
        
        # Zapisz do cache
        self.filter_cache[cache_key] = is_crime
        
        if len(self.filter_cache) % 10 == 0:
            self._save_cache()
        
        logger.info(f"[FILTR] {title[:50]}... → {response}")
        return is_crime

    def extract_event_info(self, title: str, teaser: str = "", content: str = "") -> dict:
        """
        EKSTRAKCJA szczegółów z artykułu
        + Cache
        """
        text = " ".join([title, teaser, content[:1500]]).strip()
        
        # Sprawdź cache
        cache_key = str(hash(text[:200]))
        if cache_key in self.extract_cache:
            logger.debug(f"Cache hit extraction: {title[:40]}...")
            return self.extract_cache[cache_key]
        
        prompt = f"""Jesteś ekspertem analizującym zdarzenia w Małopolsce dla systemu mapy zagrożeń.

=== ARTYKUŁ ===
{text}
=== KONIEC ===

Wyciągnij informacje i zwróć TYLKO poprawny JSON:

{{
    "crime_type": "[wybierz JEDNO: wypadek/pożar/kradzież/napad/zabójstwo/pobicie/oszustwo/interwencja/inne]",
    "location_name": "[DOKŁADNA nazwa ulicy/miejscowości/miejsca. Zachowaj polskie znaki. Jeśli brak: 'Kraków']",
    "severity": [liczba 1-10, gdzie: 1-3=drobne, 4-6=średnie, 7-9=poważne, 10=śmiertelne],
    "summary": "[krótkie streszczenie w 1-2 zdaniach po polsku]"
}}

WAŻNE:
- Dla location_name: szukaj nazw ulic, miejscowości (Tarnów, Nowy Sącz, Oświęcim itp.)
- Jeśli "ul. Wielickiej" to zwróć "Wielicka, Kraków"
- Jeśli "w Tarnowie" to zwróć "Tarnów"
- Zachowaj polskie znaki: ą, ę, ć, ł, ń, ó, ś, ź, ż"""

        response = self.ask_llm(prompt, max_tokens=300)
        
        # Parsuj JSON
        try:
            # Usuń markdown
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            # Znajdź { ... }
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                response = response[start:end]
            
            info = json.loads(response.strip())
            logger.info(f"LLM: {info['crime_type']} @ {info['location_name']} (waga: {info.get('severity', '?')})")
            
        except json.JSONDecodeError as e:
            logger.error(f"Błąd JSON: {e}")
            logger.debug(f"Odpowiedź: {response}")
            
            info = {
                "crime_type": "inne",
                "location_name": "Kraków",
                "severity": 5,
                "summary": text[:200]
            }
        
        # Geokodowanie (z cache)
        location_name = info.get("location_name", "Kraków")
        location_clean = (location_name
                             .replace("ulica ", "")
                             .replace("ul. ", "")
                             .replace("w ", "")
                             .replace("na ", "")
                             .strip())
        
        lat, lon = self.geocode_location(location_clean)
        
        if lat is None or lon is None:
            logger.warning("Domyślne współrzędne (centrum)")
            lat, lon = 50.0614, 19.9366
        
        result = {
            "crime_type": info.get("crime_type", "inne"),
            "location_name": location_name,
            "latitude": lat,
            "longitude": lon,
            "severity": info.get("severity", 5),
            "short_summary": info.get("summary", text[:200])
        }
        
        # Zapisz do cache
        self.extract_cache[cache_key] = result
        
        if len(self.extract_cache) % 5 == 0:
            self._save_cache()
        
        return result

    def geocode_location(self, location_name: str) -> tuple:
        """Zamienia nazwę na współrzędne + CACHE"""
        if not location_name or location_name == "Kraków":
            return 50.0614, 19.9366
        
        # Sprawdź cache
        if location_name in self.geocode_cache:
            logger.debug(f"Geocode cache: {location_name}")
            return tuple(self.geocode_cache[location_name])
        
        try:
            # Najpierw spróbuj z Małopolską
            full_address = f"{location_name}, Małopolska, Polska"
            logger.info(f"Geokodowanie: {full_address}")
            
            location = self.geolocator.geocode(full_address, language="pl")
            
            if location:
                coords = (location.latitude, location.longitude)
                logger.info(f"({coords[0]:.4f}, {coords[1]:.4f})")
                self.geocode_cache[location_name] = coords
                return coords
            
            # Fallback bez Małopolski
            location = self.geolocator.geocode(f"{location_name}, Polska", language="pl")
            if location:
                coords = (location.latitude, location.longitude)
                self.geocode_cache[location_name] = coords
                return coords
            
            logger.warning(f"Nie znaleziono: {location_name}")
            return None, None
            
        except GeocoderTimedOut:
            logger.error("Timeout")
            return None, None
        except Exception as e:
            logger.error(f" Błąd: {e}")
            return None, None

