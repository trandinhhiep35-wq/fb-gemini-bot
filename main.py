import json
import re
import js

# ==========================================
# CẤU HÌNH BẢNG GIÁ & PROMPT HỆ THỐNG
# ==========================================
SYSTEM_PROMPT = """Bạn là trợ lý bán hàng tự động chuyên nghiệp, thân thiện và nhiệt tình trên Messenger.
Nhiệm vụ của bạn:
- Tư vấn thông tin sản phẩm đầy đủ, chính xác theo bảng giá.
- Lịch sự, ngắn gọn, dùng icon phù hợp.
- Khi khách có ý định đặt hàng, hãy khéo léo xin Số Điện Thoại và Địa Chỉ của khách.
- Nếu khách muốn gặp người thật/nhân viên, hãy thông báo rằng nhân viên sẽ liên hệ lại ngay."""

PRODUCTS_INFO = """
BẢNG GIÁ VÀ SẢN PHẨM:
- Sản phẩm A: 250.000 VNĐ
- Sản phẩm B: 450.000 VNĐ
- Bảng giá dịch vụ / Tài khoản: Liên hệ trực tiếp để nhận ưu đãi.
"""

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

# ==========================================
# HỆ THỐNG XỬ LÝ (SUPABASE, AI, EMAIL, ĐƠN HÀNG)
# ==========================================
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
    return await js.fetch(url, req_options)

# 1. Chống trùng lặp tin nhắn
async def is_duplicate_message(env, mid):
    if not mid:
        return False
    res = await supabase_request(env, f"processed_messages?mid=eq.{mid}&select=mid")
    data = await res.json()
    if isinstance(data, list) and len(data) > 0:
        return True
    await supabase_request(env, "processed_messages", method="POST", body={"mid": mid})
    return False

# 2. Kiểm tra chế độ trực người thật (Handoff)
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

# 3. Lấy lịch sử trò chuyện
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

# 4. Trích xuất và lưu đơn hàng tự động
async def extract_and_save_order(env, user_id, text):
    match = re.search(r"(0[3|5|7|8|9][0-9]{8})", text)
    if match:
        phone = match.group(1)
        await supabase_request(env, "orders", method="POST", body={"user_id": user_id, "phone": phone, "note": text})
        return phone
    return None

# 5. Gửi thông báo qua Email bằng Resend
async def send_email_alert(env, subject, content):
    owner_email = getattr(env, "OWNER_EMAIL", "")
    resend_key = getattr(env, "RESEND_API_KEY", "")
    if not owner_email or not resend_key:
        return
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"}
    body = {"from": "BotNotification <onboarding@resend.dev>", "to": [owner_email], "subject": subject, "html": f"<p>{content}</p>"}
    await js.fetch(url, {"method": "POST", "headers": headers, "body": json.dumps(body)})

# 6. Gọi Gemini AI xử lý ngữ cảnh
async def call_gemini_ai(env, user_id, user_text):
    gemini_key = getattr(env, "GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    history = await get_chat_history(env, user_id)
    contents = [
        {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{PRODUCTS_INFO}"}]},
        {"role": "model", "parts": [{"text": "Dạ, em đã hiểu rõ nhiệm vụ và bảng giá sản phẩm."}]}
    ]
    for item in history[-6:]:
        contents.append(item)
    contents.append({"role": "user", "parts": [{"text": user_text}]})
    res = await js.fetch(url, {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": json.dumps({"contents": contents})})
    data = await res.json()
    try:
        reply_text = data["candidates"][0]["content"]["parts"][0]["text"]
        history.append({"role": "user", "parts": [{"text": user_text}]})
        history.append({"role": "model", "parts": [{"text": reply_text}]})
        await save_chat_history(env, user_id, history[-10:])
        return reply_text
    except Exception:
        return "Cảm ơn bạn đã nhắn tin. Shop sẽ phản hồi bạn trong giây lát nhé!"

# 7. Gửi tin nhắn qua Facebook Messenger API
async def send_fb_message(env, recipient_id, text):
    page_token = getattr(env, "PAGE_ACCESS_TOKEN", "")
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={page_token}"
    for chunk in split_message(text):
        await js.fetch(url, {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": json.dumps({"recipient": {"id": recipient_id}, "message": {"text": chunk}})})

# ==========================================
# 8. ENTRY POINT CHÍNH (Xác thực Webhook & Xử lý tin nhắn)
# ==========================================
async def fetch(request, env, ctx):
    method = request.method
    url = request.url

    if method == "GET":
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(url).query)
        mode = params.get("hub.mode", [""])[0]
        token = params.get("hub.verify_token", [""])[0]
        challenge = params.get("hub.challenge", [""])[0]
        if mode == "subscribe" and token == getattr(env, "VERIFY_TOKEN", ""):
            return js.Response.new(challenge, {"status": 200})
        return js.Response.new("Forbidden", {"status": 403})

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
                                await send_fb_message(env, sender_id, "🤖 Bot tự động đã được bật lại!")
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
            return js.Response.new("EVENT_RECEIVED", {"status": 200})
        except Exception as e:
            return js.Response.new(f"Error: {str(e)}", {"status": 500})

    return js.Response.new("Method Not Allowed", {"status": 405})
