from itemadapter import ItemAdapter
import logging
import sys
import os 

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.db import initialize_db_manager 

class RawArticlePipeline:
    """Pipeline do zapisu surowych artykułów do bazy SQLite."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.db_manager = None
        self.logger = logging.getLogger('RawArticlePipeline')
        self.saved_count = 0
        self.skipped_count = 0
        
    @classmethod
    def from_crawler(cls, crawler):
        """Pobiera ścieżkę do bazy z ustawień Scrapy"""
        db_path = crawler.settings.get('SQLITE_DB_PATH', 'data/crime_data.db') 
        return cls(db_path=db_path)

    def open_spider(self, spider):
        """Inicjalizuje DB_MANAGER na początku działania pająka"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.db_manager = initialize_db_manager(self.db_path)
        self.logger.info(f"Pipeline zainicjalizowany. Baza danych: {self.db_path}")

    def process_item(self, item, spider):
        """Przechwytuje dane i wywołuje metodę zapisu"""
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
                self.saved_count += 1
                self.logger.info(f"Zapisano ID={article_id}: {title[:50]}...")
            else:
                self.skipped_count += 1
                self.logger.debug(f"Zignorowano (duplikat): {title[:50]}...")

        return item
    
    def close_spider(self, spider):
        """Podsumowanie po zakończeniu scrapowania"""
        self.logger.info("\n" + "="*60)
        self.logger.info(f"PODSUMOWANIE PIPELINE")
        self.logger.info("="*60)
        self.logger.info(f"Zapisane nowe artykuły: {self.saved_count}")
        self.logger.info(f"Pominięte (duplikaty): {self.skipped_count}")
        self.logger.info("="*60 + "\n")