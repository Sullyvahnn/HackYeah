from transformers import pipeline
import logging

class CrimeFilter:
    """Lekki filtr AI do wstępnej klasyfikacji artykułów"""
    
    def __init__(self, model_name: str = "joeddav/xlm-roberta-large-xnli"):
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🤖 Ładuję filtr AI: {model_name}")
        
        try:
            self.classifier = pipeline(
                "zero-shot-classification",
                model=model_name,
                device=-1
            )
            self.logger.info("✅ Filtr AI załadowany!")
        except Exception as e:
            self.logger.error(f"❌ Błąd ładowania modelu: {e}")
            self.classifier = None
        
        self.crime_labels = [
            "przestępstwo i kronika policyjna",
            "kradzież i włamania", 
            "napad i rozbój",
            "wypadek drogowy",
            "przemoc i pobicie",
            "zatrzymanie przez policję",
            "news niezwiązany z przestępstwem"
        ]
        
        self.threshold = 0.65
    
    def is_crime_related(self, title: str, teaser: str = "") -> bool:
        """Sprawdza czy artykuł dotyczy przestępstwa"""
        if not self.classifier:
            self.logger.warning("⚠️ Model nie załadowany - przepuszczam artykuł")
            return True
        
        text = f"{title}. {teaser or ''}".strip()
        
        if len(text) > 300:
            text = text[:300]
        
        try:
            result = self.classifier(
                text,
                candidate_labels=self.crime_labels,
                hypothesis_template="Ten artykuł dotyczy: {}"
            )
            
            top_label = result['labels'][0]
            top_score = result['scores'][0]
            
            self.logger.debug(
                f"Klasyfikacja: {top_label} ({top_score:.2f}) - {title[:40]}"
            )
            
            if top_label == "news niezwiązany z przestępstwem":
                return False
            
            return top_score > self.threshold
            
        except Exception as e:
            self.logger.error(f"❌ Błąd klasyfikacji: {e}")
            return True
    
    def batch_filter(self, articles: list) -> list:
        """Filtruje wiele artykułów naraz"""
        filtered = []
        
        for article in articles:
            title = article.get('title', '')
            teaser = article.get('teaser', '')
            
            if self.is_crime_related(title, teaser):
                filtered.append(article)
        
        self.logger.info(
            f"📊 Filtracja: {len(filtered)}/{len(articles)} artykułów przeszło"
        )
        
        return filtered