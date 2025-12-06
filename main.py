"""
TASAUTO - Backend de Tasación vía coches.net
=============================================

AVISO LEGAL:
Este sistema realiza scraping automatizado de coches.net.
- El uso debe respetar los términos y condiciones de coches.net
- Consulta el fichero robots.txt de coches.net antes de usar
- Para uso comercial o masivo, contacta con coches.net para un acuerdo

Este código está pensado para pruebas y prototipado.
"""

import logging
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TASAUTO API", version="1.0.0")

# CORS - Permite llamadas desde tu frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, limita a tu dominio
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


def tasar_en_coches_net(data: TasacionRequest) -> str:
    """
    Abre coches.net, rellena el formulario de tasación y devuelve el valor.
    """
    logger.info(f"Iniciando tasación: {data.marca} {data.modelo} ({data.anio})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # Navegar a la página de tasación
            logger.info("Navegando a coches.net...")
            page.goto("https://www.coches.net/tasacion-de-coches/", timeout=60000, wait_until="networkidle")
            
            # Aceptar cookies si aparece el banner
            try:
                logger.info("Buscando banner de cookies...")
                cookie_btn = page.locator("#didomi-notice-agree-button, button:has-text('Aceptar'), [class*='cookie'] button").first
                if cookie_btn.is_visible(timeout=3000):
                    cookie_btn.click()
                    page.wait_for_timeout(1000)
                    logger.info("Cookies aceptadas")
            except:
                logger.info("No hay banner de cookies visible")
            
            # Esperar a que cargue el formulario
            logger.info("Esperando formulario...")
            page.wait_for_selector("text='Marca'", timeout=15000)
            page.wait_for_timeout(2000)
            
            logger.info("Formulario cargado, rellenando campos...")
            
            # === MARCA ===
            logger.info(f"Seleccionando marca: {data.marca}")
            marca_dropdown = page.locator("text='Marca'").locator("..").locator("..").locator("[class*='sui-'], [class*='select']").first
            if not marca_dropdown.is_visible():
                marca_dropdown = page.locator("[class*='FormField']").filter(has_text="Marca").locator("[class*='select'], [class*='Select']").first
            marca_dropdown.click()
            page.wait_for_timeout(500)
            
            marca_option = page.locator(f"[role='listbox'] >> text='{data.marca}'").first
            if not marca_option.is_visible(timeout=2000):
                marca_option = page.locator(f"li:has-text('{data.marca}'), [class*='option']:has-text('{data.marca}')").first
            marca_option.click()
            page.wait_for_timeout(1500)
            
            # === MODELO ===
            logger.info(f"Seleccionando modelo: {data.modelo}")
            modelo_dropdown = page.locator("text='Modelo'").locator("..").locator("..").locator("[class*='sui-'], [class*='select']").first
            if not modelo_dropdown.is_visible():
                modelo_dropdown = page.locator("[class*='FormField']").filter(has_text="Modelo").locator("[class*='select'], [class*='Select']").first
            modelo_dropdown.click()
            page.wait_for_timeout(500)
            
            modelo_option = page.locator(f"[role='listbox'] >> text='{data.modelo}'").first
            if not modelo_option.is_visible(timeout=2000):
                modelo_option = page.locator(f"li:has-text('{data.modelo}'), [class*='option']:has-text('{data.modelo}')").first
            modelo_option.click()
            page.wait_for_timeout(1500)
            
            # === AÑO ===
            logger.info(f"Seleccionando año: {data.anio}")
            anio_dropdown = page.locator("text='Año'").locator("..").locator("..").locator("[class*='sui-'], [class*='select']").first
            if not anio_dropdown.is_visible():
                anio_dropdown = page.locator("[class*='FormField']").filter(has_text="Año").locator("[class*='select'], [class*='Select']").first
            anio_dropdown.click()
            page.wait_for_timeout(500)
            
            anio_option = page.locator(f"[role='listbox'] >> text='{data.anio}'").first
            if not anio_option.is_visible(timeout=2000):
                anio_option = page.locator(f"li:has-text('{data.anio}'), [class*='option']:has-text('{data.anio}')").first
            anio_option.click()
            page.wait_for_timeout(1000)
            
            # === VERSIÓN (opcional) ===
            if data.version:
                try:
                    logger.info(f"Seleccionando versión: {data.version}")
                    version_dropdown = page.locator("text='Versión'").locator("..").locator("..").locator("[class*='sui-'], [class*='select']").first
                    if version_dropdown.is_visible(timeout=3000):
                        version_dropdown.click()
                        page.wait_for_timeout(500)
                        version_option = page.locator(f"[role='listbox'] >> text='{data.version}'").first
                        if version_option.is_visible(timeout=2000):
                            version_option.click()
                            page.wait_for_timeout(500)
                except Exception as e:
                    logger.info(f"No se pudo seleccionar versión: {e}")
            
            # === KILÓMETROS ===
            logger.info(f"Introduciendo kilómetros: {data.kms}")
            km_input = page.locator("text='Kilómetros del coche'").locator("..").locator("input").first
            if not km_input.is_visible():
                km_input = page.locator("input").nth(0)
            km_input.fill(str(data.kms))
            page.wait_for_timeout(500)
            
            # === CÓDIGO POSTAL (requerido) ===
            logger.info("Introduciendo código postal...")
            cp_input = page.locator("input[placeholder*='01234']").first
            if not cp_input.is_visible():
                cp_input = page.locator("text='Código postal'").locator("..").locator("input").first
            cp_input.fill("28001")
            page.wait_for_timeout(500)
            
            # === ENVIAR FORMULARIO ===
            logger.info("Enviando formulario...")
            submit_btn = page.locator("button:has-text('Obtener tasación')").first
            submit_btn.click()
            
            # Esperar al resultado
            logger.info("Esperando resultado...")
            page.wait_for_timeout(3000)
            
            resultado_selector = "[class*='price'], [class*='result'], [class*='valor'], [class*='tasacion']"
            page.wait_for_selector(resultado_selector, timeout=30000)
            
            resultado = page.locator(resultado_selector).first
            valor = resultado.text_content()
            
            if valor:
                match = re.search(r'[\d.,]+\s*€', valor)
                if match:
                    valor = match.group(0)
            
            logger.info(f"Tasación completada: {valor}")
            return valor.strip() if valor else "Valor no disponible"
            
        except PlaywrightTimeout as e:
            logger.error(f"Timeout: {str(e)}")
            raise Exception("La página tardó demasiado en responder")
        except Exception as e:
            logger.error(f"Error en scraping: {str(e)}")
            raise
        finally:
            browser.close()


@app.post("/api/tasar", response_model=TasacionResponse)
async def tasar(request: TasacionRequest):
    logger.info(f"Petición recibida: {request.marca} {request.modelo}")
    
    try:
        valor = tasar_en_coches_net(request)
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
