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
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

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


async def tasar_en_coches_net(data: TasacionRequest) -> str:
    """
    Abre coches.net, rellena el formulario de tasación y devuelve el valor.
    
    NOTA: Los selectores pueden cambiar si coches.net actualiza su web.
    Revisa la página manualmente si deja de funcionar.
    """
    logger.info(f"Iniciando tasación: {data.marca} {data.modelo} ({data.anio})")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Navegar a la página de tasación
            logger.info("Navegando a coches.net...")
            await page.goto("https://www.coches.net/tasacion-de-coches/", timeout=60000, wait_until="networkidle")
            
            # Aceptar cookies si aparece el banner
            try:
                logger.info("Buscando banner de cookies...")
                cookie_btn = page.locator("#didomi-notice-agree-button, button:has-text('Aceptar'), [class*='cookie'] button").first
                if await cookie_btn.is_visible(timeout=3000):
                    await cookie_btn.click()
                    await page.wait_for_timeout(1000)
                    logger.info("Cookies aceptadas")
            except:
                logger.info("No hay banner de cookies visible")
            
            # Esperar a que cargue el formulario
            logger.info("Esperando formulario...")
            await page.wait_for_selector("text='Marca'", timeout=15000)
            await page.wait_for_timeout(2000)  # Dar tiempo extra para que cargue el JS
            
            # Tomar screenshot para debug
            logger.info("Formulario cargado, rellenando campos...")
            
            # === MARCA ===
            logger.info(f"Seleccionando marca: {data.marca}")
            # Click en el dropdown de marca (primer dropdown después del label "Marca")
            marca_dropdown = page.locator("text='Marca'").locator("..").locator("..").locator("[class*='sui-'], [class*='select']").first
            if not await marca_dropdown.is_visible():
                marca_dropdown = page.locator("[class*='FormField']").filter(has_text="Marca").locator("[class*='select'], [class*='Select']").first
            await marca_dropdown.click()
            await page.wait_for_timeout(500)
            
            # Buscar la marca en el listado
            marca_option = page.locator(f"[role='listbox'] >> text='{data.marca}'").first
            if not await marca_option.is_visible(timeout=2000):
                marca_option = page.locator(f"li:has-text('{data.marca}'), [class*='option']:has-text('{data.marca}')").first
            await marca_option.click()
            await page.wait_for_timeout(1500)  # Esperar a que carguen los modelos
            
            # === MODELO ===
            logger.info(f"Seleccionando modelo: {data.modelo}")
            modelo_dropdown = page.locator("text='Modelo'").locator("..").locator("..").locator("[class*='sui-'], [class*='select']").first
            if not await modelo_dropdown.is_visible():
                modelo_dropdown = page.locator("[class*='FormField']").filter(has_text="Modelo").locator("[class*='select'], [class*='Select']").first
            await modelo_dropdown.click()
            await page.wait_for_timeout(500)
            
            modelo_option = page.locator(f"[role='listbox'] >> text='{data.modelo}'").first
            if not await modelo_option.is_visible(timeout=2000):
                modelo_option = page.locator(f"li:has-text('{data.modelo}'), [class*='option']:has-text('{data.modelo}')").first
            await modelo_option.click()
            await page.wait_for_timeout(1500)
            
            # === AÑO ===
            logger.info(f"Seleccionando año: {data.anio}")
            anio_dropdown = page.locator("text='Año'").locator("..").locator("..").locator("[class*='sui-'], [class*='select']").first
            if not await anio_dropdown.is_visible():
                anio_dropdown = page.locator("[class*='FormField']").filter(has_text="Año").locator("[class*='select'], [class*='Select']").first
            await anio_dropdown.click()
            await page.wait_for_timeout(500)
            
            anio_option = page.locator(f"[role='listbox'] >> text='{data.anio}'").first
            if not await anio_option.is_visible(timeout=2000):
                anio_option = page.locator(f"li:has-text('{data.anio}'), [class*='option']:has-text('{data.anio}')").first
            await anio_option.click()
            await page.wait_for_timeout(1000)
            
            # === VERSIÓN (opcional) ===
            if data.version:
                try:
                    logger.info(f"Seleccionando versión: {data.version}")
                    version_dropdown = page.locator("text='Versión'").locator("..").locator("..").locator("[class*='sui-'], [class*='select']").first
                    if await version_dropdown.is_visible(timeout=3000):
                        await version_dropdown.click()
                        await page.wait_for_timeout(500)
                        version_option = page.locator(f"[role='listbox'] >> text='{data.version}'").first
                        if await version_option.is_visible(timeout=2000):
                            await version_option.click()
                            await page.wait_for_timeout(500)
                except Exception as e:
                    logger.info(f"No se pudo seleccionar versión: {e}")
            
            # === KILÓMETROS ===
            logger.info(f"Introduciendo kilómetros: {data.kms}")
            km_input = page.locator("input[placeholder*='ilómetro'], input[type='number'], [class*='FormField'] input").filter(has=page.locator("text='Kilómetros'")).first
            if not await km_input.is_visible():
                km_input = page.locator("text='Kilómetros del coche'").locator("..").locator("input").first
            if not await km_input.is_visible():
                km_input = page.locator("input").nth(0)  # Primer input visible
            await km_input.fill(str(data.kms))
            await page.wait_for_timeout(500)
            
            # === CÓDIGO POSTAL (requerido) ===
            logger.info("Introduciendo código postal...")
            cp_input = page.locator("input[placeholder*='01234'], input[placeholder*='postal']").first
            if not await cp_input.is_visible():
                cp_input = page.locator("text='Código postal'").locator("..").locator("input").first
            await cp_input.fill("28001")  # Madrid centro como default
            await page.wait_for_timeout(500)
            
            # === ENVIAR FORMULARIO ===
            logger.info("Enviando formulario...")
            submit_btn = page.locator("button:has-text('Obtener tasación'), button[type='submit']").first
            await submit_btn.click()
            
            # Esperar al resultado
            logger.info("Esperando resultado...")
            await page.wait_for_timeout(3000)
            
            # Buscar el resultado de la tasación
            # Puede estar en diferentes formatos según la respuesta
            resultado_selector = "[class*='price'], [class*='result'], [class*='valor'], [class*='tasacion'] >> text=/\\d+.*€/"
            await page.wait_for_selector(resultado_selector, timeout=30000)
            
            resultado = page.locator(resultado_selector).first
            valor = await resultado.text_content()
            
            # Limpiar el valor (extraer solo número y símbolo €)
            if valor:
                # Buscar patrón de precio como "12.500 €" o "12500€"
                match = re.search(r'[\d.,]+\s*€', valor)
                if match:
                    valor = match.group(0)
            
            logger.info(f"Tasación completada: {valor}")
            return valor.strip() if valor else "Valor no disponible"
            
        except PlaywrightTimeout as e:
            logger.error(f"Timeout: {str(e)}")
            # Guardar screenshot para debug
            try:
                await page.screenshot(path="/tmp/error_screenshot.png")
                logger.info("Screenshot guardado en /tmp/error_screenshot.png")
            except:
                pass
            raise Exception("La página tardó demasiado en responder")
        except Exception as e:
            logger.error(f"Error en scraping: {str(e)}")
            # Guardar screenshot para debug
            try:
                await page.screenshot(path="/tmp/error_screenshot.png")
                logger.info("Screenshot guardado en /tmp/error_screenshot.png")
            except:
                pass
            raise
        finally:
            await browser.close()


@app.post("/api/tasar", response_model=TasacionResponse)
async def tasar(request: TasacionRequest):
    """
    Endpoint principal de tasación.
    Recibe datos del coche y devuelve el valor según coches.net.
    """
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
    """Endpoint de salud para verificar que el servidor está activo."""
    return {"status": "ok"}


# Endpoint de debug para ver la página
@app.get("/debug")
async def debug():
    """Endpoint de debug que muestra el HTML de la página de tasación."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            await page.goto("https://www.coches.net/tasacion-de-coches/", timeout=30000)
            
            # Aceptar cookies
            try:
                await page.click("#didomi-notice-agree-button", timeout=3000)
            except:
                pass
            
            await page.wait_for_timeout(3000)
            html = await page.content()
            await browser.close()
            
            return {"html_length": len(html), "preview": html[:5000]}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
