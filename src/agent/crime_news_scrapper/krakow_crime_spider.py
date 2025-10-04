import scrapy
import os
import json
import logging
from datetime import date
from urllib.parse import urlparse, urljoin

from agent.crime_news_scrapper.ai_filter_local import CrimeFilterLocal
from agent.db import initialize_db_manager

logger = logging.getLogger(__name__)


class KrakowCrimeSpider(scrapy.Spider):
    """Spider analizujący wiadomości z Krakowa - używa Groq AI"""
    name = 'krakow_crime'

    start_urls = [
        # Strony główne - będą filtrowane przez AI
        'https://tvn24.pl/krakow',
        'https://krakow.naszemiasto.pl/',
        'https://www.fakt.pl/wydarzenia/polska/krakow',
        
        # Tagi policyjne - od razu trafne artykuły
        'https://malopolska.policja.gov.pl/krk/tagi/1220,zabojstwo.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1221,wypadek.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1222,pozar.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1223,kradziez.html',
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 3.0,  
        'CONCURRENT_REQUESTS': 1,  
        'COOKIES_ENABLED': False,
        'LOG_LEVEL': 'INFO',
        'CLOSESPIDER_PAGECOUNT': 10,  # Max 10 stron
        'CLOSESPIDER_ITEMCOUNT': 5,  # Max 5 artykułów (będzie nadpisane przez batch script)
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.location = "krakow"
        self.output_dir = f"data/{self.location}"
        os.makedirs(self.output_dir, exist_ok=True)

        self.output_file = os.path.join(self.output_dir, f"events_{date.today()}.jsonl")
        self.logger.info(f"Zapis do: {self.output_file}")

        # Model AI (Groq)
        self.ai_filter = CrimeFilterLocal()
        self.db = initialize_db_manager("data/crime_data.db")

        # Cache przetworzonych URL
        self.processed_urls = set()
        conn = self.db.get_connection()
        try:
            for row in conn.execute("SELECT url FROM raw_articles"):
                self.processed_urls.add(row[0])
        except:
            pass

        # Statystyki
        self.stats = {
            "visited_pages": 0,
            "articles_checked": 0,
            "passed_ai_filter": 0,
            "saved_to_db": 0,
            "duplicates_skipped": 0,
        }

    def parse(self, response):
        """
        KROK 1: Zbiera linki i filtruje TYTUŁY przez AI
        AI odpowiada: TAK/NIE
        """
        self.stats["visited_pages"] += 1
        domain = urlparse(response.url).netloc
        self.logger.info(f"[PAGE {self.stats['visited_pages']}] {response.url}")

        # DODANE: Filtruj tylko dozwolone domeny
        allowed_domains = ['tvn24.pl', 'naszemiasto.pl', 'gazetakrakowska.pl', 
                          'fakt.pl', 'policja.gov.pl']

        anchors = response.css("a::attr(href)").getall()
        texts = response.css("a::text").getall()

        for i, href in enumerate(anchors):
            if not href or any(x in href for x in ["#", "mailto:", "javascript"]):
                continue

            full_url = urljoin(response.url, href)
            
            # DODANE: Pomiń linki spoza dozwolonych domen
            if not any(d in full_url for d in allowed_domains):
                continue
            
            # Skip jeśli już przetworzony
            if full_url in self.processed_urls:
                self.stats["duplicates_skipped"] += 1
                continue

            title = texts[i].strip() if i < len(texts) else ""
            if len(title) < 10:
                continue

            self.stats["articles_checked"] += 1
            
            # FILTR TYTUŁU przez AI
            # Prompt: "Czy to przestępstwo?" → TAK/NIE
            if self.ai_filter.is_crime_related(title):
                self.stats["passed_ai_filter"] += 1
                self.logger.info(f"Przeszło filtr: {title[:60]}...")
                
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_article,
                    meta={"title": title, "source": domain, "url": full_url},
                    dont_filter=True,
                )

        # Paginacja
        next_page = response.css('a[rel="next"]::attr(href), a.pagination__next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        """
        KROK 2: Wchodzi w artykuł i AI wyciąga szczegóły z TREŚCI
        AI zwraca JSON: {crime_type, location, severity, summary}
        """
        title = response.meta["title"]
        url = response.meta["url"]
        source = response.meta["source"]

        # Skip duplikatów
        if url in self.processed_urls:
            return

        # Pobierz treść artykułu
        paragraphs = response.css("article p::text, div p::text, main p::text").getall()
        text = "\n".join(p.strip() for p in paragraphs if len(p.strip()) > 20)

        if len(text) < 50:
            self.logger.debug(f"Pomijam pusty artykuł: {url}")
            return

        # ANALIZA TREŚCI przez AI
        # Prompt: "Wyciągnij: typ, lokalizację, wagę" → JSON
        info = self.ai_filter.extract_event_info(title, "", text)
        
        # Pobierz dane z odpowiedzi AI
        crime_type = info["crime_type"]
        location_name = info["location_name"]
        lat = info["latitude"]
        lon = info["longitude"]
        severity = info["severity"]
        summary = info["short_summary"]

        # Sprawdź czy są współrzędne
        if lat is None or lon is None:
            self.logger.warning(f"Brak współrzędnych dla {location_name}, pomijam artykuł")  
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
            self.logger.error(f"❌ Błąd zapisu do bazy: {e}")
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
        """Podsumowanie"""
        self.logger.info("=" * 60)
        self.logger.info("Zakończono scrapowanie Krakowa")
        self.logger.info("-" * 60)
        for k, v in self.stats.items():
            self.logger.info(f"  {k}: {v}")
        
        if self.stats["articles_checked"] > 0:
            efficiency = 100 * self.stats["saved_to_db"] / self.stats["articles_checked"]
            self.logger.info(f"  Efektywność: {efficiency:.1f}%")
        
        self.logger.info("=" * 60)