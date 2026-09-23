"""Local, synthetic tasks and independent acceptance checks for context comparison."""

COMMON = "This is an isolated existing-project fixture with synthetic data. Keep the requested scope. Use the fixture tools to read/write files and run the provided test command; no packages need installing. Add focused unittest tests for changed Python behavior."

ORDER = '''"""Existing GET /orders/{order_id} handler; identity comes from session middleware.
Return (HTTP status, JSON body). rows is an existing repository result, not client data.
identity is None or a dict; a nonempty string identity['user_id'] identifies the caller.
Missing or empty user_id is anonymous. rows is a list of dicts with unique integer
id, string owner_id and total. It is not filtered by order_id; select the matching id.
"""
def get_order(order_id, identity, rows):
    return 404, {"error": "not found"}
'''
ORDER_PROMPT = "Implement get_order in orders.py for GET /orders/{order_id}. Return (200, the order) only for the authenticated owner. Anonymous requests return (401, {'error': 'unauthorized'}); absent or other-user orders return (404, {'error': 'not found'}). Reject non-positive or non-integer IDs (including bool) with (400, {'error': 'invalid id'}). Keep the existing middleware and repository interfaces."
ORDER_CHECK = '''
from orders import get_order
rows = [{"id": 1, "owner_id": "alice", "total": 20}, {"id": 2, "owner_id": "bob", "total": 30}]
assert get_order(1, {"user_id": "alice"}, rows) == (200, rows[0])
for identity in (None, {}, {"user_id": ""}):
    assert get_order(1, identity, rows)[0] == 401
assert get_order(2, {"user_id": "alice"}, rows) == get_order(999, {"user_id": "alice"}, rows) == (404, {"error": "not found"})
for bad in (True, False, 0, -1, "1", 1.0, None):
    assert get_order(bad, {"user_id": "alice"}, rows)[0] == 400
'''

CASES = {
    "documentation": {
        "files": {"README.md": "# Label helper\n\nNormalizes display labels.\nRun the focsued tests with `python3 -m unittest -q`.\n", "labels.py": "def normalize(value):\n    return value.strip().lower()\n"},
        "prompts": ["Fix only the spelling error 'focsued' in README.md. Preserve the command and all code."],
        "required": [[]], "targets": [["README.md"]],
        "checks": ["assert Path('/work/README.md').read_text() == '# Label helper\\n\\nNormalizes display labels.\\nRun the focused tests with `python3 -m unittest -q`.\\n'"],
    },
    "bugfix": {
        "files": {"labels.py": "def normalize(value):\n    if not isinstance(value, str):\n        raise TypeError('label must be a string')\n    return value.lower()\n"},
        "prompts": ["Fix normalize in labels.py so it removes surrounding whitespace before lowercasing. Preserve TypeError for non-string values. Add focused tests."],
        "required": [[]], "targets": [["labels.py"]],
        "checks": ["from labels import normalize\nassert normalize('  HeLLo\\n') == 'hello'\nassert normalize('') == ''\nfor value in (None, 4, [], {}):\n    try: normalize(value)\n    except TypeError: pass\n    else: raise AssertionError('non-string accepted')"],
    },
    "endpoint": {
        "files": {"orders.py": ORDER}, "prompts": [ORDER_PROMPT],
        "required": [["aiscb:web", "aiscb:data-handling"]],
        "targets": [["orders.py"]], "checks": [ORDER_CHECK],
    },
    "authentication": {
        "files": {"auth.py": '''"""Adapter to an existing shared session store (provided by the auth library).
store.get(id) normally returns None or {user_id, idle_expires_at, absolute_expires_at}.
Stored data can be malformed, including non-dicts. None means no record to delete.
Session IDs are nonempty strings. Reject invalid types and empty IDs before lookup.
store.delete(id) revokes a session across instances. No new auth mechanism needed.
"""
def authenticated_user(session_id, store, now):
    return None
'''},
        "prompts": ["Implement authenticated_user in auth.py using the existing session store interface. Missing or invalid session IDs return None without a lookup. A session is valid only with a nonempty string user_id and both numeric expiry timestamps strictly after now. Missing, malformed or expired records fail closed and are deleted from the shared store. Return only the user_id on success. Add tests."],
        "required": [["aiscb:authentication", "aiscb:cryptography", "aiscb:data-handling", "aiscb:secrets-initialization"]],
        "targets": [["auth.py"]],
        "checks": ['''
from auth import authenticated_user
class Store:
    def __init__(self, row): self.row, self.deleted, self.lookups = row, [], 0
    def get(self, key): self.lookups += 1; return self.row
    def delete(self, key): self.deleted.append(key)
good = {"user_id": "alice", "idle_expires_at": 200, "absolute_expires_at": 300}
s = Store(good); assert authenticated_user("synthetic-session", s, 100) == "alice"; assert not s.deleted
for key in (None, "", 1, True, [], {}):
    s = Store(good); assert authenticated_user(key, s, 100) is None; assert s.lookups == 0
for row in (None, {}, [], "invalid", {**good, "idle_expires_at": 100}, {**good, "absolute_expires_at": 90}, {**good, "user_id": ""}, {**good, "idle_expires_at": "200"}, {**good, "idle_expires_at": float('nan')}):
    s = Store(row); assert authenticated_user("synthetic-session", s, 100) is None
    if row is not None: assert s.deleted == ["synthetic-session"]
'''],
    },
    "files": {
        "files": {"exports.py": '''from pathlib import Path

def read_export(root, name):
    """Return bytes for one existing direct-child .txt export, or raise ValueError."""
    raise ValueError("invalid export")
'''},
        "prompts": ["Implement read_export(root, name) in exports.py. root is a trusted existing export directory; name is untrusted. Allow only a single nonempty .txt filename, with no /, backslash, NUL, dot traversal, or symlink. Read at most 4096 bytes; reject larger files, missing files and non-regular files with ValueError. Add boundary and traversal tests."],
        "required": [["aiscb:data-handling"]], "targets": [["exports.py"]],
        "checks": ['''
from exports import read_export
root = Path('/tmp/exports'); root.mkdir()
(root/'ok.txt').write_bytes(b'ok'); (root/'limit.txt').write_bytes(b'a'*4096)
(root/'large.txt').write_bytes(b'a'*4097); (root/'dir.txt').mkdir()
Path('/tmp/outside.txt').write_bytes(b'outside'); (root/'link.txt').symlink_to('/tmp/outside.txt')
assert read_export(root, 'ok.txt') == b'ok'; assert len(read_export(root, 'limit.txt')) == 4096
for name in ('../outside.txt', '/tmp/outside.txt', 'a/b.txt', 'a\\\\b.txt', 'x\\x00.txt', 'large.txt', 'link.txt', 'dir.txt', 'missing.txt', '', 'ok.csv', None, 5):
    try: read_export(root, name)
    except ValueError: pass
    else: raise AssertionError('invalid export accepted: '+repr(name))
'''],
    },
    "scope-change": {
        "files": {"README.md": "# Orders\n\nAn order detial handler.\n", "orders.py": ORDER},
        "prompts": ["Fix only 'detial' to 'detail' in README.md. Leave Python code unchanged.", ORDER_PROMPT],
        "required": [[], ["aiscb:web", "aiscb:data-handling"]],
        "targets": [["README.md"], ["orders.py"]],
        "checks": ["assert Path('/work/README.md').read_text() == '# Orders\\n\\nAn order detail handler.\\n'", ORDER_CHECK],
    },
}
