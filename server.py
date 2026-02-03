from fastapi import FastAPI, HTTPException, Query
import json, os, re, unicodedata
from difflib import get_close_matches

app = FastAPI(title="Philips Manual API", version="2.0")

DB_PATH = os.environ.get("DB_PATH", "philips_manual_extract.json")

with open(DB_PATH, "r", encoding="utf-8") as f:
    DB = json.load(f)

# --- Normalizácia textu (bez diakritiky, malé písmená) ---
def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 +()×x/-]", "", s)  # povolíme aj znaky ako ×
    return re.sub(r"\s+", " ", s).strip()

# --- Index: normalizovaný názov -> originál kľúč z DB ---
FOOD_INDEX = {norm(k): k for k in DB.keys()}
FOOD_KEYS_NORM = list(FOOD_INDEX.keys())

# --- Synonymá (môžeš rozširovať) ---
SYNONYMS = {
    "hranolky": "domace hranolky",
    "mrazene hranolky": "tenke mrazene hranolceky",
    "frozen fries": "tenke mrazene hranolceky",
    "nugety": "mrazene kuracie nugety",
    "spring rolls": "mrazene jarne zavitky",
    "zavitky": "mrazene jarne zavitky",
    "kuracie stehna": "kuracie stehna",
    "kuracie prsia": "kuracie prsia",
    "cele kura": "cele kurca",
    "ryba": "cele ryby",
    "filety": "rybie filety",
    "zelenina": "zmiesana zelenina",
    "falafel": "veganske",
    "kolac": "kolac",
    "chlieb": "domaci chlieb",
}

def resolve_food(query: str) -> str | None:
    q = norm(query)

    # 1) Priame zhody
    if q in FOOD_INDEX:
        return FOOD_INDEX[q]

    # 2) Synonymá -> pokus o match podľa obsahu
    if q in SYNONYMS:
        hint = SYNONYMS[q]
        # nájdi prvý DB názov, ktorý obsahuje hint
        for nk, original in FOOD_INDEX.items():
            if hint in nk:
                return original

    # 3) “contains” match (užitočné pre dlhé názvy)
    for nk, original in FOOD_INDEX.items():
        if q and q in nk:
            return original

    # 4) Fuzzy match (najbližší názov)
    close = get_close_matches(q, FOOD_KEYS_NORM, n=1, cutoff=0.72)
    if close:
        return FOOD_INDEX[close[0]]

    return None

def suggestions(query: str, n: int = 8):
    q = norm(query)
    close = get_close_matches(q, FOOD_KEYS_NORM, n=n, cutoff=0.55)
    return [FOOD_INDEX[c] for c in close]

@app.get("/foods")
def foods():
    return sorted(DB.keys())

@app.get("/cook")
def cook(
    food: str = Query(..., description="Potravina (môže byť aj bežný názov: 'hranolky', 'nugety'...)"),
    mode: str = Query(..., description="Režim presne ako v DB (napr. 'Teplý vzduch', 'Para', 'Para + teplý vzduch')"),
    pan: str | None = Query(None, description="Voliteľné: 'Veľká nádoba' alebo 'Malá nádoba'. Ak nevyplníš, vráti obe."),
):
    resolved = resolve_food(food)
    if not resolved:
        return {
            "found": False,
            "message": "Potravina sa nenašla. Skús iný názov alebo vyber z návrhov.",
            "suggestions": suggestions(food)
        }

    item = DB[resolved]
    if mode not in item:
        return {
            "found": False,
            "message": "Režim sa pre túto potravinu nenašiel.",
            "available_modes": sorted(item.keys()),
            "food": resolved
        }

    mode_obj = item[mode]

    # Ak používateľ zadal pan -> vráť len jednu
    if pan:
        if pan not in mode_obj:
            return {
                "found": False,
                "message": "Nádoba sa nenašla pre danú potravinu a režim.",
                "available_pans": sorted(mode_obj.keys()),
                "food": resolved,
                "mode": mode
            }
        return {
            "found": True,
            "food": resolved,
            "mode": mode,
            "results": {
                pan: mode_obj[pan]
            }
        }

    # Inak vráť obe nádoby naraz (ak existujú)
    return {
        "found": True,
        "food": resolved,
        "mode": mode,
        "results": mode_obj
    }
