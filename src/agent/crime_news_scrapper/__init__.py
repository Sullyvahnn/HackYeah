"""
Crime News Scraper Module
"""

__version__ = '1.0.0'

from .spider import CrimeNewsSpider
from .ai_filter import CrimeFilter

__all__ = ['CrimeNewsSpider', 'CrimeFilter']