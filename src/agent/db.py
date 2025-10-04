import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import os

class DatabaseManager:
    """Menedżer bazy danych dla systemu analizy przestępstw"""
    
    def __init__(self, db_path: str = "crime_data.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Tworzy połączenie z bazą danych"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Zwraca wiersze jako słowniki
        return conn
    
    def init_database(self):
        """Inicjalizuje strukturę bazy danych"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabela z surowymi artykułami
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS raw_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                source TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_processed INTEGER DEFAULT 0,
                processing_attempts INTEGER DEFAULT 0
            )
        ''')
        
        # Tabela z przetworzonymi danymi
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_article_id INTEGER NOT NULL,
                crime_type TEXT,
                location TEXT,
                summary TEXT,
                keywords TEXT,
                latitude REAL,
                longitude REAL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (raw_article_id) REFERENCES raw_articles(id)
            )
        ''')
        
        # Indeksy dla wydajności
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_is_processed 
            ON raw_articles(is_processed)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_location 
            ON processed_articles(location)
        ''')
        
        conn.commit()
        conn.close()
        print(f"Baza danych zainicjalizowana: {self.db_path}")
    
    def save_raw_article(self, url: str, title: str, raw_text: str, 
                        source: str = "unknown") -> Optional[int]:
        """
        Zapisuje surowy artykuł do bazy
        
        Returns:
            ID artykułu lub None jeśli już istnieje
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO raw_articles (url, title, raw_text, source)
                VALUES (?, ?, ?, ?)
            ''', (url, title, raw_text, source))
            
            conn.commit()
            article_id = cursor.lastrowid
            print(f"Zapisano artykuł ID={article_id}: {title[:50]}...")
            return article_id
            
        except sqlite3.IntegrityError:
            print(f"Artykuł już istnieje: {url}")
            return None
        finally:
            conn.close()
    
    def get_unprocessed_articles(self, limit: int = 10) -> List[Dict]:
        """
        Pobiera nieprzetworzony artykuły (is_processed=0)
        
        Args:
            limit: Maksymalna liczba artykułów do pobrania
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, url, title, raw_text, source
            FROM raw_articles
            WHERE is_processed = 0 AND processing_attempts < 3
            ORDER BY scraped_at DESC
            LIMIT ?
        ''', (limit,))
        
        articles = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        print(f"📥 Pobrano {len(articles)} nieprzetworzonych artykułów")
        return articles
    
    def update_processed_article(self, raw_article_id: int, 
                                 crime_type: str, location: str,
                                 summary: str, keywords: str,
                                 latitude: float = None, 
                                 longitude: float = None):
        """Zapisuje przetworzone dane artykułu"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Zapisz przetworzone dane
            cursor.execute('''
                INSERT INTO processed_articles 
                (raw_article_id, crime_type, location, summary, keywords, 
                 latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (raw_article_id, crime_type, location, summary, keywords,
                  latitude, longitude))
            
            # Oznacz artykuł jako przetworzony
            cursor.execute('''
                UPDATE raw_articles 
                SET is_processed = 1 
                WHERE id = ?
            ''', (raw_article_id,))
            
            conn.commit()
            print(f"Przetworzono artykuł ID={raw_article_id}")
            
        except Exception as e:
            print(f"Błąd przetwarzania artykułu ID={raw_article_id}: {e}")
            # Zwiększ licznik prób
            cursor.execute('''
                UPDATE raw_articles 
                SET processing_attempts = processing_attempts + 1 
                WHERE id = ?
            ''', (raw_article_id,))
            conn.commit()
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict:
        """Zwraca statystyki bazy danych"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM raw_articles')
        total_articles = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM raw_articles WHERE is_processed = 1')
        processed_articles = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM raw_articles WHERE is_processed = 0')
        pending_articles = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_articles': total_articles,
            'processed': processed_articles,
            'pending': pending_articles,
            'completion_rate': f"{(processed_articles/total_articles*100):.1f}%" if total_articles > 0 else "0%"
        }
    
    def get_crimes_by_location(self, location_filter: str = None) -> List[Dict]:
        """
        Pobiera przestępstwa z opcjonalnym filtrem lokalizacji
        
        Args:
            location_filter: Fragment nazwy lokalizacji (np. "Kraków")
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if location_filter:
            cursor.execute('''
                SELECT 
                    r.title,
                    r.url,
                    r.source,
                    p.crime_type,
                    p.location,
                    p.summary,
                    p.keywords,
                    p.latitude,
                    p.longitude,
                    p.processed_at
                FROM processed_articles p
                JOIN raw_articles r ON p.raw_article_id = r.id
                WHERE p.location LIKE ?
                ORDER BY p.processed_at DESC
            ''', (f'%{location_filter}%',))
        else:
            cursor.execute('''
                SELECT 
                    r.title,
                    r.url,
                    r.source,
                    p.crime_type,
                    p.location,
                    p.summary,
                    p.keywords,
                    p.latitude,
                    p.longitude,
                    p.processed_at
                FROM processed_articles p
                JOIN raw_articles r ON p.raw_article_id = r.id
                ORDER BY p.processed_at DESC
            ''')
        
        crimes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return crimes


# Globalna instancja (singleton)
DB_MANAGER: Optional['DatabaseManager'] = None 

def initialize_db_manager(db_path: str):
    """Leniwa inicjalizacja menedżera bazy danych."""
    global DB_MANAGER
    if DB_MANAGER is None:
        DB_MANAGER = DatabaseManager(db_path=db_path)
    return DB_MANAGER