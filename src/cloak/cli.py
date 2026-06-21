"""``cloak`` command-line interface.

Subcommands:
    scan       Detect and report PII (no replacement).
    mask       Mask PII and (optionally) save a vault for later restore.
    unmask     Restore PII in masked text using a saved vault.
    serve-mcp  Run the MCP server (stdio).
    proxy      Run the round-trip masking reverse proxy.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import NoReturn

from ._version import __version__
from .engine import Cloak
from .policy import CloakPolicy
from .vault import Vault


def _die(message: str) -> NoReturn:
    """Print a clean CLI error and exit non-zero (no traceback)."""
    print(f"cloak: error: {message}", file=sys.stderr)
    raise SystemExit(2)


def _read_input(path: str | None) -> str:
    if path is None or path == "-":
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        _die(f"cannot read input {path!r}: {exc.strerror or exc}")


def _policy_from_args(args: argparse.Namespace) -> CloakPolicy:
    # --config / --profile are authoritative when given (they replace the other
    # policy flags); precedence: config > profile > individual flags.
    if getattr(args, "config", None):
        try:
            return CloakPolicy.from_file(args.config)
        except (OSError, ValueError, ImportError) as exc:
            _die(f"could not load config {args.config!r}: {exc}")
    if getattr(args, "profile", None):
        try:
            return CloakPolicy.from_profile(args.profile)
        except ValueError as exc:
            _die(str(exc))

    detectors = [d.strip() for d in args.detectors.split(",") if d.strip()]
    policy = CloakPolicy(
        detectors=detectors,
        strategy=args.strategy,
        min_score=args.min_score,
        skip_code_blocks=not args.no_skip_code,
        locale=args.locale,
        seed=args.seed,
        phone_region=args.phone_region,
    )
    if args.types:
        policy.enabled_types = {t.strip().upper() for t in args.types.split(",") if t.strip()}
    if args.allow:
        policy.allowlist = [a for a in args.allow.split(",") if a]
    if args.deny:
        policy.denylist = [d for d in args.deny.split(",") if d]
    if getattr(args, "ner_backend", None):
        policy.ner_backend = args.ner_backend
    if getattr(args, "ner_model", None):
        policy.ner_model = args.ner_model
    return policy


def _add_detector_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--profile", default=None,
                   help="Compliance preset (gdpr/hipaa/pci/strict/secrets); overrides other flags")
    p.add_argument("--config", default=None,
                   help="Policy file (.json/.toml/.yaml); overrides other flags")
    p.add_argument("--detectors", default="regex", help="Comma list: regex,ner,llm")
    p.add_argument(
        "--strategy",
        default="placeholder",
        choices=["placeholder", "pseudonym", "redact", "hash"],
    )
    p.add_argument("--min-score", type=float, default=0.5, dest="min_score")
    p.add_argument("--types", default="", help="Only mask these entity types (comma list)")
    p.add_argument("--allow", default="", help="Literal strings to never mask (comma list)")
    p.add_argument("--deny", default="", help="Literal strings to always mask (comma list)")
    p.add_argument("--no-skip-code", action="store_true", dest="no_skip_code")
    p.add_argument("--locale", default="en_US", help="Faker locale for pseudonyms")
    p.add_argument("--phone-region", default="US", dest="phone_region",
                   help="Assumed region for national-format phone numbers")
    p.add_argument("--seed", type=int, default=None, help="Deterministic seed")
    p.add_argument("--ner-backend", default=None, dest="ner_backend")
    p.add_argument("--ner-model", default=None, dest="ner_model")


def _add_policy_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", nargs="?", help="Input file, or '-'/omitted for stdin")
    _add_detector_flags(p)


def cmd_scan(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    cloak = Cloak(_policy_from_args(args))
    entities = cloak.scan(text)
    payload = [
        {"type": e.type, "text": e.text, "start": e.start, "end": e.end,
         "score": round(e.score, 3), "source": e.source}
        for e in entities
    ]
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for e in payload:
            print(f"{e['type']:<14} {e['score']:<5} {e['source']:<9} {e['text']!r}")
        print(f"\n{len(payload)} entities", file=sys.stderr)
    return 0


def cmd_mask(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    cloak = Cloak(_policy_from_args(args))
    result = cloak.mask_text(text)
    sys.stdout.write(result.text or "")
    if args.vault:
        result.vault.save(args.vault, password=args.password)
        print(
            f"\n[cloak] {result.entity_count} entities masked; vault -> {args.vault}",
            file=sys.stderr,
        )
    elif result.entity_count:
        print(
            f"\n[cloak] {result.entity_count} entities masked "
            "(no --vault given; restore won't be possible)",
            file=sys.stderr,
        )
    return 0


def cmd_unmask(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    try:
        vault = Vault.load(args.vault, password=args.password)
    except OSError as exc:
        _die(f"cannot read vault {args.vault!r}: {exc.strerror or exc}")
    except Exception as exc:  # bad password / corrupt vault
        _die(f"could not load vault {args.vault!r}: {exc}")
    sys.stdout.write(vault.restore(text))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from .evaluate import evaluate, load_corpus

    try:
        examples = load_corpus(args.dataset)
    except OSError as exc:
        _die(f"cannot read corpus {args.dataset!r}: {exc.strerror or exc}")
    cloak = Cloak(_policy_from_args(args))
    report = evaluate(cloak, examples)
    print(report.format_table())
    return 0


def cmd_serve_mcp(args: argparse.Namespace) -> int:
    from .mcp_server import run as run_mcp

    try:
        run_mcp()  # deps imported lazily inside; ImportError -> clean message
    except ImportError as exc:
        _die(str(exc))
    return 0


def cmd_proxy(args: argparse.Namespace) -> int:
    from .proxy import run as run_proxy

    try:
        run_proxy(
            host=args.host,
            port=args.port,
            upstream=args.upstream,
            strategy=args.strategy,
            detectors=[d.strip() for d in args.detectors.split(",") if d.strip()],
            restore=not args.no_restore,
        )
    except ImportError as exc:
        _die(str(exc))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cloak", description="Reversible PII redaction for LLMs")
    parser.add_argument("--version", action="version", version=f"cloak {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Detect PII (no replacement)")
    _add_policy_flags(p_scan)
    p_scan.add_argument("--json", action="store_true", help="Output JSON")
    p_scan.set_defaults(func=cmd_scan)

    p_mask = sub.add_parser("mask", help="Mask PII")
    _add_policy_flags(p_mask)
    p_mask.add_argument("--vault", default=None, help="Path to write the vault (for restore)")
    p_mask.add_argument("--password", default=None, help="Encrypt the vault with this password")
    p_mask.set_defaults(func=cmd_mask)

    p_unmask = sub.add_parser("unmask", help="Restore masked text from a vault")
    p_unmask.add_argument("input", nargs="?", help="Masked input file or stdin")
    p_unmask.add_argument("--vault", required=True, help="Vault file to restore from")
    p_unmask.add_argument("--password", default=None, help="Vault password (if encrypted)")
    p_unmask.set_defaults(func=cmd_unmask)

    p_eval = sub.add_parser("eval", help="Score detectors against a gold corpus")
    p_eval.add_argument("dataset", help="Gold corpus file ([[TYPE|value]] markup)")
    _add_detector_flags(p_eval)
    p_eval.set_defaults(func=cmd_eval)

    p_mcp = sub.add_parser("serve-mcp", help="Run the MCP server over stdio")
    p_mcp.set_defaults(func=cmd_serve_mcp)

    p_proxy = sub.add_parser("proxy", help="Run the round-trip masking proxy")
    p_proxy.add_argument("--host", default="127.0.0.1")
    p_proxy.add_argument("--port", type=int, default=8788)
    p_proxy.add_argument(
        "--upstream",
        default="https://api.openai.com",
        help="Upstream LLM base URL to forward to",
    )
    p_proxy.add_argument("--detectors", default="regex")
    p_proxy.add_argument(
        "--strategy",
        default="placeholder",
        choices=["placeholder", "pseudonym", "redact", "hash"],
    )
    p_proxy.add_argument("--no-restore", action="store_true", help="Do not restore responses")
    p_proxy.set_defaults(func=cmd_proxy)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
