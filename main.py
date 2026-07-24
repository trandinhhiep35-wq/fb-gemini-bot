from workers import WorkerEntrypoint, Response
import urllib.parse
from ai import (
    call_gemini, 
    send_facebook_message, 
    get_history_from_supabase, 
    save_history_to_supabase
)

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # 1. Xác thực Webhook từ Facebook
        if request.method == "GET":
            url_str = str(request.url)
            parsed_url = urllib.parse.urlparse(url_str)
            params = urllib.parse.parse_qs(parsed_url.query)
            
            mode = params.get("hub.mode", [""])[0]
            token = params.get("hub.verify_token", [""])[0]
            challenge = params.get("hub.challenge", [""])[0]
            
            # Đọc VERIFY_TOKEN từ Environment Variables
            VERIFY_TOKEN = getattr(self.env, "VERIFY_TOKEN", "")
            
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return Response(challenge, status=200)
            return Response("Xác thực thất bại", status=403)

        # 2. Xử lý tin nhắn POST từ khách
        if request.method == "POST":
            try:
                body = await request.json()
                
                for entry in body.get("entry", []):
                    for messaging_event in entry.get("messaging", []):
                        if "message" in messaging_event and "text" in messaging_event["message"]:
                            sender_id = messaging_event["sender"]["id"]
                            message_text = messaging_event["message"]["text"]
                            
                            # A. Lấy lịch sử từ Supabase
                            history = await get_history_from_supabase(sender_id, self.env)
                            
                            # B. Gọi Gemini xử lý kèm lịch sử
                            reply_text = await call_gemini(message_text, history, self.env)
                            
                            # C. Cập nhật câu thoại mới
                            history.append({"role": "user", "parts": [{"text": message_text}]})
                            history.append({"role": "model", "parts": [{"text": reply_text}]})
                            history = history[-10:]
                            
                            # D. Lưu lại lịch sử mới vào Supabase
                            await save_history_to_supabase(sender_id, history, self.env)
                            
                            # E. Gửi phản hồi Facebook
                            await send_facebook_message(sender_id, reply_text, self.env)
                
                return Response("EVENT_RECEIVED", status=200)
            except Exception as e:
                return Response(f"Lỗi: {str(e)}", status=500)

        return Response("Method not allowed", status=405)
