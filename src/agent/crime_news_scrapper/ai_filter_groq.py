import logging
import json
import os
import time  # ✅ DODANE
from groq import Groq
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CrimeFilterLocal:
    """
    Używa Groq API (Llama 3.3) - DARMOWE 30 req/min
    Rejestracja: https://console.groq.com
    """
    
    def __init__(self):
        logger.info("=== Inicjalizuję Groq API (Llama 3.3) ===")
        
        # Groq API - DARMOWE!
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "Brak GROQ_API_KEY! Ustaw: export GROQ_API_KEY='gsk_...'\n"
                "Zdobądź klucz: https://console.groq.com"
            )
        
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"  # Najlepszy darmowy model
        
        logger.info(f"✅ Model: {self.model}")
        logger.info("✅ Limit: 30 requestów/minutę (DARMOWE)")
        
        # ✅ DODANE: Throttling
        self.request_count = 0
        self.last_minute_start = time.time()
        self.max_requests_per_minute = 25  # Bezpieczny margines (30-5)
        
        # Geokoder
        self.geolocator = Nominatim(user_agent="krakow_crime_groq", timeout=10)

    def check_rate_limit(self):
        """✅ NOWA FUNKCJA: Sprawdza i egzekwuje limit"""
        # Reset licznika co minutę
        if time.time() - self.last_minute_start > 60:
            self.request_count = 0
            self.last_minute_start = time.time()
            logger.info("🔄 Reset licznika requestów")
        
        # Jeśli osiągnięto limit - czekaj
        if self.request_count >= self.max_requests_per_minute:
            elapsed = time.time() - self.last_minute_start
            if elapsed < 60:
                wait_time = 60 - elapsed + 2  # +2s bufora
                logger.warning(f"⏳ LIMIT! Osiągnięto {self.request_count} req. Czekam {wait_time:.0f}s...")
                time.sleep(wait_time)
                self.request_count = 0
                self.last_minute_start = time.time()

    def ask_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Wysyła zapytanie do Groq"""
        # ✅ DODANE: Sprawdź limit PRZED requestem
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
            
            # ✅ DODANE: Zwiększ licznik PO sukcesie
            self.request_count += 1
            
            return response.choices[0].message.content.strip()
                
        except Exception as e:
            logger.error(f"❌ Błąd Groq: {e}")
            return ""

    def is_crime_related(self, title: str, teaser: str = "", content: str = "") -> bool:
        """
        ✅ PROMPT 1: Filtruje tytuły - czy to przestępstwo?
        """
        text = " ".join([title, teaser, content[:200]]).strip()
        
        system = """Jesteś systemem filtrującym wiadomości dla mapy zagrożeń miasta Kraków.
Twoim zadaniem jest określić czy artykuł dotyczy bezpieczeństwa publicznego.

ODPOWIADAJ TYLKO: TAK lub NIE (bez dodatkowych słów)"""
        
        user = f"""Tytuł/Fragment artykułu: "{text}"

Czy ten artykuł dotyczy któregoś z poniższych?
- Wypadki drogowe, kolizje
- Pożary, zagrożenia pożarowe
- Przestępstwa: kradzieże, napady, włamania
- Pobicia, bójki, ataki
- Zabójstwa, ciężkie obrażenia
- Interwencje policji/straży
- Zagrożenia publiczne

Odpowiedź (TAK/NIE):"""

        response = self.ask_llm(system, user)
        
        is_crime = "TAK" in response.upper()
        logger.info(f"[FILTR] {title[:50]}... → {response}")
        
        return is_crime

    def extract_event_info(self, title: str, teaser: str = "", content: str = "") -> dict:
        """
        ✅ PROMPT 2: Wyciąga szczegóły z TREŚCI artykułu
        """
        text = " ".join([title, teaser, content[:1500]]).strip()
        
        system = """Jesteś ekspertem analizującym zdarzenia w Krakowie dla systemu mapy zagrożeń.
Twoje zadanie: przeanalizować treść artykułu i wyciągnąć kluczowe informacje.

ZWRACASZ TYLKO POPRAWNY JSON, bez żadnego dodatkowego tekstu."""
        
        user = f"""Przeanalizuj dokładnie treść tego artykułu:

=== ARTYKUŁ ===
{text}
=== KONIEC ===

Wyciągnij informacje i zwróć w formacie JSON:

{{
    "crime_type": "[wybierz JEDNO: wypadek/pożar/kradzież/napad/zabójstwo/pobicie/oszustwo/interwencja/inne]",
    "location_name": "[DOKŁADNA nazwa ulicy/dzielnicy/miejsca wymieniona w artykule. Zachowaj polskie znaki. Jeśli brak konkretnego miejsca: 'Kraków']",
    "severity": [liczba 1-10, gdzie: 1-3=drobne, 4-6=średnie, 7-9=poważne, 10=śmiertelne],
    "summary": "[krótkie streszczenie w 1-2 zdaniach po polsku]"
}}

WAŻNE:
- Dla location_name: szukaj w tekście nazw ulic (np. "Wielicka", "Mogilska"), dzielnic (np. "Nowa Huta"), miejsc (np. "Rynek Główny")
- Jeśli artykuł wspomina "ul. Wielickiej" to zwróć "Wielicka"
- Jeśli tylko "w Krakowie" bez konkretnego miejsca, zwróć "Kraków"
- Zachowaj polskie znaki: ą, ę, ć, ł, ń, ó, ś, ź, ż

Zwróć TYLKO JSON:"""

        response = self.ask_llm(system, user)
        
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
            logger.info(f"✅ LLM: {info['crime_type']} @ {info['location_name']} (waga: {info.get('severity', '?')})")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Błąd JSON: {e}")
            logger.debug(f"Odpowiedź: {response}")
            
            # Fallback
            info = {
                "crime_type": "inne",
                "location_name": "Kraków",
                "severity": 5,
                "summary": text[:200]
            }
        
        # ✅ Geokodowanie
        location_name = info.get("location_name", "Kraków")
        
        # Oczyszczanie: usuń "ul.", "ulica", "w ", "na "
        location_clean = (location_name
                         .replace("ulica ", "")
                         .replace("ul. ", "")
                         .replace("w ", "")
                         .replace("na ", "")
                         .strip())
        
        lat, lon = self.geocode_location(location_clean)
        
        if lat is None or lon is None:
            logger.warning("⚠️ Domyślne współrzędne (centrum)")
            lat, lon = 50.0614, 19.9366
        
        return {
            "crime_type": info.get("crime_type", "inne"),
            "location_name": location_name,
            "latitude": lat,
            "longitude": lon,
            "severity": info.get("severity", 5),
            "short_summary": info.get("summary", text[:200])
        }

    def geocode_location(self, location_name: str) -> tuple:
        """Zamienia nazwę na współrzędne"""
        if not location_name or location_name == "Kraków":
            return 50.0614, 19.9366
        
        try:
            full_address = f"{location_name}, Kraków, Polska"
            logger.info(f"🔍 Geokodowanie: {full_address}")
            
            location = self.geolocator.geocode(full_address, language="pl")
            
            if location:
                logger.info(f"✅ ({location.latitude:.4f}, {location.longitude:.4f})")
                return location.latitude, location.longitude
            
            location = self.geolocator.geocode(f"{location_name}, Polska", language="pl")
            if location:
                return location.latitude, location.longitude
            
            logger.warning(f"❌ Nie znaleziono: {location_name}")
            return None, None
            
        except GeocoderTimedOut:
            logger.error("⏱️ Timeout")
            return None, None
        except Exception as e:
            logger.error(f"❌ Błąd: {e}")
            return None, None