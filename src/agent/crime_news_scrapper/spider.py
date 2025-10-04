import scrapy
import sys
import os
import time
from urllib.parse import urlparse  # <-- potrzebny do rozpoznania domeny

# Dodaj ścieżkę, żeby import CrimeFilter działał
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent.crime_news_scrapper.ai_filter import CrimeFilter


class CrimeNewsSpider(scrapy.Spider):
    """Spider do scrapowania artykułów o przestępstwach"""
    name = 'crime_news'

    start_urls = [
        'https://tvn24.pl/krakow',
        'https://www.fakt.pl/wydarzenia/polska/krakow',
        'https://krakow.naszemiasto.pl/',
        'https://tvn24.pl/tagi/Krak%C3%B3w',
        'https://malopolska.policja.gov.pl/krk/tagi/1220,zabojstwo.html',
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ROBOTSTXT_OBEY': False,  # ❗️ważne – TVN24/Fakt blokują boty
        'CONCURRENT_REQUESTS': 4,
        'DOWNLOAD_DELAY': 1.5,
        'COOKIES_ENABLED': False,
        'LOG_LEVEL': 'INFO'
    }

    def __init__(self, debug=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_mode = debug

        init_start_time = time.time()
        self.logger.info("Inicjalizuję AI Filter...")
        self.ai_filter = CrimeFilter()
        init_elapsed = time.time() - init_start_time
        self.logger.info(f"AI Filter zainicjalizowany w: {init_elapsed:.2f}s")

        self.scraped_count = 0
        self.filtered_count = 0
        self.passed_count = 0
        self.urls_found = 0

    def parse(self, response):
        """Główna metoda parsowania — selektory dla różnych domen"""
        domain = urlparse(response.url).netloc
        self.logger.info(f"Scrapuję: {response.url}")

        # Zapisz stronę do debugowania
        if self.debug_mode:
            filename = f"debug_page_{domain.replace('.', '_')}.html"
            with open(filename, 'wb') as f:
                f.write(response.body)
            self.logger.info(f"Zapisano HTML do: {filename}")

        articles = []
        titles = []

                # === NaszeMiasto.pl ===
        if "naszemiasto.pl" in domain:
            # sekcja newsów lokalnych ma 'div.teaser' i 'a.title'
            articles = response.css('div.teaser a::attr(href), a.teaser-title::attr(href)').getall()
            titles = response.css('div.teaser h2::text, a.teaser-title::text').getall()

        # === Fakt.pl ===
        elif "fakt.pl" in domain:
            # na Fakt.pl artykuły są w <a data-testid="ContentTeaser-link">
            articles = response.css('a[data-testid="ContentTeaser-link"]::attr(href)').getall()
            titles = response.css('a[data-testid="ContentTeaser-link"] h2::text, h2::text').getall()

        # === TVN24.pl ===
        elif "tvn24.pl" in domain:
            # nowy układ: <a class="tiles__wrap"> i <a class="styles__link">
            articles = response.css('a.tiles__wrap::attr(href), a.styles__link::attr(href)').getall()
            titles = response.css('h2.styles__title::text, h2::text, a.styles__link::text').getall()

        # === Policja Małopolska ===
        elif "policja.gov.pl" in domain:
            # aktualny układ: <div class="news"> -> <a>
            articles = response.css('div.news a::attr(href), article a::attr(href)').getall()
            titles = response.css('div.news h3::text, article h2::text').getall()
            articles = [response.urljoin(link) for link in articles]

        # === fallback ===
        else:
            articles = response.css('a::attr(href)').getall()
            titles = response.css('a::text').getall()

        self.logger.info(f"Znaleziono {len(articles)} potencjalnych linków")

        # Jeśli nie ma wyników – fallback
        if not articles:
            self.logger.warning("Nie znaleziono artykułów — używam fallback.")
            articles = response.css('a::attr(href)').getall()
            titles = response.css('a::text').getall()

        for i, link in enumerate(articles[:100]):
            if not link or any(x in link for x in ['#', 'mailto:', 'javascript']):
                continue

            full_url = response.urljoin(link)
            title = titles[i].strip() if i < len(titles) else ""

            # prosty filtr po słowach kluczowych
            if not any(x in link for x in ['krakow', 'zabojstwo', 'przestepstwo', 'wiadomosci', 'policja']):
                continue

            self.process_article(response, full_url, title, None)

        next_page = response.css('a[rel="next"]::attr(href), a.pagination__next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

        if self.scraped_count == 0:
            self.logger.warning("Nie znaleziono żadnych artykułów na tej stronie.")

    def process_article(self, response, link, title, teaser):
        full_url = response.urljoin(link)
        source = response.url.split('/')[2]

        title = (title or "").strip()
        teaser = (teaser or "").strip()

        self.urls_found += 1
        self.scraped_count += 1

        if self.debug_mode or self.scraped_count <= 5:
            self.logger.info(f"[{self.scraped_count}] {title[:60]} — {full_url}")

        # Tymczasowo przepuszczamy wszystkie (można przywrócić filtr AI później)
        if True or self.ai_filter.is_crime_related(title, teaser):
            self.passed_count += 1
            yield scrapy.Request(
                full_url,
                callback=self.parse_full_article,
                meta={'title': title, 'source': source, 'url': full_url},
                dont_filter=False
            )
        else:
            self.filtered_count += 1

    def parse_full_article(self, response):
        """Pobiera treść artykułu"""
        title = response.meta['title']
        source = response.meta['source']
        url = response.meta['url']

        paragraphs = response.css(
            'article p::text, div.article__body p::text, div.text-content p::text, main p::text, section p::text'
        ).getall()

        raw_text = '\n'.join(p.strip() for p in paragraphs if len(p.strip()) > 20)

        if not raw_text:
            self.logger.warning(f"Nie znaleziono treści: {url}")

        if raw_text and len(raw_text) > 100:
            yield {
                'url': url,
                'title': title,
                'raw_text': raw_text,
                'source': source
            }

    def closed(self, reason):
        self.logger.info("=" * 70)
        self.logger.info("PODSUMOWANIE SCRAPOWANIA")
        self.logger.info("=" * 70)
        self.logger.info(f"Znalezione linki: {self.urls_found}")
        self.logger.info(f"Przeanalizowane artykuły: {self.scraped_count}")
        self.logger.info(f"Przeszło filtr AI: {self.passed_count}")
        self.logger.info(f"Odrzucone: {self.filtered_count}")
        if self.scraped_count > 0:
            ratio = (self.passed_count / self.scraped_count) * 100
            self.logger.info(f"Wskaźnik akceptacji: {ratio:.1f}%")
        else:
            self.logger.warning("BRAK ARTYKUŁÓW — sprawdź selektory CSS!")
        self.logger.info("=" * 70)
