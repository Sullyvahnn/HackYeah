import scrapy
import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# Importujemy tylko CrimeFilter. DB_MANAGER będzie używany w Pipeline.
from db import initialize_db_manager

from agent.crime_news_scrapper.ai_filter import CrimeFilter 


class CrimeNewsSpider(scrapy.Spider):
    """Spider do scrapowania artykułów o przestępstwach"""
    name = 'crime_news'
    
    start_urls = [
        'https://tvn24.pl/krakow',
        # Dodaj więcej stron kategorii dla lepszych wyników
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
        print("Inicjalizuję AI Filter...")
        
        self.ai_filter = CrimeFilter() 
        
        init_elapsed = time.time() - init_start_time
        print(f" AI Filter zainicjalizowany w: {init_elapsed:.2f}s")
        
        self.scraped_count = 0
        self.saved_count = 0 # To pole będzie teraz mniej precyzyjne, lepiej polegać na logach Pipeline
    
    def parse(self, response):
        """Główna metoda parsowania i wstępnej filtracji"""
        self.logger.info(f"🔍 Scrapuję: {response.url}")
        
        # Selektory dla TVN24
        for article in response.css('a[title][href*="st"]'):
            
            url = article.css('::attr(href)').get()
            title = article.css('::attr(title)').get() 
            # Użycie ogólnego selektora na wypadek, gdyby zajawka była w innym miejscu
            teaser = article.css('div.TextBox span::text, p::text').get() 

            if title and url:
                full_url = response.urljoin(url)
                source = response.url.split('/')[2]
                
                self.scraped_count += 1
                
                # Krok 1: Wstępna Filtracja AI
                if self.ai_filter.is_crime_related(title, teaser or ''):
                    self.logger.info(f"✅ Przeszło filtr AI: {title[:60]}...")
                    
                    yield scrapy.Request(
                        full_url,
                        callback=self.parse_full_article,
                        meta={'title': title, 'source': source, 'url': full_url},
                        errback=self.handle_error,
                        dont_filter=True
                    )
                else:
                    self.logger.debug(f"❌ Odrzucono filtr AI: {title[:60]}...")
        
    def parse_full_article(self, response):
        """Pobiera pełny tekst artykułu i przekazuje do Pipeline"""
        title = response.meta['title']
        source = response.meta['source']
        url = response.meta['url']
        
        # Poprawiony selektor dla treści artykułu
        paragraphs = response.css('''
            div.article-body p::text,
            div[class*="content"] p::text,
            div.text-content p::text
        ''').getall()
        
        raw_text = '\n'.join(p.strip() for p in paragraphs if p.strip())
        
        if raw_text and len(raw_text) > 100:
            # Krok 2: Zwracanie danych do Pipeline
            yield { 
                'url': url,
                'title': title,
                'raw_text': raw_text,
                'source': source
            }
        else:
            self.logger.warning(f"Za mało tekstu lub błąd parsowania: {url}")
    
    
    def handle_error(self, failure):
        self.logger.error(f" Błąd: {failure.request.url}")
    
    def closed(self, reason):
        self.logger.info("\n" + "="*60)
        self.logger.info(f"PODSUMOWANIE SCRAPOWANIA")
        self.logger.info("="*60)
        self.logger.info(f"  Znalezione artykuły: {self.scraped_count}")
        self.logger.info(f"  Zapisane do bazy: {self.saved_count}")
        if self.scraped_count > 0:
            self.logger.info(f"  Wskaźnik filtracji: {(self.saved_count/self.scraped_count*100):.1f}%")
        self.logger.info("="*60 + "\n")