# -*- coding: utf-8 -*-

BOT_NAME = 'scrashtest'

SPIDER_MODULES = ['scrashtest.spiders']
NEWSPIDER_MODULE = 'scrashtest.spiders'

DOWNLOADER_MIDDLEWARES = {
    # Engine side
    'scrapy_prerender.PrerenderCookiesMiddleware': 723,
    'scrapy_prerender.PrerenderMiddleware': 725,
    'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
    # Downloader side
}

SPIDER_MIDDLEWARES = {
    'scrapy_prerender.PrerenderDeduplicateArgsMiddleware': 100,
}
PRERENDER_URL = 'http://127.0.0.1:3000/'
# PRERENDER_URL = 'http://192.168.59.103:3000/'
DUPEFILTER_CLASS = 'scrapy_prerender.PrerenderAwareDupeFilter'
HTTPCACHE_STORAGE = 'scrapy_prerender.PrerenderAwareFSCacheStorage'
