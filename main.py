import os
import logging
import asyncio
import qrcode
import io
import random
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from openai import OpenAI
import httpx
from api import gateway, utmfy, tiktok
from datetime import datetime, timezone
import secrets
import string
import database
import json
from typing import Dict, Any, List, Optional

# Initialize database
database.init_db()

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Track pending reminders: {bot_id: {user_id: asyncio.Task}}
pending_reminders = {}

# Media cache: {bot_id: {key: file_id}}
media_cache = {}

def get_media_source(key, default_rel_path):
    """Safely gets media path from DB or fallback to default."""
    try:
        custom_path = database.get_bot_content(key)
        if custom_path and custom_path.startswith("/media/"):
            full_path = os.path.join("painel", custom_path.lstrip("/"))
            if os.path.exists(full_path):
                return full_path
    except Exception as e:
        logger.error(f"get_media_source error: {e}")
    return default_rel_path

# --- Product Data ---
def get_products():
    return database.get_active_products()

# --- Inactivity Reminder Data ---
INACTIVITY_TEXT = (
    "Sumiu rápido, hein? 👀\n\n"
    "Tu me viu de quatro... e agora podia me ver apanhando do jeitinho que eu gosto 😈\n\n"
    "Então antes que perca a chance de vez, deixei 15% OFF liberado ✅\n\n"
    "Não vou deixar ativo por muito tempo ⏳\n\n"
    "Aproveita aqui 👇"
)

INACTIVITY_KEYBOARD = [
    [InlineKeyboardButton("VIP VITALICIO + 🔥 LIVES POR R$25,41 (15% OFF)", callback_data='buy_vip_live_disc')],
    [InlineKeyboardButton("VIP VITALICIO 💎 POR R$18,91 (15% OFF)", callback_data='buy_vip_vital_disc')],
    [InlineKeyboardButton("VIP MENSAL 😈 POR R$15,37 (15% OFF)", callback_data='buy_vip_mensal_disc')],
    [InlineKeyboardButton("SUPORTE 💬", callback_data='support')]
]

IMAGINA_TEXT = (
    "imagina essa cena aqui... 💭\n\n"
    "Eu de joelhos 😈\n"
    "Lambendo tuas bolas com vontade 👅\n"
    "Subindo com a língua até teu pau ficar pulsando na minha boca 🍆💦\n\n"
    "Aí eu começo o boquete...\n\n"
    "Babando tudo 🤤\n"
    "Descendo até engasgar, com a garganta toda molhada 💦💦\n"
    "E te olhando no olho enquanto engulo teu pau até o fim 😳\n\n"
    "Se ainda tiver imaginando como seria isso em ti...\n\n"
    "Clica aqui agora antes que suma. 👇🔥"
)

IMAGINA_KEYBOARD = [
    [InlineKeyboardButton("VIP VITALICIO + 🔥 LIVES POR R$21,90 (20% OFF)", callback_data='buy_vip_live_disc2')],
    [InlineKeyboardButton("VIP VITALICIO 🔥 POR R$16,62 (20% OFF)", callback_data='buy_vip_vital_disc2')],
    [InlineKeyboardButton("VIP MENSAL 🔥 POR R$13,28 (20% OFF)", callback_data='buy_vip_mensal_disc2')],
    [InlineKeyboardButton("SUPORTE 💬", callback_data='support')]
]

async def get_ai_response(bot_id: str, user_id: int, user_message: str):
    """Generates a response using OpenAI based on bot-specific personality."""
    api_key = database.get_setting("openai_api_key")
    if not api_key:
        logger.warning("OpenAI API Key not configured.")
        return None
    
    # Get bot config for prompt and enablement
    all_bots = database.get_all_managed_bots()
    bot_config = next((b for b in all_bots if b['id'] == bot_id), None)
    
    if not bot_config or not bot_config.get("ai_enabled"):
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        history = database.get_ai_history(bot_id, user_id)
        
        system_prompt = bot_config.get("system_prompt", "Você é a Kamylinha, uma vendedora carismática.")
        
        messages = [{"role": "system", "content": system_prompt}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        
        messages.append({"role": "user", "content": user_message})
        
        # Save user message to history
        database.add_ai_history(bot_id, user_id, "user", user_message)
        
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o",
            messages=messages,
            max_tokens=400,
            temperature=0.8
        )
        
        ai_reply = response.choices[0].message.content
        
        # Save AI reply to history
        database.add_ai_history(bot_id, user_id, "assistant", ai_reply)
        
        return ai_reply
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        return None

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler for non-command text messages."""
    if await check_maintenance(update): return
    
    user = update.effective_user
    bot_id = context.application.bot_data.get("bot_id")
    user_message = update.message.text
    
    # Check if AI should respond
    ai_reply = await get_ai_response(bot_id, user.id, user_message)
    
    if ai_reply:
        await update.message.reply_text(ai_reply)
    else:
        # Fallback or just ignore if not enabled
        pass

async def check_maintenance(update: Update):
    is_maintenance = database.get_setting("maintenance_mode", "false").lower() == "true"
    if is_maintenance:
        msg = "🛠 **MODO MANUTENÇÃO**\n\nEstamos fazendo algumas melhorias rápidas. Voltamos em instantes! 😘"
        if update.callback_query:
            await update.callback_query.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        return True
    return False

async def run_reminder(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE, bot_id: str, product_id: str = None):
    """Smart CRM Multi-stage recovery."""
    try:
        # Stage 1: 10 Minutes - Video Objeção/Curiosidade
        await asyncio.sleep(600) # 10 min
        database.update_abandoned_checkout(user_id, bot_id, last_stage=1)
        
        custom_v1 = get_media_source("recovery_v10m", "imgs/videokamyrebo.mp4")
        c_bot = media_cache.setdefault(bot_id, {})
        cached_id = c_bot.get(custom_v1)

        await context.bot.send_video(
            chat_id=chat_id,
            video=cached_id or open(custom_v1, 'rb'),
            caption="🔥 **NÃO VAI EMBORA!**\n\nVi que você quase liberou seu acesso... preparei um presente especial: **15% de DESCONTO** exclusivo pra você hoje! 🎁🎬",
            reply_markup=InlineKeyboardMarkup(INACTIVITY_KEYBOARD),
            parse_mode='Markdown'
        )

        # Stage 2: 1 Hour - Áudio Real (Conversa)
        await asyncio.sleep(3000) # + 50 min = 1 hour total
        database.update_abandoned_checkout(user_id, bot_id, last_stage=2)
        
        audio_path = get_media_source("recovery_audio_1h", "imgs/audio_venda.ogg") # Supondo existir
        if os.path.exists(audio_path):
            await context.bot.send_voice(chat_id=chat_id, voice=open(audio_path, 'rb'), caption="Escuta esse áudio que gravei pra você... ❤️")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Ainda tá aí? Quero muito te ver lá dentro do VIP... chama o suporte se tiver dúvida! 💬")

        # Stage 3: 24 Hours - Cupom 50% OFF (Oportunidade Única)
        await asyncio.sleep(82800) # + 23 hours = 24h total
        database.update_abandoned_checkout(user_id, bot_id, last_stage=3)
        await context.bot.send_message(
            chat_id=chat_id,
            text="🚨 **ÚLTIMA CHANCE: 50% DE DESCONTO** 🚨\n\nNão quero que você fique de fora. Só pelas próximas 2h, liberei o acesso pela METADE do preço. Aproveita agora ou perca pra sempre! 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔥 LIBERAR 50% OFF AGORA", callback_data='buy_vip_vital_disc_50')]])
        )

        # Stage 4: 3 Days - Retargeting "Saudade"
        await asyncio.sleep(172800) # + 2 days = 3 days total
        database.update_abandoned_checkout(user_id, bot_id, last_stage=4)
        await context.bot.send_message(chat_id=chat_id, text="Sumido(a)... 👀\n\nPassando pra dizer que postei conteúdos novos que você ia AMAR. Volta aqui? ❤️")

    except asyncio.CancelledError: pass
    except Exception as e: logger.error(f"Reminder error: {e}")
    finally:
        if bot_id in pending_reminders and user_id in pending_reminders[bot_id]:
            del pending_reminders[bot_id][user_id]

# --- CRM Recovery Configuration ---
RECOVERY_STAGES = {
    1: {"delay": 600, "type": "video", "media_key": "recovery_v10m", "default_media": "imgs/videokamyrebo.mp4", "caption": "🔥 **NÃO VAI EMBORA!**\n\nVi que você quase liberou seu acesso... preparei um presente especial: **15% de DESCONTO** exclusivo pra você hoje! 🎁🎬", "markup": INACTIVITY_KEYBOARD},
    2: {"delay": 3600, "type": "voice", "media_key": "recovery_audio_1h", "default_media": "imgs/audio_venda.ogg", "caption": "Escuta esse áudio que gravei pra você... ❤️"},
    3: {"delay": 86400, "type": "text", "content": "🚨 **ÚLTIMA CHANCE: 50% DE DESCONTO** 🚨\n\nNão quero que você fique de fora. Só pelas próximas 2h, liberei o acesso pela METADE do preço. Aproveita agora ou perca pra sempre! 👇", "markup": InlineKeyboardMarkup([[InlineKeyboardButton("🔥 LIBERAR 50% OFF AGORA", callback_data='buy_vip_vital_disc_50')]])},
    4: {"delay": 259200, "type": "text", "content": "Sumido(a)... 👀\n\nPassando pra dizer que postei conteúdos novos que você ia AMAR. Volta aqui? ❤️"}
}

async def run_recovery_worker(bot_id: str, app):
    """Background worker to check and send persistent recovery messages."""
    logger.info(f"Recovery worker started for bot {bot_id}")
    while True:
        try:
            pending = await asyncio.to_thread(database.get_pending_abandoned, bot_id)
            for rec in pending:
                now = datetime.now(timezone.utc)
                created_at = datetime.fromisoformat(rec['created_at'].replace('Z', '+00:00'))
                seconds_since = (now - created_at).total_seconds()
                
                next_stage = rec['last_stage'] + 1
                if next_stage in RECOVERY_STAGES:
                    stage_cfg = RECOVERY_STAGES[next_stage]
                    if seconds_since >= stage_cfg['delay']:
                        try:
                            user_id = rec['user_id']
                            chat_id = user_id # Assuming DM
                            
                            if stage_cfg['type'] == 'video':
                                media = get_media_source(stage_cfg['media_key'], stage_cfg['default_media'])
                                await app.bot.send_video(chat_id=chat_id, video=open(media, 'rb'), caption=stage_cfg['caption'], reply_markup=stage_cfg['markup'], parse_mode='Markdown')
                            elif stage_cfg['type'] == 'voice':
                                media = get_media_source(stage_cfg['media_key'], stage_cfg['default_media'])
                                if os.path.exists(media):
                                    await app.bot.send_voice(chat_id=chat_id, voice=open(media, 'rb'), caption=stage_cfg['caption'])
                                else:
                                    await app.bot.send_message(chat_id=chat_id, text="Ainda tá aí? Quero muito te ver lá dentro do VIP... ❤️")
                            elif stage_cfg['type'] == 'text':
                                await app.bot.send_message(chat_id=chat_id, text=stage_cfg['content'], reply_markup=stage_cfg.get('markup'), parse_mode='Markdown')
                            
                            # Update DB
                            await asyncio.to_thread(database.update_abandoned_checkout, user_id, bot_id, last_stage=next_stage)
                            logger.info(f"Recovery Stage {next_stage} sent to {user_id} for bot {bot_id}")
                            
                        except Exception as e:
                            logger.error(f"Error sending recovery to {rec['user_id']}: {e}")
                            if "Forbidden" in str(e) or "blocked" in str(e).lower():
                                await asyncio.to_thread(database.update_abandoned_checkout, rec['user_id'], bot_id, status="failed")

            await asyncio.sleep(60) # Scan every minute
        except Exception as e:
            logger.error(f"Recovery worker error for bot {bot_id}: {e}")
            await asyncio.sleep(60)

def parse_start_payload(payload: str) -> Dict[str, str]:
    tracking = {}
    if not payload: return tracking
    if "_" in payload:
        parts = payload.split("_")
        for i in range(0, len(parts) - 1, 2):
            key, val = parts[i], parts[i+1]
            if key == "ttclid": tracking["ttclid"] = val
            elif key == "utms": tracking["utm_source"] = val
            elif key == "utmm": tracking["utm_medium"] = val
            elif key == "utmc": tracking["utm_campaign"] = val
            elif key == "utmt": tracking["utm_term"] = val
            elif key == "utmn": tracking["utm_content"] = val
    else: tracking["ttclid"] = payload
    return tracking

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_id = context.application.bot_data.get("bot_id")
    
    tracking_data = parse_start_payload(context.args[0]) if context.args else {}
    asyncio.create_task(asyncio.to_thread(database.log_user, user.id, user.username, user.full_name, tracking_data, bot_id=bot_id))
    asyncio.create_task(asyncio.to_thread(database.track_event, user.id, 'start', bot_id=bot_id))
    
    user_info = {"full_name": user.full_name, "username": user.username, "tracking_data": tracking_data}
    asyncio.create_task(tiktok.send_tiktok_event("Contact", user.id, user_info))

    welcome_text = await asyncio.to_thread(database.get_bot_content, "welcome_text", "Olá! Escolha seu plano e comece agora:")
    keyboard = []
    linked_prod_ids = await asyncio.to_thread(database.get_products_for_content, "welcome_text")
    if linked_prod_ids:
        all_prods = await asyncio.to_thread(database.get_active_products)
        for prod_id in linked_prod_ids:
            product = all_prods.get(prod_id)
            if product:
                btn_label = f"🔥 {product['name']} POR R${product['price']:.2f}"
                keyboard.append([InlineKeyboardButton(btn_label, callback_data=f"buy_{prod_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    photo_path = get_media_source("welcome_photo", os.path.join("imgs", "3banner.mp4"))
    
    c_bot = media_cache.setdefault(bot_id, {})
    cached_id = c_bot.get("banner")

    if os.path.exists(photo_path):
        try:
            if photo_path.lower().endswith(('.mp4', '.mov', '.avi')):
                msg = await update.message.reply_video(video=cached_id or open(photo_path, 'rb'), caption=welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
                if not cached_id and msg.video: c_bot["banner"] = msg.video.file_id
            else:
                msg = await update.message.reply_photo(photo=cached_id or open(photo_path, 'rb'), caption=welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
                if not cached_id and msg.photo: c_bot["banner"] = msg.photo[-1].file_id
        except Exception as e:
            await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    b_reminders = pending_reminders.setdefault(bot_id, {})
    if user.id in b_reminders: b_reminders[user.id].cancel()
    b_reminders[user.id] = asyncio.create_task(run_reminder(user.id, update.effective_chat.id, context, bot_id))

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    products = get_products()
    for pid, details in products.items():
        keyboard.append([InlineKeyboardButton(f"{details['name']} - R${details['price']:.2f}", callback_data=f'prod_{pid}')])
    keyboard.append([InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='main_menu')])
    await update.callback_query.edit_message_text(text="🔥 **Catálogo de Conteúdos** 🔥", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: str):
    if await check_maintenance(update): return
    query = update.callback_query
    user = update.effective_user
    bot_id = context.application.bot_data.get("bot_id")
    
    product = get_products().get(product_id)
    if not product: return await query.answer("Produto não encontrado.", show_alert=True)

    b_reminders = pending_reminders.get(bot_id, {})
    if user.id in b_reminders:
        b_reminders[user.id].cancel()
        del b_reminders[user.id]
        
    db_user = await asyncio.to_thread(database.get_user, user.id)
    tracking_data = {k: db_user[k] for k in ["ttclid", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] if db_user and db_user.get(k)}

    await query.message.reply_text("Gerando seu Pix...")
    identifier = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10))
    order_ts = datetime.now(timezone.utc).isoformat()
    
    asyncio.create_task(utmfy.send_order(identifier, "waiting_payment", {"id": user.id, "full_name": user.full_name, "ip": None}, {"id": product_id, "name": product['name'], "price": product['price']}, tracking_data, {"created_at": order_ts}))
    
    # Log Abandonment & Start Smart Recovery
    asyncio.create_task(asyncio.to_thread(database.log_abandoned_checkout, user.id, product_id, bot_id, metadata=tracking_data))
    b_reminders[user.id] = asyncio.create_task(run_reminder(user.id, query.message.chat_id, context, bot_id, product_id))

    pix_data = await gateway.create_payment(identifier, product['price'], user.full_name or "Cliente", f"u{user.id}@tg.com", "(11)999999999", "12345678909", product['name'], tracking_data)

    if pix_data:
        database.log_transaction(identifier, user.id, product_id, product['price'], 'pending', metadata=tracking_data, created_at=order_ts, bot_id=bot_id)
        pix_key = pix_data['pix']['code']
        qr = qrcode.make(pix_key)
        bio = io.BytesIO(); bio.name = 'qr.png'; qr.save(bio, 'PNG'); bio.seek(0)
        await query.message.reply_photo(bio, caption="Seu QR Code 🚀")
        await query.message.reply_text(f"`{pix_key}`", parse_mode='Markdown')
        await query.message.reply_text("Aguardando confirmação...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirmar", callback_data=f'confirm_pay_{product_id}_{identifier}')]]))
    else:
        await query.message.reply_text("❌ Erro ao gerar Pix.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_maintenance(update): return
    query = update.callback_query
    await query.answer()
    data, user_id, bot_id = query.data, update.effective_user.id, context.application.bot_data.get("bot_id")
    
    b_reminders = pending_reminders.get(bot_id, {})
    if user_id in b_reminders:
        b_reminders[user_id].cancel()
        del b_reminders[user_id]

    if data == 'main_menu': await start(update, context) # Simplied fallback
    elif data == 'list_products': await show_products(update, context)
    elif data.startswith('prod_'):
        pid = data.split('_')[1]
        product = get_products().get(pid)
        if product:
            btn = [[InlineKeyboardButton("💳 Comprar", callback_data=f'buy_{pid}')], [InlineKeyboardButton("🔙 Voltar", callback_data='list_products')]]
            await query.edit_message_text(f"🔞 **{product['name']}**\n\n{product['desc']}\n💰 R${product['price']:.2f}", reply_markup=InlineKeyboardMarkup(btn), parse_mode='Markdown')
    elif data == "ver_planos":
        asyncio.create_task(asyncio.to_thread(database.track_event, user_id, 'view_plans', bot_id=bot_id))
        await show_products(update, context)
    elif data.startswith('buy_'):
        pid = data.replace('buy_', '', 1)
        asyncio.create_task(asyncio.to_thread(database.track_event, user_id, 'checkout', bot_id=bot_id))
        await handle_purchase(update, context, pid)
    elif data.startswith('confirm_pay_'):
        ident = data.split('_')[3]
        database.confirm_transaction(ident)
        await query.edit_message_text("✅ Pagamento informado! Enviando conteúdo...")

async def setup_bot(bot_token: str, bot_id: str):
    app = ApplicationBuilder().token(bot_token).build()
    app.bot_data["bot_id"] = bot_id
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('iniciar', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_ai_chat))
    
    # Set commands
    try:
        await app.bot.set_my_commands([BotCommand("start", "Iniciar"), BotCommand("iniciar", "Iniciar")])
    except: pass
    
    return app

async def run_bot_instance(bot_config):
    while True:
        try:
            app = await setup_bot(bot_config['token'], bot_config['id'])
            logger.info(f"Starting bot: {bot_config['username']} ({bot_config['name']})")
            await app.initialize()
            await app.start()
            
            # Start Recovery Worker
            recovery_task = asyncio.create_task(run_recovery_worker(bot_config['id'], app))
            
            # Manual polling loop to handle conflicts gracefully
            updater = app.updater
            await updater.start_polling(drop_pending_updates=True)
            # Keep running until cancelled or bot is deactivated
            while True:
                await asyncio.sleep(10)
                # Check if bot still active in DB
                all_bots = await asyncio.to_thread(database.get_all_managed_bots)
                current = next((b for b in all_bots if b['id'] == bot_config['id']), None)
                if not current or not current['is_active']:
                    logger.info(f"Bot {bot_config['name']} deactivated, stopping...")
                    recovery_task.cancel()
                    await updater.stop()
                    await app.stop()
                    await app.shutdown()
                    return
        except Exception as e:
            logger.error(f"Error in bot {bot_config['name']}: {e}")
            if 'recovery_task' in locals(): recovery_task.cancel()
            await asyncio.sleep(10)

async def main():
    managed_tasks = {} # {bot_id: Task}
    
    while True:
        try:
            active_bots = await asyncio.to_thread(database.get_all_managed_bots)
            active_bots = [b for b in active_bots if b['is_active']]
            
            # Start new bots
            for bot in active_bots:
                if bot['id'] not in managed_tasks:
                    managed_tasks[bot['id']] = asyncio.create_task(run_bot_instance(bot))
            
            # Cleanup removed bots from task list (run_bot_instance handles shutdown for 'inactive' flag)
            to_remove = [bid for bid in managed_tasks if not any(b['id'] == bid for b in active_bots)]
            for bid in to_remove:
                managed_tasks[bid].cancel()
                del managed_tasks[bid]
            
            # If no bots found and TELEGRAM_TOKEN exists in .env, add it as a managed bot automatically
            if not active_bots and os.getenv("TELEGRAM_TOKEN"):
                logger.info("No managed bots found. Adding default TELEGRAM_TOKEN from .env")
                import httpx
                async with httpx.AsyncClient() as client:
                    token = os.getenv("TELEGRAM_TOKEN")
                    res = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                    info = res.json()
                    if info.get("ok"):
                        database.add_managed_bot(token, "Default Bot", "@" + info["result"]["username"])

        except Exception as e:
            logger.error(f"Main loop error: {e}")
        
        await asyncio.sleep(30)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
