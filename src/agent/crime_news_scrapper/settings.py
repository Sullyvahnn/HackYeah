# Scrapy settings for crime_news_scrapper
# Dokumentacja: https://docs.scrapy.org/en/latest/topics/settings.html

BOT_NAME = 'crime_news_scrapper'

SPIDER_MODULES = ['agent.crime_news_scrapper']
NEWSPIDER_MODULE = 'agent.crime_news_scrapper'

# Crawl responsibly
ROBOTSTXT_OBEY = False
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Configure delays
DOWNLOAD_DELAY = 3
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# Disable cookies
COOKIES_ENABLED = False

# Configure logging
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

# Item pipelines
ITEM_PIPELINES = {}

# Enable stats collection
STATS_CLASS = 'scrapy.statscollectors.MemoryStatsCollector'