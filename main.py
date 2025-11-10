import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductIn(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
    image: Optional[str] = None
    rating: Optional[float] = 4.5
    reviews: Optional[int] = 0


class ProductOut(ProductIn):
    id: str


@app.get("/")
def read_root():
    return {"message": "Shopping API running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Utilities to convert Mongo docs

def _doc_to_product(doc) -> ProductOut:
    return ProductOut(
        id=str(doc.get("_id")),
        title=doc.get("title"),
        description=doc.get("description"),
        price=float(doc.get("price", 0)),
        category=doc.get("category"),
        in_stock=bool(doc.get("in_stock", True)),
        image=doc.get("image"),
        rating=float(doc.get("rating", 4.5)),
        reviews=int(doc.get("reviews", 0)),
    )


@app.get("/api/products", response_model=List[ProductOut])
def list_products(q: Optional[str] = Query(None), category: Optional[str] = Query(None), limit: int = Query(24, ge=1, le=100)):
    try:
        from database import db
    except Exception:
        raise HTTPException(status_code=503, detail="Database not configured")

    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    filters = {}
    if q:
        # Simple text search across title/description
        filters["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    if category:
        filters["category"] = category

    cursor = db["product"].find(filters).limit(limit)
    results = [_doc_to_product(doc) for doc in cursor]
    return results


@app.post("/api/products", response_model=str)
def create_product(product: ProductIn):
    try:
        from database import db
        from datetime import datetime, timezone
    except Exception:
        raise HTTPException(status_code=503, detail="Database not configured")

    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    data = product.model_dump()
    data["created_at"] = datetime.now(timezone.utc)
    data["updated_at"] = datetime.now(timezone.utc)
    result = db["product"].insert_one(data)
    return str(result.inserted_id)


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    try:
        from database import db
    except Exception:
        raise HTTPException(status_code=503, detail="Database not configured")

    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")

    doc = db["product"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return _doc_to_product(doc)


@app.get("/api/categories", response_model=List[str])
def list_categories():
    try:
        from database import db
    except Exception:
        raise HTTPException(status_code=503, detail="Database not configured")

    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    categories = db["product"].distinct("category")
    return [c for c in categories if c]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
