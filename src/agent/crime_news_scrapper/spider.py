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
    ]
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 4,
        'DOWNLOAD_DELAY': 2,
        'COOKIES_ENABLED': False,
        'LOG_LEVEL': 'INFO'
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        init_start_time = time.time()
        self.logger.info("🤖 Inicjalizuję AI Filter...")
        
        self.ai_filter = CrimeFilter() 
        
        init_elapsed = time.time() - init_start_time
        self.logger.info(f"✅ AI Filter zainicjalizowany w: {init_elapsed:.2f}s")
        
        self.scraped_count = 0
        self.filtered_count = 0
        self.passed_count = 0
    
    def parse(self, response):
        """Główna metoda parsowania i wstępnej filtracji"""
        self.logger.info(f"🔍 Scrapuję: {response.url}")
        
        # Selektory dla TVN24 - artykuły z linkami
        for article in response.css('article a[href], div.article-item a[href]'):
            url = article.css('::attr(href)').get()
            title = article.css('::attr(title)').get() or article.css('::text').get()
            
            # Zajawka może być w różnych miejscach
            teaser = article.css('p::text, span.description::text').get()

            if title and url:
                # Upewnij się, że URL jest pełny
                full_url = response.urljoin(url)
                source = response.url.split('/')[2]
                
                self.scraped_count += 1
                
                # Krok 1: Wstępna Filtracja AI
                if self.ai_filter.is_crime_related(title, teaser or ''):
                    self.passed_count += 1
                    self.logger.info(f"✅ [{self.passed_count}] Przeszło filtr: {title[:60]}...")
                    
                    yield scrapy.Request(
                        full_url,
                        callback=self.parse_full_article,
                        meta={'title': title, 'source': source, 'url': full_url},
                        errback=self.handle_error,
                        dont_filter=False  # Pozwól Scrapy filtrować duplikaty URL
                    )
                else:
                    self.filtered_count += 1
                    self.logger.debug(f"❌ [{self.filtered_count}] Odrzucono: {title[:60]}...")
        
        # Podążaj za następnymi stronami paginacji (opcjonalnie)
        next_page = response.css('a.next::attr(href), a[rel="next"]::attr(href)').get()
        if next_page:
            self.logger.info(f"➡️ Przechodzę do następnej strony")
            yield response.follow(next_page, self.parse)
        
    def parse_full_article(self, response):
        """Pobiera pełny tekst artykułu i przekazuje do Pipeline"""
        title = response.meta['title']
        source = response.meta['source']
        url = response.meta['url']
        
        # Poprawiony selektor dla treści artykułu TVN24
        paragraphs = response.css('''
            article p::text,
            div.article-body p::text,
            div.article__body p::text,
            div[class*="content"] p::text,
            div.text-content p::text
        ''').getall()
        
        raw_text = '\n'.join(p.strip() for p in paragraphs if p.strip())
        
        if raw_text and len(raw_text) > 100:
            self.logger.info(f"📄 Pełny tekst pobrany ({len(raw_text)} znaków): {title[:50]}...")
            # Krok 2: Zwracanie danych do Pipeline
            yield { 
                'url': url,
                'title': title,
                'raw_text': raw_text,
                'source': source
            }
        else:
            self.logger.warning(f"⚠️ Za mało tekstu ({len(raw_text)} znaków): {url}")
    
    def handle_error(self, failure):
        self.logger.error(f"❌ Błąd pobierania: {failure.request.url}")
    
    def closed(self, reason):
        self.logger.info("\n" + "="*70)
        self.logger.info(f"📊 PODSUMOWANIE SCRAPOWANIA")
        self.logger.info("="*70)
        self.logger.info(f"  🔍 Znalezione artykuły: {self.scraped_count}")
        self.logger.info(f"  ✅ Przeszło filtr AI: {self.passed_count}")
        self.logger.info(f"  ❌ Odrzucone przez AI: {self.filtered_count}")
        if self.scraped_count > 0:
            self.logger.info(f"  📈 Wskaźnik filtracji: {(self.passed_count/self.scraped_count*100):.1f}%")
        self.logger.info("="*70 + "\n")