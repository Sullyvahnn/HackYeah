# Scrapy settings for crime_news_scrapper
BOT_NAME = 'crime_news_scrapper'

SPIDER_MODULES = ['agent.crime_news_scrapper']
NEWSPIDER_MODULE = 'agent.crime_news_scrapper'
# ===============================================
# A. DATABASE CONFIGURATION (NEW) 💾
# ===============================================

# Path to the SQLite database file. 
# The Pipeline will read this to initialize DB_MANAGER.
# Ensure the 'data/' directory exists in your project root.
SQLITE_DB_PATH = 'data/crime_data.db' 

# ===============================================
# B. PIPELINE ACTIVATION (NEW) 🔗
# ===============================================

# Configure Item Pipelines. The key is the full import path to your Pipeline class.
# The value (300) sets the order of execution.
ITEM_PIPELINES = {
    'crime_news_scrapper.pipelines.RawArticlePipeline': 300, 
}

# ===============================================
# C. DEFAULT SCRAPY SETTINGS (UNCHANGED/REVIEWED)
# ===============================================

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests
CONCURRENT_REQUESTS = 4

# Configure a delay for requests
DOWNLOAD_DELAY = 2

# Disable cookies
COOKIES_ENABLED = False

# Override the default request headers
DEFAULT_REQUEST_HEADERS = {
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'pl',
}

# LOG
LOG_LEVEL = 'INFO'