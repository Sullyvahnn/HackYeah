#!/usr/bin/env python3
"""
Uruchamia scrapy w partiach z przerwami
Bezpiecznie wykorzystuje limit 30 req/min przez dłuższy czas
"""

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
    def __init__(self, duration_minutes=20, batch_items=5, pause_seconds=65):
        """
        Args:
            duration_minutes: Ile minut ma działać (np. 20)
            batch_items: Ile artykułów na batch (np. 5)
            pause_seconds: Ile sekund przerwy (np. 65 = bezpieczne)
        """
        self.duration = duration_minutes * 60  # konwersja na sekundy
        self.batch_items = batch_items
        self.pause = pause_seconds
        
        self.total_items = 0
        self.total_batches = 0
        self.start_time = time.time()

    def run_single_batch(self):
        """Uruchamia jeden batch scrapera"""
        self.total_batches += 1
        
        logger.info("=" * 70)
        logger.info(f"🚀 BATCH #{self.total_batches} - Cel: {self.batch_items} artykułów")
        logger.info("=" * 70)
        
        try:
            # Uruchom scrapy z limitem artykułów
            cmd = [
                "scrapy", "runspider",
                "agent/crime_news_scrapper/krakow_crime_spider.py",
                "-s", f"CLOSESPIDER_ITEMCOUNT={self.batch_items}",
                "-s", "CLOSESPIDER_PAGECOUNT=10",  # Max 10 stron na batch
                "-s", "LOG_LEVEL=INFO"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 min max na batch
            )
            
            # Policz zebrane artykuły z outputu
            output = result.stdout + result.stderr
            saved = output.count("✅ [")  # Licznik z logów
            self.total_items += saved
            
            logger.info(f"✅ Batch zakończony: zebrano {saved} artykułów")
            logger.info(f"📊 TOTAL: {self.total_items} artykułów w {self.total_batches} batchach")
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("⏱️ Timeout - batch trwał za długo!")
            return False
        except Exception as e:
            logger.error(f"❌ Błąd: {e}")
            return False

    def run(self):
        """Główna pętla - uruchamia batche przez określony czas"""
        logger.info("🎯 START BATCH SCRAPERA")
        logger.info(f"⏱️  Czas działania: {self.duration/60:.0f} minut")
        logger.info(f"📦 Artykułów na batch: {self.batch_items}")
        logger.info(f"⏸️  Pauza między batchami: {self.pause}s")
        logger.info("=" * 70)
        
        while True:
            elapsed = time.time() - self.start_time
            
            # Sprawdź czy czas się skończył
            if elapsed >= self.duration:
                logger.info("=" * 70)
                logger.info("🏁 KONIEC - Osiągnięto limit czasu")
                break
            
            remaining = self.duration - elapsed
            logger.info(f"⏰ Pozostało: {remaining/60:.1f} min")
            
            # Uruchom batch
            success = self.run_single_batch()
            
            if not success:
                logger.warning("⚠️  Batch nieudany, ale kontynuuję...")
            
            # Sprawdź czy starczy czasu na następny batch
            if remaining < self.pause + 120:  # 120s = czas na batch
                logger.info("⏱️  Za mało czasu na kolejny batch")
                break
            
            # Pauza przed następnym batchem
            logger.info(f"💤 Pauza {self.pause}s (reset limitu API)...")
            logger.info("")
            time.sleep(self.pause)
        
        # Podsumowanie
        self.print_summary()

    def print_summary(self):
        """Wyświetla podsumowanie"""
        elapsed = time.time() - self.start_time
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 PODSUMOWANIE")
        logger.info("=" * 70)
        logger.info(f"⏱️  Czas działania: {elapsed/60:.1f} minut")
        logger.info(f"📦 Uruchomionych batchy: {self.total_batches}")
        logger.info(f"📰 Zebranych artykułów: {self.total_items}")
        
        if self.total_batches > 0:
            avg = self.total_items / self.total_batches
            logger.info(f"📈 Średnio na batch: {avg:.1f} artykułów")
        
        logger.info("=" * 70)
        logger.info(f"✅ Dane zapisane w: data/krakow/events_{datetime.now().date()}.jsonl")
        logger.info(f"✅ Baza danych: data/crime_data.db")
        logger.info("=" * 70)


def main():
    """
    Przykładowe konfiguracje:
    
    # Konserwatywna (20 min, małe batche):
    scraper = BatchScraper(duration_minutes=20, batch_items=3, pause_seconds=70)
    
    # Standardowa (20 min, średnie batche):
    scraper = BatchScraper(duration_minutes=20, batch_items=5, pause_seconds=65)
    
    # Agresywna (30 min, większe batche):
    scraper = BatchScraper(duration_minutes=30, batch_items=8, pause_seconds=65)
    """
    
    # 🎯 TWOJA KONFIGURACJA:
    scraper = BatchScraper(
        duration_minutes=20,   # 20 minut działania
        batch_items=5,         # 5 artykułów na batch
        pause_seconds=65       # 65s pauzy (bezpieczne)
    )
    
    try:
        scraper.run()
    except KeyboardInterrupt:
        logger.info("\n⛔ Przerwano przez użytkownika (Ctrl+C)")
        scraper.print_summary()


if __name__ == "__main__":
    main()