# -*- coding: utf-8 -*-
from __future__ import absolute_import

from scrapy.http import Response
from scrapy.responsetypes import ResponseTypes

import scrapy_prerender


class PrerenderResponseTypes(ResponseTypes):
    CLASSES = {
        'text/html': 'scrapy_prerender.response.PrerenderTextResponse',
        'application/atom+xml': 'scrapy_prerender.response.PrerenderTextResponse',
        'application/rdf+xml': 'scrapy_prerender.response.PrerenderTextResponse',
        'application/rss+xml': 'scrapy_prerender.response.PrerenderTextResponse',
        'application/xhtml+xml': 'scrapy_prerender.response.PrerenderTextResponse',
        'application/vnd.wap.xhtml+xml': 'scrapy_prerender.response.PrerenderTextResponse',
        'application/xml': 'scrapy_prerender.response.PrerenderTextResponse',
        'application/json': 'scrapy_prerender.response.PrerenderJsonResponse',
        'application/x-json': 'scrapy_prerender.response.PrerenderJsonResponse',
        'application/javascript': 'scrapy_prerender.response.PrerenderTextResponse',
        'application/x-javascript': 'scrapy_prerender.response.PrerenderTextResponse',
        'text/xml': 'scrapy_prerender.response.PrerenderTextResponse',
        'text/*': 'scrapy_prerender.response.PrerenderTextResponse',
    }

    def from_args(self, headers=None, url=None, filename=None, body=None):
        """Guess the most appropriate Response class based on
        the given arguments."""
        cls = super(PrerenderResponseTypes, self).from_args(
            headers=headers,
            url=url,
            filename=filename,
            body=body
        )
        if cls is Response:
            cls = scrapy_prerender.PrerenderResponse
        return cls


responsetypes = PrerenderResponseTypes()
