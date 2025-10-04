
from itemadapter import ItemAdapter
import logging
import sys
import os 
# DODAJ ŚCIEŻKĘ JAK W SPIDERZE:
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Teraz importujemy 'db' bezpośrednio
from db import initialize_db_manager 

class RawArticlePipeline:
    """Pipeline do zapisu surowych artykułów do bazy SQLite."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.db_manager = None
        self.logger = logging.getLogger('RawArticlePipeline')
        
    @classmethod
    def from_crawler(cls, crawler):
        """Pobiera ścieżkę do bazy z ustawień Scrapy (settings.py)"""
        # Używamy ścieżki z settings.py
        db_path = crawler.settings.get('SQLITE_DB_PATH', 'crime_data.db') 
        return cls(db_path=db_path)

    def open_spider(self, spider):
        """Inicjalizuje DB_MANAGER na początku działania pająka"""
        # Zapewniamy, że DB_MANAGER jest globalnie dostępny i zainicjalizowany
        self.db_manager = initialize_db_manager(self.db_path)
        self.logger.info(f"Pipeline zainicjalizowany. Baza danych: {self.db_path}")

    def process_item(self, item, spider):
        """Przechwytuje dane i wywołuje metodę zapisu (Krok 3 Cyklu)"""
        
        adapter = ItemAdapter(item)
        title = adapter.get('title')
        url = adapter.get('url')
        raw_text = adapter.get('raw_text')
        source = adapter.get('source') 

        if self.db_manager:
            article_id = self.db_manager.save_raw_article(
                url=url,
                title=title,
                raw_text=raw_text,
                source=source
            )
            
            if article_id:
                # Zapis zakończony sukcesem - artykuł trafił do raw_articles z is_processed=0
                spider.logger.info(f"✅ Zapisano ID={article_id}. Gotowy do AI Agent.")
            else:
                # Artykuł został zignorowany (np. duplikat URL)
                spider.logger.debug(f"ℹ️ Zignorowano (duplikat): {title[:60]}...")

        return item