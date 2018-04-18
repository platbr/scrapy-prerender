# -*- coding: utf-8 -*-
"""
To handle "prerender" Request meta key properly a custom DupeFilter must be set.
See https://github.com/scrapy/scrapy/issues/900 for more info.
"""
from __future__ import absolute_import
from copy import deepcopy

try:
    from scrapy.dupefilters import RFPDupeFilter
except ImportError:
    # scrapy < 1.0
    from scrapy.dupefilter import RFPDupeFilter

from scrapy.utils.url import canonicalize_url
from scrapy.utils.request import request_fingerprint

from .utils import dict_hash


def prerender_request_fingerprint(request, include_headers=None):
    """ Request fingerprint which takes 'prerender' meta key into account """

    fp = request_fingerprint(request, include_headers=include_headers)
    if 'prerender' not in request.meta:
        return fp

    prerender_options = deepcopy(request.meta['prerender'])
    args = prerender_options.setdefault('args', {})

    if 'url' in args:
        args['url'] = canonicalize_url(args['url'], keep_fragments=True)

    return dict_hash(prerender_options, fp)


class PrerenderAwareDupeFilter(RFPDupeFilter):
    """
    DupeFilter that takes 'prerender' meta key in account.
    It should be used with PrerenderMiddleware.
    """
    def request_fingerprint(self, request):
        return prerender_request_fingerprint(request)
