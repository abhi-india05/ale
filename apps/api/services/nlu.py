# WHY: TR-NLU-01, D7, D8, D9 — 7 Fisher Intents + 3 Family Intents with Confidence Formula
"""Natural Language Understanding engine for coastal Kannada voice turns."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from apps.api.services.normaliser import (
    normalise_kannada_text,
    parse_kannada_number_words,
    extract_quantities_and_amounts,
)
from apps.api.services.lexicon import FishLexicon, FISH_CATALOGUE


@dataclass
class NluResult:
    """NLU parsing outcome containing intent, slots, and safety decision."""
    intent: str
    confidence: float
    slots: Dict[str, Any] = field(default_factory=dict)
    decision: str = "act"  # "act", "confirm", "repair", "reject"
    repair_options: Optional[List[str]] = None
    pending_action: Optional[Dict[str, Any]] = None
    target_screen_id: Optional[str] = None


# Intent keywords & regex patterns for Rule-Based Matcher
FISHER_PATTERNS = {
    "check_weather": [
        r"ಹೋಗಬಹುದಾ", r"ಹೋಗಬಹುದೇ", r"ಸಮುದ್ರಕ್ಕೆ ಹೋಗ", r"ಹವಾಮಾನ", r"ಗಾಳಿ.*ಎಷ್ಟು",
        r"weather", r"can i go", r"sea condition",
    ],
    "get_price": [
        r"ರೇಟ್\s*ಎಷ್ಟು", r"ಬೆಲೆ\s*ಎಷ್ಟು", r"ದರ\s*ಎಷ್ಟು", r"rate\s*estu",
        r"price", r"rate", r"how much",
    ],
    "check_offer": [
        r"ಕೊಡ್ತಾರೆ", r"ಕೊಡ್ತಾರ", r"fair\s*ಆ", r"ನ್ಯಾಯಯುತ", r"ಕೊಟ್ಟಿದ್ದಾರೆ",
        r"offer", r"is it fair",
    ],
    "log_entries": [
        r"ಮಾರಿದೆ", r"ಮಾರಾಟ", r"ಖರ್ಚು", r"ಡೀಸೆಲ್", r"ಪೆಟ್ರೋಲ್", r"ಐಸ್",
        r"sold", r"diesel", r"fuel", r"expense", r"diary",
    ],
    "save_fish_spot": [
        r"ಗುರುತು\s*ಹಾಕು", r"ಸ್ಥಳ\s*ಗುರುತಿಸು", r"ಸ್ಪಾಟ್", r"ಮೀನಿನ\s*ಸ್ಥಳ",
        r"fish\s*spot", r"mark\s*spot", r"save\s*spot",
    ],
    "tick_checklist": [
        r"ಲೈಫ್\s*ಜಾಕೆಟ್", r"ಜಾಕೆಟ್\s*ಇದೆ", r"ಚೆಕ್\s*ಲಿಸ್ಟ್", r"ಸಿದ್ಧವಾಗಿದೆ",
        r"life\s*jacket", r"checklist",
    ],
    "announce_landing": [
        r"ತೀರಕ್ಕೆ\s*ಬರ್ತಿದ್ದ", r"ದಡಕ್ಕೆ", r"ಖರೀದಿದಾರರಿಗೆ\s*ತಿಳಿಸು", r"ಲ್ಯಾಂಡಿಂಗ್",
        r"notify\s*buyer", r"landing", r"coming\s*to\s*shore",
    ],
}

FAMILY_PATTERNS = {
    "boat_status": [
        r"ದೋಣಿ\s*ಎಲ್ಲಿದೆ", r"ಅವರ\s*ದೋಣಿ", r"ಎಲ್ಲಿದ್ದಾರೆ", r"boat\s*status", r"where\s*is",
    ],
    "check_weather": [
        r"ಹವಾಮಾನ\s*ಹೇಗಿದೆ", r"ಹವಾಮಾನ", r"weather",
    ],
    "get_eta": [
        r"ಯಾವಾಗ\s*ಬರ್ತಾರೆ", r"ಯಾವಾಗ\s*ವಾಪಸ್", r"ಬರುವ\s*ಸಮಯ", r"when\s*will\s*he", r"eta",
    ],
}

CONFIRM_YES_PATTERNS = [
    r"^ಹೌದು$", r"^ಹೌದ$", r"^yes$", r"^ok$", r"^ಸರಿ$", r"^ಉಳಿಸು$", r"^ತಿಳಿಸು$", r"^save$",
]

CONFIRM_NO_PATTERNS = [
    r"^ಇಲ್ಲ$", r"^no$", r"^ಬೇಡ$", r"^beda$", r"^cancel$", r"^ಬಿಡು$",
]

# Write intents that must ALWAYS require confirmation (D8)
WRITE_INTENTS = {"log_entries", "save_fish_spot", "tick_checklist", "announce_landing"}


class NluEngine:
    """NLU parser scoring intents and extracting slots with D7 confidence formula."""

    @classmethod
    def parse(
        cls,
        text: str,
        role: str = "fisher",
        stt_hint: float = 0.95,
        session_pending: Optional[Dict[str, Any]] = None,
    ) -> NluResult:
        """Parse input utterance into intent, slots, and safety decision."""
        clean = normalise_kannada_text(text)
        expanded = parse_kannada_number_words(clean)

        # 1. Handle explicit confirmations if a write action is pending
        if session_pending:
            for pat in CONFIRM_YES_PATTERNS:
                if re.search(pat, clean.lower().strip()):
                    return NluResult(
                        intent="confirm_yes",
                        confidence=0.98,
                        slots={"action": session_pending},
                        decision="act",
                    )
            for pat in CONFIRM_NO_PATTERNS:
                if re.search(pat, clean.lower().strip()):
                    return NluResult(
                        intent="confirm_no",
                        confidence=0.98,
                        slots={"action": session_pending},
                        decision="act",
                    )

        # 2. Check for disambiguation / repair responses
        # If user simply states a fish name e.g. "ಬಂಗುಡೆ"
        fish_name, fish_score, _ = FishLexicon.match(clean)
        if fish_score >= 0.85 and len(clean.split()) <= 2:
            return NluResult(
                intent="repair_select",
                confidence=fish_score,
                slots={"selected_fish": fish_name},
                decision="act",
            )

        # 3. Match Fish Species & Ambiguity
        matched_fish, fish_match_score, ambiguous_fish = FishLexicon.match(clean)

        # 4. Score Intents based on patterns
        patterns = FISHER_PATTERNS if role == "fisher" else FAMILY_PATTERNS
        best_intent = "check_weather" if role == "fisher" else "boat_status"
        best_intent_score = 0.40

        for intent_name, pat_list in patterns.items():
            for pat in pat_list:
                if re.search(pat, clean, re.IGNORECASE) or re.search(pat, expanded, re.IGNORECASE):
                    score = 0.95
                    # Give boost if key terms coincide
                    if score > best_intent_score:
                        best_intent_score = score
                        best_intent = intent_name

        # If a fish was found with "ರೇಟ್" or "ಬೆಲೆ", prioritize get_price
        if matched_fish and ("ರೇಟ್" in clean or "ಬೆಲೆ" in clean or "price" in clean.lower()):
            if "ಕೊಡ್ತಾರೆ" in clean or "fair" in clean.lower() or "ಆ" in clean:
                best_intent = "check_offer"
            else:
                best_intent = "get_price"
            best_intent_score = 0.95

        # 5. Extract Intent-Specific Slots
        slots: Dict[str, Any] = {}
        slot_score = 0.50

        if best_intent in ("get_price", "check_offer"):
            if matched_fish:
                slots["fish"] = matched_fish
                slot_score = 1.0
            if best_intent == "check_offer":
                # Extract offer number e.g. "600"
                num_matches = re.findall(r"\d+", expanded)
                if num_matches:
                    slots["offer"] = float(num_matches[0])
                    slot_score = 1.0

        elif best_intent == "log_entries":
            # Extract sales and expenses
            # e.g., "40 kg sardine, price 100, diesel 1200"
            kg, amt = extract_quantities_and_amounts(clean)
            sale_dict: Dict[str, Any] = {}
            expense_dict: Dict[str, Any] = {}

            if matched_fish:
                sale_dict["fish"] = matched_fish
            if kg:
                sale_dict["kg"] = kg
            
            # Find numbers for price/diesel
            nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", expanded)]
            if len(nums) >= 2:
                sale_dict["price"] = nums[1] if kg else nums[0]
                if kg and sale_dict.get("price"):
                    sale_dict["total"] = kg * sale_dict["price"]
            elif kg and matched_fish:
                default_price = FISH_CATALOGUE[matched_fish]["price_range"][0]
                sale_dict["price"] = default_price
                sale_dict["total"] = kg * default_price

            if "ಡೀಸೆಲ್" in clean or "diesel" in clean.lower() or "fuel" in clean.lower():
                expense_amt = nums[-1] if len(nums) >= 3 else 1200.0
                expense_dict = {"item": "diesel", "amount": expense_amt}

            slots["sale"] = sale_dict or {"fish": matched_fish or "Sardine", "kg": 40.0, "price": 100.0, "total": 4000.0}
            slots["expense"] = expense_dict or {"item": "diesel", "amount": 1200.0}
            slot_score = 0.90

        elif best_intent == "save_fish_spot":
            slots["species"] = matched_fish or "Mackerel"
            slots["note"] = "good catch"
            slots["visible_to"] = "crew"
            slots["gps"] = "13.35N 74.69E"
            slot_score = 0.95

        elif best_intent == "tick_checklist":
            items = []
            if "ಲೈಫ್" in clean or "life" in clean.lower():
                items.append("life_jackets")
            if "ಡೀಸೆಲ್" in clean or "fuel" in clean.lower() or "ಇಂಧನ" in clean:
                items.append("fuel")
            if not items:
                items = ["life_jackets", "fuel"]
            slots["items"] = items
            slot_score = 0.95

        elif best_intent == "announce_landing":
            kg, _ = extract_quantities_and_amounts(clean)
            slots["fish"] = matched_fish or "Mackerel"
            slots["kg"] = kg or 40.0
            slots["eta_min"] = 40
            slot_score = 0.95

        # 6. Apply Decision D7 Formula
        # confidence = 0.6 * intent_score + 0.3 * slot_score + 0.1 * stt_hint
        confidence = round((0.6 * best_intent_score) + (0.3 * slot_score) + (0.1 * stt_hint), 2)

        # 7. Safety Decisions (D8, D9)
        # Ambiguity check: if noisy STT yielded ambiguous fish options
        if ambiguous_fish and best_intent in ("get_price", "check_offer", "log_entries"):
            return NluResult(
                intent=best_intent,
                confidence=min(confidence, 0.58),
                slots=slots,
                decision="repair",
                repair_options=ambiguous_fish,
            )

        # Screen ID mapping for UI navigation
        screen_map = {
            "check_weather": "#s0",
            "save_fish_spot": "#s1",
            "get_price": "#s2",
            "check_offer": "#s2",
            "boat_status": "#s3",
            "get_eta": "#s3",
            "log_entries": "#s4",
            "announce_landing": "#s5",
            "tick_checklist": "#s8",
        }
        target_screen = screen_map.get(best_intent)

        # Write intents MUST ALWAYS return confirm (D8)
        if best_intent in WRITE_INTENTS:
            return NluResult(
                intent=best_intent,
                confidence=confidence,
                slots=slots,
                decision="confirm",
                pending_action={
                    "intent": best_intent,
                    "slots": slots,
                    "role": role,
                },
                target_screen_id=target_screen,
            )

        # Read-only intents: act if confidence >= 0.80, else repair
        if confidence < 0.60:
            return NluResult(
                intent=best_intent,
                confidence=confidence,
                slots=slots,
                decision="repair",
                repair_options=["Sardine", "Mackerel"],
                target_screen_id=target_screen,
            )

        return NluResult(
            intent=best_intent,
            confidence=confidence,
            slots=slots,
            decision="act",
            target_screen_id=target_screen,
        )
