import os
import re
import json
import time
import requests
import threading
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# ================= Load Environment Variables =================
load_dotenv()

BOT_TOKEN = "8660352533:AAHgcFG8EADe-m1HiIgUYnfJub9GCjbGQMM"
OWNER_ID = 903018274

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_URL = f"https://api.telegram.org/file/bot{BOT_TOKEN}/"

file_lock = threading.Lock()
BD_TZ = timezone(timedelta(hours=6))

db = {
    "admins": [OWNER_ID],
    "proxies": {},          
    "vpn_plans": {},        
    "orders": {},          
    "deposits": {},        
    "users": {},            
    "settings": {
        "min_purchase": 1,
        "max_purchase": 20,
        "bkash": "017XXXXXXXX (Personal)",
        "binance": "123456789",
        "support": "anik2000",
        "supabase_url": "",
        "supabase_key": ""
    }
}

user_states = {}
temp_data = {}

def load_data():
    global db
    s_url = db.get("settings", {}).get("supabase_url", "")
    s_key = db.get("settings", {}).get("supabase_key", "")
    
    if s_url and s_key:
        try:
            headers = {"apikey": s_key, "Authorization": f"Bearer {s_key}"}
            res = requests.get(f"{s_url}/rest/v1/bot_storage?key=eq.main_db", headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    val = data[0].get("value", {})
                    if isinstance(val, dict):
                        db.update(val)
        except Exception as e:
            print(f"Error loading from Supabase REST: {e}")

    if OWNER_ID not in db["admins"]:
        db["admins"].append(OWNER_ID)
    if "support" not in db["settings"]:
        db["settings"]["support"] = "anik2000"
    if "deposits" not in db:
        db["deposits"] = {}
    if "vpn_plans" not in db:
        db["vpn_plans"] = {}

def save_data():
    with file_lock:
        s_url = db["settings"].get("supabase_url", "")
        s_key = db["settings"].get("supabase_key", "")
        if s_url and s_key:
            try:
                headers = {"apikey": s_key, "Authorization": f"Bearer {s_key}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
                payload = {"key": "main_db", "value": db}
                requests.post(f"{s_url}/rest/v1/bot_storage", headers=headers, json=payload, timeout=10)
            except Exception as e:
                print(f"Error saving to Supabase REST: {e}")

load_data()

session = requests.Session()

def api_call(method, payload=None):
    url = f"{BASE_URL}/{method}"
    try:
        res = session.post(url, json=payload, timeout=12)
        return res.json()
    except Exception:
        return {}

def send_msg(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup: payload["reply_markup"] = reply_markup
    return api_call("sendMessage", payload)

def edit_msg(chat_id, msg_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup: payload["reply_markup"] = reply_markup
    return api_call("editMessageText", payload)

def delete_msg(chat_id, msg_id):
    return api_call("deleteMessage", {"chat_id": chat_id, "message_id": msg_id})

def is_admin(user_id):
    load_data()
    return int(user_id) in [int(x) for x in db.get("admins", [OWNER_ID])]

# ================= Keyboards =================
def main_kb(user_id):
    kb = [
        [
            {"text": "🛒 Buy Proxies", "style": "primary"},
            {"text": "🔒 Buy VPN", "style": "primary"}
        ],
        [
            {"text": "💰 Deposit Balance", "style": "success"},
            {"text": "📊 Order History", "style": "success"}
        ],
        [
            {"text": "⚡ Live Proxy Checker", "style": "primary"},
            {"text": "👤 My Profile", "style": "success"}
        ],
        [
            {"text": "📞 Support", "style": "primary"}
        ]
    ]
    if is_admin(user_id):
        kb.append([{"text": "🛠 Admin Panel", "style": "danger"}])
    return {"keyboard": kb, "resize_keyboard": True}

def admin_kb():
    return {"inline_keyboard": [
        [{"text": "➕ Add Proxies (Unlimited .txt)", "callback_data": "adm_add_proxy", "style": "success"}],
        [{"text": "🗑 Delete / Manage Proxy Stock", "callback_data": "adm_del_proxy", "style": "danger"}],
        [{"text": "➕ Add VPN Plan", "callback_data": "adm_add_vpn", "style": "success"}],
        [{"text": "🛠 Manage / Edit VPN Stock & Plans", "callback_data": "adm_manage_vpn", "style": "primary"}],
        [{"text": "💰 Add/Cut User Balance", "callback_data": "adm_balance_menu", "style": "success"}],
        [{"text": "⚙️ Set Supabase Config", "callback_data": "adm_set_supabase", "style": "success"}],
        [{"text": "📢 Broadcast Message", "callback_data": "adm_broadcast", "style": "primary"}],
        [{"text": "👑 Manage Admins", "callback_data": "adm_manage_admins", "style": "primary"}],
        [{"text": "⚙️ Set Limits & Payments", "callback_data": "adm_settings", "style": "primary"}],
        [{"text": "👥 Total Users & Stats", "callback_data": "adm_stats", "style": "primary"}],
        [{"text": "❌ Close Console", "callback_data": "close", "style": "danger"}]
    ]}

def cancel_kb():
    return {"inline_keyboard": [[{"text": "Cancel", "callback_data": "cancel_state", "style": "danger"}]]}

# ================= Message Handler =================
def handle_message(msg):
    chat_id = msg["chat"]["id"]
    sender_id = msg.get("from", {}).get("id", chat_id)
    text = msg.get("text", "").strip()
    username = msg.get("from", {}).get("username", "")

    load_data()
    if str(sender_id) not in db.get("users", {}):
        db["users"][str(sender_id)] = {"username": username, "balance": 0.0, "time": time.time()}
        save_data()
    else:
        if "balance" not in db["users"][str(sender_id)]:
            db["users"][str(sender_id)]["balance"] = 0.0
            save_data()

    if chat_id in user_states:
        state = user_states[chat_id]
        
        if state == "adm_set_supabase_url" and text:
            temp_data[chat_id] = {"sup_url": text}
            user_states[chat_id] = "adm_set_supabase_key"
            send_msg(chat_id, f"🔑 Ekhon apnar Supabase <b>API Key</b> ti likhe pathan:", reply_markup=cancel_kb())
            return

        elif state == "adm_set_supabase_key" and text:
            s_url = temp_data[chat_id]["sup_url"]
            s_key = text
            if "settings" not in db: db["settings"] = {}
            db["settings"]["supabase_url"] = s_url
            db["settings"]["supabase_key"] = s_key
            save_data()
            
            del user_states[chat_id]
            del temp_data[chat_id]
            send_msg(chat_id, f"✅ Supabase config updated successfully!", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_wait_cat" and text:
            temp_data[chat_id] = {"category": text}
            user_states[chat_id] = "adm_wait_price"
            send_msg(chat_id, f"📌 Category: <b>{text}</b>\n\nPer proxy price koto hobe likhe pathan:")
            return

        elif state == "adm_wait_price" and text:
            try:
                price = float(text)
                temp_data[chat_id]["price"] = price
                user_states[chat_id] = "adm_wait_proxies"
                send_msg(chat_id, f"📤 Proxy gulo pathan (.txt file ba text):", reply_markup=cancel_kb())
            except ValueError:
                send_msg(chat_id, "❌ Invalid price!")
            return

        elif state == "adm_wait_proxies":
            raw_lines = []
            if "document" in msg:
                doc = msg["document"]
                if doc["file_name"].endswith(".txt"):
                    f_info = api_call("getFile", {"file_id": doc["file_id"]})
                    f_path = f_info.get("result", {}).get("file_path")
                    if f_path:
                        file_res = requests.get(f"{FILE_URL}{f_path}")
                        if file_res.status_code == 200:
                            content = file_res.content.decode('utf-8', errors='ignore')
                            raw_lines = content.splitlines()
            elif text:
                raw_lines = text.splitlines()

            if not raw_lines:
                send_msg(chat_id, "❌ Kono proxy data paoa jayni!")
                return

            cat = temp_data[chat_id]["category"]
            price = temp_data[chat_id]["price"]
            if cat not in db["proxies"]: db["proxies"][cat] = []
            added = 0
            for line in raw_lines:
                line = line.strip()
                if line:
                    db["proxies"][cat].append({"proxy": line, "price": price})
                    added += 1
            save_data()
            del user_states[chat_id]
            del temp_data[chat_id]
            send_msg(chat_id, f"✅ Success! <b>{added}</b> proxies added.", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_wait_vpn_name" and text:
            temp_data[chat_id] = {"vpn_name": text}
            user_states[chat_id] = "adm_wait_vpn_price"
            send_msg(chat_id, f"📌 VPN Name: <b>{text}</b>\n\nPrice koto hobe likhe pathan:", reply_markup=cancel_kb())
            return

        elif state == "adm_wait_vpn_price" and text:
            try:
                price = float(text)
                temp_data[chat_id]["vpn_price"] = price
                user_states[chat_id] = "adm_wait_vpn_stock"
                send_msg(chat_id, f"📦 Stock koiti available ase likhe pathan:", reply_markup=cancel_kb())
            except ValueError:
                send_msg(chat_id, "❌ Invalid price!")
            return

        elif state == "adm_wait_vpn_stock" and text:
            if not text.isdigit():
                send_msg(chat_id, "❌ Shudhu valid number pathan:")
                return
            temp_data[chat_id]["vpn_stock"] = int(text)
            user_states[chat_id] = "adm_wait_vpn_details"
            send_msg(chat_id, f"📝 VPN description likhe pathan:", reply_markup=cancel_kb())
            return

        elif state == "adm_wait_vpn_details" and text:
            v_data = temp_data[chat_id]
            db["vpn_plans"][v_data["vpn_name"]] = {"price": v_data["vpn_price"], "stock": v_data["vpn_stock"], "desc": text}
            save_data()
            del user_states[chat_id]
            del temp_data[chat_id]
            send_msg(chat_id, f"✅ VPN Plan added successfully.", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_edit_vpn_stock_val" and text:
            if not text.isdigit():
                send_msg(chat_id, "❌ Shudhu valid number pathan:")
                return
            v_name = temp_data[chat_id]["edit_vpn_name"]
            if v_name in db["vpn_plans"]:
                db["vpn_plans"][v_name]["stock"] = int(text)
                save_data()
                send_msg(chat_id, f"✅ VPN stock updated!", reply_markup=main_kb(sender_id))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "dep_wait_amount" and text:
            try:
                amount = float(text)
                if amount <= 0:
                    send_msg(chat_id, "❌ Shothik amount din:")
                    return
                temp_data[chat_id] = {"dep_amount": amount}
                pay_kb = {"inline_keyboard": [[{"text": "🟢 bKash", "callback_data": "dep_pay_bkash"}], [{"text": "🟡 Binance Pay", "callback_data": "dep_pay_binance"}]]}
                send_msg(chat_id, f"💳 Deposit Amount: <b>{amount}</b>\nPayment method select korun:", reply_markup=pay_kb)
                del user_states[chat_id]
            except ValueError:
                send_msg(chat_id, "❌ Shudhu number pathan:")
            return

        elif state == "dep_wait_trx" or state == "vpn_wait_trx":
            k = "dep_trx" if state == "dep_wait_trx" else "vpn_trx"
            temp_data[chat_id][k] = text
            user_states[chat_id] = "dep_wait_screenshot" if state == "dep_wait_trx" else "vpn_wait_screenshot"
            send_msg(chat_id, f"📤 Payment-er screenshot (photo) upload korun:", reply_markup=cancel_kb())
            return

        elif state == "adm_wait_user_id_for_balance" and text:
            if not text.isdigit():
                send_msg(chat_id, "❌ Valid User ID din:")
                return
            temp_data[chat_id] = {"target_uid": text.strip()}
            user_states[chat_id] = "adm_wait_balance_amount"
            send_msg(chat_id, f"💵 Koto taka add ba katte chan likhun:", reply_markup=cancel_kb())
            return

        elif state == "adm_wait_balance_amount" and text:
            try:
                amount = float(text)
                target_uid = temp_data[chat_id]["target_uid"]
                if target_uid not in db["users"]:
                    db["users"][target_uid] = {"username": "Unknown", "balance": 0.0, "time": time.time()}
                db["users"][target_uid]["balance"] += amount
                save_data()
                del user_states[chat_id]
                del temp_data[chat_id]
                send_msg(chat_id, f"✅ Balance updated!", reply_markup=main_kb(sender_id))
            except ValueError:
                send_msg(chat_id, "❌ Sothik number likhun:")
            return

        elif state == "adm_broadcast":
            del user_states[chat_id]
            send_msg(chat_id, "🚀 Broadcast shuru hocche...")
            count = 0
            for u_id in db.get("users", {}).keys():
                res = api_call("copyMessage", {"chat_id": u_id, "from_chat_id": chat_id, "message_id": msg["message_id"]})
                if res.get("ok"): count += 1
                time.sleep(0.03)
            send_msg(chat_id, f"✅ Broadcast Complete! ({count} users reached)", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_add_admin" and text:
            del user_states[chat_id]
            if text.isdigit():
                aid = int(text)
                if aid not in db["admins"]:
                    db["admins"].append(aid)
                    save_data()
                    send_msg(chat_id, f"✅ Admin added!", reply_markup=main_kb(sender_id))
            return

        elif state == "user_wait_qty":
            if not text.isdigit():
                send_msg(chat_id, "❌ Shudhu valid number pathan:")
                return
            qty = int(text)
            cat = temp_data[chat_id]["category"]
            stock = len(db["proxies"].get(cat, []))
            if qty > stock:
                send_msg(chat_id, f"⚠️ Stock insufficient! Current stock: {stock}")
                return
            total_amt = qty * db["proxies"][cat][0]["price"]
            temp_data[chat_id]["qty"] = qty
            temp_data[chat_id]["total"] = total_amt
            pay_kb = {"inline_keyboard": [[{"text": "💰 Wallet Balance", "callback_data": "pay_balance"}], [{"text": "🟢 bKash", "callback_data": "pay_bkash"}], [{"text": "🟡 Binance", "callback_data": "pay_binance"}]]}
            send_msg(chat_id, f"💳 Total: <b>{total_amt}</b>\nPayment method select korun:", reply_markup=pay_kb)
            return

        elif state == "user_wait_trx":
            temp_data[chat_id]["trx"] = text
            user_states[chat_id] = "user_wait_screenshot"
            send_msg(chat_id, f"📤 Payment-er screenshot upload korun:", reply_markup=cancel_kb())
            return

        elif state == "adm_wait_vpn_details" and is_admin(chat_id):
            order_id = temp_data[chat_id]["deliver_order_id"]
            load_data()
            order = db.get("orders", {}).get(order_id)
            if order:
                order["status"] = "delivered"
                save_data()
                send_msg(order["user_id"], f"✅ <b>VPN Order Delivered!</b>\n\n🔑 <b>Details:</b>\n{text}")
                send_msg(chat_id, f"✅ VPN details delivered!", reply_markup=main_kb(sender_id))
                
                admin_msgs = order.get("admin_msgs", {})
                for adm_id, adm_msg_id in admin_msgs.items():
                    try:
                        api_call("editMessageCaption", {
                            "chat_id": int(adm_id),
                            "message_id": adm_msg_id,
                            "caption": f"✅ <b>VPN Order Delivered Successfully!</b>\n🆔 ID: <code>{order_id}</code>",
                            "parse_mode": "HTML",
                            "reply_markup": {"inline_keyboard": []}
                        })
                    except Exception:
                        pass
            del user_states[chat_id]
            del temp_data[chat_id]
            return

    if "photo" in msg and chat_id in user_states:
        state = user_states[chat_id]
        photo_id = msg["photo"][-1]["file_id"]
        if state == "dep_wait_screenshot":
            data = temp_data[chat_id]
            dep_id = f"DEP-{int(time.time())}"
            if "deposits" not in db: db["deposits"] = {}
            db["deposits"][dep_id] = {"user_id": chat_id, "username": username, "amount": data["dep_amount"], "method": data["dep_method"], "trx": data["dep_trx"], "status": "pending"}
            save_data()
            for adm in db.get("admins", [OWNER_ID]):
                api_call("sendPhoto", {"chat_id": adm, "photo": photo_id, "caption": f"🔔 <b>Deposit Request!</b>\nID: {dep_id}\nUser: @{username}\nAmount: {data['dep_amount']}\nTrx: {data['dep_trx']}", "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[{"text": "✅ Approve", "callback_data": f"dep_app_{dep_id}"}, {"text": "❌ Reject", "callback_data": f"dep_rej_{dep_id}"}]]}})
            send_msg(chat_id, f"✅ Deposit request submitted!", reply_markup=main_kb(sender_id))
            del user_states[chat_id]
            del temp_data[chat_id]
            return
        elif state == "vpn_wait_screenshot":
            data = temp_data[chat_id]
            order_id = f"VPN-{int(time.time())}"
            if "orders" not in db: db["orders"] = {}
            db["orders"][order_id] = {"type": "vpn", "user_id": chat_id, "username": username, "vpn_name": data["vpn_name"], "total": data["vpn_price"], "method": "Manual", "trx": data["vpn_trx"], "status": "pending"}
            save_data()
            for adm in db.get("admins", [OWNER_ID]):
                res_msg = api_call("sendPhoto", {"chat_id": adm, "photo": photo_id, "caption": f"🔔 <b>VPN Order!</b>\nID: {order_id}\nUser: @{username}\nVPN: {data['vpn_name']}\nPrice: {data['vpn_price']}", "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[{"text": "📤 Send Details", "callback_data": f"vpn_deliver_{order_id}"}, {"text": "❌ Reject", "callback_data": f"ord_rej_{order_id}"}]]}})
                if res_msg.get("ok"):
                    if "admin_msgs" not in db["orders"][order_id]: db["orders"][order_id]["admin_msgs"] = {}
                    db["orders"][order_id]["admin_msgs"][str(adm)] = res_msg["result"]["message_id"]
            save_data()
            send_msg(chat_id, f"✅ VPN order submitted!", reply_markup=main_kb(sender_id))
            del user_states[chat_id]
            del temp_data[chat_id]
            return
        elif state == "user_wait_screenshot":
            data = temp_data[chat_id]
            order_id = f"ORD-{int(time.time())}"
            if "orders" not in db: db["orders"] = {}
            db["orders"][order_id] = {"type": "proxy", "user_id": chat_id, "username": username, "category": data["category"], "qty": data["qty"], "total": data["total"], "method": data["method"], "trx": data["trx"], "status": "pending"}
            save_data()
            for adm in db.get("admins", [OWNER_ID]):
                api_call("sendPhoto", {"chat_id": adm, "photo": photo_id, "caption": f"🔔 <b>Proxy Order!</b>\nID: {order_id}\nUser: @{username}\nCategory: {data['category']} | Qty: {data['qty']}", "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[{"text": "✅ Approve", "callback_data": f"ord_app_{order_id}"}, {"text": "❌ Reject", "callback_data": f"ord_rej_{order_id}"}]]}})
            send_msg(chat_id, f"✅ Proxy order submitted!", reply_markup=main_kb(sender_id))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

    if text.startswith("/start"):
        send_msg(chat_id, f"👋 <b>Welcome!</b>", reply_markup=main_kb(sender_id))
    elif "🛒 Buy Proxies" in text:
        proxies = db.get("proxies", {})
        if not proxies:
            send_msg(chat_id, f"❌ Proxy Stock empty!")
            return
        kb = [[{"text": f"🌐 {cat} — {items[0]['price']} ({len(items)} left)", "callback_data": f"buycat_{cat}"}] for cat, items in proxies.items() if items]
        send_msg(chat_id, f"🌐 <b>Proxy Categories:</b>", reply_markup={"inline_keyboard": kb})
    elif "🔒 Buy VPN" in text:
        vpn_plans = db.get("vpn_plans", {})
        if not vpn_plans:
            send_msg(chat_id, f"❌ Kono VPN plan available nei!")
            return
        kb = [[{"text": f"🔒 {name} — Price: {info['price']} ({info['stock']} left)", "callback_data": f"buyvpn_{name}"}] for name, info in vpn_plans.items()]
        send_msg(chat_id, f"🔒 <b>Available VPN Plans:</b>", reply_markup={"inline_keyboard": kb})
    elif "💰 Deposit Balance" in text:
        user_states[chat_id] = "dep_wait_amount"
        send_msg(chat_id, f"💰 Koto taka deposit korte chan sankhay likhe pathan:", reply_markup=cancel_kb())
    elif "📊 Order History" in text:
        my_orders = [o for o in db.get("orders", {}).values() if o["user_id"] == chat_id]
        if not my_orders:
            send_msg(chat_id, "📜 No order history.")
            return
        txt = "📊 <b>Your Orders:</b>\n\n" + "".join([f"📦 {o.get('category', o.get('vpn_name'))} | Total: {o['total']} | Status: <b>{o['status'].upper()}</b>\n" for o in my_orders[-5:]])
        send_msg(chat_id, txt)
    elif "👤 My Profile" in text:
        bal = db.get("users", {}).get(str(sender_id), {}).get("balance", 0.0)
        send_msg(chat_id, f"👤 ID: <code>{sender_id}</code>\n💰 Balance: <b>{bal}</b>")
    elif "📞 Support" in text:
        send_msg(chat_id, f"🎧 Support: @{db.get('settings', {}).get('support', 'anik2000')}")
    elif "🛠 Admin Panel" in text and is_admin(sender_id):
        send_msg(chat_id, f"📊 <b>Admin Control Console</b>", reply_markup=admin_kb())

# ================= Callback Handler =================
def handle_callback(call):
    chat_id = call["message"]["chat"]["id"]
    from_user_id = call.get("from", {}).get("id", chat_id)
    msg_id = call["message"]["message_id"]
    data = call.get("data", "")
    api_call("answerCallbackQuery", {"callback_query_id": call["id"]})

    if data == "close":
        delete_msg(chat_id, msg_id)
    elif data == "cancel_state":
        if chat_id in user_states: del user_states[chat_id]
        if chat_id in temp_data: del temp_data[chat_id]
        delete_msg(chat_id, msg_id)
        send_msg(chat_id, "Cancelled.", reply_markup=main_kb(from_user_id))

    elif data == "dep_pay_bkash" or data == "dep_pay_binance":
        amt = temp_data[chat_id]["dep_amount"]
        method = "bKash" if "bkash" in data else "Binance"
        temp_data[chat_id]["dep_method"] = method
        user_states[chat_id] = "dep_wait_trx"
        edit_msg(chat_id, msg_id, f"💳 {method} Amount: <b>{amt}</b>\nTrxID pathan:", reply_markup=cancel_kb())

    elif data.startswith("dep_app_") and is_admin(from_user_id):
        dep_id = data.replace("dep_app_", "")
        load_data()
        dep = db.get("deposits", {}).get(dep_id)
        if dep and dep["status"] == "pending":
            u_id = str(dep["user_id"])
            if u_id not in db["users"]: db["users"][u_id] = {"balance": 0.0}
            db["users"][u_id]["balance"] += dep["amount"]
            dep["status"] = "approved"
            save_data()
            send_msg(int(u_id), f"✅ Deposit Approved! Balance added: {dep['amount']}")
            edit_msg(chat_id, msg_id, f"✅ Deposit Approved!")

    elif data.startswith("dep_rej_") and is_admin(from_user_id):
        dep_id = data.replace("dep_rej_", "")
        load_data()
        if dep_id in db.get("deposits", {}):
            db["deposits"][dep_id]["status"] = "rejected"
            save_data()
            send_msg(db["deposits"][dep_id]["user_id"], "❌ Deposit rejected.")
            edit_msg(chat_id, msg_id, "❌ Deposit Rejected.")

    elif data.startswith("buyvpn_"):
        vpn_name = data.replace("buyvpn_", "")
        v_info = db.get("vpn_plans", {}).get(vpn_name)
        if not v_info or v_info["stock"] <= 0:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Stock out!", "show_alert": True})
            return
        temp_data[chat_id] = {"vpn_name": vpn_name, "vpn_price": v_info["price"]}
        pay_kb = {"inline_keyboard": [[{"text": "💰 Pay from Wallet", "callback_data": "pay_vpn_balance"}], [{"text": "🟢 Manual Payment", "callback_data": "pay_vpn_manual"}]]}
        edit_msg(chat_id, msg_id, f"🔒 <b>{vpn_name}</b>\nPrice: <b>{v_info['price']}</b>\nSelect payment method:", reply_markup=pay_kb)

    elif data == "pay_vpn_balance":
        if chat_id not in temp_data:
            edit_msg(chat_id, msg_id, "❌ Session expired. Please select VPN again.")
            return
        v_name = temp_data[chat_id]["vpn_name"]
        v_price = temp_data[chat_id]["vpn_price"]
        u_key = str(chat_id)
        bal = db.get("users", {}).get(u_key, {}).get("balance", 0.0)
        if bal < v_price:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Insufficient balance!", "show_alert": True})
            return
        
        # Check stock again
        v_info = db.get("vpn_plans", {}).get(v_name)
        if not v_info or v_info["stock"] <= 0:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Stock out!", "show_alert": True})
            return

        db["users"][u_key]["balance"] -= v_price
        db["vpn_plans"][v_name]["stock"] -= 1
        order_id = f"VPN-{int(time.time())}"
        if "orders" not in db: db["orders"] = {}
        db["orders"][order_id] = {"type": "vpn", "user_id": chat_id, "username": username, "vpn_name": v_name, "total": v_price, "method": "Wallet", "status": "pending_admin_delivery"}
        save_data()

        for adm in db.get("admins", [OWNER_ID]):
            res_msg = api_call("sendMessage", {"chat_id": adm, "text": f"🔔 <b>VPN Order (Wallet)!</b>\nID: {order_id}\nUser: @{username}\nVPN: {v_name}", "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[{"text": "📤 Send Details", "callback_data": f"vpn_deliver_{order_id}"}]]}})
            if res_msg.get("ok"):
                if "admin_msgs" not in db["orders"][order_id]: db["orders"][order_id]["admin_msgs"] = {}
                db["orders"][order_id]["admin_msgs"][str(adm)] = res_msg["result"]["message_id"]
        save_data()

        edit_msg(chat_id, msg_id, f"✅ Order successful! Admin details pathiye dibe.")
        send_msg(chat_id, "Main menu:", reply_markup=main_kb(chat_id))
        del temp_data[chat_id]

    elif data == "pay_vpn_manual":
        if chat_id not in temp_data: return
        user_states[chat_id] = "vpn_wait_trx"
        edit_msg(chat_id, msg_id, f"💳 bKash/Binance TrxID pathan:", reply_markup=cancel_kb())

    elif data.startswith("vpn_deliver_") and is_admin(from_user_id):
        order_id = data.replace("vpn_deliver_", "")
        user_states[chat_id] = "adm_wait_vpn_details"
        temp_data[chat_id] = {"deliver_order_id": order_id}
        edit_msg(chat_id, msg_id, f"📥 Order ID <code>{order_id}</code> er jonno <b>VPN Details</b> likhe pathan:")

    elif data.startswith("buycat_"):
        cat = data.replace("buycat_", "")
        stock = len(db["proxies"].get(cat, []))
        if stock == 0: return
        temp_data[chat_id] = {"category": cat}
        user_states[chat_id] = "user_wait_qty"
        edit_msg(chat_id, msg_id, f"🌐 <b>{cat}</b> (Stock: {stock})\nKoto gulo proxy kinte chan?", reply_markup=cancel_kb())

    elif data == "pay_balance":
        if chat_id not in temp_data: return
        total = temp_data[chat_id]["total"]
        cat = temp_data[chat_id]["category"]
        qty = temp_data[chat_id]["qty"]
        u_key = str(chat_id)
        bal = db.get("users", {}).get(u_key, {}).get("balance", 0.0)
        if bal < total:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Insufficient balance!", "show_alert": True})
            return
        proxies_list = db["proxies"].get(cat, [])
        if len(proxies_list) < qty:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Stock insufficient!", "show_alert": True})
            return
        db["users"][u_key]["balance"] -= total
        assigned = proxies_list[:qty]
        db["proxies"][cat] = proxies_list[qty:]
        order_id = f"ORD-{int(time.time())}"
        if "orders" not in db: db["orders"] = {}
        db["orders"][order_id] = {"type": "proxy", "user_id": chat_id, "username": username, "category": cat, "qty": qty, "total": total, "method": "Wallet", "status": "approved"}
        save_data()
        
        file_path = f"{order_id}.txt"
        with open(file_path, "w", encoding="utf-8") as f: f.write("\n".join([p["proxy"] for p in assigned]))
        with open(file_path, "rb") as doc_file:
            session.post(f"{BASE_URL}/sendDocument", data={"chat_id": chat_id, "caption": f"✅ Proxies ({qty} pcs):"}, files={"document": doc_file})
        if os.path.exists(file_path): os.remove(file_path)
        
        edit_msg(chat_id, msg_id, f"✅ Order Successful!")
        send_msg(chat_id, "Main menu:", reply_markup=main_kb(chat_id))
        del temp_data[chat_id]

    elif data == "pay_bkash" or data == "pay_binance":
        if chat_id not in temp_data: return
        method = "bKash" if "bkash" in data else "Binance"
        temp_data[chat_id]["method"] = method
        user_states[chat_id] = "user_wait_trx"
        edit_msg(chat_id, msg_id, f"💳 {method} TrxID pathan:", reply_markup=cancel_kb())

    elif data.startswith("ord_app_") and is_admin(from_user_id):
        order_id = data.replace("ord_app_", "")
        load_data()
        order = db.get("orders", {}).get(order_id)
        if order:
            order["status"] = "approved"
            save_data()
            send_msg(order["user_id"], f"✅ Order approved!")
            edit_msg(chat_id, msg_id, f"✅ Approved.")

    elif data.startswith("ord_rej_") and is_admin(from_user_id):
        order_id = data.replace("ord_rej_", "")
        load_data()
        order = db.get("orders", {}).get(order_id)
        if order:
            order["status"] = "rejected"
            save_data()
            send_msg(order["user_id"], f"❌ Order rejected.")
            edit_msg(chat_id, msg_id, f"❌ Rejected.")

    elif is_admin(from_user_id):
        if data == "adm_set_supabase":
            user_states[chat_id] = "adm_set_supabase_url"
            edit_msg(chat_id, msg_id, "🔗 Supabase Project URL likhe pathan:", reply_markup=cancel_kb())
        elif data == "adm_add_proxy":
            user_states[chat_id] = "adm_wait_cat"
            edit_msg(chat_id, msg_id, "📌 Category name likhun:", reply_markup=cancel_kb())
        elif data == "adm_del_proxy":
            proxies = db.get("proxies", {})
            if not proxies:
                edit_msg(chat_id, msg_id, "No stock.", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "admin_main"}]]})
                return
            kb = [[{"text": f"Delete: {cat}", "callback_data": f"delcat_{cat}"}] for cat in proxies.keys()]
            kb.append([{"text": "Back", "callback_data": "admin_main"}])
            edit_msg(chat_id, msg_id, "Select category:", reply_markup={"inline_keyboard": kb})
        elif data.startswith("delcat_"):
            cat = data.replace("delcat_", "")
            if cat in db["proxies"]:
                del db["proxies"][cat]
                save_data()
            edit_msg(chat_id, msg_id, f"✅ Deleted category: {cat}", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "admin_main"}]]})
        elif data == "adm_add_vpn":
            user_states[chat_id] = "adm_wait_vpn_name"
            edit_msg(chat_id, msg_id, "📌 VPN Name likhun:", reply_markup=cancel_kb())
        elif data == "adm_manage_vpn":
            vpn_plans = db.get("vpn_plans", {})
            if not vpn_plans:
                edit_msg(chat_id, msg_id, "Kono VPN plan nei.", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "admin_main"}]]})
                return
            kb = [[{"text": f"{name} (Stock: {info['stock']})", "callback_data": "none"}, {"text": "Edit Stock", "callback_data": f"edivpn_{name}"}, {"text": "Del", "callback_data": f"delvpn_{name}"}] for name, info in vpn_plans.items()]
            kb.append([{"text": "Back", "callback_data": "admin_main"}])
            edit_msg(chat_id, msg_id, "🛠 Manage VPN:", reply_markup={"inline_keyboard": kb})
        elif data.startswith("edivpn_"):
            user_states[chat_id] = "adm_edit_vpn_stock_val"
            temp_data[chat_id] = {"edit_vpn_name": data.replace("edivpn_", "")}
            edit_msg(chat_id, msg_id, "✏️ Notun stock number pathan:", reply_markup=cancel_kb())
        elif data.startswith("delvpn_"):
            v_name = data.replace("delvpn_", "")
            if v_name in db["vpn_plans"]:
                del db["vpn_plans"][v_name]
                save_data()
            edit_msg(chat_id, msg_id, f"✅ Deleted VPN!", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "adm_manage_vpn"}]]})
        elif data == "adm_balance_menu":
            user_states[chat_id] = "adm_wait_user_id_for_balance"
            edit_msg(chat_id, msg_id, "👤 User ID pathan:", reply_markup=cancel_kb())
        elif data == "adm_broadcast":
            user_states[chat_id] = "adm_broadcast"
            edit_msg(chat_id, msg_id, "📢 Broadcast message pathan:", reply_markup=cancel_kb())
        elif data == "adm_manage_admins":
            adms = db.get("admins", [OWNER_ID])
            kb = [[{"text": f"👤 {aid}", "callback_data": "none"}] for aid in adms]
            kb.append([{"text": "➕ Add Admin", "callback_data": "adm_add_admin_btn"}])
            kb.append([{"text": "Back", "callback_data": "admin_main"}])
            edit_msg(chat_id, msg_id, "👑 Admins:", reply_markup={"inline_keyboard": kb})
        elif data == "adm_add_admin_btn":
            user_states[chat_id] = "adm_add_admin"
            edit_msg(chat_id, msg_id, "Notun Admin ID pathan:", reply_markup=cancel_kb())
        elif data == "adm_stats":
            edit_msg(chat_id, msg_id, f"📊 Stats:\nUsers: {len(db.get('users', {}))}\nProxies: {sum([len(v) for v in db.get('proxies', {}).values()])}", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "admin_main"}]]})
        elif data == "admin_main":
            edit_msg(chat_id, msg_id, "📊 Admin Control Console", reply_markup=admin_kb())

def main():
    offset = None
    executor = ThreadPoolExecutor(max_workers=20)
    print("🚀 Bot is running with Fully Fixed VPN Wallet & Delivery flow...")
    while True:
        try:
            updates = api_call("getUpdates", {"timeout": 30, "offset": offset})
            if updates and "result" in updates:
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update:
                        executor.submit(handle_message, update["message"])
                    elif "callback_query" in update:
                        executor.submit(handle_callback, update["callback_query"])
        except Exception:
            time.sleep(2)

if __name__ == "__main__":
     main()
