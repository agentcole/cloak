"""Token-restoration over a streamed response.

A placeholder token (e.g. ``[EMAIL_1]``) can be split across two SSE chunks, so
we cannot just ``str.replace`` each chunk independently. :class:`StreamRestorer`
buffers the smallest suffix that might still be completing a token, restores
everything before it, and flushes the remainder at the end.
"""

from __future__ import annotations

from ..vault import Vault


class StreamRestorer:
    def __init__(self, vault: Vault) -> None:
        self._vault = vault
        self._tokens = [e.token for e in vault.reversible_entries()]
        self._max_token = max((len(t) for t in self._tokens), default=0)
        self._buf = ""

    def _holdback_len(self, s: str) -> int:
        """Length of the trailing suffix of ``s`` that could still grow into a token.

        Returns the largest ``k`` (``1..max_token-1``) such that ``s[-k:]`` is a
        strict prefix of some token, else ``0``.
        """
        if self._max_token == 0:
            return 0
        limit = min(self._max_token - 1, len(s))
        for k in range(limit, 0, -1):
            suffix = s[-k:]
            if any(t.startswith(suffix) and len(t) > k for t in self._tokens):
                return k
        return 0

    def feed(self, text: str) -> str:
        """Consume a chunk of response text; return text safe to forward now."""
        if self._max_token == 0:
            return text  # nothing reversible — pass through untouched
        self._buf += text
        hold = self._holdback_len(self._buf)
        cut = len(self._buf) - hold
        emit, self._buf = self._buf[:cut], self._buf[cut:]
        return self._vault.restore(emit)

    def flush(self) -> str:
        """Restore and return any buffered remainder (call once at stream end)."""
        out = self._vault.restore(self._buf)
        self._buf = ""
        return out
