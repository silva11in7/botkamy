import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY environment variables not set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def init_db():
    """
    Supabase tables are typically created via SQL migrations.
    This function remains for compatibility but doesn't perform DDL.
    """
    pass

# --- User & Transaction Helpers ---
def log_user(user_id: int, username: str, full_name: str):
    supabase = get_supabase()
    data = {
        "id": user_id,
        "username": username,
        "full_name": full_name,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("users").upsert(data).execute()

def log_transaction(identifier: str, user_id: int, product_id: str, amount: float, status: str = 'pending', payment_method: str = 'PIX', client_email: str = None):
    supabase = get_supabase()
    data = {
        "id": identifier,
        "user_id": user_id,
        "product_id": product_id,
        "amount": amount,
        "status": status,
        "payment_method": payment_method,
        "client_email": client_email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("transactions").insert(data).execute()

def update_transaction_status(identifier: str, status: str, oasyfy_id: str = None):
    supabase = get_supabase()
    update_data = {"status": status}
    if status == 'confirmed':
        update_data["confirmed_at"] = datetime.now(timezone.utc).isoformat()
    if oasyfy_id:
        update_data["oasyfy_id"] = oasyfy_id

    # Update by ID or oasyfy_id
    query = supabase.table("transactions").update(update_data)
    if oasyfy_id:
        query.or_(f"id.eq.{identifier},oasyfy_id.eq.{oasyfy_id}").execute()
    else:
        query.eq("id", identifier).execute()

def confirm_transaction(identifier: str):
    update_transaction_status(identifier, 'confirmed')

# --- Data Fetching for Metrics/Admin ---
def get_metrics():
    supabase = get_supabase()
    
    total_users = supabase.table("users").select("id", count="exact").execute().count
    total_sales = supabase.table("transactions").select("id", count="exact").eq("status", "confirmed").execute().count
    
    response = supabase.table("transactions").select("amount").eq("status", "confirmed").execute()
    total_revenue = sum(row['amount'] for row in response.data) if response.data else 0.0
    
    pending_pix = supabase.table("transactions").select("id", count="exact").eq("status", "pending").execute().count
    
    return {
        "total_users": total_users,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "pending_pix": pending_pix
    }

def get_all_transactions(limit: int = 100):
    supabase = get_supabase()
    response = supabase.table("transactions").select("*, users!left(username, full_name)").order("created_at", descending=True).limit(limit).execute()
    
    results = []
    for row in response.data:
        user_info = row.pop('users', {}) or {}
        row['username'] = user_info.get('username')
        row['full_name'] = user_info.get('full_name')
        results.append(row)
    return results

def get_all_users(limit: int = 1000):
    supabase = get_supabase()
    response = supabase.table("users").select("*").order("created_at", descending=True).limit(limit).execute()
    return response.data

# --- Product Management ---
def get_active_products():
    supabase = get_supabase()
    response = supabase.table("products").select("*").eq("active", 1).execute()
    return {row['id']: {"name": row['name'], "price": row['price'], "desc": row['description']} for row in response.data}

def get_all_products_raw():
    supabase = get_supabase()
    response = supabase.table("products").select("*").execute()
    return response.data

def update_product(p_id: str, name: str, price: float, description: str, active: int):
    supabase = get_supabase()
    supabase.table("products").update({
        "name": name,
        "price": price,
        "description": description,
        "active": active
    }).eq("id", p_id).execute()

# --- Settings ---
def get_setting(key: str, default: str = "") -> str:
    supabase = get_supabase()
    response = supabase.table("settings").select("value").eq("key", key).maybe_single().execute()
    return response.data['value'] if response.data else default

def set_setting(key: str, value: Any):
    supabase = get_supabase()
    supabase.table("settings").upsert({"key": key, "value": str(value)}).execute()

# --- Stats for Charts ---
def get_revenue_stats(days: int = 7):
    supabase = get_supabase()
    # Simplified: Get all confirmed and group in Python for consistency
    response = supabase.table("transactions").select("created_at, amount").eq("status", "confirmed").order("created_at", descending=True).execute()
    
    stats = {}
    for row in response.data:
        day = row['created_at'].split("T")[0]
        stats[day] = stats.get(day, 0) + row['amount']
        if len(stats) >= days: break
        
    return [{"day": d, "total": v} for d, v in sorted(stats.items())]

# --- V3: Funnel & Analytics ---
def track_event(user_id: int, event_type: str):
    supabase = get_supabase()
    supabase.table("funnel_events").insert({
        "user_id": user_id,
        "event_type": event_type
    }).execute()

def get_funnel_stats():
    supabase = get_supabase()
    stages = ['start', 'view_plans', 'checkout', 'payment_success']
    stats = {}
    for stage in stages:
        response = supabase.table("funnel_events").select("user_id", count="exact").eq("event_type", stage).execute()
        # count for distinct would be better but exact count of user_ids is close for now
        # Supabase doesn't easily support select count(distinct) via API
        stats[stage] = response.count
    return stats

# --- V3: Bot Content ---
def get_bot_content(key: str, default: str = "") -> str:
    supabase = get_supabase()
    response = supabase.table("bot_content").select("value").eq("key", key).maybe_single().execute()
    return response.data['value'] if response.data else default

def update_bot_content(key: str, value: str):
    supabase = get_supabase()
    supabase.table("bot_content").upsert({"key": key, "value": value}).execute()

def get_all_content():
    supabase = get_supabase()
    response = supabase.table("bot_content").select("*").execute()
    
    content_list = []
    for item in response.data:
        key = item['key']
        links = supabase.table("content_product_links").select("product_id").eq("content_key", key).execute()
        item['products'] = [r['product_id'] for r in links.data]
        content_list.append(item)
    return content_list

def get_products_for_content(content_key: str):
    supabase = get_supabase()
    response = supabase.table("content_product_links").select("product_id").eq("content_key", content_key).execute()
    return [r['product_id'] for r in response.data]

def get_linked_content_for_product(product_id: str):
    supabase = get_supabase()
    response = supabase.table("content_product_links").select("bot_content(*)").eq("product_id", product_id).execute()
    return [r['bot_content'] for r in response.data if r.get('bot_content')]

def get_content_for_product(key: str, product_id: str, default: str = ""):
    supabase = get_supabase()
    # Try specific link first
    response = supabase.table("content_product_links").select("bot_content!inner(value)").eq("content_key", key).eq("product_id", product_id).maybe_single().execute()
    if response.data:
        return response.data['bot_content']['value']
        
    return get_bot_content(key, default)

def update_bot_content_advanced(key: str, value: str, description: str, product_ids: List[str], button_text: str = "", button_url: str = ""):
    supabase = get_supabase()
    supabase.table("bot_content").upsert({
        "key": key,
        "value": value,
        "description": description,
        "button_text": button_text,
        "button_url": button_url
    }).execute()
    
    supabase.table("content_product_links").delete().eq("content_key", key).execute()
    if product_ids:
        links = [{"content_key": key, "product_id": pid} for pid in product_ids]
        supabase.table("content_product_links").insert(links).execute()

def delete_bot_content(key: str):
    supabase = get_supabase()
    supabase.table("bot_content").delete().eq("key", key).execute()

# --- V3: Automation ---
def get_automation_rules():
    supabase = get_supabase()
    response = supabase.table("automation_rules").select("*").execute()
    return response.data

def update_automation_rule(rule_id: int, delay: int, message: str, active: int):
    supabase = get_supabase()
    supabase.table("automation_rules").update({
        "delay_minutes": delay,
        "message": message,
        "active": active
    }).eq("id", rule_id).execute()

def get_pending_automations():
    """Retorna Pix pendentes que precisam de automação (Postgres version)"""
    # Note: Complex cross-join logic is better handled via a RPC function in Supabase if needed,
    # but let's implement a core version here using filters.
    supabase = get_supabase()
    
    rules = get_automation_rules()
    pending = []
    
    for rule in rules:
        if not rule['active']: continue
        
        # We need to filter transactions by date range. 
        # created_at <= now - delay and created_at > now - (delay + 15)
        # For simplicity in API, we'll fetch and filter if not too many, 
        # or use specialized where clause.
        response = supabase.table("transactions").select("*, users!inner(username, full_name)").eq("status", "pending").execute()
        
        for t in response.data:
            created = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00'))
            diff = (datetime.now(timezone.utc) - created).total_seconds() / 60
            
            if rule['delay_minutes'] <= diff < (rule['delay_minutes'] + 15):
                t['message'] = rule['message']
                user_info = t.pop('users', {})
                t['username'] = user_info.get('username')
                t['full_name'] = user_info.get('full_name')
                pending.append(t)
                
    return pending

def get_transaction_user(identifier: str) -> Optional[int]:
    supabase = get_supabase()
    response = supabase.table("transactions").select("user_id").eq("id", identifier).maybe_single().execute()
    return response.data['user_id'] if response.data else None
