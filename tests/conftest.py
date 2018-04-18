import os

import pytest
from scrapy.settings import Settings


@pytest.fixture()
def settings(request):
    """ Default scrapy-prerender settings """
    s = dict(
        # collect scraped items to .collected_items attribute
        ITEM_PIPELINES={
            'tests.utils.CollectorPipeline': 100,
        },

        # scrapy-prerender settings
        PRERENDER_URL=os.environ.get('PRERENDER_URL'),
        DOWNLOADER_MIDDLEWARES={
            # Engine side
            'scrapy_prerender.PrerenderCookiesMiddleware': 723,
            'scrapy_prerender.PrerenderMiddleware': 725,
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
            # Downloader side
        },
        SPIDER_MIDDLEWARES={
            'scrapy_prerender.PrerenderDeduplicateArgsMiddleware': 100,
        },
        DUPEFILTER_CLASS='scrapy_prerender.PrerenderAwareDupeFilter',
        HTTPCACHE_STORAGE='scrapy_prerender.PrerenderAwareFSCacheStorage',
    )
    return Settings(s)


