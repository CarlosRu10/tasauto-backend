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
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer'
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-ES"
        )
        page = await context.new_page()
        
        try:
            # Navegar a la página de tasación con más tiempo
            logger.info("Navegando a coches.net...")
            await page.goto("https://www.coches.net/tasacion-de-coches/", timeout=90000, wait_until="domcontentloaded")
            
            # Esperar un poco para que se cargue JavaScript
            await page.wait_for_timeout(3000)
            
            # Aceptar cookies si aparece el banner
            try:
                logger.info("Buscando banner de cookies...")
                # Intentar varios selectores de cookies
                cookie_selectors = [
                    "#didomi-notice-agree-button",
                    "button:has-text('Aceptar')",
                    "button:has-text('Aceptar todo')",
                    "button:has-text('Aceptar y cerrar')",
                    "[class*='cookie'] button",
                    "[id*='cookie'] button"
                ]
                for selector in cookie_selectors:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible(timeout=1000):
                            await btn.click()
                            logger.info(f"Cookies aceptadas con: {selector}")
                            await page.wait_for_timeout(2000)
                            break
                    except:
                        continue
            except Exception as e:
                logger.info(f"No se encontró banner de cookies: {e}")
            
            # Esperar a que cargue la página completamente
            logger.info("Esperando carga completa de la página...")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Guardar screenshot de estado actual
            try:
                await page.screenshot(path="/tmp/page_loaded.png")
                logger.info("Screenshot inicial guardado")
            except:
                pass
            
            # Buscar el formulario con selectores más flexibles
            logger.info("Buscando formulario de tasación...")
            
            # Lista de selectores posibles para el formulario
            form_selectors = [
                "form",
                "[class*='form']",
                "[class*='valuation']",
                "[class*='tasacion']",
                "select",
                "[class*='dropdown']"
            ]
            
            form_found = False
            for selector in form_selectors:
                try:
                    if await page.locator(selector).first.is_visible(timeout=5000):
                        form_found = True
                        logger.info(f"Formulario encontrado con: {selector}")
                        break
                except:
                    continue
            
            if not form_found:
                # Intentar hacer scroll para cargar contenido lazy
                await page.evaluate("window.scrollTo(0, 500)")
                await page.wait_for_timeout(2000)
            
            # === MARCA ===
            logger.info(f"Seleccionando marca: {data.marca}")
            
            # Buscar dropdown de marca con múltiples estrategias
            marca_selectors = [
                "[data-testid*='brand'] [class*='select']",
                "[class*='FormField']:has-text('Marca') [class*='select']",
                "label:has-text('Marca') ~ div [class*='select']",
                "[class*='select']"
            ]
            
            marca_dropdown = None
            for selector in marca_selectors:
                try:
                    dropdown = page.locator(selector).first
                    if await dropdown.is_visible(timeout=3000):
                        marca_dropdown = dropdown
                        logger.info(f"Dropdown marca encontrado: {selector}")
                        break
                except:
                    continue
            
            if marca_dropdown:
                await marca_dropdown.click()
                await page.wait_for_timeout(1000)
                
                # Buscar opción de marca
                marca_option = page.locator(f"[role='option']:has-text('{data.marca}'), li:has-text('{data.marca}')").first
                if await marca_option.is_visible(timeout=3000):
                    await marca_option.click()
                    await page.wait_for_timeout(2000)
                    logger.info("Marca seleccionada")
            else:
                logger.error("No se encontró dropdown de marca")
                raise Exception("No se pudo encontrar el formulario de marca")
            
            # === MODELO ===
            logger.info(f"Seleccionando modelo: {data.modelo}")
            
            # Esperar a que se carguen los modelos
            await page.wait_for_timeout(1500)
            
            modelo_selectors = [
                "[data-testid*='model'] [class*='select']",
                "[class*='FormField']:has-text('Modelo') [class*='select']",
                "label:has-text('Modelo') ~ div [class*='select']"
            ]
            
            modelo_dropdown = None
            for selector in modelo_selectors:
                try:
                    dropdown = page.locator(selector).first
                    if await dropdown.is_visible(timeout=3000):
                        modelo_dropdown = dropdown
                        break
                except:
                    continue
            
            if modelo_dropdown:
                await modelo_dropdown.click()
                await page.wait_for_timeout(1000)
                
                modelo_option = page.locator(f"[role='option']:has-text('{data.modelo}'), li:has-text('{data.modelo}')").first
                if await modelo_option.is_visible(timeout=3000):
                    await modelo_option.click()
                    await page.wait_for_timeout(2000)
                    logger.info("Modelo seleccionado")
            
            # === AÑO ===
            logger.info(f"Seleccionando año: {data.anio}")
            
            anio_selectors = [
                "[data-testid*='year'] [class*='select']",
                "[class*='FormField']:has-text('Año') [class*='select']",
                "label:has-text('Año') ~ div [class*='select']"
            ]
            
            anio_dropdown = None
            for selector in anio_selectors:
                try:
                    dropdown = page.locator(selector).first
                    if await dropdown.is_visible(timeout=3000):
                        anio_dropdown = dropdown
                        break
                except:
                    continue
            
            if anio_dropdown:
                await anio_dropdown.click()
                await page.wait_for_timeout(1000)
                
                anio_option = page.locator(f"[role='option']:has-text('{data.anio}'), li:has-text('{data.anio}')").first
                if await anio_option.is_visible(timeout=3000):
                    await anio_option.click()
                    await page.wait_for_timeout(1500)
                    logger.info("Año seleccionado")
            
            # === KILÓMETROS ===
            logger.info(f"Introduciendo kilómetros: {data.kms}")
            
            km_selectors = [
                "input[placeholder*='ilómetro']",
                "input[type='number']",
                "[class*='FormField']:has-text('Kilómetros') input",
                "input[name*='km']"
            ]
            
            for selector in km_selectors:
                try:
                    km_input = page.locator(selector).first
                    if await km_input.is_visible(timeout=2000):
                        await km_input.fill(str(data.kms))
                        logger.info("Kilómetros introducidos")
                        break
                except:
                    continue
            
            await page.wait_for_timeout(500)
            
            # === CÓDIGO POSTAL ===
            logger.info("Introduciendo código postal...")
            
            cp_selectors = [
                "input[placeholder*='postal']",
                "input[placeholder*='01234']",
                "[class*='FormField']:has-text('Código postal') input",
                "input[name*='postal']"
            ]
            
            for selector in cp_selectors:
                try:
                    cp_input = page.locator(selector).first
                    if await cp_input.is_visible(timeout=2000):
                        await cp_input.fill("28001")
                        logger.info("Código postal introducido")
                        break
                except:
                    continue
            
            await page.wait_for_timeout(500)
            
            # === ENVIAR FORMULARIO ===
            logger.info("Enviando formulario...")
            
            submit_selectors = [
                "button:has-text('Obtener tasación')",
                "button:has-text('Tasar')",
                "button:has-text('Calcular')",
                "button[type='submit']",
                "[class*='submit']"
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = page.locator(selector).first
                    if await submit_btn.is_visible(timeout=2000):
                        await submit_btn.click()
                        logger.info("Formulario enviado")
                        break
                except:
                    continue
            
            # Esperar al resultado
            logger.info("Esperando resultado...")
            await page.wait_for_timeout(5000)
            
            # Buscar el resultado de la tasación
            result_selectors = [
                "[class*='price']",
                "[class*='result']",
                "[class*='valor']",
                "[class*='tasacion']",
                "text=/\\d+\\.?\\d*\\s*€/"
            ]
            
            valor = None
            for selector in result_selectors:
                try:
                    result = page.locator(selector).first
                    if await result.is_visible(timeout=10000):
                        valor = await result.text_content()
                        if valor and "€" in valor:
                            break
                except:
                    continue
            
            if not valor:
                # Intentar buscar cualquier texto con formato de precio
                all_text = await page.content()
                match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*€', all_text)
                if match:
                    valor = match.group(0)
            
            if valor:
                # Limpiar el valor
                match = re.search(r'[\d.,]+\s*€', valor)
                if match:
                    valor = match.group(0)
                logger.info(f"Tasación completada: {valor}")
                return valor.strip()
            else:
                raise Exception("No se encontró el resultado de la tasación")
            
        except PlaywrightTimeout as e:
            logger.error(f"Timeout: {str(e)}")
            try:
                await page.screenshot(path="/tmp/error_screenshot.png")
                logger.info("Screenshot guardado en /tmp/error_screenshot.png")
            except:
                pass
            raise Exception("La página tardó demasiado en responder")
        except Exception as e:
            logger.error(f"Error en scraping: {str(e)}")
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


@app.get("/debug")
async def debug():
    """Endpoint de debug que muestra el HTML de la página de tasación."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                locale="es-ES"
            )
            page = await context.new_page()
            await page.goto("https://www.coches.net/tasacion-de-coches/", timeout=60000)
            
            # Aceptar cookies
            try:
                await page.click("#didomi-notice-agree-button", timeout=5000)
                await page.wait_for_timeout(2000)
            except:
                pass
            
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            html = await page.content()
            
            # Buscar selectores disponibles
            selects = await page.locator("select, [class*='select'], [class*='dropdown']").all()
            select_info = []
            for s in selects[:10]:
                try:
                    select_info.append({
                        "text": await s.text_content(),
                        "class": await s.get_attribute("class")
                    })
                except:
                    pass
            
            await browser.close()
            
            return {
                "html_length": len(html), 
                "preview": html[:10000],
                "selects_found": len(selects),
                "select_info": select_info
            }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
