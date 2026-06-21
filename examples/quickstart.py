"""cloak quickstart — mask PII, (pretend to) send to an LLM, restore the answer.

Runs fully offline (regex tier only). No API key needed.

    python examples/quickstart.py
"""

from __future__ import annotations

from cloak import Cloak, CloakPolicy


def main() -> None:
    cloak = Cloak(CloakPolicy(detectors=["regex"], strategy="placeholder"))

    prompt = (
        "Email jane@acme.com or call +1 415 555 0123 about SSN 123-45-6789. "
        "Charge card 4111 1111 1111 1111."
    )

    # 1) Mask before the prompt leaves your machine.
    res = cloak.mask_text(prompt)
    print("ORIGINAL :", prompt)
    print("MASKED   :", res.text)  # this is all the LLM ever sees
    print("ENTITIES :", res.by_type())

    # 2) Pretend we sent res.text to an LLM. A real model would echo the tokens
    #    it was given, e.g. it replies referencing [EMAIL_1] and [PHONE_1].
    llm_reply = "Sure — I'll email [EMAIL_1] and call [PHONE_1] this afternoon."

    # 3) Restore the originals before showing the answer to your user.
    restored = cloak.unmask_text(llm_reply, res.vault)
    print("\nLLM SAW  :", llm_reply)
    print("USER SEES:", restored)


if __name__ == "__main__":
    main()
