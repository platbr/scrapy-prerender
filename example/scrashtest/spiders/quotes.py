# -*- coding: utf-8 -*-
import scrapy
from scrapy.linkextractors import LinkExtractor

from scrapy_prerender import PrerenderRequest


class QuotesSpider(scrapy.Spider):
    name = "quotes"
    allowed_domains = ["toscrape.com"]
    start_urls = ['http://quotes.toscrape.com/']

    # http_user = 'prerender-user'
    # http_pass = 'prerender-password'

    def parse(self, response):
        le = LinkExtractor()
        for link in le.extract_links(response):
            yield PrerenderRequest(
                link.url,
                self.parse_link,
                endpoint='render.json',
                args={
                    'har': 1,
                    'html': 1,
                }
            )

    def parse_link(self, response):
        print("PARSED", response.real_url, response.url)
        print(response.css("title").extract())
        print(response.data["har"]["log"]["pages"])
        print(response.headers.get('Content-Type'))
