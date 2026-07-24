import json
import re
from js import Response, fetch

SYSTEM_PROMPT = """Bạn là trợ lý bán hàng tự động chuyên nghiệp trên Messenger. Tư vấn sản phẩm lịch sự, ngắn gọn và khéo léo xin SĐT, địa chỉ khi khách muốn đặt hàng."""
PRODUCTS_INFO = "BẢNG GIÁ:\n- Sản phẩm A: 250.000 VNĐ\n- Sản phẩm B: 450.000 VNĐ"

def split_message(text, max_length=1500):
    if len(text) <= max_length:
        return [text]
    chunks = []
    while len(text) > max_length:
        split_at = text.rfind(' ', 0, max_length)
        if split_at == -1:
            split_at = max_length
        chunks.append(text[:split_at])
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks

async def supabase_request(env, endpoint, method="GET", body=None, extra_headers=None):
    url = f"{getattr(env, 'SUPABASE_URL', '')}/rest/v1/{endpoint}"
    headers = {
        "apikey": getattr(env, "SUPABASE_KEY", ""),
        "Authorization": f"Bearer {getattr(env, 'SUPABASE_KEY', '')}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    if extra_headers:
        headers.update(extra_headers)
    req_options = {"method": method, "headers": headers}
    if body:
        req_options["body"] = json.dumps(body)
    return await fetch(url, req_options)

async def is_duplicate_message(env, mid):
    if not mid:
        return False
    res = await supabase_request(env, f"processed_messages?mid=eq.{mid}&select=mid")
    data = await res.json()
    if isinstance(data, list) and len(data) > 0:
        return True
    await supabase_request(env, "processed_messages", method="POST", body={"mid": mid})
    return False

async def check_human_takeover(env, user_id):
    res = await supabase_request(env, f"user_settings?user_id=eq.{user_id}&select=is_human_took_over")
    data = await res.json()
    if isinstance(data, list) and len(data) > 0:
        return data[0].get("is_human_took_over", False)
    return False

async def set_human_takeover(env, user_id, status=True):
    body = {"user_id": user_id, "is_human_took_over": status}
    headers = {"Prefer": "resolution=merge-duplicates"}
    await supabase_request(env, "user_settings", method="POST", body=body, extra_headers=headers)

async def get_chat_history(env, user_id):
    res = await supabase_request(env, f"chat_history?user_id=eq.{user_id}&select=history")
    data = await res.json()
    if isinstance(data, list) and len(data) > 0:
        return data[0].get("history", [])
    return []

async def save_chat_history(env, user_id, history):
    body = {"user_id": user_id, "history": history}
    headers = {"Prefer": "resolution=merge-duplicates"}
    await supabase_request(env, "chat_history", method="POST", body=body, extra_headers=headers)

async def extract_and_save_order(env, user_id, text):
    match = re.search(r"(0[3|5|7|8|9][0-9]{8})", text)
    if match:
        phone = match.group(1)
        await supabase_request(env, "orders", method="POST", body={"user_id": user_id, "phone": phone, "note": text})
        return phone
    return None

async def send_email_alert(env, subject, content):
    owner_email = getattr(env, "OWNER_EMAIL", "")
    resend_key = getattr(env, "RESEND_API_KEY", "")
    if not owner_email or not resend_key:
        return
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"}
    body = {"from": "BotNotification <onboarding@resend.dev>", "to": [owner_email], "subject": subject, "html": f"<p>{content}</p>"}
    await fetch(url, {"method": "POST", "headers": headers, "body": json.dumps(body)})

async def call_gemini_ai(env, user_id, user_text):
    gemini_key = getattr(env, "GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    history = await get_chat_history(env, user_id)
    contents = [
        {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{PRODUCTS_INFO}"}]},
        {"role": "model", "parts": [{"text": "Dạ, em đã hiểu rõ nhiệm vụ."}]}
    ]
    for item in history[-6:]:
        contents.append(item)
    contents.append({"role": "user", "parts": [{"text": user_text}]})
    res = await fetch(url, {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": json.dumps({"contents": contents})})
    data = await res.json()
    try:
        reply_text = data["candidates"][0]["content"]["parts"][0]["text"]
        history.append({"role": "user", "parts": [{"text": user_text}]})
        history.append({"role": "model", "parts": [{"text": reply_text}]})
        await save_chat_history(env, user_id, history[-10:])
        return reply_text
    except Exception:
        return "Cảm ơn bạn đã nhắn tin. Shop sẽ phản hồi trong giây lát nhé!"

async def send_fb_message(env, recipient_id, text):
    page_token = getattr(env, "PAGE_ACCESS_TOKEN", "")
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={page_token}"
    for chunk in split_message(text):
        await fetch(url, {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": json.dumps({"recipient": {"id": recipient_id}, "message": {"text": chunk}})})

class DefaultExport:
    async def fetch(self, request, env, ctx):
        method = request.method
        url = request.url

        if method == "GET":
            from urllib.parse import parse_qs, urlparse
            params = parse_qs(urlparse(url).query)
            mode = params.get("hub.mode", [""])[0]
            token = params.get("hub.verify_token", [""])[0]
            challenge = params.get("hub.challenge", [""])[0]
            if mode == "subscribe" and token == getattr(env, "VERIFY_TOKEN", ""):
                return Response.new(challenge, status=200)
            return Response.new("Forbidden", status=403)

        if method == "POST":
            try:
                data = json.loads(await request.text())
                if data.get("object") == "page":
                    for entry in data.get("entry", []):
                        for event in entry.get("messaging", []):
                            sender_id = event.get("sender", {}).get("id")
                            message = event.get("message", {})
                            mid = message.get("mid")
                            user_text = message.get("text")

                            if not user_text or not sender_id:
                                continue
                            if await is_duplicate_message(env, mid):
                                continue
                            if await check_human_takeover(env, sender_id):
                                if user_text.strip().lower() == "/bot":
                                    await set_human_takeover(env, sender_id, False)
                                    await send_fb_message(env, sender_id, "🤖 Bot đã được bật lại!")
                                continue

                            if any(kw in user_text.lower() for kw in ["gặp nhân viên", "người thật", "tắt bot"]):
                                await set_human_takeover(env, sender_id, True)
                                await send_fb_message(env, sender_id, "Nhân viên sẽ liên hệ lại ngay.")
                                await send_email_alert(env, f"🚨 Khách {sender_id} gọi nhân viên", user_text)
                                continue

                            phone = await extract_and_save_order(env, sender_id, user_text)
                            if phone:
                                await send_email_alert(env, f"📦 Đơn hàng mới SĐT: {phone}", user_text)

                            ai_reply = await call_gemini_ai(env, sender_id, user_text)
                            await send_fb_message(env, sender_id, ai_reply)
                return Response.new("EVENT_RECEIVED", status=200)
            except Exception as e:
                return Response.new(f"Error: {str(e)}", status=500)

        return Response.new("Method Not Allowed", status=405)
