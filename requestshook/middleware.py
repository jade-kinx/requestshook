import os
import stat
import webob.dec
import webob.exc

import textwrap
import uuid
from urllib3.util import parse_url

from requestshook.utils import (
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

PKG_NAME = __package__ or "requestshook"
LOG_PATH = f'/var/log/{PKG_NAME}' 
CONF_PATH = f'/etc'

if os.name == 'nt': 
    LOG_PATH = os.path.expanduser(os.path.join('~', 'log', PKG_NAME))
    CONF_PATH = os.path.expanduser(os.path.join('~', 'conf'))

LOG_FILE_PATH = os.path.join(LOG_PATH, f'{PKG_NAME}.log')
CONF_FILE_PATH = os.path.join(CONF_PATH, f'{PKG_NAME}.conf')
DIAGRAM_FILE_PATH = os.path.join(LOG_PATH, f'{PKG_NAME}-diagram.md')
DOC_FILE_PATH = os.path.join(LOG_PATH, f'{PKG_NAME}-doc.md')

try:
    # create log path if not exists...
    if not os.path.exists(LOG_PATH):
        os.makedirs(LOG_PATH)
        if os.name == 'posix': os.chmod(LOG_PATH, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
except Exception as e:
    write_syslog(e)

# formatted log writer class
class LogWriter(object):
    def __init__(self, req = None, resp = None):

        if (req and resp) or (not req and not resp): raise Exception('wrong usage')

        self.resp = resp
        self.req = resp.request if resp else req
        self.service = get_current_service() or 'unknown'
        self.headers = resp.headers if resp else req.headers
        self.req_id = get_request_id(self.headers, 'none')
        self.req_from = get_request_from(self.headers, 'unknown')
        self.url = parse_url(self.req.url)
        self.header = format_header(self.headers)
        self.body = format_body(resp or req)

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
                ``` http title="{self.req.method} {self.url}"
            {header}
                ```

            === "Body"
                ```
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
                ``` http title="{self.resp.status} {self.url}"
            {header}
                ```

            === "Body"
                ```
            {body}
                ```
        """).format(
            self=self,
            header = textwrap.indent(self.header, ' '*4),
            body = textwrap.indent(self.body, ' '*4)
            ))


# requestshook logger middleware class
class RequestsHookLogger(object):

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
        response = self.process_request(req)
        if response:
            return response

        response = req.get_response(self.application)
        response.request = req

        try:
            return self.process_response(response)
        except webob.exc.HTTPException as e:
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

            writer = LogWriter(req = req)
            writer.write_request_log()
            writer.write_request_diagram()
            writer.write_request_markdown()

        except Exception as e:
            write_syslog(repr(e))

        return None

    # write response
    def process_response(self, resp):
        try:
            # process resposne header
            self.on_process_response_header(resp)

            writer = LogWriter(resp = resp)
            writer.write_response_log()
            writer.write_response_diagram()
            writer.write_response_markdown()

        except Exception as e:
            write_syslog(repr(e))

        return resp

    # # write request log
    # def write_request_log(self, req, req_from, url, header, body):
    #     write_text(LOG_FILE_PATH, textwrap.dedent("""
    #     ### ({req_from}) REQ >>> ({service}) : {req.method} {req.url}
    #     {header}

    #     {body}
    #     """).format(
    #         req_from = req_from,
    #         service = self.service,
    #         req = req,
    #         header = header,
    #         body = body
    #     ))

    # # write response log
    # def write_response_log(self, resp, req_from, url, header, body):
    #     write_text(LOG_FILE_PATH, textwrap.dedent("""
    #     ### ({req_from}) RESP <<< ({service}) : {resp.status} {req.method} {req.url}
    #     {header}

    #     {body}
    #     """).format(
    #         req_from = req_from,
    #         service = self.service,
    #         resp = resp,
    #         req = resp.request,
    #         header = header,
    #         body = body
    #     ))

    # # write request diagram
    # def write_request_diagram(self, req, req_from, url, header, body):
    #     write_text(DIAGRAM_FILE_PATH, f"{req_from}->>{self.service}: {req.method} {url.path}")

    # # write response diagram
    # def write_response_diagram(self, resp, req_from, url, header, body):
    #     write_text(DIAGRAM_FILE_PATH, f"{self.service}-->>{req_from}: {resp.status} {url.path}")

    # # write request markdown
    # def write_request_markdown(self, req, req_from, url, header, body):
    #     write_text(DOC_FILE_PATH, textwrap.dedent("""
    #         ### {req.method} {url.path}
    #         `{req_from}` --> `{service}`

    #         === "Header"
    #             ``` http title="{req.method} {url}"
    #         {header}
    #             ```

    #         === "Body"
    #             ```
    #         {body}
    #             ```
    #         """).format(
    #             req = req,
    #             url = url,
    #             req_from = req_from,
    #             service = self.service,
    #             header = textwrap.indent(header, ' '*4),
    #             body = textwrap.indent(body, ' '*4)
    #         ))

    # # write response markdown
    # def write_response_markdown(self, resp, req_from, url, header, body):
    #     write_text(DOC_FILE_PATH, textwrap.dedent("""
    #         ### {resp.status} {url.path}
    #         `{req_from}` <-- `{service}`

    #         === "Header"
    #             ``` http title="{resp.status} {url}"
    #         {header}
    #             ```

    #         === "Body"
    #             ```
    #         {body}
    #             ```
    #         """).format(
    #             resp = resp,
    #             url = url,
    #             req_from = req_from,
    #             service = self.service,
    #             header = textwrap.indent(header, ' '*4),
    #             body = textwrap.indent(body, ' '*4)
    #         ))
