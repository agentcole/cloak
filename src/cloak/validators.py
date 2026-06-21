"""Checksum / format validators for structured-PII recognizers.

These keep the regex tier's precision high: a pattern that matches a bare digit
run only emits an entity if the run also passes the relevant national/industry
checksum. Each function takes the matched string (which may contain separators)
and returns whether it is a valid identifier of that kind.
"""

from __future__ import annotations


def _luhn(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def canada_sin_valid(value: str) -> bool:
    """Canadian Social Insurance Number: 9 digits, Luhn; first digit not 0 or 8."""
    d = [c for c in value if c.isdigit()]
    if len(d) != 9 or d[0] in ("0", "8"):
        return False
    return _luhn("".join(d))


def spain_dni_valid(value: str) -> bool:
    """Spanish DNI/NIE: 8 digits + a check letter (mod-23)."""
    s = value.replace("-", "").replace(" ", "").upper()
    if len(s) != 9 or not s[:8].isdigit() or not s[8].isalpha():
        return False
    return "TRWAGMYFPDXBNJZSQVHLCKE"[int(s[:8]) % 23] == s[8]


def cpf_valid(value: str) -> bool:
    """Brazilian CPF: 11 digits with two check digits."""
    d = [int(c) for c in value if c.isdigit()]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        total = sum(d[i] * ((n + 1) - i) for i in range(n))
        check = (total * 10) % 11 % 10
        if check != d[n]:
            return False
    return True


def german_taxid_valid(value: str) -> bool:
    """German Steuer-IdNr: 11 digits, ISO 7064 MOD 11,10 check digit."""
    d = [int(c) for c in value if c.isdigit()]
    if len(d) != 11:
        return False
    product = 10
    for i in range(10):
        s = (d[i] + product) % 10
        if s == 0:
            s = 10
        product = (s * 2) % 11
    return (11 - product) % 10 == d[10]


def france_insee_valid(value: str) -> bool:
    """French INSEE / social-security number: 15 digits, mod-97 key."""
    s = "".join(c for c in value if c.isdigit())
    if len(s) != 15:
        return False
    body, key = int(s[:13]), int(s[13:])
    return (97 - (body % 97)) == key


def npi_valid(value: str) -> bool:
    """US National Provider Identifier: 10 digits, Luhn over the 80840 prefix."""
    d = "".join(c for c in value if c.isdigit())
    if len(d) != 10:
        return False
    return _luhn("80840" + d)


_VIN_TRANS = {
    **{str(i): i for i in range(10)},
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
    "J": 1,
    "K": 2,
    "L": 3,
    "M": 4,
    "N": 5,
    "P": 7,
    "R": 9,
    "S": 2,
    "T": 3,
    "U": 4,
    "V": 5,
    "W": 6,
    "X": 7,
    "Y": 8,
    "Z": 9,
}
_VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def vin_valid(value: str) -> bool:
    """Vehicle Identification Number: 17 chars (no I/O/Q), check digit at pos 9."""
    s = value.upper()
    if len(s) != 17 or any(c in "IOQ" for c in s):
        return False
    try:
        total = sum(_VIN_TRANS[c] * _VIN_WEIGHTS[i] for i, c in enumerate(s))
    except KeyError:
        return False
    r = total % 11
    return s[8] == ("X" if r == 10 else str(r))


# Verhoeff checksum (used by India's Aadhaar).
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def aadhaar_valid(value: str) -> bool:
    """India Aadhaar: 12 digits, Verhoeff check digit; never starts with 0 or 1."""
    digits = [int(c) for c in value if c.isdigit()]
    if len(digits) != 12 or digits[0] in (0, 1):
        return False
    c = 0
    for i, d in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][d]]
    return c == 0
