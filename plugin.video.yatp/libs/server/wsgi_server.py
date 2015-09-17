# coding: utf-8
# Module: wsgi_server
# Created on: 01.07.2015
# Author: Roman Miroshnychenko aka Roman V.M. (romanvm@yandex.ua)
# License: GPL v.3 https://www.gnu.org/copyleft/gpl.html
"""
Custom WSGI Server and RequestHandler
"""

import sys
import threading
import Queue
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler


class ThreadPoolMixin:
    """
    Mixin to use a fixed pool of threads to handle requests.
    .. note::
       When shutting down the server, please ensure you call this mixin's
       `join()` to shut down the pool along with the server's `shutdown()`
       method. The order in which these are performed is not significant,
       but both actions must be performed.
    """

    # Size of pool.
    pool_size = 5

    # How long to wait on an empty queue, in seconds. Can be a float.
    timeout_on_get = 0.2

    def __init__(self):
        self._request_queue = Queue.Queue(self.pool_size)
        # This beastie serves a different purpose than __shutdown_request
        # and __is_shut_down: those are superprivate so we can't touch them,
        # and even if we could, they're not really useful in shutting down
        # the pool.
        self._shutdown_event = threading.Event()
        for i in xrange(self.pool_size):
            thread = threading.Thread(target=self.process_request_thread)
            thread.daemon = True
            thread.start()

    def process_request_thread(self):
        """Same as in BaseServer, but as a thread."""
        while True:
            try:
                request, client_address = self._request_queue.get(
                    timeout=self.timeout_on_get,
                )
            except Queue.Empty:
                # You wouldn't believe how much crap this can end up leaking,
                # so we clear the exception.
                sys.exc_clear()
                if self._shutdown_event.isSet():
                    return
                continue
            try:
                self.finish_request(request, client_address)
            except:
                self.handle_error(request, client_address)
            finally:
                self.shutdown_request(request)
            self._request_queue.task_done()

    def process_request(self, request, client_address):
        """Queue the given request."""
        self._request_queue.put((request, client_address))

    def join(self):
        """Wait on the pool to clear and shut down the worker threads."""
        # A nicer place for this would be shutdown(), but this being a mixin,
        # that method can't safely do anything with that method, thus we add
        # an extra method explicitly for clearing the queue and shutting
        # down the workers.
        self._request_queue.join()
        self._shutdown_event.set()


class CustomWSGIRequestHandler(WSGIRequestHandler):
    """Custom WSGI Request Handler"""
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args, **kwargs):
        """Disable log messages"""
        pass


class ThreadedWSGIServer(ThreadPoolMixin, WSGIServer):
    """Multi-threaded WSGI server"""
    allow_reuse_address = True

    def __init__(self, *args, **kwargs):
        ThreadPoolMixin.__init__(self)
        WSGIServer.__init__(self, *args, **kwargs)


def create_server(app, host='', port=8668):
    """
    Create a new WSGI server listening on 'host' and 'port' for WSGI app
    """
    httpd = ThreadedWSGIServer((host, port), CustomWSGIRequestHandler)
    httpd.set_app(app)
    return httpd
