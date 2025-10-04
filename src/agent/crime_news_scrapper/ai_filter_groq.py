import logging
import json
import os
import time
from groq import Groq
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CrimeFilterLocal:
    """
    Używa Groq API (Llama 3.3) zoptymalizowany dla Małopolski i z cache.
    """

    def __init__(self):
        logger.info("=== Inicjalizuję Groq API (Llama 3.3) dla MAŁOPOLSKI ===")

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "Brak GROQ_API_KEY! Ustaw: export GROQ_API_KEY='gsk_...'\n"
                "Zdobądź klucz: https://console.groq.com"
            )

        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

        logger.info(f"Model: {self.model}")
        logger.info("Limit: 30 requestów/minutę (DARMOWE)")

        self.request_count = 0
        self.last_minute_start = time.time()
        self.max_requests_per_minute = 25

        self.geolocator = Nominatim(user_agent="malopolska_crime_groq", timeout=10)

        # NOWOŚĆ: Cache, aby nie przetwarzać ponownie tych samych artykułów
        self.filter_cache = {}
        self.extract_cache = {}
        self.geocode_cache = {}
        self.cache_file = "data/groq_cache.json"
        self._load_cache()
        logger.info(f"Cache: {len(self.filter_cache)} filtrów, {len(self.extract_cache)} ekstrakcji, {len(self.geocode_cache)} lokalizacji")

    def _load_cache(self):
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
        if time.time() - self.last_minute_start > 60:
            self.request_count = 0
            self.last_minute_start = time.time()
        if self.request_count >= self.max_requests_per_minute:
            wait_time = 60 - (time.time() - self.last_minute_start) + 2
            logger.warning(f"LIMIT! Osiągnięto {self.request_count} req. Czekam {wait_time:.0f}s...")
            time.sleep(wait_time)
            self.request_count = 0
            self.last_minute_start = time.time()

    def ask_llm(self, system_prompt: str, user_prompt: str) -> str:
        self.check_rate_limit()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            self.request_count += 1
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Błąd Groq: {e}")
            return ""

    def is_crime_related(self, title: str, teaser: str = "", content: str = "") -> bool:
        cache_key = str(hash(title))
        if cache_key in self.filter_cache:
            logger.info(f"[CACHE-FILTR] {title[:50]}...")
            return self.filter_cache[cache_key]

        text = " ".join([title, teaser, content[:200]]).strip()
        system = """Jesteś systemem filtrującym wiadomości dla mapy zagrożeń regionu Małopolska.
Twoim zadaniem jest określić czy artykuł dotyczy bezpieczeństwa publicznego.
ODPOWIADAJ TYLKO: TAK lub NIE (bez dodatkowych słów)"""
        user = f"""Tytuł/Fragment artykułu: "{text}"
Czy ten artykuł dotyczy któregoś z poniższych na terenie Małopolski?
- Wypadki drogowe, kolizje
- Pożary, zagrożenia pożarowe
- Przestępstwa: kradzieże, napady, włamania, oszustwa
- Pobicia, bójki, ataki
- Zabójstwa, ciężkie obrażenia
- Interwencje policji/straży
- Zagrożenia publiczne
Odpowiedź (TAK/NIE):"""
        response = self.ask_llm(system, user)
        is_crime = "TAK" in response.upper()
        logger.info(f"[FILTR] {title[:50]}... → {response}")
        self.filter_cache[cache_key] = is_crime
        if len(self.filter_cache) % 5 == 0: self._save_cache()
        return is_crime

    def extract_event_info(self, title: str, teaser: str = "", content: str = "") -> dict:
        text_full = " ".join([title, teaser, content[:1500]]).strip()
        cache_key = str(hash(text_full))
        if cache_key in self.extract_cache:
            logger.info(f"[CACHE-EKSTRAKCJA] {title[:50]}...")
            return self.extract_cache[cache_key]

        system = """Jesteś ekspertem analizującym zdarzenia w Małopolsce dla systemu mapy zagrożeń.
Twoje zadanie: przeanalizować treść artykułu i wyciągnąć kluczowe informacje.
ZWRACASZ TYLKO POPRAWNY JSON, bez żadnego dodatkowego tekstu."""
        user = f"""Przeanalizuj dokładnie treść tego artykułu:
=== ARTYKUŁ ===
{text_full}
=== KONIEC ===
Wyciągnij informacje i zwróć w formacie JSON:
{{
    "crime_type": "[wybierz JEDNO: wypadek/pożar/kradzież/napad/zabójstwo/pobicie/oszustwo/interwencja/inne]",
    "location_name": "[DOKŁADNA nazwa ulicy/miejscowości/miejsca wymieniona w artykule. Np. 'Wieliczka', 'ul. Długa, Kraków', 'Tarnów'. Jeśli brak: 'Małopolska']",
    "severity": [liczba 1-10, gdzie: 1-3=drobne, 4-6=średnie, 7-9=poważne, 10=śmiertelne],
    "summary": "[krótkie streszczenie w 1-2 zdaniach po polsku]"
}}
WAŻNE:
- Dla location_name: szukaj nazw ulic i miejscowości (Tarnów, Nowy Sącz, Zakopane, Wieliczka itp.)
- Jeśli "w Tarnowie na ul. Lwowskiej", zwróć "ul. Lwowska, Tarnów"
- Zachowaj polskie znaki: ą, ę, ć, ł, ń, ó, ś, ź, ż
Zwróć TYLKO JSON:"""
        response = self.ask_llm(system, user)
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            start, end = response.find("{"), response.rfind("}") + 1
            info = json.loads(response[start:end].strip())
            logger.info(f"LLM: {info.get('crime_type')} @ {info.get('location_name')} (waga: {info.get('severity', '?')})")
        except Exception as e:
            logger.error(f"Błąd JSON: {e}, Odpowiedź: {response}")
            info = {"crime_type": "inne", "location_name": "Małopolska", "severity": 5, "summary": text_full[:200]}

        location_name = info.get("location_name", "Małopolska")
        location_clean = location_name.replace("ulica ", "").replace("ul. ", "").replace("w ", "").replace("na ", "").strip()
        lat, lon = self.geocode_location(location_clean)
        
        result = {
            "crime_type": info.get("crime_type", "inne"),
            "location_name": location_name,
            "latitude": lat,
            "longitude": lon,
            "severity": info.get("severity", 5),
            "short_summary": info.get("summary", text_full[:200]),
            "source_title": title # Dodajemy oryginalny tytuł
        }
        self.extract_cache[cache_key] = result
        if len(self.extract_cache) % 5 == 0: self._save_cache()
        return result

    def geocode_location(self, location_name: str) -> tuple:
        if not location_name or location_name == "Małopolska":
            return 50.0614, 19.9366 # Domyślnie Kraków
        
        if location_name in self.geocode_cache:
            logger.info(f"[CACHE-GEO] {location_name}")
            return tuple(self.geocode_cache[location_name])

        try:
            full_address = f"{location_name}, Małopolska, Polska"
            logger.info(f"Geokodowanie: {full_address}")
            location = self.geolocator.geocode(full_address, language="pl")
            if location:
                coords = (location.latitude, location.longitude)
                self.geocode_cache[location_name] = coords
                self._save_cache()
                return coords

            logger.warning(f"Nie znaleziono w Małopolsce, próba ogólna: {location_name}")
            location = self.geolocator.geocode(f"{location_name}, Polska", language="pl")
            if location:
                coords = (location.latitude, location.longitude)
                self.geocode_cache[location_name] = coords
                self._save_cache()
                return coords
            
            logger.error(f"Nie znaleziono nigdzie: {location_name}")
            return 50.0614, 19.9366
        except (GeocoderTimedOut, Exception) as e:
            logger.error(f"Błąd geokodowania: {e}")
            return 50.0614, 19.9366