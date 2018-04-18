Changes
=======

0.7.2 (2017-03-30)
------------------

* fixed issue with response type detection.

0.7.1 (2016-12-20)
------------------

* Scrapy 1.0.x support is back;
* README updates.

0.7 (2016-05-16)
----------------

* ``PRERENDER_COOKIES_DEBUG`` setting allows to log cookies
  sent and received to/from Prerender in ``cookies`` request/response fields.
  It is similar to Scrapy's builtin ``COOKIES_DEBUG``, but works for
  Prerender requests;
* README cleanup.

0.6.1 (2016-04-29)
------------------

* Warning about HTTP methods is no longer logged for non-Prerender requests.

0.6 (2016-04-20)
----------------

* ``PrerenderAwareDupeFilter`` and ``prerender_request_fingerprint`` are improved:
  they now canonicalize URLs and take URL fragments in account;
* ``cache_args`` value fingerprints are now calculated faster.

0.5 (2016-04-18)
----------------

* ``cache_args`` PrerenderRequest argument and
  ``request.meta['prerender']['cache_args']`` key allow to save network traffic
  and disk storage by not storing duplicate Prerender arguments in disk request
  queues and not sending them to Prerender multiple times. This feature requires
  Prerender 2.1+.

To upgrade from v0.4 enable ``PrerenderDeduplicateArgsMiddleware`` in settings.py::

  SPIDER_MIDDLEWARES = {
      'scrapy_prerender.PrerenderDeduplicateArgsMiddleware': 100,
  }

0.4 (2016-04-14)
----------------

* PrerenderFormRequest class is added; it is a variant of FormRequest which uses
  Prerender;
* Prerender parameters are no longer stored in request.meta twice; this change
  should decrease disk queues data size;
* PrerenderMiddleware now increases request priority when rescheduling the request;
  this should decrease disk queue data size and help with stale cookie
  problems.

0.3 (2016-04-11)
----------------

Package is renamed from ``scrapyjs`` to ``scrapy-prerender``.

An easiest way to upgrade is to replace ``scrapyjs`` imports with
``scrapy_prerender`` and update ``settings.py`` with new defaults
(check the README).

There are many new helpers to handle JavaScript rendering transparently;
the recommended way is now to use ``scrapy_prerender.PrerenderRequest`` instead
of  ``request.meta['prerender']``. Please make sure to read the README if
you're upgrading from scrapyjs - you may be able to drop some code from your
project, especially if you want to access response html, handle cookies
and headers.

* new PrerenderRequest class; it can be used as a replacement for scrapy.Request
  to provide a better integration with Prerender;
* added support for POST requests;
* PrerenderResponse, PrerenderTextResponse and PrerenderJsonResponse allow to
  handle Prerender responses transparently, taking care of response.url,
  response.body, response.headers and response.status. PrerenderJsonResponse
  allows to access decoded response JSON data as ``response.data``.
* cookie handling improvements: it is possible to handle Scrapy and Prerender
  cookies transparently; current cookiejar is exposed as response.cookiejar;
* headers are passed to Prerender by default;
* URLs with fragments are handled automatically when using PrerenderRequest;
* logging is improved: ``PrerenderRequest.__repr__`` shows both requested URL
  and Prerender URL;
* in case of Prerender HTTP 400 errors the response is logged by default;
* an issue with dupefilters is fixed: previously the order of keys in
  JSON request body could vary, making requests appear as non-duplicates;
* it is now possible to pass custom headers to Prerender server itself;
* test coverage reports are enabled.

0.2 (2016-03-26)
----------------

* Scrapy 1.0 and 1.1 support;
* Python 3 support;
* documentation improvements;
* project is moved to https://github.com/scrapy-plugins/scrapy-prerender.

0.1.1 (2015-03-16)
------------------

Fixed fingerprint calculation for non-string meta values.

0.1 (2015-02-28)
----------------

Initial release
