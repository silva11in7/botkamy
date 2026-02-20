import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 2. Transactions Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        product_id TEXT,
        amount REAL,
        status TEXT, -- 'pending', 'confirmed', 'failed', 'refunded'
        payment_method TEXT,
        client_email TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        confirmed_at DATETIME,
        oasyfy_id TEXT
    )
    ''')
    
    # 3. Products Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT,
        active INTEGER DEFAULT 1,
        category TEXT DEFAULT 'vip'
    )
    ''')
    
    # 4. Settings Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')
    
    # 5. Broadcasts Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        recipients_count INTEGER DEFAULT 0,
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # **NOVO V3: Funil de Vendas**
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS funnel_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        event_type TEXT, -- 'start', 'view_plans', 'checkout', 'payment_success'
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # **NOVO V3: Conteúdo Dinâmico (No-Code)**
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_content (
        key TEXT PRIMARY KEY,
        value TEXT,
        description TEXT,
        button_text TEXT,
        button_url TEXT
    )
    ''')

    # **NOVO V3.5: Ligação Conteúdo-Produto (Many-to-Many)**
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS content_product_links (
        content_key TEXT,
        product_id TEXT,
        PRIMARY KEY (content_key, product_id),
        FOREIGN KEY (content_key) REFERENCES bot_content(key),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    ''')
    
    # Inicia conteúdos padrão se não existirem
    default_content = {
        "welcome_text": ("Olá gatão! Escolha seu plano abaixo e comece agora:", "Texto de boas-vindas do bot"),
        "support_text": ("Precisa de ajuda? Fale com nosso suporte:", "Texto que antecede o botão de suporte"),
        "plans_button": ("🎭 VER PLANOS VIP", "Texto do botão que abre o catálogo"),
        "support_button": ("💎 SUPORTE", "Texto do botão de suporte")
    }
    for k, (v, d) in default_content.items():
        # Check if description column exists (migration helper)
        try:
            cursor.execute("INSERT OR IGNORE INTO bot_content (key, value, description) VALUES (?, ?, ?)", (k, v, d))
        except sqlite3.OperationalError:
            cursor.execute("INSERT OR IGNORE INTO bot_content (key, value) VALUES (?, ?)", (k, v))
            cursor.execute(f"UPDATE bot_content SET description = ? WHERE key = ?", (d, k))

    # **NOVO V3: Automação de Recuperação**
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS automation_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        delay_minutes INTEGER,
        message TEXT,
        active INTEGER DEFAULT 1
    )
    ''')
    
    # Regra padrão: 15 minutos
    cursor.execute("INSERT OR IGNORE INTO automation_rules (id, delay_minutes, message, active) VALUES (1, 15, 'Vi que você gerou um Pix mas não concluiu. O conteúdo expira em breve! Vamos fechar?', 1)")
    
    # Initialize default settings
    default_settings = {
        'webhook_token': '',
        'maintenance_mode': 'false',
        'support_user': '@SeuUsuarioTelegram',
        'recovery_message': 'Vimos que você não finalizou seu Pix... Ganhe +5% de desconto agora! Use o código: K10'
    }
    for key, value in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    
    # Initialize default products if empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        initial_products = [
            ("vip_live", "VIP VITALICIO + 🔥 LIVES", 29.91, "Acesso vitalício + Lives exclusivas"),
            ("vip_vital", "VIP VITALICIO 💎", 21.91, "Acesso vitalício a todo conteúdo"),
            ("vip_mensal", "VIP MENSAL 😈", 17.91, "Acesso por 30 dias"),
            ("vip_live_disc", "VIP VITALICIO + 🔥 LIVES (15% OFF)", 25.41, "Acesso vitalício + Lives exclusivas"),
            ("vip_vital_disc", "VIP VITALICIO 💎 (15% OFF)", 18.91, "Acesso vitalício a todo conteúdo"),
            ("vip_mensal_disc", "VIP MENSAL 😈 (15% OFF)", 15.37, "Acesso por 30 dias"),
            ("vip_live_disc2", "VIP VITALICIO + 🔥 LIVES (20% OFF)", 21.90, "Acesso vitalício + Lives exclusivas"),
            ("vip_vital_disc2", "VIP VITALICIO 🔥 (20% OFF)", 16.62, "Acesso vitalício a todo conteúdo"),
            ("vip_mensal_disc2", "VIP MENSAL 🔥 (20% OFF)", 13.28, "Acesso por 30 dias")
        ]
        cursor.executemany("INSERT INTO products (id, name, price, description) VALUES (?, ?, ?, ?)", initial_products)
    
    conn.commit()
    conn.close()

# --- User & Transaction Helpers ---
def log_user(user_id, username, full_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)', (user_id, username, full_name))
    cursor.execute('UPDATE users SET username = ?, full_name = ? WHERE id = ?', (username, full_name, user_id))
    conn.commit()
    conn.close()

def log_transaction(identifier, user_id, product_id, amount, status='pending', payment_method='PIX', client_email=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO transactions (id, user_id, product_id, amount, status, payment_method, client_email)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (identifier, user_id, product_id, amount, status, payment_method, client_email))
    conn.commit()
    conn.close()

def update_transaction_status(identifier, status, oasyfy_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    update_time = datetime.now().isoformat() if status == 'confirmed' else None
    cursor.execute('''
    UPDATE transactions 
    SET status = ?, confirmed_at = COALESCE(confirmed_at, ?), oasyfy_id = COALESCE(oasyfy_id, ?)
    WHERE id = ? OR oasyfy_id = ?
    ''', (status, update_time, oasyfy_id, identifier, oasyfy_id))
    conn.commit()
    conn.close()

def confirm_transaction(identifier):
    update_transaction_status(identifier, 'confirmed')

# --- Data Fetching for Metrics/Admin ---
def get_metrics():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'confirmed'")
    total_sales = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE status = 'confirmed'")
    total_revenue = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'")
    pending_pix = cursor.fetchone()[0]
    conn.close()
    return {"total_users": total_users, "total_sales": total_sales, "total_revenue": total_revenue, "pending_pix": pending_pix}

def get_all_transactions(limit=100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT t.*, u.username, u.full_name FROM transactions t LEFT JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_users(limit=1000):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Product Management ---
def get_active_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE active = 1")
    rows = cursor.fetchall()
    conn.close()
    return {row['id']: {"name": row['name'], "price": row['price'], "desc": row['description']} for row in rows}

def get_all_products_raw():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_product(p_id, name, price, description, active):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET name=?, price=?, description=?, active=? WHERE id=?", (name, price, description, active, p_id))
    conn.commit()
    conn.close()

# --- Settings ---
def get_setting(key, default=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# --- Stats for Charts ---
def get_revenue_stats(days=7):
    conn = get_connection()
    cursor = conn.cursor()
    # Mocking real stats for now to avoid complexity of SQL date functions across OS (sqlite date vs isoformat)
    # In a production app, we would query group by strftime('%Y-%m-%d', confirmed_at)
    cursor.execute('''
        SELECT DATE(created_at) as day, SUM(amount) as total 
        FROM transactions 
        WHERE status = 'confirmed' 
        GROUP BY day 
        ORDER BY day DESC 
        LIMIT ?
    ''', (days,))
    rows = cursor.fetchall()
    conn.close()
    return [{"day": row['day'], "total": row['total']} for row in rows]

# --- V3: Funnel & Analytics ---
def track_event(user_id, event_type):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO funnel_events (user_id, event_type) VALUES (?, ?)", (user_id, event_type))
    conn.commit()
    conn.close()

def get_funnel_stats():
    conn = get_connection()
    cursor = conn.cursor()
    stages = ['start', 'view_plans', 'checkout', 'payment_success']
    stats = {}
    for stage in stages:
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM funnel_events WHERE event_type = ?", (stage,))
        stats[stage] = cursor.fetchone()[0]
    conn.close()
    return stats

# --- V3: Bot Content ---
def get_bot_content(key, default=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_content WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def update_bot_content(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_content (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_all_content():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bot_content")
    rows = cursor.fetchall()
    
    content_list = []
    for row in rows:
        # Convert to dict for safety and ease of use
        item = dict(row)
        key = item['key']
        
        # Buscar produtos ligados
        cursor.execute("SELECT product_id FROM content_product_links WHERE content_key = ?", (key,))
        products = [r[0] for r in cursor.fetchall()]
        
        content_list.append({
            "key": key,
            "value": item.get('value', ''),
            "description": item.get('description', ''),
            "button_text": item.get('button_text', ''),
            "button_url": item.get('button_url', ''),
            "products": products
        })
    conn.close()
    return content_list

def get_products_for_content(content_key):
    """Retorna IDs de produtos vinculados a uma chave de conteúdo."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM content_product_links WHERE content_key = ?", (content_key,))
    products = [r[0] for r in cursor.fetchall()]
    conn.close()
    return products

def get_linked_content_for_product(product_id):
    """Retorna todos os conteúdos vinculados a um produto específico."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT bc.* 
        FROM bot_content bc
        JOIN content_product_links cpl ON bc.key = cpl.content_key
        WHERE cpl.product_id = ?
    ''', (product_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_content_for_product(key, product_id, default=""):
    """Prioritiza conteúdo ligado ao produto específico, senão retorna o padrão."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Tentar buscar conteúdo ligado especificamente a este produto
    cursor.execute('''
        SELECT bc.value 
        FROM bot_content bc
        JOIN content_product_links cpl ON bc.key = cpl.content_key
        WHERE bc.key = ? AND cpl.product_id = ?
    ''', (key, product_id))
    
    row = cursor.fetchone()
    if row:
        conn.close()
        return row[0]
        
    # 2. Fallback para o conteúdo geral (sem ligação) ou primeiro disponível
    cursor.execute("SELECT value FROM bot_content WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def update_bot_content_advanced(key, value, description, product_ids, button_text="", button_url=""):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Update or insert content
    cursor.execute('''
        INSERT OR REPLACE INTO bot_content (key, value, description, button_text, button_url) 
        VALUES (?, ?, ?, ?, ?)
    ''', (key, value, description, button_text, button_url))
    
    # Update links
    cursor.execute("DELETE FROM content_product_links WHERE content_key = ?", (key,))
    for p_id in product_ids:
        cursor.execute("INSERT INTO content_product_links (content_key, product_id) VALUES (?, ?)", 
                       (key, p_id))
    
    conn.commit()
    conn.close()

def delete_bot_content(key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bot_content WHERE key = ?", (key,))
    cursor.execute("DELETE FROM content_product_links WHERE content_key = ?", (key,))
    conn.commit()
    conn.close()

# --- V3: Automation ---
def get_automation_rules():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM automation_rules")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_automation_rule(rule_id, delay, message, active):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE automation_rules SET delay_minutes = ?, message = ?, active = ? WHERE id = ?", (delay, message, active, rule_id))
    conn.commit()
    conn.close()

def get_pending_automations():
    """Retorna Pix pendentes que precisam de automação"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, r.message, u.username, u.full_name
        FROM transactions t
        INNER JOIN users u ON t.user_id = u.id
        CROSS JOIN automation_rules r
        WHERE t.status = 'pending' 
        AND r.active = 1
        AND datetime(t.created_at) <= datetime('now', '-' || r.delay_minutes || ' minutes', 'localtime')
        AND datetime(t.created_at) > datetime('now', '-' || (r.delay_minutes + 15) || ' minutes', 'localtime')
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- V3 Utility ---
def execute_sql(query, params=(), commit=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    if commit:
        conn.commit()
        res = cursor.lastrowid
    else:
        res = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return res

def get_transaction_user(identifier):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM transactions WHERE id = ?", (identifier,))
    row = cursor.fetchone()
    conn.close()
    return row['user_id'] if row else None
