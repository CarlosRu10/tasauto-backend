import os
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno (.env en local, vars en producción)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en variables de entorno")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI(
    title="Tasauto Backend",
    description="Backend ETL para TASAUTO: agrega raw_listings -> market_prices",
    version="0.1.0",
)


def km_to_range(km: int) -> str:
    """Convierte kilómetros en rangos de texto coherentes con la web."""
    if km is None:
        return ">180k"
    if km < 60000:
        return "<60k"
    elif km < 120000:
        return "60-120k"
    elif km < 180000:
        return "120-180k"
    else:
        return ">180k"


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/etl/rebuild-market-prices")
def rebuild_market_prices(limit: int = 50000):
    """
    Recalcula la tabla market_prices a partir de raw_listings.

    Flujo:
    1. Leer raw_listings (últimos N registros).
    2. Limpiar outliers y nulos básicos.
    3. Calcular km_range.
    4. Agrupar por brand, model, year, km_range.
    5. Calcular price_min, price_max, price_avg y sample_size.
    6. Upsert en market_prices.
    """

    try:
        # 1. Leer datos desde Supabase
        # Puedes añadir filtros de fechas (fetched_at) si quieres.
        resp = (
            supabase.table("raw_listings")
            .select("*")
            .limit(limit)
            .execute()
        )

        rows = resp.data

        if not rows:
            return JSONResponse({"message": "No hay datos en raw_listings para procesar"}, status_code=200)

        df = pd.DataFrame(rows)

        # 2. Limpieza básica
        # Asegúrate de que las columnas existan en tu tabla raw_listings
        required_cols = ["brand", "model", "year", "km", "price"]
        for col in required_cols:
            if col not in df.columns:
                raise RuntimeError(f"Falta la columna '{col}' en raw_listings")

        # Quitar nulos y registros claramente inválidos
        df = df.dropna(subset=["brand", "model", "year", "km", "price"])
        df = df[(df["price"] > 500) & (df["price"] < 200000)]
        df = df[(df["year"] >= 1990) & (df["year"] <= datetime.utcnow().year)]

        # Forzar tipos numéricos por seguridad
        df["km"] = pd.to_numeric(df["km"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

        df = df.dropna(subset=["km", "price", "year"])

        # 3. Calcular km_range
        df["km_range"] = df["km"].astype(int).apply(km_to_range)

        # 4. Agrupar
        grouped = (
            df.groupby(["brand", "model", "year", "km_range"])["price"]
            .agg(["count", "min", "max", "median"])
            .reset_index()
        )

        grouped = grouped.rename(
            columns={
                "count": "sample_size",
                "min": "price_min",
                "max": "price_max",
                "median": "price_avg",
            }
        )

        # 5. Upsert en market_prices
        upsert_payload = []
        now = datetime.utcnow().isoformat()

        for _, row in grouped.iterrows():
            upsert_payload.append(
                {
                    "brand": row["brand"],
                    "model": row["model"],
                    "year": int(row["year"]),
                    "km_range": row["km_range"],
                    "price_min": float(row["price_min"]),
                    "price_max": float(row["price_max"]),
                    "price_avg": float(row["price_avg"]),
                    "sample_size": int(row["sample_size"]),
                    "updated_at": now,
                }
            )

        if not upsert_payload:
            return JSONResponse({"message": "No se generaron agregados válidos"}, status_code=200)

        # IMPORTANTE: necesitas una unique constraint en market_prices para (brand, model, year, km_range)
        # para que el upsert funcione correctamente.
        upsert_resp = supabase.table("market_prices").upsert(upsert_payload).execute()

        return {
            "message": "market_prices reconstruido correctamente",
            "rows_aggregated": len(grouped),
            "rows_upserted": len(upsert_resp.data) if upsert_resp.data else len(grouped),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
