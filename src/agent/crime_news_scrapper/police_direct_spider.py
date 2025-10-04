import scrapy
import os
import json
from datetime import date
from urllib.parse import urlparse, urljoin

from agent.crime_news_scrapper.ai_filter_local import CrimeFilterLocal
from agent.db import initialize_db_manager


class PoliceDirectSpider(scrapy.Spider):
    """
    Spider dla stron policji - POMIJA filtrowanie tytułów
    Wszystkie artykuły z policja.gov.pl są o przestępstwach!
    """
    name = 'police_direct'

    # Tylko strony policji - wszystko tu jest crime-related
    start_urls = [
        'https://malopolska.policja.gov.pl/krk/',
        'https://malopolska.policja.gov.pl/krk/tagi/1220,zabojstwo.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1221,wypadek.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1222,pozar.html',
        'https://malopolska.policja.gov.pl/krk/tagi/1223,kradziez.html',
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS': 1,
        'COOKIES_ENABLED': False,
        'LOG_LEVEL': 'INFO',
        'CLOSESPIDER_PAGECOUNT': 20,
        'CLOSESPIDER_ITEMCOUNT': 30,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.location = "krakow"
        self.output_dir = f"data/{self.location}"
        os.makedirs(self.output_dir, exist_ok=True)

        self.output_file = os.path.join(self.output_dir, f"police_events_{date.today()}.jsonl")
        self.logger.info(f"Zapis do: {self.output_file}")

        # AI tylko do ekstrakcji (nie do filtrowania!)
        self.ai_filter = CrimeFilterLocal()
        self.db = initialize_db_manager("data/crime_data.db")

        # Cache
        self.processed_urls = set()
        conn = self.db.get_connection()
        try:
            for row in conn.execute("SELECT url FROM raw_articles"):
                self.processed_urls.add(row[0])
        except:
            pass

        self.stats = {
            "visited_pages": 0,
            "articles_found": 0,
            "saved_to_db": 0,
            "duplicates_skipped": 0,
        }

    def parse(self, response):
        """
        Zbiera linki BEZ FILTROWANIA przez AI
        (strona policji = wszystko crime-related)
        """
        self.stats["visited_pages"] += 1
        self.logger.info(f"[PAGE {self.stats['visited_pages']}] {response.url}")

        # Znajdź wszystkie linki do artykułów
        # Policja używa: /krk/aktualnosci/123456,tytul.html
        article_links = response.css("a[href*='/krk/aktualnosci/']::attr(href)").getall()
        
        for href in article_links:
            if not href:
                continue

            full_url = urljoin(response.url, href)
            
            # Skip duplikatów
            if full_url in self.processed_urls:
                self.stats["duplicates_skipped"] += 1
                continue

            self.stats["articles_found"] += 1
            
            # Wyciągnij tytuł z URL (opcjonalne)
            title = href.split(',')[-1].replace('.html', '').replace('-', ' ')
            
            self.logger.info(f"Znaleziono artykuł: {title[:60]}...")
            
            # BEZPOŚREDNIO do ekstrakcji (bez filtrowania!)
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={"title": title, "source": "policja.gov.pl", "url": full_url},
                dont_filter=True,
            )

        # Paginacja
        next_page = response.css('a.pagination__next::attr(href), a[rel="next"]::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        """
        Ekstrakcja szczegółów przez AI (bez wstępnego filtrowania)
        """
        title = response.meta["title"]
        url = response.meta["url"]
        source = response.meta["source"]

        # Skip duplikatów
        if url in self.processed_urls:
            return

        # Pobierz treść
        paragraphs = response.css("article p::text, div.news-content p::text, main p::text").getall()
        text = "\n".join(p.strip() for p in paragraphs if len(p.strip()) > 20)

        if len(text) < 50:
            self.logger.warning(f"Pomijam pusty artykuł: {url}")
            return

        # Ekstrakcja przez AI
        info = self.ai_filter.extract_event_info(title, "", text)
        
        crime_type = info["crime_type"]
        location_name = info["location_name"]
        lat = info["latitude"]
        lon = info["longitude"]
        severity = info["severity"]
        summary = info["short_summary"]

        if lat is None or lon is None:
            self.logger.warning(f"Brak współrzędnych dla {location_name}, używam centrum")
            lat, lon = 50.0614, 19.9366  # Centrum Krakowa

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
            self.logger.error(f"Błąd zapisu: {e}")
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
        self.logger.info("Zakończono scraping policji")
        self.logger.info("-" * 60)
        for k, v in self.stats.items():
            self.logger.info(f"  {k}: {v}")
        
        if self.stats["articles_found"] > 0:
            efficiency = 100 * self.stats["saved_to_db"] / self.stats["articles_found"]
            self.logger.info(f"  Efektywność: {efficiency:.1f}%")
        
        self.logger.info("=" * 60)