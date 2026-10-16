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
OWNER_ID_STR = "903018274"

if not BOT_TOKEN or not OWNER_ID_STR:
    print("❌ Error: Please configure BOT_TOKEN and OWNER_ID inside your .env file!")
    exit(1)

OWNER_ID = int(OWNER_ID_STR)

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_URL = f"https://api.telegram.org/file/bot{BOT_TOKEN}/"

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
DB_FILE = os.path.join(CURRENT_DIR, "proxy_bot_data.json")

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
        "support": "anik2000"
    }
}

user_states = {}
temp_data = {}

def load_data():
    global db
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    db.update(data)
        except Exception:
            pass
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
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving data: {e}")

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
        
        if state == "adm_wait_cat" and text:
            temp_data[chat_id] = {"category": text}
            user_states[chat_id] = "adm_wait_price"
            send_msg(chat_id, f"📌 Category: <b>{text}</b>\n\nEkhon ei category-er <b>per proxy price</b> koto hobe ta likhe pathan:")
            return

        elif state == "adm_wait_price" and text:
            try:
                price = float(text)
                temp_data[chat_id]["price"] = price
                user_states[chat_id] = "adm_wait_proxies"
                send_msg(chat_id, f"📤 Ekhon proxy gulo pathan (.txt file upload ba text paste korun):", reply_markup=cancel_kb())
            except ValueError:
                send_msg(chat_id, "❌ Invalid price! Shudhu number pathan:")
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
                            content = None
                            for enc in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
                                try:
                                    content = file_res.content.decode(enc)
                                    break
                                except UnicodeDecodeError:
                                    continue
                            if content: raw_lines = content.splitlines()
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
            send_msg(chat_id, f"✅ Success! <b>{added}</b> proxies added under <b>{cat}</b>.", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_wait_vpn_name" and text:
            temp_data[chat_id] = {"vpn_name": text}
            user_states[chat_id] = "adm_wait_vpn_price"
            send_msg(chat_id, f"📌 VPN Name: <b>{text}</b>\n\nEkhon ei VPN-er <b>Price</b> koto hobe ta likhe pathan:", reply_markup=cancel_kb())
            return

        elif state == "adm_wait_vpn_price" and text:
            try:
                price = float(text)
                temp_data[chat_id]["vpn_price"] = price
                user_states[chat_id] = "adm_wait_vpn_stock"
                send_msg(chat_id, f"📦 Ei VPN-er <b>Stock (koiti available ase)</b> sankhay likhe pathan (e.g. 10):", reply_markup=cancel_kb())
            except ValueError:
                send_msg(chat_id, "❌ Invalid price! Shudhu number pathan:")
            return

        elif state == "adm_wait_vpn_stock" and text:
            if not text.isdigit():
                send_msg(chat_id, "❌ Shudhu valid number pathan:")
                return
            stock = int(text)
            temp_data[chat_id]["vpn_stock"] = stock
            user_states[chat_id] = "adm_wait_vpn_details"
            send_msg(chat_id, f"📝 Ei VPN-er description ba details likhe pathan:", reply_markup=cancel_kb())
            return

        elif state == "adm_wait_vpn_details" and text:
            v_data = temp_data[chat_id]
            v_name = v_data["vpn_name"]
            v_price = v_data["vpn_price"]
            v_stock = v_data["vpn_stock"]
            v_desc = text

            if "vpn_plans" not in db: db["vpn_plans"] = {}
            db["vpn_plans"][v_name] = {"price": v_price, "stock": v_stock, "desc": v_desc}
            save_data()

            del user_states[chat_id]
            del temp_data[chat_id]
            send_msg(chat_id, f"✅ Success! VPN Plan <b>{v_name}</b> added successfully.", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_edit_vpn_stock_val" and text:
            if not text.isdigit():
                send_msg(chat_id, "❌ Shudhu valid number pathan:")
                return
            new_stock = int(text)
            v_name = temp_data[chat_id]["edit_vpn_name"]
            if v_name in db["vpn_plans"]:
                db["vpn_plans"][v_name]["stock"] = new_stock
                save_data()
                send_msg(chat_id, f"✅ VPN <b>{v_name}</b> stock updated to <b>{new_stock}</b>!", reply_markup=main_kb(sender_id))
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
                
                pay_kb = {
                    "inline_keyboard": [
                        [{"text": "🟢 bKash (Send Money)", "callback_data": "dep_pay_bkash"}],
                        [{"text": "🟡 Binance Pay", "callback_data": "dep_pay_binance"}],
                        [{"text": "Cancel", "callback_data": "cancel_state", "style": "danger"}]
                    ]
                }
                send_msg(chat_id, f"💳 Deposit Amount: <b>{amount}</b>\n\nPayment Method select korun:", reply_markup=pay_kb)
                del user_states[chat_id]
            except ValueError:
                send_msg(chat_id, "❌ Shudhu number pathan:")
            return

        elif state == "dep_wait_trx":
            temp_data[chat_id]["dep_trx"] = text
            user_states[chat_id] = "dep_wait_screenshot"
            send_msg(chat_id, f"📤 Ekhon payment-er <b>Screenshot (Photo)</b> upload korun:", reply_markup=cancel_kb())
            return

        elif state == "vpn_wait_trx":
            temp_data[chat_id]["vpn_trx"] = text
            user_states[chat_id] = "vpn_wait_screenshot"
            send_msg(chat_id, f"📤 Ekhon payment-er <b>Screenshot (Photo)</b> upload korun:", reply_markup=cancel_kb())
            return

        elif state == "adm_wait_user_id_for_balance" and text:
            if not text.isdigit():
                send_msg(chat_id, "❌ Valid User ID din:", reply_markup=cancel_kb())
                return
            target_uid = text.strip()
            temp_data[chat_id] = {"target_uid": target_uid}
            user_states[chat_id] = "adm_wait_balance_amount"
            send_msg(chat_id, f"💵 User ID: <code>{target_uid}</code>\n\nKoto taka add ba katte chan ta likhun:", reply_markup=cancel_kb())
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
                current_bal = db["users"][target_uid]["balance"]
                send_msg(chat_id, f"✅ Balance updated!\n👤 User ID: <code>{target_uid}</code>\n💰 New Balance: <b>{current_bal}</b>", reply_markup=main_kb(sender_id))
            except ValueError:
                send_msg(chat_id, "❌ Sothik number likhun:", reply_markup=cancel_kb())
            return

        elif state == "adm_broadcast":
            del user_states[chat_id]
            send_msg(chat_id, "🚀 Broadcast shuru hocche...")
            count = 0
            for u_id in db.get("users", {}).keys():
                res = api_call("copyMessage", {"chat_id": u_id, "from_chat_id": chat_id, "message_id": msg["message_id"]})
                if res.get("ok"): count += 1
                time.sleep(0.03)
            send_msg(chat_id, f"✅ <b>Broadcast Complete!</b> ({count} users reached)", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_add_admin" and text:
            del user_states[chat_id]
            if text.isdigit():
                aid = int(text)
                if aid not in db["admins"]:
                    db["admins"].append(aid)
                    save_data()
                    send_msg(chat_id, f"✅ Admin ID <code>{aid}</code> added!", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_set_limits" and text:
            try:
                parts = text.split(",")
                db["settings"]["min_purchase"] = int(parts[0].strip())
                db["settings"]["max_purchase"] = int(parts[1].strip())
                save_data()
                del user_states[chat_id]
                send_msg(chat_id, f"✅ Limits updated!", reply_markup=main_kb(sender_id))
            except:
                send_msg(chat_id, "❌ Sothik format-e din (e.g. 1,20):", reply_markup=cancel_kb())
            return

        elif state == "adm_set_bkash" and text:
            db["settings"]["bkash"] = text
            save_data()
            del user_states[chat_id]
            send_msg(chat_id, f"✅ bKash number updated!", reply_markup=main_kb(sender_id))
            return

        elif state == "adm_set_binance" and text:
            db["settings"]["binance"] = text
            save_data()
            del user_states[chat_id]
            send_msg(chat_id, f"✅ Binance ID updated!", reply_markup=main_kb(sender_id))
            return

        elif state == "user_wait_qty":
            if not text.isdigit():
                send_msg(chat_id, "❌ Shudhu valid number pathan:")
                return
            qty = int(text)
            cat = temp_data[chat_id]["category"]
            stock = len(db["proxies"].get(cat, []))
            if qty > stock:
                send_msg(chat_id, f"⚠️ Stock insufficient! Current stock is <b>{stock}</b>.")
                return
            price_per = db["proxies"][cat][0]["price"]
            total_amt = qty * price_per
            temp_data[chat_id]["qty"] = qty
            temp_data[chat_id]["total"] = total_amt

            pay_kb = {
                "inline_keyboard": [
                    [{"text": "💰 Pay from Account Balance", "callback_data": "pay_balance"}],
                    [{"text": "🟢 bKash (Send Money)", "callback_data": "pay_bkash"}],
                    [{"text": "🟡 Binance Pay", "callback_data": "pay_binance"}],
                    [{"text": "Cancel", "callback_data": "cancel_state", "style": "danger"}]
                ]
            }
            send_msg(chat_id, f"💳 <b>Order Summary:</b>\n\nCategory: <b>{cat}</b>\nQuantity: <b>{qty}</b>\nTotal: <b>{total_amt}</b>\n\nPayment method select korun:", reply_markup=pay_kb)
            return

        elif state == "user_wait_trx":
            temp_data[chat_id]["trx"] = text
            user_states[chat_id] = "user_wait_screenshot"
            send_msg(chat_id, f"📤 Ekhon payment-er <b>Screenshot (Photo)</b> upload korun:", reply_markup=cancel_kb())
            return

        # --- Admin Sending VPN Details (FIXED & FULLY FUNCTIONAL) ---
        elif state == "adm_wait_vpn_details" and is_admin(chat_id):
            order_id = temp_data[chat_id]["deliver_order_id"]
            vpn_details = text
            load_data()
            order = db.get("orders", {}).get(order_id)
            if order:
                order["status"] = "delivered"
                save_data()
                user_target = order["user_id"]
                
                # Send VPN details to user
                send_msg(user_target, f"✅ <b>Apnar VPN Order Approved & Delivered!</b>\n\n📦 Order ID: <code>{order_id}</code>\n🔒 VPN Plan: <b>{order['vpn_name']}</b>\n\n🔑 <b>VPN Details:</b>\n{vpn_details}")
                send_msg(chat_id, f"✅ VPN details successfully delivered to user for order <code>{order_id}</code>!", reply_markup=main_kb(chat_id))

                # Update Admin message caption
                admin_msgs = order.get("admin_msgs", {})
                for adm_id, adm_msg_id in admin_msgs.items():
                    try:
                        api_call("editMessageCaption", {
                            "chat_id": int(adm_id),
                            "message_id": adm_msg_id,
                            "caption": f"✅ <b>VPN Order Delivered Successfully!</b>\n🆔 Order ID: <code>{order_id}</code>",
                            "parse_mode": "HTML",
                            "reply_markup": {"inline_keyboard": []}
                        })
                    except Exception:
                        pass
            else:
                send_msg(chat_id, "❌ Order paoa jayni!")

            del user_states[chat_id]
            del temp_data[chat_id]
            return

    # Handle Photo for Deposit
    if "photo" in msg and chat_id in user_states and user_states[chat_id] == "dep_wait_screenshot":
        photo_id = msg["photo"][-1]["file_id"]
        data = temp_data[chat_id]
        dep_id = f"DEP-{int(time.time())}"
        if "deposits" not in db: db["deposits"] = {}
        db["deposits"][dep_id] = {
            "user_id": chat_id, "username": username,
            "amount": data["dep_amount"], "method": data["dep_method"],
            "trx": data["dep_trx"], "screenshot": photo_id, "status": "pending"
        }
        save_data()

        admin_caption = f"""🔔 <b>New Balance Deposit Request!</b>
🆔 ID: <code>{dep_id}</code>
👤 User: @{username} (<code>{chat_id}</code>)
💰 Amount: <b>{data['dep_amount']}</b>
💳 Method: <b>{data['dep_method']}</b>
📝 TrxID: <code>{data['dep_trx']}</code>"""

        admin_kb_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Approve Deposit", "callback_data": f"dep_app_{dep_id}", "style": "success"},
                    {"text": "❌ Reject", "callback_data": f"dep_rej_{dep_id}", "style": "danger"}
                ]
            ]
        }

        for adm in db.get("admins", [OWNER_ID]):
            res_msg = api_call("sendPhoto", {"chat_id": adm, "photo": photo_id, "caption": admin_caption, "parse_mode": "HTML", "reply_markup": admin_kb_markup})
            if res_msg.get("ok"):
                if "admin_msgs" not in db["deposits"][dep_id]: db["deposits"][dep_id]["admin_msgs"] = {}
                db["deposits"][dep_id]["admin_msgs"][str(adm)] = res_msg["result"]["message_id"]
        save_data()

        send_msg(chat_id, f"✅ Deposit request submitted successfully!", reply_markup=main_kb(sender_id))
        del user_states[chat_id]
        del temp_data[chat_id]
        return

    # Handle Photo for Manual VPN Order
    if "photo" in msg and chat_id in user_states and user_states[chat_id] == "vpn_wait_screenshot":
        photo_id = msg["photo"][-1]["file_id"]
        data = temp_data[chat_id]
        order_id = f"VPN-{int(time.time())}"
        if "orders" not in db: db["orders"] = {}
        db["orders"][order_id] = {
            "type": "vpn", "user_id": chat_id, "username": username,
            "vpn_name": data["vpn_name"], "total": data["vpn_price"],
            "method": "Manual", "trx": data["vpn_trx"], "screenshot": photo_id, "status": "pending"
        }
        save_data()

        admin_caption = f"""🔔 <b>New Manual VPN Order!</b>
🆔 ID: <code>{order_id}</code>
👤 User: @{username} (<code>{chat_id}</code>)
🔒 VPN: <b>{data['vpn_name']}</b> | Price: <b>{data['vpn_price']}</b> | TrxID: <code>{data['vpn_trx']}</code>"""

        admin_kb_markup = {"inline_keyboard": [[{"text": "📤 Send VPN Details", "callback_data": f"vpn_deliver_{order_id}", "style": "success"}, {"text": "❌ Reject", "callback_data": f"ord_rej_{order_id}", "style": "danger"}]]}

        for adm in db.get("admins", [OWNER_ID]):
            res_msg = api_call("sendPhoto", {"chat_id": adm, "photo": photo_id, "caption": admin_caption, "parse_mode": "HTML", "reply_markup": admin_kb_markup})
            if res_msg.get("ok"):
                if "admin_msgs" not in db["orders"][order_id]: db["orders"][order_id]["admin_msgs"] = {}
                db["orders"][order_id]["admin_msgs"][str(adm)] = res_msg["result"]["message_id"]
        save_data()

        send_msg(chat_id, f"✅ VPN order submitted successfully!", reply_markup=main_kb(sender_id))
        del user_states[chat_id]
        del temp_data[chat_id]
        return

    # Handle Photo for Proxy Order
    if "photo" in msg and chat_id in user_states and user_states[chat_id] == "user_wait_screenshot":
        photo_id = msg["photo"][-1]["file_id"]
        data = temp_data[chat_id]
        order_id = f"ORD-{int(time.time())}"
        if "orders" not in db: db["orders"] = {}
        db["orders"][order_id] = {
            "type": "proxy", "user_id": chat_id, "username": username,
            "category": data["category"], "qty": data["qty"], "total": data["total"],
            "method": data["method"], "trx": data["trx"], "screenshot": photo_id, "status": "pending"
        }
        save_data()

        admin_caption = f"""🔔 <b>New Proxy Order!</b>
🆔 ID: <code>{order_id}</code>
👤 User: @{username} (<code>{chat_id}</code>)
🌐 Category: <b>{data['category']}</b> | Qty: <b>{data['qty']}</b>
💰 Total: <b>{data['total']}</b> | TrxID: <code>{data['trx']}</code>"""

        admin_kb_markup = {"inline_keyboard": [[{"text": "✅ Approve", "callback_data": f"ord_app_{order_id}", "style": "success"}, {"text": "❌ Reject", "callback_data": f"ord_rej_{order_id}", "style": "danger"}]]}

        for adm in db.get("admins", [OWNER_ID]):
            res_msg = api_call("sendPhoto", {"chat_id": adm, "photo": photo_id, "caption": admin_caption, "parse_mode": "HTML", "reply_markup": admin_kb_markup})
            if res_msg.get("ok"):
                if "admin_msgs" not in db["orders"][order_id]: db["orders"][order_id]["admin_msgs"] = {}
                db["orders"][order_id]["admin_msgs"][str(adm)] = res_msg["result"]["message_id"]
        save_data()

        send_msg(chat_id, f"✅ Proxy order submitted successfully!", reply_markup=main_kb(sender_id))
        del user_states[chat_id]
        del temp_data[chat_id]
        return

    if text.startswith("/start"):
        send_msg(chat_id, f"👋 <b>Welcome to Bot!</b>", reply_markup=main_kb(sender_id))

    elif "🛒 Buy Proxies" in text:
        proxies = db.get("proxies", {})
        if not proxies:
            send_msg(chat_id, f"❌ Proxy Stock empty!")
            return
        kb = []
        for cat, items in proxies.items():
            if items:
                price = items[0]["price"]
                kb.append([{"text": f"🌐 {cat} — {price} ({len(items)} left)", "callback_data": f"buycat_{cat}"}])
        send_msg(chat_id, f"🌐 <b>Proxy Categories:</b>", reply_markup={"inline_keyboard": kb})

    elif "🔒 Buy VPN" in text:
        vpn_plans = db.get("vpn_plans", {})
        if not vpn_plans:
            send_msg(chat_id, f"❌ Kono VPN plan available nei!")
            return
        kb = []
        for vpn_name, info in vpn_plans.items():
            stock_status = f"({info['stock']} left)" if info['stock'] > 0 else "(Stock Out ❌)"
            kb.append([{"text": f"🔒 {vpn_name} — Price: {info['price']} {stock_status}", "callback_data": f"buyvpn_{vpn_name}"}])
        send_msg(chat_id, f"🔒 <b>Available VPN Plans:</b>", reply_markup={"inline_keyboard": kb})

    elif "💰 Deposit Balance" in text:
        user_states[chat_id] = "dep_wait_amount"
        send_msg(chat_id, f"💰 <b>Balance Deposit</b>\n\nAapni koto taka deposit korte chan? Taka sankhay likhe pathan:", reply_markup=cancel_kb())

    elif "📊 Order History" in text:
        orders = db.get("orders", {})
        my_orders = [o for o in orders.values() if o["user_id"] == chat_id]
        if not my_orders:
            send_msg(chat_id, "📜 No order history.")
            return
        txt = "📊 <b>Your Orders:</b>\n\n"
        for o in my_orders[-5:]:
            item_name = o.get('category', o.get('vpn_name', 'Item'))
            txt += f"📦 {item_name} | Total: {o['total']} | Status: <b>{o['status'].upper()}</b>\n"
        send_msg(chat_id, txt)

    elif "👤 My Profile" in text:
        user_data = db.get("users", {}).get(str(sender_id), {})
        balance = user_data.get("balance", 0.0)
        send_msg(chat_id, f"👤 ID: <code>{sender_id}</code>\nUser: @{username}\n💰 Balance: <b>{balance}</b>")

    elif "📞 Support" in text:
        sup_u = db.get("settings", {}).get("support", "anik2000")
        send_msg(chat_id, f"🎧 Support: @{sup_u}")

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

    # --- Deposit Callbacks ---
    elif data == "dep_pay_bkash":
        bkash_no = db.get("settings", {}).get("bkash", "017XXXXXXXX")
        amount = temp_data[chat_id]["dep_amount"]
        temp_data[chat_id]["dep_method"] = "bKash"
        user_states[chat_id] = "dep_wait_trx"
        edit_msg(chat_id, msg_id, f"💳 <b>bKash Send Money</b>\nAmount: <b>{amount} BDT</b>\nNumber: <code>{bkash_no}</code>\n\nTrxID ti pathan:", reply_markup=cancel_kb())

    elif data == "dep_pay_binance":
        binance_id = db.get("settings", {}).get("binance", "123456789")
        amount = temp_data[chat_id]["dep_amount"]
        temp_data[chat_id]["dep_method"] = "Binance Pay"
        user_states[chat_id] = "dep_wait_trx"
        edit_msg(chat_id, msg_id, f"🔶 <b>Binance Pay</b>\nAmount: <b>{amount} USD</b>\nBinance ID: <code>{binance_id}</code>\n\nTransaction ID pathan:", reply_markup=cancel_kb())

    elif data.startswith("dep_app_") and is_admin(from_user_id):
        dep_id = data.replace("dep_app_", "")
        load_data()
        dep = db.get("deposits", {}).get(dep_id)
        if not dep or dep["status"] != "pending": return
        user_target = dep["user_id"]
        amount = dep["amount"]

        if str(user_target) not in db["users"]:
            db["users"][str(user_target)] = {"username": dep["username"], "balance": 0.0, "time": time.time()}
        db["users"][str(user_target)]["balance"] += amount
        dep["status"] = "approved"
        save_data()

        send_msg(user_target, f"✅ <b>Deposit Approved!</b>\nApnar account-e <b>{amount}</b> balance add kora hoyeche.")
        edit_msg(chat_id, msg_id, f"✅ Deposit <code>{dep_id}</code> Approved Successfully!")

    elif data.startswith("dep_rej_") and is_admin(from_user_id):
        dep_id = data.replace("dep_rej_", "")
        load_data()
        dep = db.get("deposits", {}).get(dep_id)
        if not dep or dep["status"] != "pending": return
        dep["status"] = "rejected"
        save_data()
        send_msg(dep["user_id"], "❌ Apnar deposit request-ti reject kora hoyeche.")
        edit_msg(chat_id, msg_id, f"❌ Deposit <code>{dep_id}</code> Rejected.")

    # --- VPN Buy Callbacks ---
    elif data.startswith("buyvpn_"):
        vpn_name = data.replace("buyvpn_", "")
        v_info = db.get("vpn_plans", {}).get(vpn_name)
        if not v_info: return
        
        if v_info["stock"] <= 0:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Sorry, this VPN plan is currently out of stock!", "show_alert": True})
            return

        temp_data[chat_id] = {"vpn_name": vpn_name, "vpn_price": v_info["price"]}
        
        pay_kb = {
            "inline_keyboard": [
                [{"text": "💰 Pay from Account Balance", "callback_data": "pay_vpn_balance"}],
                [{"text": "🟢 bKash / Binance (Manual)", "callback_data": "pay_vpn_manual"}],
                [{"text": "Cancel", "callback_data": "cancel_state", "style": "danger"}]
            ]
        }
        edit_msg(chat_id, msg_id, f"🔒 <b>VPN Plan: {vpn_name}</b>\n📝 Details: {v_info['desc']}\n💰 Price: <b>{v_info['price']}</b>\n📦 Available Stock: <b>{v_info['stock']}</b>\n\nPayment method select korun:", reply_markup=pay_kb)

    elif data == "pay_vpn_balance":
        user_data = db.get("users", {}).get(str(chat_id), {})
        balance = user_data.get("balance", 0.0)
        
        if chat_id not in temp_data or "vpn_name" not in temp_data[chat_id]:
            edit_msg(chat_id, msg_id, "❌ Session expired or invalid selection. Please select VPN plan again from menu.")
            return

        v_name = temp_data[chat_id]["vpn_name"]
        v_price = temp_data[chat_id]["vpn_price"]
        v_info = db["vpn_plans"].get(v_name)

        if not v_info or v_info["stock"] <= 0:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Stock out!", "show_alert": True})
            return

        if balance < v_price:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Insufficient balance!", "show_alert": True})
            return

        db["users"][str(chat_id)]["balance"] -= v_price
        db["vpn_plans"][v_name]["stock"] -= 1

        order_id = f"VPN-{int(time.time())}"
        if "orders" not in db: db["orders"] = {}
        db["orders"][order_id] = {
            "type": "vpn", "user_id": chat_id, "username": username,
            "vpn_name": v_name, "total": v_price, "method": "Account Balance", "status": "pending_admin_delivery"
        }
        save_data()

        admin_caption = f"""🔔 <b>New VPN Order (Paid via Balance)!</b>
🆔 Order ID: <code>{order_id}</code>
👤 User: @{username} (<code>{chat_id}</code>)
🔒 VPN Plan: <b>{v_name}</b> | Paid: <b>{v_price}</b>"""

        admin_kb_markup = {"inline_keyboard": [[{"text": "📤 Send VPN Details to User", "callback_data": f"vpn_deliver_{order_id}", "style": "success"}]]}

        for adm in db.get("admins", [OWNER_ID]):
            res_msg = api_call("sendMessage", {"chat_id": adm, "text": admin_caption, "parse_mode": "HTML", "reply_markup": admin_kb_markup})
            if res_msg.get("ok"):
                if "admin_msgs" not in db["orders"][order_id]: db["orders"][order_id]["admin_msgs"] = {}
                db["orders"][order_id]["admin_msgs"][str(adm)] = res_msg["result"]["message_id"]
        save_data()

        edit_msg(chat_id, msg_id, f"✅ VPN Order <code>{order_id}</code> successful! Balance deducted: {v_price}.\nAdmin khub shighri VPN details pathiye dibe.")
        send_msg(chat_id, "Main menu:", reply_markup=main_kb(chat_id))
        if chat_id in user_states: del user_states[chat_id]
        if chat_id in temp_data: del temp_data[chat_id]

    elif data == "pay_vpn_manual":
        bkash_no = db.get("settings", {}).get("bkash", "017XXXXXXXX")
        if chat_id not in temp_data or "vpn_price" not in temp_data[chat_id]:
            edit_msg(chat_id, msg_id, "❌ Session expired.")
            return
        v_price = temp_data[chat_id]["vpn_price"]
        temp_data[chat_id]["method"] = "bKash/Binance"
        user_states[chat_id] = "vpn_wait_trx"
        edit_msg(chat_id, msg_id, f"💳 <b>VPN Payment</b>\nAmount: <b>{v_price}</b>\nbKash: <code>{bkash_no}</code>\n\nTrxID pathan:", reply_markup=cancel_kb())

    # --- Fixed VPN Deliver Callback ---
    elif data.startswith("vpn_deliver_") and is_admin(from_user_id):
        order_id = data.replace("vpn_deliver_", "")
        user_states[chat_id] = "adm_wait_vpn_details"
        temp_data[chat_id] = {"deliver_order_id": order_id}
        edit_msg(chat_id, msg_id, f"📥 Order ID <code>{order_id}</code> er jonno <b>VPN Details (Username, Password, Config)</b> likhe pathan:")

    # --- Proxy Buy Callbacks ---
    elif data.startswith("buycat_"):
        cat = data.replace("buycat_", "")
        stock = len(db["proxies"].get(cat, []))
        if stock == 0: return
        min_p = db.get("settings", {}).get("min_purchase", 1)
        max_p = db.get("settings", {}).get("max_purchase", 20)
        temp_data[chat_id] = {"category": cat}
        user_states[chat_id] = "user_wait_qty"
        edit_msg(chat_id, msg_id, f"🌐 <b>{cat}</b>\nStock: <b>{stock}</b>\nLimit: <b>{min_p} - {max_p}</b>\n\nKoto gulo proxy kinte chan?", reply_markup=cancel_kb())

    elif data == "pay_balance":
        user_data = db.get("users", {}).get(str(chat_id), {})
        balance = user_data.get("balance", 0.0)
        if chat_id not in temp_data: return
        total = temp_data[chat_id]["total"]
        cat = temp_data[chat_id]["category"]
        qty = temp_data[chat_id]["qty"]

        if balance < total:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Insufficient balance!", "show_alert": True})
            return

        available_proxies = db["proxies"].get(cat, [])
        if len(available_proxies) < qty:
            api_call("answerCallbackQuery", {"callback_query_id": call["id"], "text": "Stock insufficient!", "show_alert": True})
            return

        db["users"][str(chat_id)]["balance"] -= total
        assigned = available_proxies[:qty]
        db["proxies"][cat] = available_proxies[qty:]
        
        order_id = f"ORD-{int(time.time())}"
        if "orders" not in db: db["orders"] = {}
        db["orders"][order_id] = {
            "type": "proxy", "user_id": chat_id, "username": username,
            "category": cat, "qty": qty, "total": total, "method": "Account Balance", "trx": "Auto-Balance", "status": "approved"
        }
        save_data()

        proxy_text = "\n".join([p["proxy"] for p in assigned])
        file_path = f"{order_id}_proxies.txt"
        with open(file_path, "w", encoding="utf-8") as f: f.write(proxy_text)
        
        url = f"{BASE_URL}/sendDocument"
        with open(file_path, "rb") as doc_file:
            files = {"document": (f"{cat}_proxies.txt", doc_file)}
            payload = {"chat_id": chat_id, "caption": f"✅ <b>Proxies ({qty} pcs):</b>", "parse_mode": "HTML"}
            session.post(url, data=payload, files=files)
        if os.path.exists(file_path): os.remove(file_path)

        edit_msg(chat_id, msg_id, f"✅ Order <code>{order_id}</code> Successful!")
        send_msg(chat_id, "Main menu:", reply_markup=main_kb(chat_id))
        if chat_id in user_states: del user_states[chat_id]
        if chat_id in temp_data: del temp_data[chat_id]

    elif data == "pay_bkash":
        bkash_no = db.get("settings", {}).get("bkash", "017XXXXXXXX")
        if chat_id not in temp_data: return
        total = temp_data[chat_id]["total"]
        temp_data[chat_id]["method"] = "bKash"
        user_states[chat_id] = "user_wait_trx"
        edit_msg(chat_id, msg_id, f"💳 bKash Amount: <b>{total} BDT</b>\nNumber: <code>{bkash_no}</code>\n\nTrxID pathan:", reply_markup=cancel_kb())

    elif data == "pay_binance":
        binance_id = db.get("settings", {}).get("binance", "123456789")
        if chat_id not in temp_data: return
        total = temp_data[chat_id]["total"]
        temp_data[chat_id]["method"] = "Binance Pay"
        user_states[chat_id] = "user_wait_trx"
        edit_msg(chat_id, msg_id, f"🔶 Binance Pay Amount: <b>{total} USD</b>\nID: <code>{binance_id}</code>\n\nTrxID pathan:", reply_markup=cancel_kb())

    elif data.startswith("ord_app_") and is_admin(from_user_id):
        order_id = data.replace("ord_app_", "")
        load_data()
        order = db.get("orders", {}).get(order_id)
        if not order or order["status"] != "pending": return
        order["status"] = "approved"
        save_data()
        send_msg(order["user_id"], f"✅ Order <code>{order_id}</code> approved!")
        edit_msg(chat_id, msg_id, f"✅ Order Approved.")

    elif data.startswith("ord_rej_") and is_admin(from_user_id):
        order_id = data.replace("ord_rej_", "")
        load_data()
        order = db.get("orders", {}).get(order_id)
        if not order or order["status"] != "pending": return
        order["status"] = "rejected"
        save_data()
        send_msg(order["user_id"], f"❌ Order <code>{order_id}</code> rejected.")
        edit_msg(chat_id, msg_id, f"❌ Order Rejected.")

    # --- Admin Panel Management ---
    elif is_admin(from_user_id):
        if data == "adm_add_proxy":
            user_states[chat_id] = "adm_wait_cat"
            edit_msg(chat_id, msg_id, "📌 Category name likhun:", reply_markup=cancel_kb())

        elif data == "adm_del_proxy":
            proxies = db.get("proxies", {})
            if not proxies:
                edit_msg(chat_id, msg_id, "No stock.", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "admin_main"}]]})
                return
            kb = [[{"text": f"Delete: {cat} ({len(items)})", "callback_data": f"delcat_{cat}", "style": "danger"}] for cat, items in proxies.items()]
            kb.append([{"text": "Back", "callback_data": "admin_main"}])
            edit_msg(chat_id, msg_id, "Select category to delete:", reply_markup={"inline_keyboard": kb})

        elif data.startswith("delcat_"):
            cat = data.replace("delcat_", "")
            if cat in db["proxies"]:
                del db["proxies"][cat]
                save_data()
            edit_msg(chat_id, msg_id, f"✅ Deleted category: <b>{cat}</b>", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "admin_main"}]]})

        elif data == "adm_add_vpn":
            user_states[chat_id] = "adm_wait_vpn_name"
            edit_msg(chat_id, msg_id, "📌 VPN Name likhun (e.g. Premium 30 Days):", reply_markup=cancel_kb())

        elif data == "adm_manage_vpn":
            vpn_plans = db.get("vpn_plans", {})
            if not vpn_plans:
                edit_msg(chat_id, msg_id, "Kono VPN plan nei.", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "admin_main"}]]})
                return
            kb = []
            for v_name, info in vpn_plans.items():
                kb.append([
                    {"text": f"{v_name} (Stock: {info['stock']})", "callback_data": "none"},
                    {"text": "✏️ Edit Stock", "callback_data": f"edivpn_{v_name}", "style": "success"},
                    {"text": "❌ Delete", "callback_data": f"delvpn_{v_name}", "style": "danger"}
                ])
            kb.append([{"text": "Back", "callback_data": "admin_main"}])
            edit_msg(chat_id, msg_id, "🛠 <b>Manage VPN Plans & Stock:</b>", reply_markup={"inline_keyboard": kb})

        elif data.startswith("edivpn_"):
            v_name = data.replace("edivpn_", "")
            user_states[chat_id] = "adm_edit_vpn_stock_val"
            temp_data[chat_id] = {"edit_vpn_name": v_name}
            edit_msg(chat_id, msg_id, f"✏️ VPN <b>{v_name}</b> er notun <b>stock number</b> likhe pathan:", reply_markup=cancel_kb())

        elif data.startswith("delvpn_"):
            v_name = data.replace("delvpn_", "")
            if v_name in db["vpn_plans"]:
                del db["vpn_plans"][v_name]
                save_data()
            edit_msg(chat_id, msg_id, f"✅ Deleted VPN plan: <b>{v_name}</b>", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "adm_manage_vpn"}]]})

        elif data == "adm_balance_menu":
            user_states[chat_id] = "adm_wait_user_id_for_balance"
            edit_msg(chat_id, msg_id, "👤 User ID pathan:", reply_markup=cancel_kb())

        elif data == "adm_broadcast":
            user_states[chat_id] = "adm_broadcast"
            edit_msg(chat_id, msg_id, "📢 Broadcast message pathan:", reply_markup=cancel_kb())

        elif data == "adm_manage_admins":
            adms = db.get("admins", [OWNER_ID])
            kb = [[{"text": f"👤 {aid}", "callback_data": "none"}] for aid in adms]
            kb.append([{"text": "➕ Add Admin", "callback_data": "adm_add_admin_btn", "style": "success"}])
            kb.append([{"text": "Back", "callback_data": "admin_main"}])
            edit_msg(chat_id, msg_id, "👑 <b>Admin List</b>", reply_markup={"inline_keyboard": kb})

        elif data == "adm_add_admin_btn":
            user_states[chat_id] = "adm_add_admin"
            edit_msg(chat_id, msg_id, "Notun Admin ID pathan:", reply_markup=cancel_kb())

        elif data == "adm_settings":
            st = db.get("settings", {})
            txt = f"⚙️ <b>Settings:</b>\nbKash: <code>{st.get('bkash')}</code>\nBinance: <code>{st.get('binance')}</code>"
            kb = [
                [{"text": "Change bKash", "callback_data": "set_bk_btn"}],
                [{"text": "Change Binance", "callback_data": "set_bi_btn"}],
                [{"text": "Back", "callback_data": "admin_main"}]
            ]
            edit_msg(chat_id, msg_id, txt, reply_markup={"inline_keyboard": kb})

        elif data == "set_bk_btn":
            user_states[chat_id] = "adm_set_bkash"
            edit_msg(chat_id, msg_id, "Notun bKash number pathan:", reply_markup=cancel_kb())

        elif data == "set_bi_btn":
            user_states[chat_id] = "adm_set_binance"
            edit_msg(chat_id, msg_id, "Notun Binance ID pathan:", reply_markup=cancel_kb())

        elif data == "adm_stats":
            total_users = len(db.get("users", {}))
            total_proxies = sum([len(v) for v in db.get("proxies", {}).values()])
            total_vpns = len(db.get("vpn_plans", {}))
            edit_msg(chat_id, msg_id, f"📊 <b>Stats:</b>\nUsers: {total_users}\nProxies: {total_proxies}\nVPN Plans: {total_vpns}", reply_markup={"inline_keyboard": [[{"text": "Back", "callback_data": "admin_main"}]]})

        elif data == "admin_main":
            edit_msg(chat_id, msg_id, f"📊 <b>Admin Control Console</b>", reply_markup=admin_kb())

def main():
    offset = None
    executor = ThreadPoolExecutor(max_workers=20)
    print("🚀 Bot is running with Full VPN Delivery feature fixed...")
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
