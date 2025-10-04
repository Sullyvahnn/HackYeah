# Scrapy settings for crime_news_scrapper
BOT_NAME = 'crime_news_scrapper'

SPIDER_MODULES = ['agent.crime_news_scrapper']
NEWSPIDER_MODULE = 'agent.crime_news_scrapper'

SQLITE_DB_PATH = 'data/crime_data.db' 

ITEM_PIPELINES = {
    'agent.crime_news_scrapper.pipelines.RawArticlePipeline': 300, 
}

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 2
COOKIES_ENABLED = False

DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pl',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(levelname)s: %(message)s'