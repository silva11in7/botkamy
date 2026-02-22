import os
import sys

# Adicionar o diretório pai ao topo do path para priorizar o robô e o database
# Isso evita conflitos com o arquivo painel/main.py que tem o mesmo nome
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Agora importa do diretório pai corretamente
import database
import main as bot_main
from api import utmfy
import logging
import asyncio
import threading
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Render URL for keep-alive (User should set RENDER_EXTERNAL_URL in dashboard)
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

async def keep_alive():
    """Tarefa de background que pinga o próprio servidor para evitar sleep no Render Free Tier."""
    if not RENDER_URL:
        logger.info("RENDER_EXTERNAL_URL não configurada. Keep-alive desativado.")
        return
        
    logger.info(f"Keep-alive iniciado para: {RENDER_URL}")
    import httpx
    while True:
        try:
            await asyncio.sleep(840) # 14 minutos (Render dorme em 15)
            async with httpx.AsyncClient() as client:
                await client.get(f"{RENDER_URL}/health")
                logger.info("Keep-alive ping enviado com sucesso.")
        except Exception as e:
            logger.error(f"Erro no keep-alive: {e}")

async def bot_watchdog():
    """Tarefa que monitora se o bot parou de rodar e tenta reiniciar."""
    logger.info("Watchdog do Bot iniciado.")
    while True:
        await asyncio.sleep(300) # Verifica a cada 5 minutos
        if not hasattr(app.state, "bot_app") or not app.state.bot_app.updater.running:
            logger.warning("⚠️ WATCHDOG: Bot detectado como OFFLINE! Tentando reiniciar...")
            try:
                if hasattr(app.state, "bot_app"):
                    try:
                        await app.state.bot_app.updater.stop()
                        await app.state.bot_app.stop()
                    except: pass
                
                application = bot_main.start_bot()
                await application.initialize()
                await application.start()
                await application.updater.start_polling()
                app.state.bot_app = application
                logger.info("✅ WATCHDOG: Bot reiniciado com sucesso.")
            except Exception as e:
                logger.error(f"❌ WATCHDOG: Falha ao reiniciar o bot: {e}")

@app.on_event("startup")
async def startup_event():
    """Inicia o bot de forma assíncrona junto com o FastAPI."""
    # Inicia o keep-alive e o watchdog
    if RENDER_URL:
        asyncio.create_task(keep_alive())
    asyncio.create_task(bot_watchdog())
        
    # Espera um pouco para garantir que tudo carregou
    await asyncio.sleep(2)
    try:
        application = bot_main.start_bot()
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        app.state.bot_app = application
        logger.info("Bot Telegram iniciado com sucesso no ciclo de vida do FastAPI.")
    except Exception as e:
        logger.error(f"⚠️ ERRO CRÍTICO AO INICIAR BOT: {e}")
        # Não trava o FastAPI se o bot falhar (ex: conflito 409)
        pass

@app.on_event("shutdown")
async def shutdown_event():
    """Finaliza o bot ao desligar o servidor."""
    if hasattr(app.state, "bot_app"):
        await app.state.bot_app.updater.stop()
        await app.state.bot_app.stop()
        await app.state.bot_app.shutdown()
        logger.info("Bot Telegram desligado com sucesso.")

# Initialize database
database.init_db()

# Setup templates relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Simple session-less auth for demo
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

authenticated_users = set()

def get_current_user(request: Request):
    if request.client.host not in authenticated_users:
        return None
    return ADMIN_USERNAME

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        authenticated_users.add(request.client.host)
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciais inválidas!"})

@app.get("/logout")
async def logout(request: Request):
    authenticated_users.discard(request.client.host)
    return RedirectResponse(url="/")

# Dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    try:
        metrics = database.get_metrics()
        recent = database.get_all_transactions(10)
        funnel = database.get_funnel_stats()
        return templates.TemplateResponse("dashboard.html", {"request": request, "metrics": metrics, "recent": recent, "funnel": funnel, "active_page": "dashboard"})
    except Exception as e:
        import traceback
        logger.error(f"FATAL ERROR in Dashboard Route: {e}")
        logger.error(traceback.format_exc())
        return HTMLResponse(content=f"<h1>Erro Interno 500</h1><pre>{e}</pre>", status_code=500)

# Vendas Page
@app.get("/vendas", response_class=HTMLResponse)
async def vendas(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    transactions = database.get_all_transactions(100)
    return templates.TemplateResponse("vendas.html", {"request": request, "transactions": transactions, "active_page": "vendas"})

# Usuários Page
@app.get("/usuarios", response_class=HTMLResponse)
async def usuarios(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    users = database.get_all_users(1000)
    return templates.TemplateResponse("usuarios.html", {"request": request, "users": users, "active_page": "usuarios"})

# **NOVO: Gestão de Produtos**
@app.get("/produtos", response_class=HTMLResponse)
async def list_products(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    prods = database.get_all_products_raw()
    return templates.TemplateResponse("produtos.html", {"request": request, "products": prods, "active_page": "produtos"})

@app.post("/produtos/update")
async def update_product_route(request: Request, p_id: str = Form(...), name: str = Form(...), price: float = Form(...), desc: str = Form(...), active: int = Form(...)):
    if not get_current_user(request): return RedirectResponse(url="/")
    database.update_product(p_id, name, price, desc, active)
    return RedirectResponse(url="/produtos", status_code=status.HTTP_303_SEE_OTHER)

# **NOVO: Recuperação de Vendas**
@app.get("/recuperacao", response_class=HTMLResponse)
async def recovery_page(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    # All pending transactions
    txs = [t for t in database.get_all_transactions(100) if t['status'] == 'pending']
    recovery_msg = database.get_setting("recovery_message")
    return templates.TemplateResponse("recuperacao.html", {"request": request, "transactions": txs, "recovery_msg": recovery_msg, "active_page": "recuperacao"})

@app.post("/recuperar")
async def trigger_recovery(request: Request, user_id: int = Form(...), tx_id: str = Form(...), message: str = Form(...)):
    if not get_current_user(request): return RedirectResponse(url="/")
    # Here we would normally use a bot instance to send message. 
    # For now, let's log it. In a real scenario, this would call a bot API or send via shared queue.
    logger.info(f"Recovery message sent to user {user_id} for transaction {tx_id}: {message}")
    return RedirectResponse(url="/recuperacao", status_code=status.HTTP_303_SEE_OTHER)

# **NOVO: Comunicação (Broadcast)**
@app.get("/comunicacao", response_class=HTMLResponse)
async def comms_page(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    user_count = database.get_metrics()['total_users']
    return templates.TemplateResponse("comunicacao.html", {"request": request, "user_count": user_count, "active_page": "comunicacao"})

@app.post("/broadcast")
async def send_broadcast(request: Request, message: str = Form(...)):
    if not get_current_user(request): return RedirectResponse(url="/")
    # In a real app, we would loop through all users and use the bot to send.
    logger.info(f"BROADCAST triggered for all users: {message}")
    return RedirectResponse(url="/comunicacao", status_code=status.HTTP_303_SEE_OTHER)

# **NOVO V3: Editor de Conteúdo (No-Code)**
# **NOVO V3: Editor de Conteúdo (No-Code)**
@app.get("/conteudo", response_class=HTMLResponse)
async def content_editor(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    content_list = database.get_all_content()
    products = database.get_all_products_raw()
    return templates.TemplateResponse("conteudo.html", {
        "request": request, 
        "content_list": content_list, 
        "products": products,
        "active_page": "conteudo"
    })

@app.post("/conteudo/add")
async def add_content(request: Request, key: str = Form(...), value: str = Form(...), description: str = Form(...), btn_text: str = Form(""), btn_url: str = Form("")):
    if not get_current_user(request): return RedirectResponse(url="/")
    database.update_bot_content_advanced(key, value, description, [], btn_text, btn_url)
    return RedirectResponse(url="/conteudo", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/conteudo/update")
async def update_content(request: Request, key: str = Form(...), value: str = Form(...), description: str = Form(...), products: list = Form([]), btn_text: str = Form(""), btn_url: str = Form("")):
    if not get_current_user(request): return RedirectResponse(url="/")
    database.update_bot_content_advanced(key, value, description, products, btn_text, btn_url)
    return RedirectResponse(url="/conteudo", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/conteudo/delete")
async def delete_content(request: Request, key: str = Form(...)):
    if not get_current_user(request): return RedirectResponse(url="/")
    database.delete_bot_content(key)
    return RedirectResponse(url="/conteudo", status_code=status.HTTP_303_SEE_OTHER)

# **NOVO V3: Automação**
@app.get("/automacao", response_class=HTMLResponse)
async def automation_page(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    rules = database.get_automation_rules()
    return templates.TemplateResponse("automacao.html", {"request": request, "rules": rules, "active_page": "automacao"})

@app.post("/automacao/update")
async def update_automation(request: Request, rule_id: int = Form(...), delay: int = Form(...), message: str = Form(...), active: int = Form(...)):
    if not get_current_user(request): return RedirectResponse(url="/")
    database.update_automation_rule(rule_id, delay, message, active)
    return RedirectResponse(url="/automacao", status_code=status.HTTP_303_SEE_OTHER)

# **NOVO: Stats API para Gráficos**
@app.get("/api/stats/revenue")
async def get_chart_data():
    data = database.get_revenue_stats(7)
    # Reverse for chronological order
    data.reverse()
    labels = [d['day'] for d in data]
    values = [d['total'] for d in data]
    return JSONResponse({"labels": labels, "values": values})

# Configurações
@app.get("/configuracoes", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not get_current_user(request): return RedirectResponse(url="/")
    settings = {
        "webhook_token": database.get_setting("webhook_token"),
        "maintenance_mode": database.get_setting("maintenance_mode", "false"),
        "support_user": database.get_setting("support_user"),
        "recovery_message": database.get_setting("recovery_message")
    }
    return templates.TemplateResponse("configuracoes.html", {"request": request, "settings": settings, "active_page": "settings"})

@app.post("/configuracoes")
async def save_settings(request: Request, webhook_token: str = Form(...), maintenance_mode: str = Form(...), support_user: str = Form(...), recovery_message: str = Form(...)):
    if not get_current_user(request): return RedirectResponse(url="/")
    database.set_setting("webhook_token", webhook_token)
    database.set_setting("maintenance_mode", maintenance_mode)
    database.set_setting("support_user", support_user)
    database.set_setting("recovery_message", recovery_message)
    return RedirectResponse(url="/configuracoes", status_code=status.HTTP_303_SEE_OTHER)

# --- Webhook Endpoint ---
@app.post("/webhook")
async def receive_webhook(request: Request, data: dict = Body(...)):
    logger.info(f"Received webhook: {data.get('type') or 'update'}")
    
    # Babylon payload has the transaction details inside the 'data' key
    transaction_data = data.get("data", {})
    if not transaction_data:
        logger.warning("Webhook received without 'data' content.")
        return {"status": "success"}

    # Extract identifier from metadata (where we stored it) or use the transaction ID
    metadata = transaction_data.get("metadata") or {}
    identifier = metadata.get("identifier") if isinstance(metadata, dict) else None
    
    # Fallback to the transaction ID if identifier not in metadata
    if not identifier:
        identifier = transaction_data.get("id")

    babylon_id = transaction_data.get("id")
    status = transaction_data.get("status", "").lower()
    
    local_status = 'pending'
    if status == 'paid': 
        local_status = 'confirmed'
        # Track conversion success
        user_id = database.get_transaction_user(identifier)
        if user_id:
             database.track_event(user_id, 'payment_success')
    elif status in ['refused', 'canceled', 'failed', 'expired']: 
        local_status = 'failed'
    elif status == 'refunded': 
        local_status = 'refunded'
    elif status == 'chargedback':
        local_status = 'refunded' # Or handle specifically if needed

    logger.info(f"Updating transaction {identifier} to status {local_status} (Babylon ID: {babylon_id})")
    database.update_transaction_status(identifier=identifier, status=local_status, oasyfy_id=babylon_id)
    
    # NEW: UTMfy "Purchase" event tracking
    if local_status == 'confirmed':
        try:
            # We need the user info and tracking data from metadata
            user_id = database.get_transaction_user(identifier)
            db_user = database.get_user(user_id) if user_id else None
            
            if db_user:
                # Merge user info with the actual metadata received in webhook
                user_info = {
                    "id": user_id,
                    "username": db_user.get("username"),
                    "full_name": db_user.get("full_name"),
                    **metadata # This contains ttclid, utms, etc.
                }
                tx_info = {
                    "id": identifier,
                    "amount": transaction_data.get("amount") / 100, # Babylon cents to real
                    "babylon_id": babylon_id,
                    "method": transaction_data.get("paymentMethod")
                }
                # Run in background to avoid delaying the webhook response
                asyncio.create_task(utmfy.send_event("Purchase", user_info, tx_info))
        except Exception as e:
            logger.error(f"Error sending Purchase event to UTMfy: {e}")
    
    return {"status": "success", "processed": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
