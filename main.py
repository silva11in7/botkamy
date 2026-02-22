import os
import logging
import asyncio
import qrcode
import io
import random
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from api import babylon, utmfy
import secrets
import string
import database
import json

# Initialize database
database.init_db()

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Track pending reminders: {user_id: asyncio.Task}
pending_reminders = {}

# Media cache to avoid re-uploading files: {file_path: file_id}
media_cache = {
    "banner": None,
    "reminder_videos": {}
}

# --- Content Data (Now Dynamic) ---
def get_products():
    return database.get_active_products()

# Fallback for initialization
INITIAL_PRODUCTS = get_products()

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

# --- Inactivity Reminder Stage 2 Data ---
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

async def check_maintenance(update: Update):
    """Checks if the bot is in maintenance mode."""
    is_maintenance = database.get_setting("maintenance_mode", "false").lower() == "true"
    if is_maintenance:
        msg = "🛠 **MODO MANUTENÇÃO**\n\nEstamos fazendo algumas melhorias rápidas. Voltamos em instantes! 😘"
        if update.callback_query:
            await update.callback_query.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        return True
    return False

async def run_reminder(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Waits for 5 seconds and sends the inactivity reminder with a video."""
    print(f"[DEBUG] Reminder task STARTED for user {user_id}")
    try:
        # Step 1: Wait 30 seconds
        await asyncio.sleep(30)
        print(f"[DEBUG] Reminder timer EXPIRED (30s) for user {user_id}. Sending video...")
        # Stage 1: Random Video + 15% OFF
        video_files = [
            "imgs/videokamyrebo.mp4",
            "imgs/1.mp4",
            "imgs/2.mp4"
        ]
        chosen_video = random.choice(video_files)
        
        if os.path.exists(chosen_video):
            # Check cache for file_id
            cached_id = media_cache["reminder_videos"].get(chosen_video)
            
            try:
                msg = await context.bot.send_video(
                    chat_id=chat_id,
                    video=cached_id or open(chosen_video, 'rb'),
                    caption="🔥 **NÃO VAI EMBORA!**\n\nPreparei um presente especial: **15% de DESCONTO** exclusivo pra você hoje! 🎁🎬",
                    reply_markup=InlineKeyboardMarkup(INACTIVITY_KEYBOARD),
                    parse_mode='Markdown'
                )
                # Store file_id if not cached
                if not cached_id and msg.video:
                    media_cache["reminder_videos"][chosen_video] = msg.video.file_id
            except Exception as e:
                print(f"[ERROR] Failed to send reminder video: {e}")
                # Fallback text if sending fails
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🔥 **ESPERA!** Preparei um desconto de **15% OFF** pra você não perder nada hoje! 🎁",
                    reply_markup=InlineKeyboardMarkup(INACTIVITY_KEYBOARD),
                    parse_mode='Markdown'
                )
        else:
            print(f"[ERROR] Video file {chosen_video} not found for reminder.")
            # Fallback if video is missing
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔥 **ESPERA!** Preparei um desconto de **15% OFF** pra você não perder nada hoje! 🎁",
                reply_markup=InlineKeyboardMarkup(INACTIVITY_KEYBOARD),
                parse_mode='Markdown'
            )
        print(f"[DEBUG] Reminder level 1 SENT to user {user_id}")

        # --- Stage 2: 20 more seconds ---
        await asyncio.sleep(20)
        print(f"[DEBUG] Reminder stage 2 timer EXPIRED (20s) for user {user_id}. Sending photo...")
        
        photo_path = os.path.join("imgs", "kamyimagina.jpeg")
        
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=IMAGINA_TEXT,
                    reply_markup=InlineKeyboardMarkup(IMAGINA_KEYBOARD)
                )
        else:
            print(f"[DEBUG] Photo not found at {photo_path}, falling back to text.")
            await context.bot.send_message(
                chat_id=chat_id,
                text=IMAGINA_TEXT,
                reply_markup=InlineKeyboardMarkup(IMAGINA_KEYBOARD)
            )
        print(f"[DEBUG] Reminder level 2 SENT to user {user_id}")

    except asyncio.CancelledError:
        print(f"[DEBUG] Reminder task CANCELLED for user {user_id}")
    except Exception as e:
        print(f"[DEBUG] ERROR in reminder task for user {user_id}: {e}")
        logging.error(f"Error in reminder task for user {user_id}: {e}")
    finally:
        if user_id in pending_reminders:
            del pending_reminders[user_id]
        print(f"[DEBUG] Reminder task CLEANED UP for user {user_id}")

def parse_start_payload(payload: str) -> Dict[str, str]:
    """Parses standard and custom tracking parameters from the start payload."""
    tracking = {}
    if not payload: return tracking
    
    # Example format: ttclid_12345_utms_tiktok_utmm_cpc
    if "_" in payload:
        parts = payload.split("_")
        for i in range(0, len(parts) - 1, 2):
            key = parts[i]
            val = parts[i+1]
            if key == "ttclid": tracking["ttclid"] = val
            elif key == "utms": tracking["utm_source"] = val
            elif key == "utmm": tracking["utm_medium"] = val
            elif key == "utmc": tracking["utm_campaign"] = val
            elif key == "utmt": tracking["utm_term"] = val
            elif key == "utmn": tracking["utm_content"] = val
    else:
        # Fallback: Treat as ttclid if no separators
        tracking["ttclid"] = payload
        
    return tracking

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: Welcome Message with Banner."""
    user = update.effective_user
    
    # Parse tracking data from /start payload
    tracking_data = {}
    if context.args:
        tracking_data = parse_start_payload(context.args[0])
        print(f"[DEBUG] Tracking detected for user {user.id}: {tracking_data}")

    # Log user with tracking data
    asyncio.create_task(asyncio.to_thread(database.log_user, user.id, user.username, user.full_name, tracking_data))
    
    # Track "Lead" event in UTMfy
    user_info = {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        **tracking_data
    }
    asyncio.create_task(utmfy.send_event("Lead", user_info))
    asyncio.create_task(asyncio.to_thread(database.track_event, user.id, 'start'))

    # Fetch content and products safely in threads
    welcome_text = await asyncio.to_thread(database.get_bot_content, "welcome_text", "Olá gatão! Escolha seu plano abaixo e comece agora:")
    # Build Keyboard
    keyboard = []
    
    # Adicionar produtos linkados primeiro
    linked_prod_ids = await asyncio.to_thread(database.get_products_for_content, "welcome_text")
    if linked_prod_ids:
        all_prods = await asyncio.to_thread(database.get_active_products)
        for prod_id in linked_prod_ids:
            product = all_prods.get(prod_id)
            if product:
                # Formatar preço igual ao exemplo do usuário
                price_val = product['price']
                price_formated = f"R${price_val:,.2f}".replace('.', 'v').replace(',', '.').replace('v', ',')
                btn_label = f"🔥 {product['name']} POR {price_formated}"
                keyboard.append([InlineKeyboardButton(btn_label, callback_data=f"buy_{prod_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    photo_path = os.path.join("imgs", "3banner.mp4")
    
    if os.path.exists(photo_path):
        # Check cache for file_id
        cached_id = media_cache.get("banner")
        
        try:
            if photo_path.lower().endswith(('.mp4', '.mov', '.avi')):
                msg = await update.message.reply_video(
                    video=cached_id or open(photo_path, 'rb'),
                    caption=welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                if not cached_id and msg.video:
                    media_cache["banner"] = msg.video.file_id
            else:
                msg = await update.message.reply_photo(
                    photo=cached_id or open(photo_path, 'rb'),
                    caption=welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                if not cached_id and msg.photo:
                    media_cache["banner"] = msg.photo[-1].file_id
        except Exception as e:
            print(f"[ERROR] Failed to send banner: {e}")
            await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Schedule inactivity reminder
    user_id = user.id
    if user_id in pending_reminders:
        pending_reminders[user_id].cancel()
    pending_reminders[user_id] = asyncio.create_task(run_reminder(user_id, update.effective_chat.id, context))

async def post_init(application):
    """Sets the bot commands and profile descriptions."""
    # 1. Set Menu Commands
    commands = [
        BotCommand("iniciar", "Iniciar o robô 🤖"),
        BotCommand("start", "Recomeçar 🔄")
    ]
    await application.bot.set_my_commands(commands)
    
    # 2. Set "What can this bot do?" Description (shown before start)
    description_text = (
        "oi delícia😈\n"
        "Minhas putarias +18 mais escondidas, tudo\n"
        "organizadinho pra você achar rapidinho o\n"
        "que quer.\n\n"
        "clica em \"INCIAR\" que eu libero tudo agora\n"
        "👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻"
    )
    await application.bot.set_my_description(description_text)
    
    # 3. Set Short Description (shown on profile)
    await application.bot.set_my_short_description("O melhor conteúdo VIP da Kamy! 🔥😈")
    
    print("[DEBUG] Bot commands and descriptions set successfully.")

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu."""
    keyboard = [
        [InlineKeyboardButton("VIP VITALICIO + 🔥 LIVES POR R$29,91", callback_data='buy_vip_live')],
        [InlineKeyboardButton("VIP VITALICIO 💎 POR R$21,91", callback_data='buy_vip_vital')],
        [InlineKeyboardButton("VIP MENSAL � POR R$17,91", callback_data='buy_vip_mensal')],
        [InlineKeyboardButton("SUPORTE 💬", callback_data='support')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if called from callback or message
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text="Bem-vindo(a) ao meu espaço secreto! 😈\nEscolha uma opção abaixo:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text="Bem-vindo(a) ao meu espaço secreto! 😈\nEscolha uma opção abaixo:",
            reply_markup=reply_markup
        )

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists available products."""
    keyboard = []
    products = get_products()
    for product_id, details in products.items():
        price_formated = f"R$ {details['price']}".replace(".", ",")
        btn_text = f"{details['name']} - {price_formated}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'prod_{product_id}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text="🔥 **Catálogo de Conteúdos** 🔥\n\nSelecione um item para ver detalhes:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: str):
    """Shows details for a specific product."""
    products = get_products()
    product = products.get(product_id)
    if not product:
        await update.callback_query.answer("Produto não encontrado.", show_alert=True)
        return

    keyboard = [
        [InlineKeyboardButton("💳 Comprar Agora", callback_data=f'buy_{product_id}')],
        [InlineKeyboardButton("🔙 Voltar aos Conteúdos", callback_data='list_products')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    price_formated = f"R$ {product['price']}".replace(".", ",")
    
    # NEW V3.5: Dynamic custom description for product
    # If there's a custom key linked to this product, we can use it.
    # Looking for a key that might be a 'product_description' or similar if linked.
    # For now, let's use the core description but look if there's a custom override.
    custom_text = database.get_content_for_product(f"desc_{product_id}", product_id, None)
    display_desc = custom_text if custom_text else product['desc']
    
    text = (
        f"🔞 **{product['name']}**\n\n"
        f"📝 {display_desc}\n"
        f"💰 Preço: **{price_formated}**\n\n"
        "O envio é imediato após a confirmação do pagamento!"
    )
    
    # --- NEW V3.5: Safety for Edit ---
    try:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except:
        # Fallback if message cannot be edited (e.g. is a media message)
        await update.callback_query.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # --- NEW V3.5: Send Linked Follow-up Messages ---
    linked_msgs = database.get_linked_content_for_product(product_id)
    for msg in linked_msgs:
        # Avoid showing the standard description override twice if it's already used as desc_{id}
        if msg['key'] == f"desc_{product_id}":
            continue
            
        markup = None
        if msg.get('button_text') and msg.get('button_url'):
            markup = InlineKeyboardMarkup([[InlineKeyboardButton(msg['button_text'], url=msg['button_url'])]])
            
        await update.callback_query.message.reply_text(
            text=msg['value'],
        )

async def handle_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: str):
    """Handles the purchase flow using Babylon API."""
    if await check_maintenance(update): return
    query = update.callback_query
    user = update.effective_user
    user_id = user.id
    client_email = f"user_{user_id}@telegram.com" # Global for this function scope
    
    product = get_products().get(product_id)
    if not product:
        await query.answer("Produto não encontrado.", show_alert=True)
        return

    # Cancel inactivity reminder if user chooses a package
    if user_id in pending_reminders:
        print(f"[DEBUG] Package selected. Cancelling reminders for user {user_id}")
        pending_reminders[user_id].cancel()
        del pending_reminders[user_id]
        
    # Get internal user data (for tracking)
    db_user = await asyncio.to_thread(database.get_user, user_id)
    tracking_data = {}
    if db_user:
        # Extract tracking fields
        for key in ["ttclid", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]:
            if db_user.get(key):
                tracking_data[key] = db_user[key]

    await query.message.reply_text("Certo, me dá só um minuto enquanto gero seu Pix de pagamento...")
    
    # Generate unique identifier
    identifier = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10))
    
    # Create Pix payment via Babylon
    client_email = f"user_{user_id}@telegram.com"
    print(f"[DEBUG] Tentando gerar Pix para {product_id} - R${product['price']}")
    
    # Track "InitiateCheckout" event in UTMfy
    checkout_info = {
        "id": user_id,
        "username": user.username,
        "full_name": user.full_name,
        **tracking_data
    }
    tx_meta = {
        "product_id": product_id,
        "product_name": product['name'],
        "amount": product['price']
    }
    asyncio.create_task(utmfy.send_event("InitiateCheckout", checkout_info, tx_meta))

    pix_data = await babylon.create_pix_payment(
        identifier=identifier,
        amount=product['price'],
        client_name=user.full_name or "Cliente Telegram",
        client_email=client_email,
        client_phone="(11) 99999-9999", # Placeholder
        client_document="12345678909", # Placeholder
        product_title=product['name'],
        metadata=tracking_data # Pass tracking metadata to Babylon for webhook usage
    )

    if pix_data:
        print(f"[DEBUG] Pix gerado com sucesso!")
        # Log transaction to database with tracking metadata
        database.log_transaction(
            identifier=identifier,
            user_id=user_id,
            product_id=product_id,
            amount=product['price'],
            status='pending',
            client_email=client_email,
            metadata=tracking_data
        )
    else:
        print(f"[DEBUG] FALHA na geração do Pix via Babylon.")

    if not pix_data:
        await query.message.reply_text("❌ Desculpe, ocorreu um erro ao gerar seu Pix. Por favor, tente novamente mais tarde ou contate o suporte.")
        return

    pix_key = pix_data['pix']['code']
    qr_image_url = pix_data['pix'].get('image')
    qr_base64 = pix_data['pix'].get('base64')

    # 2. Segunda mensagem: Instruções + Chave
    msg_instrucoes = (
        "✅ Prontinho\n\n"
        "Escaneie o QR Code acima 👆 ou utilize a opção PIX Copia e Cola no seu aplicativo bancário.\n\n"
        "Para copiar a chave, clique nela abaixo ⬇️"
    )
    
    # Enviar QR Code (Prioritize URL or Base64 if available, fallback to local generation if needed)
    if qr_image_url:
        await query.message.reply_photo(photo=qr_image_url, caption="Seu QR Code para pagamento 🚀")
    elif qr_base64 and qr_base64.startswith("data:image"):
        # Decode base64 if needed, but usually photo=base64 doesn't work directly in telegram-python-bot easily without buffer
        # For simplicity, if we have the code, we can regenerate it locally to be safe
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(pix_key)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        bio.name = 'qrcode.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        await query.message.reply_photo(photo=bio, caption="Seu QR Code para pagamento 🚀")
    else:
        # Fallback local generation
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(pix_key)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        bio.name = 'qrcode.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        await query.message.reply_photo(photo=bio, caption="Seu QR Code para pagamento 🚀")
    
    await query.message.reply_text(msg_instrucoes)
    
    # Envia a chave Pix separada e formatada como código para facilitar a cópia
    await query.message.reply_text(f"`{pix_key}`", parse_mode='Markdown')
    
    # 3. Terceira mensagem: Importante + Botão Confirmar
    keyboard = [
        [InlineKeyboardButton("✅ Confirmar Pagamento", callback_data=f'confirm_pay_{product_id}_{identifier}')],
        [InlineKeyboardButton("🔙 Cancelar", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg_importante = (
        "⚠️ Importante! Após o pagamento, o acesso é liberado automaticamente.\n\n"
        "🕑 Aguarde alguns instantes para que nosso sistema receba a confirmação do seu pagamento pelo banco.\n\n"
        "Caso não receba o link automaticamente em alguns minutos, clique no botão \"Confirmar Pagamento\" abaixo ⬇️."
    )
    await query.message.reply_text(msg_importante, reply_markup=reply_markup)
    
    # 4. Quarta mensagem: Suporte
    support_user = database.get_setting("support_user", "@SeuUsuarioTelegram")
    await query.message.reply_text(f"📱 Se precisar, contate {support_user} para atendimento e suporte")

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simulates payment confirmation."""
    query = update.callback_query
    data_parts = query.data.split('_')
    # Format: confirm_pay_{product_id}_{identifier}
    if len(data_parts) >= 4:
        identifier = data_parts[3]
        database.confirm_transaction(identifier)
        print(f"[DEBUG] Transaction {identifier} confirmed by user button.")

    keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text="✅ **Pagamento Informado!**\n\n"
             "Vou verificar seu pagamento e te envio o conteúdo em instantes! 😘\n"
             "Caso demore, chame no suporte.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support information."""
    keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    support_user = database.get_setting("support_user", "@SeuUsuarioTelegram")
    await update.callback_query.edit_message_text(
        text="💬 **Suporte**\n\n"
             "Teve algum problema? Quer algo personalizado?\n"
             f"Entre em contato comigo: {support_user}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Router for callback queries."""
    if await check_maintenance(update): return
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Cancel inactivity reminder if user interacts
    user_id = update.effective_user.id
    if user_id in pending_reminders:
        print(f"[DEBUG] Interaction detected. Cancelling reminder for user {user_id}")
        pending_reminders[user_id].cancel()
        del pending_reminders[user_id]

    if data == 'verify_age_yes':
        await main_menu(update, context)
    elif data == 'verify_age_no':
        await query.edit_message_text("Desculpe, este conteúdo não é para você. 🚫")
    elif data == 'main_menu':
        await main_menu(update, context)
    elif data == 'list_products':
        await show_products(update, context)
    elif data == 'support':
        await support(update, context)
    elif data.startswith('prod_'):
        product_id = data.split('_')[1]
        await product_detail(update, context, product_id)
    elif data == "ver_planos":
        asyncio.create_task(asyncio.to_thread(database.track_event, user_id, 'view_plans'))
        await show_products(update, context)
    elif data.startswith('buy_'):
        product_id = data.replace('buy_', '', 1)
        asyncio.create_task(asyncio.to_thread(database.track_event, user_id, 'checkout'))
        await handle_purchase(update, context, product_id)
    elif data.startswith('confirm_pay_'):
        await confirm_payment(update, context)
    elif data == 'my_orders':
        # Placeholder for order history
        await query.answer("Você ainda não possui compras confirmadas.", show_alert=True)
    elif data == 'back_to_start':
        await start(update, context)


from telegram.error import Conflict

def start_bot():
    """Build and return the bot application."""
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('iniciar', start))
    app.add_handler(CallbackQueryHandler(button_handler))

    return app

if __name__ == '__main__':
    from telegram.error import NetworkError, Conflict
    import time

    backoff = 1
    while True:
        try:
            application = start_bot()
            print("Bot Kamy is starting polling...")
            application.run_polling(drop_pending_updates=True)
        except Conflict:
            print("⚠️ Conflito Detectado: Outra instância está rodando. Aguardando 10s...")
            time.sleep(10)
        except NetworkError:
            print(f"⚠️ Erro de Rede: Falha na conexão. Tentando novamente em {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60) # Exponential backoff max 60s
        except Exception as e:
            print(f"💥 Erro Inesperado: {e}. Reiniciando em 5s...")
            time.sleep(5)
        else:
            # Se sair normalmente (o que não deve acontecer no polling), reseta o backoff
            backoff = 1
