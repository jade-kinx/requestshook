import json
import os
import psutil

from pathlib import Path
from urllib3.util import parse_url

try:
    import syslog
except:
    syslog = None

# write error message to syslog
def write_error(*messages):

    if messages:
        if syslog:
            syslog.syslog(' '.join(messages))
        else:
            print(' '.join(messages))

# write text to file
def write_text(file, *messages):

    if messages:
        # create permission all file if not exists
        if not os.path.exists(file):
            mask = os.umask(0)
            Path(file).touch(mode=0o666, exist_ok=True)
            os.umask(mask)

        # write messages to file
        with open(file, 'a') as f:
            f.write('{0}\n'.format(' '.join(messages)))

# beautify json string
def beautify_json(body, indent=2):
    try:
        return json.dumps(json.loads(body), indent=indent)
    except:
        return None

# format headers( headers should be dictionary type )
def format_header(headers):
    try:
        return '\n'.join(f'{k}: {v}' for k, v in headers.items())
    except:
        return repr(headers)

# format body
def format_body(body):
    if not body: return None
    if isinstance(body, str): return beautify_json(body) or body

    return str(body)

# get service name from url (devstack default environment)
def get_service_from_url(url):
    parsed_url = parse_url(url)
    if parsed_url.port == 8080: return 'swift-proxy-server'
    if parsed_url.port == 8779: return 'trove-api'
    if parsed_url.port == 9696: return 'neutron-server'
    if parsed_url.path.startswith('/identity'): return 'keystone'
    if parsed_url.path.startswith('/image'): return 'glance-api'
    if parsed_url.path.startswith('/volume'): return 'cinder-api'
    if parsed_url.path.startswith('/compute'): return 'nova-api'
    if parsed_url.path.startswith('/placement'): return 'placement-api'

    return parsed_url.path

# get service name from command line args
def get_current_service():

    p = psutil.Process(os.getpid())
    args = p.cmdline()

    # match command line exact?
    services = {
        'horizon': '(wsgi:horizon)', 
        'trove-api': '(wsgi:trove-api)', 
        'keystone': 'keystoneuWSGI', 
        'glance-api': 'glance-apiuWSGI',
        'cinder-api': 'cinder-apiuWSGI',
        'nova-api': 'nova-apiuWSGI',
        'placement-api': 'placementuWSGI',
        'neutron-server': 'neutron-server',
        'swift-proxy-server': 'swift-proxy-server',
    }

    matches = [service for arg in (args or []) for (service, tag) in services.items() if tag == arg or service in arg]
    return matches[0] if matches else p.name()
