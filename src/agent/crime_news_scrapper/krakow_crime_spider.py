import scrapy
from agent.crime_news_scrapper.ai_filter_groq import CrimeFilterLocal

class MalopolskaCrimeSpider(scrapy.Spider):
    name = 'malopolska_crime'
    
    # WAŻNE: Wstaw tutaj adresy stron z wiadomościami z Małopolski
    start_urls = [
        '[https://gazetakrakowska.pl/wiadomosci](https://gazetakrakowska.pl/wiadomosci)',
        # '[https://www.tarnow.net.pl/](https://www.tarnow.net.pl/)', # Przykład
        # '[https://www.dts24.pl/kategoria/fakty/](https://www.dts24.pl/kategoria/fakty/)', # Przykład Nowy Sącz
    ]

    def __init__(self, *args, **kwargs):
        super(MalopolskaCrimeSpider, self).__init__(*args, **kwargs)
        self.ai_filter = CrimeFilterLocal()

    def parse(self, response):
        # WAŻNE: Dostosuj ten selektor, aby pasował do linków do artykułów na stronie
        article_links = response.css('a.article__link::attr(href)').getall()
        
        for link in article_links:
            # Upewnij się, że link jest pełnym adresem URL
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_article)
            
        # Logika przechodzenia do następnej strony (jeśli istnieje)
        # WAŻNE: Dostosuj selektor do przycisku "następna strona"
        # next_page = response.css('a.pagination__next::attr(href)').get()
        # if next_page:
        #     yield response.follow(next_page, callback=self.parse)

    def parse_article(self, response):
        # WAŻNE: Dostosuj selektory do struktury strony artykułu
        title = response.css('h1.article__title::text').get('').strip()
        teaser = response.css('p.article__teaser::text').get('').strip()
        # Pobierz wszystkie paragrafy i połącz je w jeden tekst
        content_parts = response.css('div.article__content p::text').getall()
        content = "\n".join(part.strip() for part in content_parts)

        if not title:
            self.logger.warning(f"Nie znaleziono tytułu na: {response.url}")
            return
            
        # Krok 1: Szybkie filtrowanie przez AI
        if self.ai_filter.is_crime_related(title, teaser, content):
            self.logger.info(f"ISTOTNY ARTYKUŁ: {title}")
            # Krok 2: Głęboka analiza i ekstrakcja danych
            event_data = self.ai_filter.extract_event_info(title, teaser, content)
            
            # Dodaj URL do finalnych danych
            event_data['url'] = response.url
            
            # Przekaż dane do zapisu (do pipeline'u)
            yield event_data
        else:
            self.logger.info(f"POMIJAM: {title}")