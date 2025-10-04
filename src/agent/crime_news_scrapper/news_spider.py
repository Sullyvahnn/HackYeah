import scrapy
import sys
import os

# Import z folderu nadrzędnego (agent/)
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from db import DB_MANAGER
from crime_news_scraper.ai_filter import CrimeFilter


class CrimeNewsSpider(scrapy.Spider):
    """
    Spider do scrapowania artykułów o przestępstwach
    Z wbudowaną filtracją AI
    """
    name = 'crime_news'
    
    # KONFIGURACJA ŹRÓDEŁ - dostosuj do swoich potrzeb!
    start_urls = [
        'https://www.tvn24.pl/polska',
        'https://wiadomosci.onet.pl/kraj',
        'https://wiadomosci.wp.pl/kategoria/kronika',
        # Dodaj więcej źródeł
    ]
    
    # Ustawienia scrapera
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'COOKIES_ENABLED': False,
        'TELNETCONSOLE_ENABLED': False,
        'LOG_LEVEL': 'INFO'
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Załaduj filtr AI
        self.ai_filter = CrimeFilter()
        self.scraped_count = 0
        self.saved_count = 0
    
    def parse(self, response):
        """
        GŁÓWNA METODA - parsuje stronę z listą artykułów
        
        UWAGA: Musisz dostosować selektory CSS do swojego źródła!
        Poniżej przykłady dla różnych portali.
        """
        
        # Wykryj źródło i użyj odpowiednich selektorów
        if 'tvn24.pl' in response.url:
            yield from self.parse_tvn24(response)
        elif 'onet.pl' in response.url:
            yield from self.parse_onet(response)
        elif 'wp.pl' in response.url:
            yield from self.parse_wp(response)
        else:
            # Uniwersalny parser (może nie działać dobrze)
            yield from self.parse_generic(response)
    
    def parse_tvn24(self, response):
        """Parser specyficzny dla TVN24"""
        self.logger.info(f"🔍 Scrapuję TVN24: {response.url}")
        
        # UWAGA: To są przykładowe selektory - sprawdź rzeczywiste!
        for article in response.css('article.news-card'):
            title = article.css('h3.news-card__title::text').get()
            teaser = article.css('p.news-card__lead::text').get()
            url = article.css('a.news-card__link::attr(href)').get()
            
            if title and url:
                full_url = response.urljoin(url)
                yield from self.process_article_link(
                    full_url, title, teaser, 'tvn24'
                )
    
    def parse_onet(self, response):
        """Parser specyficzny dla Onet"""
        self.logger.info(f"🔍 Scrapuję Onet: {response.url}")
        
        for article in response.css('article.articleItem'):
            title = article.css('h3::text').get()
            teaser = article.css('p.lead::text').get()
            url = article.css('a::attr(href)').get()
            
            if title and url:
                full_url = response.urljoin(url)
                yield from self.process_article_link(
                    full_url, title, teaser, 'onet'
                )
    
    def parse_wp(self, response):
        """Parser specyficzny dla WP"""
        self.logger.info(f"🔍 Scrapuję WP: {response.url}")
        
        for article in response.css('article.sc-1ju2w1o-0'):
            title = article.css('h2::text').get()
            teaser = article.css('p.sc-15vif9k-1::text').get()
            url = article.css('a::attr(href)').get()
            
            if title and url:
                full_url = response.urljoin(url)
                yield from self.process_article_link(
                    full_url, title, teaser, 'wp'
                )
    
    def parse_generic(self, response):
        """Uniwersalny parser (backup)"""
        self.logger.info(f"🔍 Scrapuję (generic): {response.url}")
        
        # Próbuj znaleźć artykuły uniwersalnymi selektorami
        for article in response.css('article, div.article, div[class*="article"]'):
            title = (
                article.css('h1::text, h2::text, h3::text').get() or
                article.css('[class*="title"]::text').get()
            )
            
            url = article.css('a::attr(href)').get()
            teaser = article.css('p::text').get()
            
            if title and url:
                full_url = response.urljoin(url)
                source = response.url.split('/')[2]  # Domena jako źródło
                yield from self.process_article_link(
                    full_url, title, teaser, source
                )
    
    def process_article_link(self, url, title, teaser, source):
        """
        Przetwarza link do artykułu:
        1. Filtruje przez AI
        2. Jeśli pasuje - pobiera pełny artykuł
        """
        self.scraped_count += 1
        
        # Wstępna filtracja AI
        if self.ai_filter.is_crime_related(title, teaser):
            self.logger.info(f"✅ Przeszło filtr: {title[:60]}...")
            
            # Pobierz pełny artykuł
            yield scrapy.Request(
                url,
                callback=self.parse_full_article,
                meta={
                    'title': title,
                    'source': source,
                    'url': url
                },
                errback=self.handle_error
            )
        else:
            self.logger.debug(f"❌ Odrzucono: {title[:60]}...")
    
    def parse_full_article(self, response):
        """Parsuje pełny artykuł i zapisuje do bazy"""
        title = response.meta['title']
        source = response.meta['source']
        url = response.meta['url']
        
        # Pobierz tekst artykułu - uniwersalny selektor
        # Szuka paragrafów wewnątrz article, main, lub div.content
        paragraphs = response.css('''
            article p::text,
            main p::text,
            div[class*="content"] p::text,
            div[class*="article"] p::text
        ''').getall()
        
        # Połącz paragrafy
        raw_text = '\n'.join(p.strip() for p in paragraphs if p.strip())
        
        if raw_text and len(raw_text) > 100:  # Min 100 znaków
            # Zapisz do bazy
            article_id = DB_MANAGER.save_raw_article(
                url=url,
                title=title,
                raw_text=raw_text,
                source=source
            )
            
            if article_id:
                self.saved_count += 1
                self.logger.info(
                    f"💾 Zapisano [{self.saved_count}]: {title[:60]}..."
                )
            
            yield {
                'url': url,
                'title': title,
                'source': source,
                'status': 'saved' if article_id else 'duplicate'
            }
        else:
            self.logger.warning(f"⚠️ Za mało tekstu w: {url}")
    
    def handle_error(self, failure):
        """Obsługa błędów podczas pobierania"""
        self.logger.error(f"❌ Błąd: {failure.request.url}")
    
    def closed(self, reason):
        """Wywoływane po zakończeniu scrapowania"""
        self.logger.info("\n" + "="*60)
        self.logger.info(f"📊 PODSUMOWANIE SCRAPOWANIA")
        self.logger.info("="*60)
        self.logger.info(f"  Znalezione artykuły: {self.scraped_count}")
        self.logger.info(f"  Zapisane do bazy: {self.saved_count}")
        self.logger.info(f"  Wskaźnik filtracji: {(self.saved_count/self.scraped_count*100):.1f}%" if self.scraped_count > 0 else "0%")
        self.logger.info("="*60 + "\n")