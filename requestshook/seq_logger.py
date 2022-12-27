import os
import sys
import stat
import json

from pathlib import Path
import textwrap
from urllib3.util import parse_url
from requestshook._middleware import Middleware

from requestshook._utils import (
    write_error,
    write_text,
    format_header,
    format_body,
    get_service_from_url,
    get_current_service,
)

PKG_NAME = __package__ or "requestshook"
LOG_PATH = f'/var/log/{PKG_NAME}' 
CONF_PATH = f'/etc'

if os.name == 'nt': 
    LOG_PATH = os.path.expanduser(os.path.join('~', 'log', PKG_NAME))
    CONF_PATH = os.path.expanduser(os.path.join('~', 'conf'))

try:
    # create log path if not exists...
    if not os.path.exists(LOG_PATH):
        os.makedirs(LOG_PATH)
        if os.name == 'posix': os.chmod(LOG_PATH, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
except Exception as e:
    write_error(__name__, e)

class SeqLogger(Middleware):
    def __init__(self, application, conf=None):
        super(SeqLogger, self).__init__(application, conf)
        self.file = os.path.join(LOG_PATH, f'{__name__}.log')
    
    # write request
    # {req.method, req.url, req.headers, req.body, req.environ}
    def process_request(self, req):
        try:
            # write request log
            write_text(self.file, textwrap.dedent("""
            {req_from} >>> REQ {req_to} : {req.method} {url.path}
            {header}

            {body}
            """).format(
                req_from = self.get_request_from(req.headers),
                req_to = get_current_service(),
                req = req,
                url = parse_url(req.url),
                header = format_header(req.headers),
                body = format_body(req.body)
            ))
        except Exception as e:
            write_error(__name__, repr(e))
        finally:
            return None

    # write response
    # {resp.status, resp.body(or text), resp.request}
    def process_response(self, resp):
        try:
            req = resp.request

            req_id = self.get_request_id(req.headers)
            req_from = self.get_request_from(req.headers)
            req_to = self.get_request_to(req.headers)
            service = get_current_service()

            # add requestshook header
            if req_id: resp.headers['x-requestshook-request-id'] = req_id or 'None'
            if req_from: resp.headers['x-requestshook-request-from'] = req_from or 'None'
            if req_to: resp.headers['x-requestshook-request-to'] = req_to or 'None'

            write_text(self.file, textwrap.dedent("""
            {req_from} <<< RESP {service} : {resp.status} {req.method} {url.path}
            {header}

            {body}
            """).format(
                req_from = req_from,
                service = service,
                resp = resp,
                req = req,
                url = parse_url(req.url),
                header = format_header(resp.headers),
                body = format_body(resp.body or resp.text)
            ))
        except Exception as e:
            write_error(__name__, repr(e))
        finally:
            return resp

    def get_request_id(self, headers, fallback = None):
        try:
            return headers.get('x-requestshook-request-id') or fallback
        except:
            return fallback

    def get_request_from(self, headers, fallback = None):
        try:
            return headers.get('x-requestshook-request-from') or fallback
        except:
            return fallback

    def get_request_to(self, headers, fallback = None):
        try:
            return headers.get('x-requestshook-request-to') or fallback
        except:
            return fallback