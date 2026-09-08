"""LiteLLM proxy hook that appends the organization's system block to every request.

The block is the built bundle's ``adapters/gateway/system-block.md``: aiscb
followed by the overlay. It is read once at startup and checked against the
digest the release recorded; a mismatch stops the proxy from starting. Nothing
is fetched per request.

Configure through the environment of the proxy process:

    AISCB_GATEWAY_BLOCK    path to system-block.md
    AISCB_GATEWAY_SHA256   its SHA-256 from the bundle manifest
"""

import hashlib
import os
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

MAX_BLOCK_BYTES = 256 * 1024


def load_block() -> str:
    path = os.environ.get("AISCB_GATEWAY_BLOCK")
    expected = os.environ.get("AISCB_GATEWAY_SHA256", "").lower()
    if not path or len(expected) != 64:
        raise SystemExit("AISCB_GATEWAY_BLOCK and AISCB_GATEWAY_SHA256 are required")
    data = Path(path).read_bytes()
    if len(data) > MAX_BLOCK_BYTES:
        raise SystemExit("system block exceeds the size limit")
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit("system block does not match its pinned digest")
    return data.decode("utf-8")


BASELINE_TEXT = load_block()
BASELINE_BLOCK = {"type": "text", "text": BASELINE_TEXT}


class BaselineInjector(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        system = data.get("system")
        if system is None:
            # Not an Anthropic-format request. Add the formats you serve.
            return data
        if isinstance(system, str):
            system = [{"type": "text", "text": system}]
        if any(block.get("text") == BASELINE_TEXT for block in system):
            return data  # already present, for example on a retry
        # Append as its own block: the client's first block must stay first
        # and untouched, and merging would change the cached prefix.
        data["system"] = list(system) + [dict(BASELINE_BLOCK)]
        return data


proxy_handler_instance = BaselineInjector()
