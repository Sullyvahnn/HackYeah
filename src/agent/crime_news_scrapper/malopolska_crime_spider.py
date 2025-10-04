import scrapy
import os
import json
import logging
from datetime import date, datetime, timedelta
from urllib.parse import urlparse, urljoin

from agent.crime_news_scrapper.ai_filter_ollama import CrimeFilterLocal
from agent.db import initialize_db_manager

logger = logging.getLogger(__name__)


class MalopolskaCrimeSpider(scrapy.Spider):
    """Spider analizujący wiadomości z CAŁEJ Małopolski - używa Ollama AI"""
    name = 'malopolska_crime'

    # WSZYSTKIE miasta Małopolski + ogólne źródła
    start_urls = [
        # === KRAKÓW ===
        'https://tvn24.pl/krakow',
        'https://krakow.naszemiasto.pl/',
        'https://www.fakt.pl/wydarzenia/polska/krakow',
        
        # === TARNÓW ===
        'https://tarnow.naszemiasto.pl/',
        'https://www.fakt.pl/wydarzenia/polska/tarnow',
        
        # === NOWY SĄCZ ===
        'https://nowysacz.naszemiasto.pl/',
        
        # === OŚWIĘCIM ===
        'https://oswiecim.naszemiasto.pl/',
        
        # === CHRZANÓW ===
        'https://chrzanow.naszemiasto.pl/',
        
        # === WIELICZKA ===
        'https://wieliczka.naszemiasto.pl/',
        
        # === ZAKOPANE ===
        'https://zakopane.naszemiasto.pl/',
        
        # === POLICJA - wszystkie tagi przestępstw ===
        'https://malopolska.policja.gov.pl/krk/tagi/1220,zabojstwo.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1221,wypadek.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1222,pozar.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1223,kradziez.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1224,napad.html',
        'https://malopolska.policja.gov.pl/krk/aktualnosci',
        
        # === OGÓLNE (filtrowane przez AI) ===
        'https://tvn24.pl/najnowsze',
        'https://www.fakt.pl/wydarzenia/polska/malopolska',
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS': 2,
        'COOKIES_ENABLED': False,
        'LOG_LEVEL': 'INFO',
        'CLOSESPIDER_PAGECOUNT': 100,
        'CLOSESPIDER_ITEMCOUNT': 150,
        'RETRY_TIMES': 2,
        'DOWNLOAD_TIMEOUT': 30,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.location = "malopolska"
        self.output_dir = f"data/{self.location}"
        os.makedirs(self.output_dir, exist_ok=True)

        self.output_file = os.path.join(self.output_dir, f"events_{date.today()}.jsonl")
        self.logger.info(f"Zapis do: {self.output_file}")
        
        # GWARANCJA UTWORZENIA PLIKU JSONL
        if not os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    pass
                self.logger.info(f"Utworzono pusty plik: {self.output_file}")
            except Exception as e:
                self.logger.error(f"Nie udało się utworzyć pliku JSONL: {e}")


        # Model AI (Ollama - lokalny!)
        self.ai_filter = CrimeFilterLocal()
        self.db = initialize_db_manager("data/crime_data.db")

        self.processed_urls = self._load_processed_urls()
        self.logger.info(f"Wczytano {len(self.processed_urls)} przetworzonych URL (ostatnie 7 dni)")

        self.stats = {
            "visited_pages": 0,
            "articles_checked": 0,
            "passed_ai_filter": 0,
            "saved_to_db": 0,
            "duplicates_skipped": 0,
            "errors": 0,
        }
        
        self.scrape_start = datetime.now()

    def _load_processed_urls(self):
        """Wczytuje TYLKO URL z ostatnich 7 dni (nie przetwarza starych)"""
        processed = set()
        conn = self.db.get_connection()
        
        try:
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            
            for row in conn.execute(
                "SELECT url FROM raw_articles WHERE scraped_at > ?",
                (week_ago,)
            ):
                processed.add(row[0])
                
        except Exception as e:
            logger.warning(f"Błąd ładowania cache: {e}")
        
        return processed

    def parse(self, response):
        """KROK 1: Zbiera linki i filtruje TYTUŁY przez AI"""
        self.stats["visited_pages"] += 1
        domain = urlparse(response.url).netloc
        self.logger.info(f"[PAGE {self.stats['visited_pages']}] {response.url}")

        allowed_domains = ['tvn24.pl', 'naszemiasto.pl', 'gazetakrakowska.pl', 
                           'fakt.pl', 'policja.gov.pl']

        # POPRAWIONE: Prostsze pobieranie linków (bez XPath)
        for link in response.css("a"):
            href = link.css("::attr(href)").get()
            text = link.css("::text").get()
            
            if not href or not text:
                continue
            
            full_url = urljoin(response.url, href)
            title = text.strip()
            
            # Skip niepotrzebne
            if any(x in full_url for x in ["#", "mailto:", "javascript"]):
                continue
            
            # Skip spoza dozwolonych domen
            if not any(d in full_url for d in allowed_domains):
                continue
            
            # Skip duplikatów
            if full_url in self.processed_urls:
                self.stats["duplicates_skipped"] += 1
                continue
            
            # Skip za krótkich tytułów
            if len(title) < 10:
                continue

            self.stats["articles_checked"] += 1
            
            # FILTR TYTUŁU przez AI (z cache!)
            if self.ai_filter.is_crime_related(title):
                self.stats["passed_ai_filter"] += 1
                self.logger.info(f"Przeszło: {title[:60]}...")
                
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_article,
                    meta={"title": title, "source": domain, "url": full_url},
                    dont_filter=True,
                )

        # Paginacja: Zawsze szukaj następnej strony.
        # USUNIĘTO WARUNEK if self.stats["passed_ai_filter"] > 0
        next_page = response.css('a[rel="next"]::attr(href), a.pagination__next::attr(href)').get()
        if next_page:
            self.logger.info(f"Przechodzę do następnej strony: {next_page}")
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        """KROK 2: Wchodzi w artykuł i AI wyciąga szczegóły"""
        title = response.meta["title"]
        url = response.meta["url"]
        source = response.meta["source"]

        if url in self.processed_urls:
            return

        # Pobierz treść
        paragraphs = response.css("article p::text, div p::text, main p::text").getall()
        text = "\n".join(p.strip() for p in paragraphs if len(p.strip()) > 20)

        if len(text) < 50:
            self.logger.debug(f"Pomijam pusty: {url}")
            return

        # ANALIZA przez AI (z cache!)
        info = self.ai_filter.extract_event_info(title, "", text)
        
        crime_type = info["crime_type"]
        location_name = info["location_name"]
        lat = info["latitude"]
        lon = info["longitude"]
        severity = info["severity"]
        summary = info["short_summary"]

        if lat is None or lon is None:
            self.logger.warning(f"❌ Brak współrzędnych dla {location_name}, pomijam") 
            return

        # Zapis do bazy
        try:
            self.db.save_raw_article(url, title, text, source)
            raw_id = self.db.get_connection().execute(
                "SELECT id FROM raw_articles WHERE url=?", (url,)
            ).fetchone()[0]

            self.db.update_processed_article(
                raw_article_id=raw_id,
                crime_type=crime_type,
                location=location_name,
                summary=summary,
                keywords=crime_type,
                latitude=lat,
                longitude=lon,
            )

            self.processed_urls.add(url)
            self.stats["saved_to_db"] += 1

        except Exception as e:
            self.logger.error(f"❌ Błąd zapisu: {e}")
            return

        # Zapis do JSONL
        event_record = {
            "title": title,
            "url": url,
            "source": source,
            "crime_type": crime_type,
            "location": location_name,
            "latitude": lat,
            "longitude": lon,
            "severity": severity,
            "summary": summary,
            "date": str(date.today()),
        }

        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_record, ensure_ascii=False) + "\n")

        self.logger.info(
            f"[{self.stats['saved_to_db']}] {crime_type} | "
            f"{location_name} ({lat:.4f}, {lon:.4f}) | "
            f"waga: {severity}/10"
        )

    def closed(self, reason):
        """Podsumowanie i WYMUSZONY ZAPIS CACHE"""
        self.logger.info("=" * 60)
        
        # ZAPIS CACHE
        try:
            self.ai_filter._save_cache() 
            self.logger.info("Cache Ollama zapisany przed zamknięciem.")
        except Exception as e:
            self.logger.error(f"Błąd zapisu cache: {e}")
        
        self.logger.info("Zakończono scrapowanie Krakowa")
        self.logger.info("-" * 60)
        for k, v in self.stats.items():
            self.logger.info(f"  {k}: {v}")
        
        if self.stats["articles_checked"] > 0:
            efficiency = 100 * self.stats["saved_to_db"] / self.stats["articles_checked"]
            self.logger.info(f"  Efektywność: {efficiency:.1f}%")
        
        self.logger.info("=" * 60)