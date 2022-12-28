import os
import stat
import functools
import textwrap
import configparser
import json

from pathlib import Path
from urllib3.util import parse_url

from requestshook.utils import (
    write_error,
    write_text,
    format_header,
    beautify_json,
    get_service_from_url,
    get_current_service
)

# requestshook name
PKG_NAME = __package__ or 'requestshook'
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
    write_error(e)

# format response body
def format_body(response):
    try:
        content_type = response.headers.get('content-type')
        if content_type and 'octet-stream' in content_type and hasattr(response, 'content') and response.content:
            return f"{content_type} [{response.content[:8].hex()}...]"
        
        if not response.text: return "None"
            
        return beautify_json(response.text)
    except:
        return 'exception!'


# get Requests.PreparedRequest from args, kwargs if exists
def get_prepared_request(*args, **kwargs):
    is_prepared_request = lambda p : 'PreparedRequest' in str(type(p))

    for arg in args:
        if is_prepared_request(arg): return arg

    for k, v in kwargs.items():
        if is_prepared_request(v): return v

    return None

def next_seq_id():
    try:
        filepath = os.path.join(LOG_PATH, f'{__name__}.seq')
        seq = get_current_seq_id(filepath) or 0
        seq += 1
    except:
        pass
    finally:
        write_current_seq_id(filepath, seq)

    return seq

# get current sequence id
def get_current_seq_id(filepath):
    try:
        with open(filepath, 'r') as file:
            return (int)(file.read())
    except:
        return None

# write current sequence id
def write_current_seq_id(filepath, seq):
    try:
        if not os.path.exists(filepath):
            mask = os.umask(0)
            Path(filepath).touch(mode=0o777, exist_ok=True)
            os.umask(mask)

        with open(filepath, 'w') as file:
            file.write('{0}'.format(seq))
    except Exception as e:
        write_error(e)

# write log for request
def write_request(request, seq):
    
    # local service name
    service = get_current_service()

    # remote service name
    remote = get_service_from_url(request.url)

    # parsed url
    url = parse_url(request.url)

    # request header
    header = format_header(request.headers)

    # request body
    body = beautify_json(request.body)

    # write request log
    write_text(os.path.join(LOG_PATH, f'{__name__}.log'),
        textwrap.dedent("""
        >>> REQ [{seq}] ({service}->{remote}) {request.method} {request.url}
        {header}
        
        {body}
        """).format(
            request = request,
            service = service,
            remote = remote,
            seq = seq,
            header = header,
            body = body
        ))

    # write request sequence diagram
    write_text(os.path.join(LOG_PATH, f'{__name__}-diagram.md'), 
        f"{service}->>{remote}: {request.method} {url.path}")

    # write request makrdown
    write_text(os.path.join(LOG_PATH, f'{__name__}.md'), 
        textwrap.dedent("""
        ### ({seq}) {request.method} {url.path}
        `{service}` --> `{remote}`

        === "Header"
            ``` http title="{request.method} {url}"
        {header}
            ```

        === "Body"
            ```
        {body}
            ```
        """).format(
            request = request,
            url = url,
            service = service,
            remote = remote,
            seq = seq,
            header = textwrap.indent(header, ' '*4),
            body = textwrap.indent(body, ' '*4)
        ))

# write log for response
def write_response(response, seq):

    # debugfile = os.path.join(LOG_PATH, f'{NAME}-debug.log')

    # local service name
    service = get_current_service()

    # remote service name
    remote = get_service_from_url(response.url)

    # parsed url
    url = parse_url(response.url)

    # header
    header = format_header(response.headers)

    # body
    body = format_body(response)

    # write response log
    write_text(os.path.join(LOG_PATH, f'{__name__}.log'),
        textwrap.dedent("""
        <<< RESP [{seq}] ({service}<-{remote}) {response.status_code} {response.reason} {response.url}
        {header}
        
        {body}
        """).format(
            response = response,
            service = service,
            remote = remote,
            seq = seq,
            header = header,
            body = body
        ))

    # write response sequence diagram
    write_text(os.path.join(LOG_PATH, f'{__name__}-diagram.md'), 
        f"{remote}-->>{service}: {response.status_code} {response.reason} {url.path}")

    # write response markdown
    write_text(os.path.join(LOG_PATH, f'{__name__}.md'), 
        textwrap.dedent("""
        ### ({seq}) {response.status_code} {response.reason} {url.path}
        `{service}` <-- `{remote}`

        === "Header"
            ```
        {header}
            ```

        === "Body"
            ```
        {body}
            ```
        """).format(
            response = response,
            url = url,
            service = service,
            remote = remote,
            seq = seq,
            header = textwrap.indent(header, ' '*4),
            body = textwrap.indent(body, ' '*4)
        ))

# should we hook for current service?
def should_hook(prepared):
    def get_list(conf, section, option, fallback=[]):
        try:
            return json.loads(conf.get(section, option, fallback=fallback))
        except:
            return fallback

    try:
        conf = configparser.ConfigParser()
        conf.read(os.path.join(CONF_PATH, f'{__name__}.conf'))

        # has should_not_hook.urls?
        urls = get_list(conf, 'should_not_hook', 'urls')
        if urls and any(url in prepared.url for url in urls): return False

        ports = get_list(conf, 'should_not_hook', 'ports')
        if ports and any(port == parse_url(prepared.url).port for port in ports): return False

        # has should_hook.services?
        current_service = get_current_service()
        services = get_list(conf, 'should_hook', 'services')
        if not services or any(service in current_service for service in services): return True

    except Exception as e:
        write_error(e)

    # don't hook in default
    return False


def trace(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
                
        try:
            # requests.PreparedRequest
            request = get_prepared_request(*args, **kwargs)

            # figure out shoud hook or not
            if not should_hook(request):
                return f(*args, **kwargs)

            # sequence id for request
            seq = next_seq_id()

            # write request log for sequence order
            if request:
                write_request(request, seq)
        except Exception as e:
            write_error(e)

        # call requests.HttpAdapter.send()
        r = f(*args, **kwargs)

        try:
            # write request log if PreparedRequest not exsits
            if not request:
                write_request(r.request, seq)

            # write response log (should increase seq.id)
            write_response(r, next_seq_id())
        except Exception as e:
            write_error(e)

        return r
    return inner
