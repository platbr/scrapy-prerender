# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import base64
import re

from scrapy.http import Response, TextResponse
from scrapy import Selector

from scrapy_prerender.utils import headers_to_scrapy


def get_prerender_status(resp):
    return getattr(resp, 'prerender_response_status', resp.status)


def get_prerender_headers(resp):
    return getattr(resp, 'prerender_response_headers', resp.headers)


class _PrerenderResponseMixin(object):
    """
    This mixin fixes response.url and adds response.real_url
    """
    def __init__(self, url, *args, **kwargs):
        real_url = kwargs.pop('real_url', None)
        if real_url is not None:
            self.real_url = real_url
        else:
            self.real_url = None
            # FIXME: create a .request @property with a setter?
            # Scrapy doesn't pass request to Response constructor;
            # it is worked around in PrerenderMiddleware.
            request = kwargs['request']
            prerender_args = self._prerender_args(request)
            _url = prerender_args.get('url')
            if _url is not None:
                self.real_url = url
                url = _url
        self.prerender_response_status = kwargs.pop('prerender_response_status',
                                                 None)
        self.prerender_response_headers = kwargs.pop('prerender_response_headers',
                                                  None)
        super(_PrerenderResponseMixin, self).__init__(url, *args, **kwargs)
        if self.prerender_response_status is None:
            self.prerender_response_status = self.status
        if self.prerender_response_headers is None:
            self.prerender_response_headers = self.headers.copy()

    def replace(self, *args, **kwargs):
        """Create a new Response with the same attributes except for those
        given new values.
        """
        for x in ['url', 'status', 'headers', 'body', 'request', 'flags',
                  'real_url', 'prerender_response_status',
                  'prerender_response_headers']:
            kwargs.setdefault(x, getattr(self, x))
        cls = kwargs.pop('cls', self.__class__)
        return cls(*args, **kwargs)

    def _prerender_options(self, request=None):
        if request is None:
            request = self.request
        return request.meta.get("prerender", {})

    def _prerender_args(self, request=None):
        return self._prerender_options(request).get('args', {})


class PrerenderResponse(_PrerenderResponseMixin, Response):
    """
    This Response subclass sets response.url to the URL of a remote website
    instead of an URL of Prerender server. "Real" response URL is still available
    as ``response.real_url``.
    """


class PrerenderTextResponse(_PrerenderResponseMixin, TextResponse):
    """
    This TextResponse subclass sets response.url to the URL of a remote website
    instead of an URL of Prerender server. "Real" response URL is still available
    as ``response.real_url``.
    """
    def replace(self, *args, **kwargs):
        kwargs.setdefault('encoding', self.encoding)
        return _PrerenderResponseMixin.replace(self, *args, **kwargs)


class PrerenderJsonResponse(PrerenderResponse):
    """
    Prerender Response with JSON data. It provides a convenient way to access
    parsed JSON response using ``response.data`` attribute and exposes
    current Prerender cookiejar when it is available.

    If Scrapy-Prerender response magic is enabled in request
    (['prerender']['magic_response'] is not False), several other response
    attributes (headers, body, url, status code) are set automatically:

    * response.url is set to the value of 'url' key, original url is
      available as ``responce.real_url``;
    * response.headers are filled from 'headers' keys; original headers are
      available as ``response.prerender_response_headers``;
    * response.status is set from the value of 'http_status' key; original
      status is available as ``response.prerender_response_status``;
    * response.body is set to the value of 'html' key,
      or to base64-decoded value of 'body' key;
    """
    def __init__(self, *args, **kwargs):
        self.cookiejar = None
        self._cached_ubody = None
        self._cached_data = None
        self._cached_selector = None
        kwargs.pop('encoding', None)  # encoding is always utf-8
        super(PrerenderJsonResponse, self).__init__(*args, **kwargs)

        # FIXME: it assumes self.request is set
        if self._prerender_options().get('magic_response', True):
            self._load_from_json()

    @property
    def data(self):
        if self._cached_data is None:
            self._cached_data = json.loads(self._ubody)
        return self._cached_data

    @property
    def text(self):
        return self._ubody

    def body_as_unicode(self):
        return self._ubody

    @property
    def _ubody(self):
        if self._cached_ubody is None:
            self._cached_ubody = self.body.decode(self.encoding)
        return self._cached_ubody

    @property
    def encoding(self):
        return 'utf8'

    @property
    def selector(self):
        if self._cached_selector is None:
            self._cached_selector = Selector(text=self.text, type='html')
        return self._cached_selector

    def xpath(self, query):
        return self.selector.xpath(query)

    def css(self, query):
        return self.selector.css(query)

    def _load_from_json(self):
        """ Fill response attributes from JSON results """

        # response.status
        if 'http_status' in self.data:
            self.status = int(self.data['http_status'])
        elif self._prerender_options().get('http_status_from_error_code', False):
            if 'error' in self.data:
                try:
                    error = self.data['info']['error']
                except KeyError:
                    error = ''
                http_code_m = re.match(r'http(\d{3})', error)
                if http_code_m:
                    self.status = int(http_code_m.group(1))

        # response.url
        if 'url' in self.data:
            self._url = self.data['url']

        # response.body
        if 'body' in self.data:
            self._body = base64.b64decode(self.data['body'])
            self._cached_ubody = self._body.decode(self.encoding)
        elif 'html' in self.data:
            self._cached_ubody = self.data['html']
            self._body = self._cached_ubody.encode(self.encoding)
            self.headers[b"Content-Type"] = b"text/html; charset=utf-8"

        # response.headers
        if 'headers' in self.data:
            self.headers = headers_to_scrapy(self.data['headers'])
