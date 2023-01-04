import configparser
import json
import os
import webob.dec
import webob.exc

import textwrap
import uuid
from urllib3.util import parse_url

from requestshook.utils import (
    CONF_FILE_PATH,
    LOG_FILE_PATH,
    DIAGRAM_FILE_PATH,
    DOC_FILE_PATH,
    write_syslog,
    write_text,
    format_header,
    format_body,
    get_current_service,
    get_request_id,
    get_request_from,
    get_user_agent,
    add_request_id,
    add_request_from,
)

from requestshook.should_not_hook import should_not_hook

# requestshook logger middleware class
class RequestsHookMiddleware(object):

    def __init__(self, application, conf = None):
        self.application = application
        self.conf = conf or {}
        self.service = get_current_service() or 'unknown'

    @classmethod
    def factory(cls, global_conf, **local_conf):
        conf = global_conf.copy() if global_conf else {}
        conf.update(local_conf)

        def middleware_filter(app):
            return cls(app, conf)

        return middleware_filter

    @webob.dec.wsgify
    def __call__(self, req):

        # requestshook enabled?
        cfg = configparser.ConfigParser()
        cfg.read(CONF_FILE_PATH)
        enabled = cfg.getboolean('DEFAULT', 'enabled', fallback=False)
        if not enabled:
            return req.get_response(self.application)

        # should not hook for this request?
        if should_not_hook(get_request_from(req.headers, get_user_agent(req.headers)), self.service, req.method, req.url):
            write_syslog("ignoring request for", req.method, req.url)
            return req.get_response(self.application)

        # process request
        response = self.process_request(req)
        if response: return response

        # get response for the request from middleware pipeline
        response = req.get_response(self.application)
        response.request = req

        # process response
        try:
            return self.process_response(response)
        except webob.exc.HTTPException as e:
            write_syslog(f'HTTPException! e={e}')
            return e
        except Exception as e:
            write_syslog(f'Exception! e={e}')
            return e

    # process request header
    def on_process_request_header(self, req):
        req_id = get_request_id(req.headers)
        if not req_id: add_request_id(req.headers, uuid.uuid4().hex)

        req_from = get_request_from(req.headers)
        if not req_from: add_request_from(req.headers, get_user_agent(req.headers, 'unknown'))

    # process response header
    def on_process_response_header(self, resp):

        # add requestshook headers to response
        add_request_id(resp.headers, get_request_id(resp.request.headers, 'None'))
        add_request_from(resp.headers, get_request_from(resp.request.headers) or get_user_agent(resp.request.headers, 'unknown'))

    # write request
    def process_request(self, req):
        try:
            # process header
            self.on_process_request_header(req)

            # write request information
            LogWriter(req = req).write_request()

        except Exception as e:
            write_syslog(f'exception! e={e}')

        return None

    # write response
    def process_response(self, resp):
        try:
            # process resposne header
            self.on_process_response_header(resp)

            # write response information
            LogWriter(resp = resp).write_response()

        except Exception as e:
            write_syslog(f'exception! e={e}')

        return resp

# formatted log writer class
class LogWriter(object):
    def __init__(self, req = None, resp = None):

        # should be one of req or resp
        if (req and resp) or (not req and not resp): 
            raise Exception('wrong usage')

        self.resp = resp
        self.req = resp.request if resp else req
        self.service = get_current_service() or 'unknown'
        self.headers = resp.headers if resp else req.headers
        self.req_id = get_request_id(self.headers, 'none')
        self.req_from = get_request_from(self.headers, 'unknown')
        self.url = parse_url(self.req.url)
        self.header = format_header(self.headers)
        self.body = format_body(resp or req)

    def get_service_name_for_diagram(self, service):
        return service

    # write request
    def write_request(self):
        self.write_request_log()
        self.write_request_diagram()
        self.write_request_markdown()

    # write response
    def write_response(self):
        self.write_response_log()
        self.write_response_diagram()
        self.write_response_markdown()

    # write request log
    def write_request_log(self):
        write_text(LOG_FILE_PATH, textwrap.dedent("""
        ### ({self.req_from}) REQ >>> ({self.service}) : {self.req.method} {self.url}
        {self.header}

        {self.body}
        """).format(self=self))

    # write response log
    def write_response_log(self):
        write_text(LOG_FILE_PATH, textwrap.dedent("""
        ### ({self.req_from}) RESP <<< ({self.service}) : {self.resp.status} {self.req.method} {self.url}
        {self.header}

        {self.body}
        """).format(self=self))

    # write request diagram
    def write_request_diagram(self):
        write_text(DIAGRAM_FILE_PATH, f'{self.req_from}->>{self.service}: {self.req.method} {self.url.path}')

    # write response diagram
    def write_response_diagram(self):
        write_text(DIAGRAM_FILE_PATH, f'{self.service}-->>{self.req_from}: {self.resp.status} {self.url.path}')

    # write request markdown
    def write_request_markdown(self):
        write_text(DOC_FILE_PATH, textwrap.dedent("""
            ### {self.req.method} {self.url.path}
            `{self.req_from}` --> `{self.service}`

            === "Header"
                ``` http title="{self.req.method} {self.url.path}" linenums="1"
            {header}
                ```

            === "Body"
                ``` json title="{self.req.method} {self.url.path}" linenums="1"
            {body}
                ```
        """).format(
            self=self,
            header = textwrap.indent(self.header or 'none', ' '*4),
            body = textwrap.indent(self.body or 'none', ' '*4)
            ))

    # write response markdown
    def write_response_markdown(self):
        write_text(DOC_FILE_PATH, textwrap.dedent("""
            ### {self.resp.status} {self.url.path}
            `{self.req_from}` <-- `{self.service}`

            === "Header"
                ``` http title="{self.resp.status} {self.url.path}" linenums="1"
            {header}
                ```

            === "Body"
                ``` json title="{self.resp.status} {self.url.path}" linenums="1"
            {body}
                ```
        """).format(
            self=self,
            header = textwrap.indent(self.header, ' '*4),
            body = textwrap.indent(self.body, ' '*4)
            ))
