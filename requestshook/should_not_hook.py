import os
import re
import json

from requestshook.utils import (
    CONF_PATH,
    write_syslog
)

DEFAULT_MAPPINGS = {
    '{uuid}': '([a-fA-F0-9-]+)',
}

DEFAULT_FILTERS = [
    {
        "from": "nova-compute",
        "to": "placement-api",
        "method": "GET",
        "urls": [
            "/placement/resource_providers",
            "/placement/resource_providers/{uuid}/inventories",
            "/placement/resource_providers/{uuid}/aggregates",
            "/placement/resource_providers/{uuid}/allocations",
            "/placement/resource_providers/{uuid}/traits"
        ]
    },
    {
        "from": "placement-api",
        "to": "keystone",
        "urls": [
            "/identity/"
        ]
    }
]

# config file path: /etc/requestshook/should_not_hook.json
config_file_path = os.path.join(CONF_PATH, 'should_not_hook.json')

# load config file ( load for every reqeust )
def load_config():
    try:
        with open(config_file_path) as f:
            return json.load(f)
    except:
        write_syslog('loading should_not_hook.json failed')
        return {
            'filters': DEFAULT_FILTERS,
            'mappings': DEFAULT_MAPPINGS
        }

def get_filtered_url(url, mappings):
    for k, v in mappings.items():
        url = url.replace(k, v)
    return url

# test match for the request
def match_filter(filter, mappings, request_from, request_to, request_method, request_url):

    # from
    filter_from = filter.get('from')
    if filter_from and filter_from.casefold() != request_from.casefold(): return False

    # to
    filter_to = filter.get('to')
    if filter_to and filter_to.casefold() != request_to.casefold(): return False

    # method
    filter_method = filter.get('method')
    if filter_method and filter_method.casefold() != request_method.casefold(): return False

    # urls
    filter_urls = filter.get('urls')
    return not filter_urls or any(re.search(get_filtered_url(filter_url, mappings), request_url) for filter_url in filter_urls)

# should not hook for this request?
def should_not_hook(request_from, request_to, request_method, request_url):
    config = load_config()

    filters = config.get('filters') or DEFAULT_FILTERS
    mappings = config.get('mappings') or DEFAULT_MAPPINGS

    return any(match_filter(filter, mappings, request_from, request_to, request_method, request_url) for filter in filters)
