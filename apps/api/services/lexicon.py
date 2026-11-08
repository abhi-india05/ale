# WHY: TR-NLU-02, D7, D15 — Fish lexicon matcher with phonetic aliases and fuzzy distance
"""Coastal fish species matching with Kannada aliases and ambiguity detection."""

from typing import Dict, List, Optional, Tuple
import unicodedata
from apps.api.services.normaliser import normalise_kannada_text


FISH_CATALOGUE = {
    "Sardine": {
        "name_en": "Sardine",
        "name_kn": "ಬೂತಾಯಿ",
        "emoji": "🐟",
        "price_range": (90, 110),
        "aliases": [
            "sardine", "sardines", "ಬೂತಾಯಿ", "ಬೂತಾಯ", "boothaayi", "butai", "mathi",
            "tarli", "ಮತ್ತಿ", "buthayi", "boothayi", "bhootai"
        ],
    },
    "Mackerel": {
        "name_en": "Mackerel",
        "name_kn": "ಬಂಗುಡೆ",
        "emoji": "🐠",
        "price_range": (140, 170),
        "aliases": [
            "mackerel", "mackerels", "ಬಂಗುಡೆ", "ಬಂಗುಡ", "bangude", "bangade",
            "ayala", "ಅಯಲ", "bangada", "bangudey", "bangudei"
        ],
    },
    "Pomfret": {
        "name_en": "Pomfret",
        "name_kn": "ಮಾಂಜಿ",
        "emoji": "🐡",
        "price_range": (620, 760),
        "aliases": [
            "pomfret", "pomfrets", "ಮಾಂಜಿ", "ಮಾಂಜ", "maanji", "manji", "paplet",
            "white pomfret", "black pomfret", "ಪಾಪ್ಲೆಟ್"
        ],
    },
    "Prawns": {
        "name_en": "Prawns",
        "name_kn": "ಸಿಗಡಿ",
        "emoji": "🦐",
        "price_range": (380, 450),
        "aliases": [
            "prawns", "prawn", "ಸಿಗಡಿ", "ಸಿಗಡೆ", "sigadi", "shrimp", "shrimps",
            "jhinga", "kolambi", "ಚಿಮ್ಮೀನ್"
        ],
    },
}


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute string similarity ratio between 0.0 and 1.0."""
    s1, s2 = s1.lower(), s2.lower()
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,      # deletion
                matrix[i][j - 1] + 1,      # insertion
                matrix[i - 1][j - 1] + cost  # substitution
            )

    dist = matrix[len1][len2]
    max_len = max(len1, len2)
    return 1.0 - (dist / max_len)


class FishLexicon:
    """Matcher for identifying fish species from multilingual user transcripts."""

    @classmethod
    def match(cls, text: str) -> Tuple[Optional[str], float, Optional[List[str]]]:
        """Match fish species from text.
        
        Returns:
            (matched_species_en, score, ambiguous_species_list_if_any)
        """
        clean_text = normalise_kannada_text(text).lower()
        tokens = clean_text.split()

        scores: Dict[str, float] = {k: 0.0 for k in FISH_CATALOGUE}

        for species_key, info in FISH_CATALOGUE.items():
            best_score = 0.0
            for alias in info["aliases"]:
                alias_lower = alias.lower()
                # Direct substring match gets full 1.0
                if alias_lower in clean_text:
                    best_score = 1.0
                    break
                # Fuzzy token match for noisy STT syllables
                for token in tokens:
                    sim = _levenshtein_ratio(alias_lower, token)
                    if sim > best_score:
                        best_score = sim
            scores[species_key] = best_score

        # Sort species by descending score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_species, top_score = sorted_scores[0]
        second_species, second_score = sorted_scores[1]

        # Check for ambiguity: if top two are within 0.1 of each other and > 0.45
        ambiguous = None
        if top_score > 0.45 and (top_score - second_score) <= 0.10 and second_score > 0.40:
            ambiguous = [top_species, second_species]

        if top_score >= 0.50:
            return top_species, top_score, ambiguous
        
        return None, 0.0, None

    @classmethod
    def get_info(cls, species: str) -> Optional[dict]:
        """Fetch metadata for a species."""
        return FISH_CATALOGUE.get(species)
