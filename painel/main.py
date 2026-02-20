from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import database
import os
import logging
import asyncio
import threading
from typing import Optional
import sys

# Adicionar o diretório pai ao path para importar o bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as bot_main

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

def run_bot():
    """Executa o bot em uma thread separada."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        application = bot_main.start_bot()
        logger.info("Iniciando o Bot Telegram em background...")
        application.run_polling(close_loop=False)
    except Exception as e:
        logger.error(f"Erro ao iniciar o bot: {e}")

@app.on_event("startup")
async def startup_event():
    # Iniciar bot em thread separada para não bloquear o FastAPI
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("FastAPI iniciado e Bot encaminhado para thread.")

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
    metrics = database.get_metrics()
    recent = database.get_all_transactions(10)
    funnel = database.get_funnel_stats()
    return templates.TemplateResponse("dashboard.html", {"request": request, "metrics": metrics, "recent": recent, "funnel": funnel, "active_page": "dashboard"})

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
    logger.info(f"Received webhook: {data.get('event')}")
    event = data.get("event")
    token = data.get("token")
    stored_token = database.get_setting("webhook_token")
    if stored_token and token != stored_token: raise HTTPException(status_code=403, detail="Invalid token")

    transaction_data = data.get("transaction")
    if not transaction_data: return {"status": "success"}

    identifier = transaction_data.get("identifier")
    oasyfy_id = transaction_data.get("id")
    status = transaction_data.get("status")
    
    if status == 'COMPLETED': 
        local_status = 'confirmed'
        # NEW V3: Track conversion success
        user_id = database.get_transaction_user(identifier)
        if user_id:
             database.track_event(user_id, 'payment_success')
    elif status in ['FAILED', 'CHARGED_BACK']: local_status = 'failed'
    elif status == 'REFUNDED': local_status = 'refunded'

    database.update_transaction_status(identifier=identifier, status=local_status, oasyfy_id=oasyfy_id)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
