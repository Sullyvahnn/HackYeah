import logging
import json
import os
import time
import google.generativeai as genai
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CrimeFilterLocal:
    """
    Używa Google Gemini API - DARMOWE 1500 req/dzień!
    Zarejestruj się: https://makersuite.google.com/app/apikey
    """
    
    def __init__(self):
        logger.info("=== Inicjalizuję Google Gemini API ===")
        
        # Google Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "Brak GEMINI_API_KEY! Ustaw: export GEMINI_API_KEY='AIza...'\n"
                "Zdobądź klucz: https://makersuite.google.com/app/apikey"
            )
        
        genai.configure(api_key=api_key)
        
        # Model: gemini-1.5-flash (szybki i darmowy)
        self.model = genai.GenerativeModel('gemini-pro')
        
        logger.info("Model: gemini-pro")
        logger.info("Limit: 60 requestów/minutę (DARMOWE)")
        
        # Rate limiting
        self.request_count = 0
        self.last_minute_start = time.time()
        self.max_requests_per_minute = 12  # Bezpieczny margines (15-3)
        
        # Cache
        self.filter_cache = {}
        self.extract_cache = {}
        self.cache_file = "data/ai_cache.json"
        self._load_cache()
        
        # Geokoder z cache
        self.geolocator = Nominatim(user_agent="krakow_crime_gemini", timeout=10)
        self.geocode_cache = {}

    def _load_cache(self):
        """Wczytaj cache z poprzednich uruchomień"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.filter_cache = cache_data.get('filter', {})
                    self.extract_cache = cache_data.get('extract', {})
                    self.geocode_cache = cache_data.get('geocode', {})
                    logger.info(f"Cache: {len(self.filter_cache)} filtrów, {len(self.geocode_cache)} lokalizacji")
            except Exception as e:
                logger.warning(f"Nie udało się wczytać cache: {e}")

    def _save_cache(self):
        """Zapisz cache na dysk"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'filter': self.filter_cache,
                    'extract': self.extract_cache,
                    'geocode': self.geocode_cache
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Błąd zapisu cache: {e}")

    def check_rate_limit(self):
        """Sprawdza i egzekwuje limit RPM"""
        if time.time() - self.last_minute_start > 60:
            self.request_count = 0
            self.last_minute_start = time.time()
            logger.info("Reset licznika requestów")
            self._save_cache()
        
        if self.request_count >= self.max_requests_per_minute:
            elapsed = time.time() - self.last_minute_start
            if elapsed < 60:
                wait_time = 60 - elapsed + 2
                logger.warning(f"LIMIT! Czekam {wait_time:.0f}s...")
                time.sleep(wait_time)
                self.request_count = 0
                self.last_minute_start = time.time()

    def ask_llm(self, prompt: str) -> str:
        """Wysyła zapytanie do Gemini"""
        self.check_rate_limit()
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.1,
                    'max_output_tokens': 500,
                }
            )
            
            self.request_count += 1
            
            return response.text.strip()
                
        except Exception as e:
            logger.error(f"Błąd Gemini: {e}")
            return ""

    def is_crime_related(self, title: str, teaser: str = "", content: str = "") -> bool:
        """
        PROMPT 1: Filtruje tytuły - czy to przestępstwo?
        + Cache
        """
        text = " ".join([title, teaser, content[:200]]).strip()
        
        # Sprawdź cache
        cache_key = str(hash(text[:100]))
        if cache_key in self.filter_cache:
            logger.debug(f"Cache hit: {title[:40]}...")
            return self.filter_cache[cache_key]
        
        prompt = f"""Jesteś systemem filtrującym wiadomości dla mapy zagrożeń miasta Kraków.
Twoim zadaniem jest określić czy artykuł dotyczy bezpieczeństwa publicznego.

Tytuł/Fragment: "{text}"

Czy ten artykuł dotyczy któregoś z poniższych?
- Wypadki drogowe, kolizje
- Pożary, zagrożenia pożarowe
- Przestępstwa: kradzieże, napady, włamania
- Pobicia, bójki, ataki
- Zabójstwa, ciężkie obrażenia
- Interwencje policji/straży
- Zagrożenia publiczne

ODPOWIEDŹ TYLKO: TAK lub NIE (bez dodatkowych słów)"""

        response = self.ask_llm(prompt)
        is_crime = "TAK" in response.upper()
        
        # Zapisz do cache
        self.filter_cache[cache_key] = is_crime
        
        logger.info(f"[FILTR] {title[:50]}... → {response}")
        return is_crime

    def extract_event_info(self, title: str, teaser: str = "", content: str = "") -> dict:
        """
        PROMPT 2: Wyciąga szczegóły z TREŚCI artykułu
        + Cache
        """
        text = " ".join([title, teaser, content[:1500]]).strip()
        
        # Sprawdź cache
        cache_key = str(hash(text[:200]))
        if cache_key in self.extract_cache:
            logger.debug(f"Cache hit extraction: {title[:40]}...")
            return self.extract_cache[cache_key]
        
        prompt = f"""Jesteś ekspertem analizującym zdarzenia w Krakowie dla systemu mapy zagrożeń.

=== ARTYKUŁ ===
{text}
=== KONIEC ===

Wyciągnij informacje i zwróć TYLKO poprawny JSON (bez markdown, bez dodatkowego tekstu):

{{
    "crime_type": "[wybierz JEDNO: wypadek/pożar/kradzież/napad/zabójstwo/pobicie/oszustwo/interwencja/inne]",
    "location_name": "[DOKŁADNA nazwa ulicy/dzielnicy/miejsca. Zachowaj polskie znaki. Jeśli brak: 'Kraków']",
    "severity": [liczba 1-10, gdzie: 1-3=drobne, 4-6=średnie, 7-9=poważne, 10=śmiertelne],
    "summary": "[krótkie streszczenie w 1-2 zdaniach po polsku]"
}}

WAŻNE:
- Dla location_name: szukaj nazw ulic, dzielnic, miejsc
- Jeśli "ul. Wielickiej" to zwróć "Wielicka"
- Jeśli tylko "w Krakowie" to zwróć "Kraków"
- Zachowaj polskie znaki: ą, ę, ć, ł, ń, ó, ś, ź, ż"""

        response = self.ask_llm(prompt)
        
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
            full_address = f"{location_name}, Kraków, Polska"
            logger.info(f"Geokodowanie: {full_address}")
            
            location = self.geolocator.geocode(full_address, language="pl")
            
            if location:
                coords = (location.latitude, location.longitude)
                logger.info(f"({coords[0]:.4f}, {coords[1]:.4f})")
                self.geocode_cache[location_name] = coords
                return coords
            
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
            logger.error(f"Błąd: {e}")
            return None, None

    def __del__(self):
        """Zapisz cache przy zamknięciu"""
        self._save_cache()