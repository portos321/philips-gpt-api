from fastapi import FastAPI, HTTPException, Query
import json
import os

app = FastAPI(title="Philips Manual API", version="1.0")

DB_PATH = os.environ.get("DB_PATH", "philips_manual_extract.json")

with open(DB_PATH, "r", encoding="utf-8") as f:
    DB = json.load(f)

@app.get("/cook")
def cook(
    food: str = Query(..., description="Názov potraviny presne ako v databáze"),
    mode: str = Query(..., description="Režim (napr. Teplý vzduch / Para / Para + teplý vzduch)"),
    pan: str = Query("Veľká nádoba", description="Veľká nádoba alebo Malá nádoba"),
):
    if food not in DB:
        raise HTTPException(404, detail="Food not found")

    if mode not in DB[food]:
        raise HTTPException(404, detail="Mode not found for this food")

    if pan not in DB[food][mode]:
        raise HTTPException(404, detail="Pan not found for this food/mode")

    return {
        "food": food,
        "mode": mode,
        "pan": pan,
        **DB[food][mode][pan]
    }

@app.get("/foods")
def foods():
    return sorted(DB.keys())
