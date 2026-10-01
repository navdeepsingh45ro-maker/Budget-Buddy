"""Detect an expense's subcategory (merchant/app/person) from its note, without AI.

Used for manually typed expenses. Voice and receipt entries already get their
merchant from Gemini. Returns None when nothing recognisable is found.
"""
import re

# keyword (lowercase, matched as a whole word or phrase) -> display name
KNOWN_MERCHANTS = {
    # Food delivery, restaurants, cafes
    "swiggy": "Swiggy", "zomato": "Zomato", "domino's": "Domino's", "dominos": "Domino's",
    "pizza hut": "Pizza Hut", "mcdonald's": "McDonald's", "mcdonalds": "McDonald's", "kfc": "KFC",
    "burger king": "Burger King", "subway": "Subway", "starbucks": "Starbucks",
    "cafe coffee day": "Cafe Coffee Day", "ccd": "Cafe Coffee Day", "chaayos": "Chaayos",
    "haldiram's": "Haldiram's", "haldirams": "Haldiram's",
    # Groceries and quick commerce
    "blinkit": "Blinkit", "zepto": "Zepto", "bigbasket": "BigBasket", "instamart": "Instamart",
    "dmart": "DMart", "reliance fresh": "Reliance Fresh", "jiomart": "JioMart", "more supermarket": "More",
    # Shopping
    "amazon": "Amazon", "flipkart": "Flipkart", "myntra": "Myntra", "ajio": "Ajio", "meesho": "Meesho",
    "nykaa": "Nykaa", "decathlon": "Decathlon", "ikea": "IKEA", "croma": "Croma",
    # Transport and travel
    "uber": "Uber", "ola": "Ola", "rapido": "Rapido", "metro": "Metro", "irctc": "IRCTC",
    "indigo": "IndiGo", "air india": "Air India", "makemytrip": "MakeMyTrip", "redbus": "redBus",
    "petrol": "Fuel", "diesel": "Fuel", "fuel": "Fuel",
    # Subscriptions and entertainment
    "netflix": "Netflix", "prime video": "Prime Video", "amazon prime": "Amazon Prime",
    "hotstar": "Hotstar", "jiocinema": "JioCinema", "spotify": "Spotify", "youtube premium": "YouTube Premium",
    "apple music": "Apple Music", "icloud": "iCloud", "chatgpt": "ChatGPT",
    "bookmyshow": "BookMyShow", "pvr": "PVR", "inox": "INOX",
    # Bills and utilities
    "electricity": "Electricity", "water bill": "Water", "wifi": "Internet", "broadband": "Internet",
    "airtel": "Airtel", "jio": "Jio", "vodafone": "Vi", "recharge": "Mobile Recharge", "gas cylinder": "Gas",
    # Health
    "apollo": "Apollo", "pharmeasy": "PharmEasy", "1mg": "Tata 1mg", "pharmacy": "Pharmacy",
    "medicine": "Medicines", "gym": "Gym",
    # Family
    "mom": "Mom", "mother": "Mom", "dad": "Dad", "father": "Dad", "brother": "Brother",
    "sister": "Sister", "wife": "Wife", "husband": "Husband",
}

# Longest phrases first, so "amazon prime" wins over "amazon".
_PATTERNS = [
    (re.compile(r"(?<![\w'])" + re.escape(key) + r"(?![\w'])", re.IGNORECASE), name)
    for key, name in sorted(KNOWN_MERCHANTS.items(), key=lambda kv: -len(kv[0]))
]

# "pizza from Pizza Hut", "lunch at Barbeque Nation": capitalised words after from/at.
_FROM_AT = re.compile(r"\b(?:from|at)\s+((?:[A-Z][\w'&.-]*)(?:\s+[A-Z][\w'&.-]*){0,2})")


def detect_subcategory(note: str | None) -> str | None:
    if not note:
        return None
    for pattern, name in _PATTERNS:
        if pattern.search(note):
            return name
    match = _FROM_AT.search(note)
    if match:
        return match.group(1).strip()[:50]
    return None
