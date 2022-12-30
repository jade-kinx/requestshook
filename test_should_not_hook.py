from requestshook import should_not_hook as should_hook

should_hook.DEFAULT_MAPPINGS = {
    '{uuid}': '([a-fA-F0-9-]+)',
    '{name}': '(.+?)'
}

should_hook.DEFAULT_FILTERS = [
  {
    "from": "nova-compute",
    "to": "placement-api",
    "method": "GET",
    "urls": [
      "/resource_providers/{uuid}/inventories",
      "/resource_providers/{uuid}/aggregates",
      "/resource_providers/{uuid}/allocations",
      "/resource_providers/{uuid}/traits",
      "/resource_providers/{name}/names"
    ]
  },
  {
    "from": "placement-api",
    "to": "keystone",
    "urls": [
      "/identity/",
    ]
  }
]

# test
if __name__ == '__main__':

    from_ = 'placement-api'
    to = 'keystone'
    method = 'GET'
    # url = 'http://{host}:{port}/placement/resource_providers/2f9d4284-5ae2-464f-8ef7-132c0c3dc3d1/allocations'
    url = 'http://{host}:{port}//identity/v3/auth/tokens'

    print(should_hook.should_not_hook(from_, to, method, url))

