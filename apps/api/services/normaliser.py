# WHY: TR-NLU-03, D14 — Kannada/English Unicode NFC normalisation & number word conversion
"""Text normaliser for coastal Kannada speech transcripts and bilingual number parsing."""

import re
import unicodedata
from typing import Optional, Tuple


# Kannada digit glyphs ೦-೯ to ASCII 0-9
KANNADA_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")

# Base Kannada numbers
KANNADA_ONES = {
    "ಒಂದು": 1, "ಒಂದ": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ನಾಕು": 4,
    "ಐದು": 5, "ಆರು": 6, "ಏಳು": 7, "ಎಂಟು": 8, "ಒಂಬತ್ತು": 9,
}

KANNADA_TEENS = {
    "ಹತ್ತೊಂಬತ್ತು": 19, "ಹದಿನೆಂಟು": 18, "ಹದಿನೇಳು": 17, "ಹದಿನಾರು": 16,
    "ಹದಿನೈದು": 15, "ಹದಿನಾಲ್ಕು": 14, "ಹದಿಮೂರು": 13, "ಹನ್ನೆರಡು": 12,
    "ಹನ್ನೊಂದು": 11, "ಹತ್ತು": 10,
}

KANNADA_TENS = {
    "ತೊಂಬತ್ತು": 90, "ಎಂಬತ್ತು": 80, "ಎಪ್ಪತ್ತು": 70, "ಅರವತ್ತು": 60,
    "ಐವತ್ತು": 50, "ನಲವತ್ತು": 40, "ನಲ್ವತ್ತು": 40, "ನಲವತ್ತ": 40,
    "ಮೂವತ್ತು": 30, "ಇಪ್ಪತ್ತು": 20,
}

KANNADA_HUNDREDS = {
    "ತೊಂಬೈನೂರು": 900, "ಎಂಟುನೂರು": 800, "ಏಳನೂರು": 700, "ಆರನೂರು": 600,
    "ಐನೂರು": 500, "ನಾನೂರು": 400, "ಮುನ್ನೂರು": 300, "ಇನ್ನೂರು": 200,
    "ನೂರು": 100,
}

# Fractional terms common in coastal marine dialogue
KANNADA_FRACTIONS = {
    "ಅರ್ಧ": 0.5,
    "ಒಂದೂವರೆ": 1.5,
    "ಎರಡೂವರೆ": 2.5,
    "ಮೂರೂವರೆ": 3.5,
    "ನಾಲ್ಕೂವರೆ": 4.5,
}


def normalise_kannada_text(text: str) -> str:
    """Canonicalise Unicode NFC, map Kannada digits to ASCII, and lowercase."""
    if not text:
        return ""
    # 1. Unicode NFC
    t = unicodedata.normalize("NFC", text)
    # 2. Kannada digits to ASCII
    t = t.translate(KANNADA_DIGITS)
    # 3. Clean multiple whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_kannada_number_words(text: str) -> str:
    """Convert spoken Kannada numbers into ASCII digits inside a text string.
    
    Handles:
    - 'ನಲವತ್ತು' -> '40'
    - 'ನೂರು' -> '100'
    - 'ಸಾವಿರದ ಇನ್ನೂರು' -> '1200'
    - 'ನಾಲ್ಕು ಸಾವಿರ' -> '4000'
    - 'ಮೂರೂವರೆ' -> '3.5'
    """
    t = normalise_kannada_text(text)

    # 1. Replace composite thousands like 'ನಾಲ್ಕು ಸಾವಿರ' -> '4000', 'ಎರಡು ಸಾವಿರ' -> '2000'
    for ones_word, val in KANNADA_ONES.items():
        t = t.replace(f"{ones_word} ಸಾವಿರ", str(val * 1000))

    # 2. Replace 'ಸಾವಿರದ ಇನ್ನೂರು' -> 1200, 'ಸಾವಿರದ ಐನೂರು' -> 1500
    for hund_word, h_val in KANNADA_HUNDREDS.items():
        t = t.replace(f"ಸಾವಿರದ {hund_word}", str(1000 + h_val))

    # 3. Replace standalone thousand
    t = t.replace("ಸಾವಿರ", "1000")

    # 4. Replace hundreds (longer first)
    for hund_word, h_val in KANNADA_HUNDREDS.items():
        t = t.replace(hund_word, str(h_val))

    # 5. Replace tens (longer first)
    for tens_word, t_val in KANNADA_TENS.items():
        t = t.replace(tens_word, str(t_val))

    # 6. Replace teens
    for teen_word, tn_val in KANNADA_TEENS.items():
        t = t.replace(teen_word, str(tn_val))

    # 7. Replace fractions
    for frac_word, f_val in KANNADA_FRACTIONS.items():
        t = t.replace(frac_word, str(f_val))

    # 8. Replace standalone single digits
    for ones_word, o_val in KANNADA_ONES.items():
        # Match ones only when delimited by whitespace or start/end
        t = re.sub(rf"(^|\s){ones_word}(\s|$)", rf"\g<1>{o_val}\g<2>", t)

    return t


def extract_quantities_and_amounts(text: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract weight (kg) and currency amounts (₹) from normalised text."""
    norm = parse_kannada_number_words(text)

    # Extract kg: e.g. '40 ಕೆಜಿ', '40kg', '40 kg', 'ನಲವತ್ತು ಕೆಜಿ'
    kg_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ಕೆಜಿ|kg|kilo|ಕೇಜಿ)(?:\s|$|[^\w])", norm, re.IGNORECASE)
    kg = float(kg_match.group(1)) if kg_match else None

    # Extract price / total: e.g. 'ರೇಟ್ 600', 'ರೂಪಾಯಿ 4000', 'ಕೆಜಿಗೆ 100', '1200 ಡೀಸೆಲ್', '₹100'
    amt_match = re.search(r"(?:₹|ರೂ|ರೂಪಾಯಿ|rs|rate|ರೇಟ್)?\s*(\d+(?:\.\d+)?)\s*(?:ರೂ|ರೂಪಾಯಿ|rs|inr)?(?:\s|$|[^\w])", norm, re.IGNORECASE)
    amt = float(amt_match.group(1)) if amt_match else None

    return kg, amt
