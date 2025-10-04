import scrapy
import sys
import os
import time

# Dodaj ścieżkę do src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from agent.crime_news_scrapper.ai_filter import CrimeFilter 

class CrimeNewsSpider(scrapy.Spider):
    """Spider do scrapowania artykułów o przestępstwach"""
    name = 'crime_news'
    
    start_urls = [
        'https://tvn24.pl/krakow',
        'https://www.fakt.pl/wydarzenia/polska/krakow',
        'https://krakow.naszemiasto.pl/'
        'https://tvn24.pl/tagi/Krak%C3%B3w',
        'https://malopolska.policja.gov.pl/krk/tagi/1220,zabojstwo.html',

    ]
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 4,
        'DOWNLOAD_DELAY': 2,
        'COOKIES_ENABLED': False,
        'LOG_LEVEL': 'INFO'
    }
    
    def __init__(self, debug=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Tryb debugowania
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
        """Główna metoda parsowania - POPRAWIONE SELEKTORY dla TVN24"""
        self.logger.info(f"Scrapuję: {response.url}")
        
        # DEBUG: Zapisz HTML do pliku jeśli tryb debug
        if self.debug_mode:
            filename = f"debug_page_{response.url.split('/')[-1]}.html"
            with open(filename, 'wb') as f:
                f.write(response.body)
            self.logger.info(f"Zapisano HTML do: {filename}")
        
        # POPRAWIONE SELEKTORY dla TVN24 Kraków
        # TVN24 używa różnych struktur dla artykułów
        
        # Wariant 1: Główne artykuły z obrazkami
        main_articles = response.css('article.article-item')
        self.logger.info(f"Znaleziono {len(main_articles)} głównych artykułów")
        
        for article in main_articles:
            # Link może być w różnych miejscach
            link = article.css('a::attr(href)').get()
            title = article.css('h2.article-item__title::text, h3.article-item__title::text').get()
            teaser = article.css('p.article-item__lead::text, div.article-item__lead::text').get()
            
            if link and title:
                self.process_article(response, link, title, teaser)
        
        # Wariant 2: Lista artykułów (prostsze elementy)
        list_items = response.css('div.news-list__item, li.news-list__item')
        self.logger.info(f"Znaleziono {len(list_items)} artykułów z listy")
        
        for item in list_items:
            link = item.css('a::attr(href)').get()
            title = item.css('a::attr(title)').get() or item.css('a::text').get()
            teaser = item.css('p::text').get()
            
            if link and title:
                self.process_article(response, link, title, teaser)
        
        # Wariant 3: Uniwersalny fallback - wszystkie linki z artykułów
        if self.scraped_count == 0:
            self.logger.warning("Standardowe selektory nie znalazły artykułów, używam fallback")
            
            all_links = response.css('a[href*="/"]::attr(href)').getall()
            all_titles = response.css('a[href*="/"]::attr(title), a[href*="/"]::text').getall()
            
            self.logger.info(f"Znaleziono {len(all_links)} linków łącznie")
            
            for link, title in zip(all_links[:50], all_titles[:50]):  # Ogranicz do 50
                # Filtruj tylko artykuły (zawierają city name lub kategorię)
                if link and title and any(x in link for x in ['krakow', 'wiadomosci', 'artykul']):
                    if len(title.strip()) > 10:  # Tytuł musi mieć >10 znaków
                        self.process_article(response, link, title, None)
        
        # Podążaj za paginacją
        next_page = response.css('a.pagination__next::attr(href), a[rel="next"]::attr(href)').get()
        if next_page:
            self.logger.info(f"Przechodzę do następnej strony: {next_page}")
            yield response.follow(next_page, self.parse)
        
        # Podsumowanie po przetworzeniu strony
        if self.scraped_count == 0:
            self.logger.error("Nie znaleziono ŻADNYCH artykułów na tej stronie!")
            self.logger.error("Uruchom spider z flagą debug=True aby zapisać HTML do analizy")
    
    def process_article(self, response, link, title, teaser):
        """Przetwarza pojedynczy artykuł"""
        # Upewnij się, że URL jest pełny
        full_url = response.urljoin(link)
        source = response.url.split('/')[2]
        
        # Usuń białe znaki
        title = title.strip() if title else ""
        teaser = teaser.strip() if teaser else ""
        
        # Ignoruj linki techniczne
        if any(x in full_url for x in ['#', 'javascript:', 'mailto:', '.jpg', '.png']):
            return
        
        self.urls_found += 1
        self.scraped_count += 1
        
        # DEBUG: Wypisz każdy znaleziony artykuł
        if self.debug_mode or self.scraped_count <= 5:
            self.logger.info(f"[{self.scraped_count}] Tytuł: {title[:60]}...")
            self.logger.info(f"   URL: {full_url}")
        
        # Krok 1: Wstępna Filtracja AI
        if self.ai_filter.is_crime_related(title, teaser):
            self.passed_count += 1
            self.logger.info(f"[{self.passed_count}] Przeszło filtr: {title[:60]}...")
            
            yield scrapy.Request(
                full_url,
                callback=self.parse_full_article,
                meta={'title': title, 'source': source, 'url': full_url},
                errback=self.handle_error,
                dont_filter=False
            )
        else:
            self.filtered_count += 1
            if self.debug_mode:
                self.logger.debug(f"[{self.filtered_count}] Odrzucono: {title[:60]}...")
        
    def parse_full_article(self, response):
        """Pobiera pełny tekst artykułu - ULEPSZONE SELEKTORY"""
        title = response.meta['title']
        source = response.meta['source']
        url = response.meta['url']
        
        # POPRAWIONE SELEKTORY dla treści artykułu TVN24
        paragraphs = response.css('''
            article.article__body p::text,
            div.article__body p::text,
            div[class*="article-body"] p::text,
            div.text-content p::text,
            section.article-content p::text,
            div.article-text p::text
        ''').getall()
        
        raw_text = '\n'.join(p.strip() for p in paragraphs if p.strip())
        
        # Jeśli nie znaleziono paragrafów, spróbuj ogólnych selektorów
        if len(raw_text) < 100:
            self.logger.warning(f"Mało tekstu ({len(raw_text)} znaków), próbuję alternatywnych selektorów")
            
            # Pobierz wszystkie paragrafy z main/article
            all_p = response.css('main p::text, article p::text').getall()
            raw_text = '\n'.join(p.strip() for p in all_p if len(p.strip()) > 20)
        
        if raw_text and len(raw_text) > 100:
            self.logger.info(f"Pełny tekst pobrany ({len(raw_text)} znaków): {title[:50]}...")
            
            yield { 
                'url': url,
                'title': title,
                'raw_text': raw_text,
                'source': source
            }
        else:
            self.logger.warning(f"Za mało tekstu ({len(raw_text)} znaków): {url}")
            
            # DEBUG: Zapisz problematyczny artykuł
            if self.debug_mode:
                filename = f"debug_article_{url.split('/')[-1]}.html"
                with open(filename, 'wb') as f:
                    f.write(response.body)
                self.logger.info(f"Zapisano problematyczny artykuł do: {filename}")
    
    def handle_error(self, failure):
        self.logger.error(f"Błąd pobierania: {failure.request.url}")
        self.logger.error(f"   Powód: {failure.value}")
    
    def closed(self, reason):
        self.logger.info("\n" + "="*70)
        self.logger.info(f"PODSUMOWANIE SCRAPOWANIA")
        self.logger.info("="*70)
        self.logger.info(f"Znalezione linki: {self.urls_found}")
        self.logger.info(f"Przeanalizowane artykuły: {self.scraped_count}")
        self.logger.info(f"Przeszło filtr AI: {self.passed_count}")
        self.logger.info(f"Odrzucone przez AI: {self.filtered_count}")
        if self.scraped_count > 0:
            self.logger.info(f"Wskaźnik akceptacji: {(self.passed_count/self.scraped_count*100):.1f}%")
        else:
            self.logger.warning("BRAK ARTYKUŁÓW - sprawdź selektory CSS!")
        self.logger.info("="*70 + "\n")