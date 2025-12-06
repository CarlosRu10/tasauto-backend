"""
TASAUTO - Backend de Tasación vía coches.net
=============================================
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TASAUTO API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TasacionRequest(BaseModel):
    marca: str
    modelo: str
    version: str
    anio: int
    kms: int

class TasacionResponse(BaseModel):
    ok: bool
    valor: str | None = None
    error: str | None = None

async def tasar_en_coches_net(data: TasacionRequest) -> str:
    logger.info(f"Iniciando tasación: {data.marca} {data.modelo} ({data.anio})")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        try:
            await page.goto("https://www.coches.net/tasacion-de-coches/", timeout=30000)
            
            try:
                await page.click("button#didomi-notice-agree-button", timeout=5000)
            except:
                pass
            
            await page.wait_for_selector("select[name='brand']", timeout=10000)
            await page.select_option("select[name='brand']", label=data.marca)
            await page.wait_for_timeout(1000)
            
            await page.wait_for_selector("select[name='model']", timeout=10000)
            await page.select_option("select[name='model']", label=data.modelo)
            await page.wait_for_timeout(1000)
            
            try:
                await page.wait_for_selector("select[name='version']", timeout=5000)
                await page.select_option("select[name='version']", label=data.version)
                await page.wait_for_timeout(500)
            except:
                logger.info("Campo versión no encontrado, continuando...")
            
            await page.select_option("select[name='year']", label=str(data.anio))
            await page.wait_for_timeout(500)
            
            km_input = page.locator("input[name='km'], input[name='kilometers']").first
            await km_input.fill(str(data.kms))
            
            await page.click("button[type='submit'], .btn-tasar, button:has-text('Tasar')")
            
            await page.wait_for_selector(".resultado-tasacion, .valuation-result, .price-result", timeout=20000)
            
            resultado = page.locator(".resultado-tasacion, .valuation-result, .price-result").first
            valor = await resultado.text_content()
            
            logger.info(f"Tasación completada: {valor}")
            return valor.strip() if valor else "Valor no disponible"
            
        except PlaywrightTimeout:
            logger.error("Timeout esperando elementos en la página")
            raise Exception("La página tardó demasiado en responder")
        except Exception as e:
            logger.error(f"Error en scraping: {str(e)}")
            raise
        finally:
            await browser.close()

@app.post("/api/tasar", response_model=TasacionResponse)
async def tasar(request: TasacionRequest):
    logger.info(f"Petición recibida: {request.marca} {request.modelo}")
    
    try:
        valor = await tasar_en_coches_net(request)
        return TasacionResponse(ok=True, valor=valor)
    except Exception as e:
        logger.error(f"Error en tasación: {str(e)}")
        return TasacionResponse(
            ok=False, 
            error="No se ha podido obtener la tasación en este momento."
        )

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
