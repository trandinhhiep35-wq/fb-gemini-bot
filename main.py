import json
from js import Response

# Import các tính năng từ các file module của ông
from dedupe import is_duplicate_message
from handoff import check_human_takeover, set_human_takeover
from orders import extract_and_save_order
from notify import send_email_alert
from ai import call_gemini_ai, send_fb_message

class DefaultExport:
    async def fetch(self, request, env, ctx):
        method = request.method
        url = request.url

        # 1. XỬ LÝ XÁC THỰC WEBHOOK VỚI FACEBOOK (GET)
        if method == "GET":
            from urllib.parse import parse_qs, urlparse
            parsed_url = urlparse(url)
            params = parse_qs(parsed_url.query)
            
            mode = params.get("hub.mode", [""])[0]
            token = params.get("hub.verify_token", [""])[0]
            challenge = params.get("hub.challenge", [""])[0]
            
            verify_token = getattr(env, "VERIFY_TOKEN", "")

            if mode == "subscribe" and token == verify_token:
                return Response.new(challenge, status=200)
            else:
                return Response.new("Forbidden", status=403)

        # 2. XỬ LÝ TIN NHẮN TỪ KHÁCH HÀNG (POST)
        if method == "POST":
            try:
                body_text = await request.text()
                data = json.loads(body_text)

                if data.get("object") == "page":
                    for entry in data.get("entry", []):
                        for messaging_event in entry.get("messaging", []):
                            
                            sender_id = messaging_event.get("sender", {}).get("id")
                            message = messaging_event.get("message", {})
                            mid = message.get("mid")
                            user_text = message.get("text")

                            if not user_text or not sender_id:
                                continue

                            # Chống trùng tin nhắn
                            if await is_duplicate_message(env, mid):
                                continue

                            # Kiểm tra chế độ nhân viên tiếp quản
                            if await check_human_takeover(env, sender_id):
                                if user_text.strip().lower() == "/bot":
                                    await set_human_takeover(env, sender_id, False)
                                    await send_fb_message(env, sender_id, "🤖 Bot tự động đã được bật lại để hỗ trợ bạn!")
                                continue

                            # Kiểm tra từ khóa gọi nhân viên thật
                            keywords_human = ["gặp nhân viên", "gặp tư vấn viên", "người thật", "chuyển người thật", "tắt bot"]
                            if any(kw in user_text.lower() for kw in keywords_human):
                                await set_human_takeover(env, sender_id, True)
                                await send_fb_message(env, sender_id, "Dạ shop đã ghi nhận yêu cầu! Nhân viên tư vấn sẽ tiếp quản hội thoại và nhắn lại cho bạn ngay nhé.")
                                await send_email_alert(env, f"🚨 YÊU CẦU TƯ VẤN VIÊN: Khách {sender_id}", f"Khách hàng id {sender_id} vừa yêu cầu gặp nhân viên thật với nội dung: '{user_text}'")
                                continue

                            # Bóc tách SĐT và lưu đơn hàng
                            phone = await extract_and_save_order(env, sender_id, user_text)
                            if phone:
                                await send_email_alert(env, f"📦 ĐƠN HÀNG MỚI từ SĐT {phone}", f"Khách hàng {sender_id} vừa để lại SĐT: {phone}\nNội dung: {user_text}")

                            # Gọi AI Gemini tư vấn và gửi phản hồi qua Messenger
                            ai_reply = await call_gemini_ai(env, sender_id, user_text)
                            await send_fb_message(env, sender_id, ai_reply)

                return Response.new("EVENT_RECEIVED", status=200)
            except Exception as e:
                return Response.new(f"Error: {str(e)}", status=500)

        return Response.new("Method Not Allowed", status=405)
