#!/usr/bin/env python3
import subprocess
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BatchScraper:
    def __init__(self, duration_minutes=60, batch_items=8, pause_seconds=65):
        self.duration = duration_minutes * 60
        self.batch_items = batch_items
        self.pause = pause_seconds
        self.total_items = 0
        self.total_batches = 0
        self.start_time = time.time()

    def run_single_batch(self):
        self.total_batches += 1
        logger.info("=" * 70)
        logger.info(f"BATCH #{self.total_batches} - Cel: {self.batch_items} artykułów")
        logger.info("=" * 70)
        try:
            # === ZMIANA TUTAJ ===
            # Poprawiona ścieżka do spidera
            cmd = [
                "scrapy", "runspider",
                "agent/crime_news_scrapper/malopolska_crime_spider.py",
                "-s", f"CLOSESPIDER_ITEMCOUNT={self.batch_items}",
                "-s", "CLOSESPIDER_PAGECOUNT=10",
                "-s", "LOG_LEVEL=INFO"
            ]
            # =====================
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            output = result.stdout + result.stderr
            saved_count = output.count("ZAPISANO DO BAZY")
            self.total_items += saved_count
            
            logger.info(f"Batch zakończony: zapisano {saved_count} nowych artykułów")
            logger.info(f"TOTAL: {self.total_items} artykułów w {self.total_batches} batchach")
            return True
        except subprocess.TimeoutExpired:
            logger.error("Timeout - batch trwał za długo!")
            return False
        except Exception as e:
            logger.error(f"Błąd uruchomienia scrapera: {e}")
            return False


    def run(self):
        logger.info("START BATCH SCRAPERA DLA MAŁOPOLSKI")
        logger.info(f"Czas działania: {self.duration/60:.0f} minut")
        logger.info(f"Artykułów na batch: {self.batch_items}")
        logger.info(f"Pauza między batchami: {self.pause}s")
        logger.info("=" * 70)
        
        while time.time() - self.start_time < self.duration:
            self.run_single_batch()
            
            remaining = self.duration - (time.time() - self.start_time)
            if remaining < self.pause + 60:
                logger.info("Za mało czasu na kolejny pełny batch i pauzę. Kończę.")
                break
                
            logger.info(f"Pauza {self.pause}s (reset limitu API)... Pozostało: {remaining/60:.1f} min")
            time.sleep(self.pause)
            
        self.print_summary()

    def print_summary(self):
        elapsed = time.time() - self.start_time
        logger.info("\n" + "=" * 70)
        logger.info("PODSUMOWANIE")
        logger.info("=" * 70)
        logger.info(f"Całkowity czas działania: {elapsed/60:.1f} minut")
        logger.info(f"Uruchomiono batchy: {self.total_batches}")
        logger.info(f"Zapisano nowych artykułów: {self.total_items}")
        logger.info(f"Baza danych: data/crime_data.db")
        logger.info("=" * 70)

def main():
    scraper = BatchScraper(
        duration_minutes=60,
        batch_items=8,
        pause_seconds=65
    )
    try:
        scraper.run()
    except KeyboardInterrupt:
        logger.info("\nPrzerwano przez użytkownika (Ctrl+C)")
        scraper.print_summary()

if __name__ == "__main__":
    main()