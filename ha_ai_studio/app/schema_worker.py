"""One-shot schema validator. Only the parent process handles application state."""
import json
import os
import resource
import sys

# Set limits before loading the validator or consuming input. Linux/amd64 only.
resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
# Account for the interpreter's initial mappings (including amd64 emulation).
with open('/proc/self/statm') as status:
    initial_address_space = int(status.read().split()[0]) * os.sysconf('SC_PAGE_SIZE')
memory_limit = initial_address_space + 256 * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

from jsonschema import Draft202012Validator


def validate(request):
    schema = request['schema']
    # Reject references even in saved manifests; never resolve remote resources.
    encoded = json.dumps(schema)
    if '"$ref"' in encoded or '"$dynamicRef"' in encoded:
        return False
    Draft202012Validator.check_schema(schema)
    if request['mode'] == 'schema':
        return True
    return Draft202012Validator(schema).is_valid(request['value'])


try:
    raw = sys.stdin.buffer.read(200001)
    if len(raw) > 200000:
        raise ValueError()
    result = validate(json.loads(raw))
except Exception:
    result = False
sys.stdout.write('true' if result else 'false')
