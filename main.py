from workers import WorkerEntrypoint, Response
import urllib.parse
import urllib.request
import json

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # 1. Xác thực Webhook từ Facebook (GET request)
        if request.method == "GET":
            url_str = str(request.url)
            parsed_url = urllib.parse.urlparse(url_str)
            params = urllib.parse.parse_qs(parsed_url.query)
            
            mode = params.get("hub.mode", [""])[0]
            token = params.get("hub.verify_token", [""])[0]
            challenge = params.get("hub.challenge", [""])[0]
            
            # Mã xác thực Webhook (hãy khớp mã này với cài đặt trên Facebook Developer)
            VERIFY_TOKEN = "12345" 
            
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return Response(challenge, status=200)
            return Response("Xác thực thất bại", status=403)

        # 2. Xử lý tin nhắn từ khách hàng gửi tới Fanpage (POST request)
        if request.method == "POST":
            try:
                body = await request.json()
                
                # Duyệt qua các sự kiện tin nhắn từ Facebook Messenger
                for entry in body.get("entry", []):
                    for messaging_event in entry.get("messaging", []):
                        if "message" in messaging_event and "text" in messaging_event["message"]:
                            sender_id = messaging_event["sender"]["id"]
                            message_text = messaging_event["message"]["text"]
                            
                            # Gọi Gemini API để sinh câu trả lời thông minh
                            reply_text = self.call_gemini(message_text)
                            
                            # Gửi phản hồi ngược lại cho khách hàng qua Facebook Graph API
                            self.send_facebook_message(sender_id, reply_text)
                
                return Response("EVENT_RECEIVED", status=200)
            except Exception as e:
                return Response(f"Lỗi: {str(e)}", status=500)

        return Response("Method not allowed", status=405)

    def call_gemini(self, prompt):
        # Thay thế khóa API Gemini của ông vào đây
        api_key = "DIEN_GEMINI_API_KEY_CUA_ONG_VAO_DAY"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                candidates = res_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "Xin lỗi, shop chưa hiểu rõ ý bạn.")
        except Exception as e:
            print(f"Gemini Error: {e}")
        
        return "Dạ shop hiện đang bận, sẽ phản hồi lại ngay ạ!"

    def send_facebook_message(self, recipient_id, message_text):
        # Thay thế Page Access Token của Fanpage vào đây
        page_access_token = "DIEN_PAGE_ACCESS_TOKEN_CUA_FANPAGE_VAO_DAY"
        url = f"https://graph.facebook.com/v19.0/me/messages?access_token={page_access_token}"
        
        headers = {"Content-Type": "application/json"}
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text}
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                return response.read()
        except Exception as e:
            print(f"Facebook Send Error: {e}")
