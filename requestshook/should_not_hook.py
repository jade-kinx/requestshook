import os
import re
import json

from requestshook.utils import (
    CONF_PATH,
    write_syslog
)

# # configuration
# CONF = configparser.ConfigParser()
# CONF.read(os.path.join(CONF_PATH, f'{PACKAGE_NAME}.conf'))

# # get multiline list from ini style config
# def get_config_list(section, option, fallback=[]):
#     try:
#         return json.loads(CONF.get(section, option, fallback=fallback))
#     except:
#         return fallback


DEFAULT_REPLACES = {
    # '{uuid}': '([a-fA-F0-9-]+)',
    # '{name}': '(.+?)'
}

DEFAULT_FILTERS = [
#   {
#     "from": "nova-compute",
#     "to": "placement-api",
#     "method": "GET",
#     "urls": [
#       "/identity/v3/auth/tokens",
#       "/resource_providers/{uuid}/inventories",
#       "/resource_providers/{uuid}/aggregates",
#       "/resource_providers/{uuid}/allocations",
#       "/resource_providers/{uuid}/traits"
#     ]
#   }
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
            'replaces': DEFAULT_REPLACES
        }

def get_filtered_url(url, replaces):
    for k, v in replaces.items():
        url = url.replace(k, v)
    return url

# test match for the request
def match_filter(filter, replaces, request_from, request_to, request_method, request_url):

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
    return not filter_urls or any(re.search(get_filtered_url(filter_url, replaces), request_url) for filter_url in filter_urls)

# should not hook for this request?
def should_not_hook(request_from, request_to, request_method, request_url):
    config = load_config()

    filters = config.get('filters') or DEFAULT_FILTERS
    replaces = config.get('replaces') or DEFAULT_REPLACES

    return any(match_filter(filter, replaces, request_from, request_to, request_method, request_url) for filter in filters)
