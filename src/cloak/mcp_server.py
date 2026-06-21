"""MCP server exposing cloak as tools any MCP client can call.

Tools:
    cloak_scan(text, detectors)             -> detected entities (no change)
    cloak_mask(text, strategy, detectors)   -> masked text + vault_id
    cloak_unmask(text, vault_id)            -> restored text

The mask→unmask round trip is stateful: ``cloak_mask`` stores the vault in
process memory and returns an opaque ``vault_id`` that ``cloak_unmask`` later
references. Vaults hold raw PII, so they live only for the server's lifetime.

Requires the ``mcp`` extra: ``pip install "cloak-llm[mcp]"``.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict

from .engine import Cloak
from .policy import CloakPolicy
from .vault import Vault

# In-memory vault store keyed by the id handed back to the client. Vaults hold
# raw PII, so the store is capacity-bounded (oldest evicted) to cap retention.
_MAX_VAULTS = 256
_VAULTS: OrderedDict[str, Vault] = OrderedDict()


def _store_vault(vault_id: str, vault: Vault) -> None:
    _VAULTS[vault_id] = vault
    _VAULTS.move_to_end(vault_id)
    while len(_VAULTS) > _MAX_VAULTS:
        _VAULTS.popitem(last=False)


def _cloak(strategy: str, detectors: str) -> Cloak:
    dets = [d.strip() for d in detectors.split(",") if d.strip()]
    return Cloak(CloakPolicy(detectors=dets, strategy=strategy))


def _build_server():  # pragma: no cover - thin wiring over the mcp package
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            'The MCP server requires the mcp extra: pip install "cloak-llm[mcp]"'
        ) from exc

    mcp = FastMCP("cloak")

    @mcp.tool()
    def cloak_scan(text: str, detectors: str = "regex") -> dict:
        """Detect PII/sensitive spans in text. Returns the entities found."""
        cloak = _cloak("placeholder", detectors)
        entities = cloak.scan(text)
        return {
            "count": len(entities),
            "entities": [
                {
                    "type": e.type,
                    "text": e.text,
                    "start": e.start,
                    "end": e.end,
                    "score": round(e.score, 3),
                }
                for e in entities
            ],
        }

    @mcp.tool()
    def cloak_mask(text: str, strategy: str = "placeholder", detectors: str = "regex") -> dict:
        """Replace PII with reversible tokens.

        Returns the masked text and a vault_id. Pass that vault_id to
        cloak_unmask to restore the original values. strategy is one of
        placeholder | pseudonym | redact | hash.
        """
        cloak = _cloak(strategy, detectors)
        result = cloak.mask_text(text)
        vault_id = uuid.uuid4().hex
        _store_vault(vault_id, result.vault)
        return {
            "masked_text": result.text,
            "vault_id": vault_id,
            "count": result.entity_count,
            "by_type": result.by_type(),
        }

    @mcp.tool()
    def cloak_unmask(text: str, vault_id: str) -> dict:
        """Restore original values in text using a vault_id from cloak_mask."""
        vault = _VAULTS.get(vault_id)
        if vault is None:
            return {"error": f"unknown vault_id: {vault_id}", "text": text}
        return {"text": vault.restore(text)}

    return mcp


def run() -> None:
    """Run the MCP server over stdio."""
    _build_server().run()


if __name__ == "__main__":
    run()
