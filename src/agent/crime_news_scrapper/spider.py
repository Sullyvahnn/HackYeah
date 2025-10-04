import scrapy
import sys
import os

# Import z folderu nadrzędnego
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from agent.db import DB_MANAGER
from agent.crime_news_scrapper.ai_filter import CrimeFilter


class CrimeNewsSpider(scrapy.Spider):
    """Spider do scrapowania artykułów o przestępstwach"""
    name = 'crime_news'
    
    # ŹRÓDŁA - możesz je edytować!
    start_urls = [
        'https://www.tvn24.pl/polska',
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
        self.ai_filter = CrimeFilter()
        self.scraped_count = 0
        self.saved_count = 0
    
    def parse(self, response):
        """Główna metoda parsowania"""
        self.logger.info(f"🔍 Scrapuję: {response.url}")
        
        # UNIWERSALNY PARSER - szuka artykułów
        for article in response.css('article, div[class*="article"]'):
            title = (
                article.css('h1::text, h2::text, h3::text').get() or
                article.css('[class*="title"]::text, [class*="headline"]::text').get()
            )
            
            url = article.css('a::attr(href)').get()
            teaser = article.css('p::text, [class*="lead"]::text, [class*="teaser"]::text').get()
            
            if title and url:
                full_url = response.urljoin(url)
                source = response.url.split('/')[2]
                
                self.scraped_count += 1
                
                # Filtruj przez AI
                if self.ai_filter.is_crime_related(title, teaser or ''):
                    self.logger.info(f"✅ Przeszło filtr: {title[:60]}...")
                    
                    yield scrapy.Request(
                        full_url,
                        callback=self.parse_full_article,
                        meta={'title': title, 'source': source, 'url': full_url},
                        errback=self.handle_error
                    )
    
    def parse_full_article(self, response):
        """Parsuje pełny artykuł"""
        title = response.meta['title']
        source = response.meta['source']
        url = response.meta['url']
        
        # Pobierz wszystkie paragrafy
        paragraphs = response.css('article p::text, main p::text, div[class*="content"] p::text').getall()
        raw_text = '\n'.join(p.strip() for p in paragraphs if p.strip())
        
        if raw_text and len(raw_text) > 100:
            article_id = DB_MANAGER.save_raw_article(
                url=url,
                title=title,
                raw_text=raw_text,
                source=source
            )
            
            if article_id:
                self.saved_count += 1
                self.logger.info(f"💾 Zapisano [{self.saved_count}]: {title[:60]}...")
    
    def handle_error(self, failure):
        self.logger.error(f"❌ Błąd: {failure.request.url}")
    
    def closed(self, reason):
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 PODSUMOWANIE")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"  Znalezione: {self.scraped_count}")
        self.logger.info(f"  Zapisane: {self.saved_count}")
        self.logger.info(f"{'='*60}\n")