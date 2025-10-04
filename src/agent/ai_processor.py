from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from typing import Dict, Optional
import re

class CrimeAIProcessor:
    """Procesor AI do ekstrakcji informacji o przestępstwach"""
    
    def __init__(self, model_name: str = "google/mt5-small"):
        print(f" Ładuję model: {model_name}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        
        print(f"Model załadowany na: {self.device}")
    
    def generate_response(self, prompt: str, max_length: int = 128) -> str:
        """Generuje odpowiedź z modelu dla danego promptu"""
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            max_length=512,
            truncation=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_length,
                num_beams=4,
                early_stopping=True,
                temperature=0.7
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response.strip()
    
    def extract_crime_type(self, text: str) -> str:
        """PROMPT 1: Ekstrakcja rodzaju przestępstwa"""
        prompt = f"""Określ rodzaj przestępstwa w poniższym artykule. 
Wybierz jedną z kategorii: kradzież, rozbój, napad, włamanie, 
oszustwo, pobicie, morderstwo, wypadek drogowy, przemoc domowa, 
narkotyki, inne.

Artykuł: {text[:1000]}

Rodzaj przestępstwa:"""
        
        crime_type = self.generate_response(prompt, max_length=20)
        return self._clean_output(crime_type)
    
    def extract_location(self, text: str) -> str:
        """PROMPT 2: Ekstrakcja lokalizacji"""
        prompt = f"""Podaj dokładne miejsce zdarzenia z artykułu.
Uwzględnij: miasto, ulicę, dzielnicę jeśli są podane.
Format: [ulica], [miasto] lub [dzielnica], [miasto]

Artykuł: {text[:1000]}

Lokalizacja:"""
        
        location = self.generate_response(prompt, max_length=50)
        return self._clean_output(location)
    
    def extract_summary(self, text: str) -> str:
        """PROMPT 3: Streszczenie artykułu"""
        prompt = f"""Streść poniższy artykuł w maksymalnie 3 zdaniach.
Skup się na: co się stało, gdzie, kto był zaangażowany.

Artykuł: {text[:1500]}

Streszczenie:"""
        
        summary = self.generate_response(prompt, max_length=150)
        return self._clean_output(summary)
    
    def extract_keywords(self, text: str) -> str:
        """PROMPT 4: Słowa kluczowe"""
        prompt = f"""Wymień 5 najważniejszych słów kluczowych z artykułu.
Oddziel je przecinkami.

Artykuł: {text[:1000]}

Słowa kluczowe:"""
        
        keywords = self.generate_response(prompt, max_length=50)
        return self._clean_output(keywords)
    
    def process_article(self, article_text: str) -> Dict[str, str]:
        """Przetwarza cały artykuł przez 4 etapy ekstrakcji"""
        print("Przetwarzam artykuł...")
        
        try:
            result = {
                'crime_type': self.extract_crime_type(article_text),
                'location': self.extract_location(article_text),
                'summary': self.extract_summary(article_text),
                'keywords': self.extract_keywords(article_text)
            }
            
            print("Ekstrakcja zakończona!")
            return result
            
        except Exception as e:
            print(f"Błąd przetwarzania: {e}")
            return {
                'crime_type': 'nieznany',
                'location': 'nieznana',
                'summary': 'Błąd przetwarzania',
                'keywords': ''
            }
    
    def _clean_output(self, text: str) -> str:
        """Czyści output z modelu"""
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        prefixes = ['Rodzaj przestępstwa:', 'Lokalizacja:', 
                   'Streszczenie:', 'Słowa kluczowe:']
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        return text
    
    def geocode_location(self, location: str) -> Optional[tuple]:
        """OPCJONALNE: Konwersja adresu na współrzędne GPS"""
        try:
            from geopy.geocoders import Nominatim
            
            geolocator = Nominatim(user_agent="crime_analyzer")
            location_data = geolocator.geocode(location, timeout=10)
            
            if location_data:
                return (location_data.latitude, location_data.longitude)
            
        except Exception as e:
            print(f"Błąd geokodowania: {e}")
        
        return None


class BatchProcessor:
    """Przetwarza wiele artykułów naraz"""
    
    def __init__(self):
        self.ai_processor = CrimeAIProcessor()
    
    def process_batch(self, articles: list) -> int:
        """Przetwarza listę artykułów"""
        from db import DB_MANAGER
        
        processed_count = 0
        
        for article in articles:
            article_id = article['id']
            text = article['raw_text']
            
            print(f"\n Przetwarzam artykuł ID={article_id}")
            
            # KROK 1: Ekstrakcja przez AI
            result = self.ai_processor.process_article(text)
            
            # KROK 2: Geokodowanie (opcjonalne)
            location = result['location']
            coords = self.ai_processor.geocode_location(location)
            
            latitude = coords[0] if coords else None
            longitude = coords[1] if coords else None
            
            # KROK 3: Zapis do bazy (POPRAWIONE!)
            DB_MANAGER.update_processed_article(
                raw_article_id=article_id,
                crime_type=result['crime_type'],
                location=location,
                summary=result['summary'],
                keywords=result['keywords'],
                latitude=latitude,
                longitude=longitude
            )
            
            processed_count += 1
        
        return processed_count