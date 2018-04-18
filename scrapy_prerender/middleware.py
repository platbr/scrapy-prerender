# -*- coding: utf-8 -*-
from __future__ import absolute_import

import copy
import json
import logging
import warnings
from collections import defaultdict

from six.moves.urllib.parse import urljoin
from six.moves.http_cookiejar import CookieJar

import scrapy
from scrapy.exceptions import NotConfigured
from scrapy.http.headers import Headers
from scrapy.http.response.text import TextResponse
from scrapy import signals

from scrapy_prerender.responsetypes import responsetypes
from scrapy_prerender.cookies import jar_to_har, har_to_jar
from scrapy_prerender.utils import (
    scrapy_headers_to_unicode_dict,
    json_based_hash,
    parse_x_prerender_saved_arguments_header,
)
from scrapy_prerender.response import get_prerender_status, get_prerender_headers


logger = logging.getLogger(__name__)


class SlotPolicy(object):
    PER_DOMAIN = 'per_domain'
    SINGLE_SLOT = 'single_slot'
    SCRAPY_DEFAULT = 'scrapy_default'

    _known = {PER_DOMAIN, SINGLE_SLOT, SCRAPY_DEFAULT}


class PrerenderCookiesMiddleware(object):
    """
    This downloader middleware maintains cookiejars for Prerender requests.

    It gets cookies from 'cookies' field in Prerender JSON responses
    and sends current cookies in 'cookies' JSON POST argument instead of
    sending them in http headers.

    It should process requests before PrerenderMiddleware, and process responses
    after PrerenderMiddleware.
    """
    def __init__(self, debug=False):
        self.jars = defaultdict(CookieJar)
        self.debug = debug

    @classmethod
    def from_crawler(cls, crawler):
        return cls(debug=crawler.settings.getbool('PRERENDER_COOKIES_DEBUG'))

    def process_request(self, request, spider):
        """
        For Prerender requests add 'cookies' key with current
        cookies to ``request.meta['prerender']['args']`` and remove cookie
        headers sent to Prerender itself.
        """
        if 'prerender' not in request.meta:
            return

        if request.meta.get('_prerender_processed'):
            request.headers.pop('Cookie', None)
            return

        prerender_options = request.meta['prerender']

        prerender_args = prerender_options.setdefault('args', {})
        if 'cookies' in prerender_args:  # cookies already set
            return

        if 'session_id' not in prerender_options:
            return

        jar = self.jars[prerender_options['session_id']]

        cookies = self._get_request_cookies(request)
        har_to_jar(jar, cookies)

        prerender_args['cookies'] = jar_to_har(jar)
        self._debug_cookie(request, spider)

    def process_response(self, request, response, spider):
        """
        For Prerender JSON responses add all cookies from
        'cookies' in a response to the cookiejar.
        """
        from scrapy_prerender import PrerenderJsonResponse
        if not isinstance(response, PrerenderJsonResponse):
            return response

        if 'cookies' not in response.data:
            return response

        if 'prerender' not in request.meta:
            return response

        if not request.meta.get('_prerender_processed'):
            warnings.warn("PrerenderCookiesMiddleware requires PrerenderMiddleware")
            return response

        prerender_options = request.meta['prerender']
        session_id = prerender_options.get('new_session_id',
                                        prerender_options.get('session_id'))
        if session_id is None:
            return response

        jar = self.jars[session_id]
        request_cookies = prerender_options['args'].get('cookies', [])
        har_to_jar(jar, response.data['cookies'], request_cookies)
        self._debug_set_cookie(response, spider)
        response.cookiejar = jar
        return response

    def _get_request_cookies(self, request):
        if isinstance(request.cookies, dict):
            return [
                {'name': k, 'value': v} for k, v in request.cookies.items()
            ]
        return request.cookies or []

    def _debug_cookie(self, request, spider):
        if self.debug:
            cl = request.meta['prerender']['args']['cookies']
            if cl:
                cookies = '\n'.join(
                    'Cookie: {}'.format(self._har_repr(c)) for c in cl)
                msg = 'Sending cookies to: {}\n{}'.format(request, cookies)
                logger.debug(msg, extra={'spider': spider})

    def _debug_set_cookie(self, response, spider):
        if self.debug:
            cl = response.data['cookies']
            if cl:
                cookies = '\n'.join(
                    'Set-Cookie: {}'.format(self._har_repr(c)) for c in cl)
                msg = 'Received cookies from: {}\n{}'.format(response, cookies)
                logger.debug(msg, extra={'spider': spider})

    @staticmethod
    def _har_repr(har_cookie):
        return '{}={}'.format(har_cookie['name'], har_cookie['value'])


class PrerenderDeduplicateArgsMiddleware(object):
    """
    Spider middleware which allows not to store duplicate Prerender argument
    values in request queue. It works together with PrerenderMiddleware downloader
    middleware.
    """
    local_values_key = '_prerender_local_values'

    def process_spider_output(self, response, result, spider):
        for el in result:
            if isinstance(el, scrapy.Request):
                yield self._process_request(el, spider)
            else:
                yield el

    def process_start_requests(self, start_requests, spider):
        if not hasattr(spider, 'state'):
            spider.state = {}
        spider.state.setdefault(self.local_values_key, {})  # fingerprint => value dict

        for req in start_requests:
            yield self._process_request(req, spider)

    def _process_request(self, request, spider):
        """
        Replace requested meta['prerender']['args'] values with their fingerprints.
        This allows to store values only once in request queue, which helps
        with disk queue size.

        Downloader middleware should restore the values from fingerprints.
        """
        if 'prerender' not in request.meta:
            return request

        if '_replaced_args' in request.meta['prerender']:
            # don't process re-scheduled requests
            # XXX: does it work as expected?
            warnings.warn("Unexpected request.meta['prerender']['_replaced_args']")
            return request

        request.meta['prerender']['_replaced_args'] = []
        cache_args = request.meta['prerender'].get('cache_args', [])
        args = request.meta['prerender'].setdefault('args', {})

        for name in cache_args:
            if name not in args:
                continue
            value = args[name]
            fp = 'LOCAL+' + json_based_hash(value)
            spider.state[self.local_values_key][fp] = value
            args[name] = fp
            request.meta['prerender']['_replaced_args'].append(name)

        return request


class PrerenderMiddleware(object):
    """
    Scrapy downloader and spider middleware that passes requests
    through Prerender when 'prerender' Request.meta key is set.

    This middleware also works together with PrerenderDeduplicateArgsMiddleware
    spider middleware to allow not to store duplicate Prerender argument values
    in request queue and not to send them multiple times to Prerender
    (the latter requires Prerender 2.1+).
    """
    default_prerender_url = 'http://127.0.0.1:8050'
    default_endpoint = "render.json"
    prerender_extra_timeout = 5.0
    default_policy = SlotPolicy.PER_DOMAIN
    rescheduling_priority_adjust = +100
    retry_498_priority_adjust = +50
    remote_keys_key = '_prerender_remote_keys'

    def __init__(self, crawler, prerender_base_url, slot_policy, log_400):
        self.crawler = crawler
        self.prerender_base_url = prerender_base_url
        self.slot_policy = slot_policy
        self.log_400 = log_400
        self.crawler.signals.connect(self.spider_opened, signals.spider_opened)

    @classmethod
    def from_crawler(cls, crawler):
        prerender_base_url = crawler.settings.get('PRERENDER_URL',
                                               cls.default_prerender_url)
        log_400 = crawler.settings.getbool('PRERENDER_LOG_400', True)
        slot_policy = crawler.settings.get('PRERENDER_SLOT_POLICY',
                                           cls.default_policy)
        if slot_policy not in SlotPolicy._known:
            raise NotConfigured("Incorrect slot policy: %r" % slot_policy)

        return cls(crawler, prerender_base_url, slot_policy, log_400)

    def spider_opened(self, spider):
        if not hasattr(spider, 'state'):
            spider.state = {}

        # local fingerprint => key returned by prerender
        spider.state.setdefault(self.remote_keys_key, {})

    @property
    def _argument_values(self):
        key = PrerenderDeduplicateArgsMiddleware.local_values_key
        return self.crawler.spider.state[key]

    @property
    def _remote_keys(self):
        return self.crawler.spider.state[self.remote_keys_key]

    def process_request(self, request, spider):
        if 'prerender' not in request.meta:
            return

        if request.method not in {'GET', 'POST'}:
            logger.warning(
                "Currently only GET and POST requests are supported by "
                "PrerenderMiddleware; %(request)s will be handled without Prerender",
                {'request': request},
                extra={'spider': spider}
            )
            return request

        if request.meta.get("_prerender_processed"):
            # don't process the same request more than once
            return

        prerender_options = request.meta['prerender']
        request.meta['_prerender_processed'] = True

        slot_policy = prerender_options.get('slot_policy', self.slot_policy)
        self._set_download_slot(request, request.meta, slot_policy)

        args = prerender_options.setdefault('args', {})

        if '_replaced_args' in prerender_options:
            # restore arguments before sending request to the downloader
            load_args = {}
            save_args = []
            local_arg_fingerprints = {}
            for name in prerender_options['_replaced_args']:
                fp = args[name]
                # Use remote Prerender argument cache: if Prerender key
                # for a value is known then don't send the value to Prerender;
                # if it is unknown then try to save the value on server using
                # ``save_args``.
                if fp in self._remote_keys:
                    load_args[name] = self._remote_keys[fp]
                    del args[name]
                else:
                    save_args.append(name)
                    args[name] = self._argument_values[fp]

                local_arg_fingerprints[name] = fp

            if load_args:
                args['load_args'] = load_args
            if save_args:
                args['save_args'] = save_args
            prerender_options['_local_arg_fingerprints'] = local_arg_fingerprints

            del prerender_options['_replaced_args']  # ??

        args.setdefault('url', request.url)
        if request.method == 'POST':
            args.setdefault('http_method', request.method)
            # XXX: non-UTF8 request bodies are not supported now
            args.setdefault('body', request.body.decode('utf8'))

        if not prerender_options.get('dont_send_headers'):
            headers = scrapy_headers_to_unicode_dict(request.headers)
            if headers:
                args.setdefault('headers', headers)

        body = json.dumps(args, ensure_ascii=False, sort_keys=True, indent=4)
        # print(body)

        if 'timeout' in args:
            # User requested a Prerender timeout explicitly.
            #
            # We can't catch a case when user requested `download_timeout`
            # explicitly because a default value for `download_timeout`
            # is set by DownloadTimeoutMiddleware.
            #
            # As user requested Prerender timeout explicitly, we shouldn't change
            # it. Another reason not to change the requested Prerender timeout is
            # because it may cause a validation error on the remote end.
            #
            # But we can change Scrapy `download_timeout`: increase
            # it when it's too small. Decreasing `download_timeout` is not
            # safe.

            timeout_requested = float(args['timeout'])
            timeout_expected = timeout_requested + self.prerender_extra_timeout

            # no timeout means infinite timeout
            timeout_current = request.meta.get('download_timeout', 1e6)

            if timeout_expected > timeout_current:
                request.meta['download_timeout'] = timeout_expected

        endpoint = prerender_options.setdefault('endpoint', self.default_endpoint)
        prerender_base_url = prerender_options.get('prerender_url', self.prerender_base_url)
        prerender_url = urljoin(prerender_base_url, endpoint)

        headers = Headers({'Content-Type': 'application/json'})
        headers.update(prerender_options.get('prerender_headers', {}))
        new_request = request.replace(
            url=prerender_url,
            method='POST',
            body=body,
            headers=headers,
            priority=request.priority + self.rescheduling_priority_adjust
        )
        self.crawler.stats.inc_value('prerender/%s/request_count' % endpoint)
        return new_request

    def process_response(self, request, response, spider):
        if not request.meta.get("_prerender_processed"):
            return response

        prerender_options = request.meta['prerender']
        if not prerender_options:
            return response

        # update stats
        endpoint = prerender_options['endpoint']
        self.crawler.stats.inc_value(
            'prerender/%s/response_count/%s' % (endpoint, response.status)
        )

        # handle save_args/load_args
        self._process_x_prerender_saved_arguments(request, response)
        if get_prerender_status(response) == 498:
            logger.debug("Got HTTP 498 response for {}; "
                         "sending arguments again.".format(request),
                         extra={'spider': spider})
            return self._498_retry_request(request, response)

        if prerender_options.get('dont_process_response', False):
            return response

        response = self._change_response_class(request, response)

        if self.log_400 and get_prerender_status(response) == 400:
            self._log_400(request, response, spider)

        return response

    def _change_response_class(self, request, response):
        from scrapy_prerender import PrerenderResponse, PrerenderTextResponse
        if not isinstance(response, (PrerenderResponse, PrerenderTextResponse)):
            # create a custom Response subclass based on response Content-Type
            # XXX: usually request is assigned to response only when all
            # downloader middlewares are executed. Here it is set earlier.
            # Does it have any negative consequences?
            respcls = responsetypes.from_args(headers=response.headers)
            if isinstance(response, TextResponse) and respcls is PrerenderResponse:
                # Even if the headers say it's binary, it has already
                # been detected as a text response by scrapy (for example
                # because it was decoded successfully), so we should not
                # convert it to PrerenderResponse.
                respcls = PrerenderTextResponse
            response = response.replace(cls=respcls, request=request)
        return response

    def _log_400(self, request, response, spider):
        from scrapy_prerender import PrerenderJsonResponse
        if isinstance(response, PrerenderJsonResponse):
            logger.warning(
                "Bad request to Prerender: %s" % response.data,
                {'request': request},
                extra={'spider': spider}
            )

    def _process_x_prerender_saved_arguments(self, request, response):
        """ Keep track of arguments saved by Prerender. """
        saved_args = get_prerender_headers(response).get(b'X-Prerender-Saved-Arguments')
        if not saved_args:
            return
        saved_args = parse_x_prerender_saved_arguments_header(saved_args)
        arg_fingerprints = request.meta['prerender']['_local_arg_fingerprints']
        for name, key in saved_args.items():
            fp = arg_fingerprints[name]
            self._remote_keys[fp] = key

    def _498_retry_request(self, request, response):
        """
        Return a retry request for HTTP 498 responses. HTTP 498 means
        load_args are not present on server; client should retry the request
        with full argument values instead of their hashes.
        """
        meta = copy.deepcopy(request.meta)
        local_arg_fingerprints = meta['prerender']['_local_arg_fingerprints']
        args = meta['prerender']['args']
        args.pop('load_args', None)
        args['save_args'] = list(local_arg_fingerprints.keys())

        for name, fp in local_arg_fingerprints.items():
            args[name] = self._argument_values[fp]
            # print('remote_keys before:', self._remote_keys)
            self._remote_keys.pop(fp, None)
            # print('remote_keys after:', self._remote_keys)

        body = json.dumps(args, ensure_ascii=False, sort_keys=True, indent=4)
        # print(body)
        request = request.replace(
            meta=meta,
            body=body,
            priority=request.priority+self.retry_498_priority_adjust
        )
        return request

    def _set_download_slot(self, request, meta, slot_policy):
        if slot_policy == SlotPolicy.PER_DOMAIN:
            # Use the same download slot to (sort of) respect download
            # delays and concurrency options.
            meta['download_slot'] = self._get_slot_key(request)

        elif slot_policy == SlotPolicy.SINGLE_SLOT:
            # Use a single slot for all Prerender requests
            meta['download_slot'] = '__prerender__'

        elif slot_policy == SlotPolicy.SCRAPY_DEFAULT:
            # Use standard Scrapy concurrency setup
            pass

    def _get_slot_key(self, request_or_response):
        return self.crawler.engine.downloader._get_slot_key(
            request_or_response, None
        )
