"""
JAN Nutrition Database — standalone app for Y&Y Trading LLC.

Run:  python app.py
Then open on your PHONE (same Wi-Fi):  http://<your-PC-IP>:8000

This is self-contained and does NOT depend on the AI-agent app in the
parent folder.
"""

import os
import base64
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

import jan_db

app = FastAPI(title="Y&Y JAN Nutrition Database")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jan_db.init_db()


class ProductIn(BaseModel):
    jan: str
    name: Optional[str] = None
    serving_size: Optional[str] = None
    energy_kcal: Optional[str] = None
    protein_g: Optional[str] = None
    fat_g: Optional[str] = None
    carbs_g: Optional[str] = None
    salt_g: Optional[str] = None
    source: str = "manual"
    notes: Optional[str] = None
    image_base64: Optional[str] = None  # optional label photo for OCR (not stored)


@app.get("/")
async def home():
    """Mobile phone-camera collector. Open this URL on your phone."""
    try:
        with open("scanner.html", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>scanner.html not found</h1>", status_code=500)


@app.post("/api/jan/scan")
async def jan_scan(product: ProductIn):
    """Save one scanned product. If an image is sent and fields are blank,
    run OCR (currently a stub) to try to fill them — see jan_db.py."""
    data = product.model_dump(exclude={"jan", "image_base64"})

    has_numbers = any(data.get(f) for f in jan_db.NUTRITION_FIELDS)
    if product.image_base64 and not has_numbers:
        try:
            image_bytes = base64.b64decode(product.image_base64.split(",")[-1])
            ocr = jan_db.extract_nutrition_from_image(image_bytes)
            for k, v in ocr.items():
                if v is not None and not data.get(k):
                    data[k] = v
            data["source"] = "ocr"
        except Exception:
            pass  # fall back to whatever the user typed

    try:
        return jan_db.upsert_product(product.jan, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/jan/stats")
async def jan_stats():
    """Coverage numbers — proof of value for buyers."""
    return jan_db.stats()


@app.get("/api/jan/list")
async def jan_list(limit: int = 100, offset: int = 0, search: str = ""):
    return jan_db.list_products(limit=limit, offset=offset, search=search)


@app.get("/api/jan/{jan}")
async def jan_lookup(jan: str):
    """THE saleable endpoint: JAN in -> nutrition JSON out."""
    product = jan_db.get_product(jan)
    if not product:
        raise HTTPException(status_code=404, detail=f"JAN '{jan}' not in database")
    return product


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\n  Y&Y JAN Nutrition Database")
    print(f"  On this PC:  http://localhost:{port}")
    print(f"  On phone:    http://<your-PC-IP>:{port}  (run 'ipconfig' for the IP)\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
