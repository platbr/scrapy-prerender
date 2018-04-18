# -*- coding: utf-8 -*-
from __future__ import absolute_import
import copy
import scrapy
from scrapy.http import FormRequest

from scrapy_prerender import SlotPolicy
from scrapy_prerender.utils import to_native_str

# XXX: we can't implement PrerenderRequest without middleware support
# because there is no way to set Prerender URL based on settings
# from inside PrerenderRequest.


class PrerenderRequest(scrapy.Request):
    """
    scrapy.Request subclass which instructs Scrapy to render
    the page using Prerender.

    It requires PrerenderMiddleware to work.
    """
    def __init__(self,
                 url=None,
                 callback=None,
                 method='GET',
                 endpoint='render.html',
                 args=None,
                 prerender_url=None,
                 slot_policy=SlotPolicy.PER_DOMAIN,
                 prerender_headers=None,
                 dont_process_response=False,
                 dont_send_headers=False,
                 magic_response=True,
                 session_id='default',
                 http_status_from_error_code=True,
                 cache_args=None,
                 meta=None,
                 **kwargs):

        if url is None:
            url = 'about:blank'
        url = to_native_str(url)

        meta = copy.deepcopy(meta) or {}
        prerender_meta = meta.setdefault('prerender', {})
        prerender_meta.setdefault('endpoint', endpoint)
        prerender_meta.setdefault('slot_policy', slot_policy)
        if prerender_url is not None:
            prerender_meta['prerender_url'] = prerender_url
        if prerender_headers is not None:
            prerender_meta['prerender_headers'] = prerender_headers
        if dont_process_response:
            prerender_meta['dont_process_response'] = True
        else:
            prerender_meta.setdefault('magic_response', magic_response)
        if dont_send_headers:
            prerender_meta['dont_send_headers'] = True
        if http_status_from_error_code:
            prerender_meta['http_status_from_error_code'] = True
        if cache_args is not None:
            prerender_meta['cache_args'] = cache_args

        if session_id is not None:
            if prerender_meta['endpoint'].strip('/') == 'execute':
                prerender_meta.setdefault('session_id', session_id)

        _args = {'url': url}  # put URL to args in order to preserve #fragment
        _args.update(args or {})
        _args.update(prerender_meta.get('args', {}))
        prerender_meta['args'] = _args

        # This is not strictly required, but it strengthens Prerender
        # requests against AjaxCrawlMiddleware
        meta['ajax_crawlable'] = True

        super(PrerenderRequest, self).__init__(url, callback, method, meta=meta,
                                            **kwargs)

    @property
    def _processed(self):
        return self.meta.get('_prerender_processed')

    @property
    def _prerender_args(self):
        return self.meta.get('prerender', {}).get('args', {})

    @property
    def _original_url(self):
        return self._prerender_args.get('url')

    @property
    def _original_method(self):
        return self._prerender_args.get('http_method', 'GET')

    def __str__(self):
        if not self._processed:
            return super(PrerenderRequest, self).__str__()
        return "<%s %s via %s>" % (self._original_method, self._original_url, self.url)

    __repr__ = __str__


class PrerenderFormRequest(PrerenderRequest, FormRequest):
    """
    Use PrerenderFormRequest if you want to make a FormRequest via prerender.
    Accepts the same arguments as PrerenderRequest, and also formdata,
    like FormRequest. First, FormRequest is initialized, and then it's
    url, method and body are passed to PrerenderRequest.
    Note that FormRequest calls escape_ajax on url (via Request._set_url).
    """
    def __init__(self, url=None, callback=None, method=None, formdata=None,
                 body=None, **kwargs):
        # First init FormRequest to get url, body and method
        if formdata:
            FormRequest.__init__(
                self, url=url, method=method, formdata=formdata)
            url, method, body = self.url, self.method, self.body
        # Then pass all other kwargs to PrerenderRequest
        PrerenderRequest.__init__(
            self, url=url, callback=callback, method=method, body=body,
            **kwargs)
