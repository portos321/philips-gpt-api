from fastapi import FastAPI, HTTPException, Query
import json
import os
import re
import unicodedata
from difflib import get_close_matches

app = FastAPI(title="Philips NA55x Manual API", version="2.1")

DB_PATH = os.environ.get("DB_PATH", "philips_complete.json")  # použi komplet JSON

with open(DB_PATH, "r", encoding="utf-8") as f:
    DB = json.load(f)


# ----------------------------
# Helpers: normalization
# ----------------------------
def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 +()×x/-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


# Build index: normalized food -> original food key
FOOD_INDEX = {norm(k): k for k in DB.keys()}
FOOD_KEYS_NORM = list(FOOD_INDEX.keys())


# ----------------------------
# Synonyms (expand anytime)
# ----------------------------
SYNONYMS = {
    # fries
    "hranolky": "hranolky",
    "mrazene hranolky": "mrazene hranol",
    "frozen fries": "mrazene hranol",
    "chips": "hranolky",

    # chicken
    "nugety": "kuracie nugety",
    "nuggets": "kuracie nugety",
    "kuracie stehna": "kuracie stehna",
    "stehna": "kuracie stehna",
    "kuracie prsia": "kuracie prsia",
    "prsia": "kuracie prsia",
    "cele kura": "cele kurca",
    "kurca": "cele kurca",

    # fish
    "ryba": "ryby",
    "ryby": "ryby",
    "filety": "rybie filety",
    "fillet": "rybie filety",

    # veg
    "zelenina": "zelenina",
    "zeler": "korenova zelenina",
    "celer": "korenova zelenina",
    "korenova zelenina": "korenova zelenina",
    "mrkva": "mrkva",
    "karfiol": "karfiol",

    # other
    "falafel": "veganske",
    "kolac": "kolac",
    "chlieb": "chlieb",
    "domaci chlieb": "domaci chlieb",
    "ryza": "ryza",
    "knedlicky": "knedlicky",
}


def resolve_food(query: str) -> str | None:
    q = norm(query)
    if not q:
        return None

    # 1) direct normalized match
    if q in FOOD_INDEX:
        return FOOD_INDEX[q]

    # 2) synonym hint -> contains search
    if q in SYNONYMS:
        hint = SYNONYMS[q]
        for nk, original in FOOD_INDEX.items():
            if hint in nk:
                return original

    # 3) contains search (useful when DB has long names)
    for nk, original in FOOD_INDEX.items():
        if q in nk:
            return original

    # 4) fuzzy match
    close = get_close_matches(q, FOOD_KEYS_NORM, n=1, cutoff=0.72)
    if close:
        return FOOD_INDEX[close[0]]

    return None


def suggestions(query: str, n: int = 8):
    q = norm(query)
    close = get_close_matches(q, FOOD_KEYS_NORM, n=n, cutoff=0.55)
    return [FOOD_INDEX[c] for c in close]


# ----------------------------
# Endpoints
# ----------------------------
@app.get("/health")
def health():
    return {"ok": True, "items": len(DB)}


@app.get("/foods")
def foods():
    return sorted(DB.keys())


@app.get("/cook")
def cook(
    food: str = Query(..., description="Potravina (môže byť aj bežný názov, napr. 'hranolky', 'zeler', 'nugety')"),
    mode: str = Query(..., description="Režim (napr. 'Teplý vzduch', 'Para', 'Para + teplý vzduch'...)"),
    pan: str | None = Query(None, description="Voliteľné: 'Veľká nádoba' alebo 'Malá nádoba'. Ak vynecháš, vráti obe."),
):
    resolved = resolve_food(food)

    # Food not found
    if not resolved:
        return {
            "found": False,
            "message": "Potravina sa nenašla v tabuľke.",
            "suggestions": suggestions(food)
        }

    item = DB[resolved]

    # Mode not found -> auto fallback to first available mode
    if mode not in item:
        first_mode = list(item.keys())[0]
        return {
            "found": True,
            "food": resolved,
            "requested_mode": mode,
            "mode_used": first_mode,
            "warning": f"Režim '{mode}' nie je pre túto potravinu v manuáli. Použil som '{first_mode}'.",
            "results": item[first_mode]
        }

    mode_obj = item[mode]

    # If user asked for a specific pan
    if pan:
        if pan not in mode_obj:
            return {
                "found": False,
                "message": "Nádoba sa pre túto potravinu a režim nenašla.",
                "available_pans": sorted(mode_obj.keys()),
                "food": resolved,
                "mode": mode
            }

        return {
            "found": True,
            "food": resolved,
            "mode": mode,
            "results": {pan: mode_obj[pan]}
        }

    # Default: return both pans (as available)
    return {
        "found": True,
        "food": resolved,
        "mode": mode,
        "results": mode_obj
    }
