from fastapi import FastAPI, Query
import json
import os

app = FastAPI(title="Philips NA55x Manual API", version="3.0")

DB_PATH = os.environ.get("DB_PATH", "philips_complete.json")

with open(DB_PATH, "r", encoding="utf-8") as f:
    DB = json.load(f)

@app.get("/health")
def health():
    return {"ok": True, "foods": len(DB)}

@app.get("/foods")
def foods():
    # zoznam kanonických položiek z manuálu
    return sorted(DB.keys())

@app.get("/cook")
def cook(
    food: str = Query(..., description="Kanonický názov jedla z manuálu (presne ako v /foods)"),
    mode: str | None = Query(None, description="Nepovinné. Ak chýba, vráti všetky dostupné režimy."),
):
    if food not in DB:
        return {"found": False, "message": "Food not found in manual table.", "available": sorted(DB.keys())}

    item = DB[food]  # {mode: {pan: {...}}}

    if mode is None or mode == "":
        # vráť všetky režimy, ktoré sú dostupné pre dané jedlo
        return {"found": True, "food": food, "results": item}

    if mode not in item:
        # vráť dostupné režimy, nech si klient (GPT) vyberie
        return {
            "found": False,
            "food": food,
            "message": "Mode not found for this food.",
            "available_modes": sorted(item.keys()),
            "results_all_modes": item
        }

    return {"found": True, "food": food, "mode": mode, "results": item[mode]}
