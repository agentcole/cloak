"""Compare replacement strategies and compliance profiles side by side.

Runs offline. The `pseudonym` strategy needs the [faker] extra; it's skipped
with a note if missing.

    python examples/strategies_and_profiles.py
"""

from __future__ import annotations

from cloak import Cloak, CloakPolicy

TEXT = "Jane (jane@acme.com), card 4111 1111 1111 1111, ip 10.0.0.1, dob 1990-07-15"


def show_strategies() -> None:
    print("== replacement strategies ==")
    for strategy in ["placeholder", "pseudonym", "redact", "hash"]:
        try:
            cloak = Cloak(CloakPolicy(detectors=["regex"], strategy=strategy, seed=7))
            print(f"  {strategy:12}: {cloak.mask_text(TEXT).text}")
        except ImportError:
            print(f"  {strategy:12}: (needs an extra — pip install 'cloak-llm[faker]')")


def show_profiles() -> None:
    print("\n== compliance profiles (detectors forced to regex for an offline demo) ==")
    for profile in ["pci", "secrets", "strict"]:
        cloak = Cloak(CloakPolicy.from_profile(profile, detectors=["regex"]))
        print(f"  {profile:10}: {cloak.mask_text(TEXT).text}")


if __name__ == "__main__":
    show_strategies()
    show_profiles()
