from pyodide.http import pyfetch
import json

# Cấu hình Supabase của ông
SUPABASE_URL = "YOUR_SUPABASE_URL_HERE"  # Ví dụ: https://xxxx.supabase.co
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY_HERE"

# 1. Hàm lấy lịch sử chat từ Supabase
async def get_history_from_supabase(user_id):
    url = f"{SUPABASE_URL}/rest/v1/chat_history?user_id=eq.{user_id}&select=messages"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    try:
        response = await pyfetch(url, method="GET", headers=headers)
        if response.status == 200:
            data = await response.json()
            if data and len(data) > 0:
                return data[0].get("messages", [])
    except Exception as e:
        print(f"Lỗi đọc Supabase: {e}")
    return []

# 2. Hàm lưu/cập nhật lịch sử chat vào Supabase (Upsert)
async def save_history_to_supabase(user_id, history):
    url = f"{SUPABASE_URL}/rest/v1/chat_history"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"  # Tự động ghi đè nếu trùng user_id
    }
    payload = {
        "user_id": user_id,
        "messages": history
    }
    
    try:
        await pyfetch(url, method="POST", headers=headers, body=json.dumps(payload))
    except Exception as e:
        print(f"Lỗi lưu Supabase: {e}")

# 3. Hàm gọi Gemini 3.6
async def call_gemini(prompt, history=[]):
    api_key = "YOUR_GEMINI_API_KEY_HERE"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6:generateContent?key={api_key}"
    
    system_instruction_text = (
        "Bạn là trợ lý tư vấn khách hàng chuyên nghiệp, thông minh, lịch sự và thân thiện.\n"
        "QUY TẮC BẮT BUỘC:\n"
        "1. Luôn tôn trọng khách hàng, xưng 'dạ/em' hoặc 'shop' và gọi khách là 'anh/chị' hoặc 'bạn'.\n"
        "2. Chỉ trả lời các câu hỏi liên quan đến dịch vụ/sản phẩm và hỗ trợ khách hàng.\n"
        "3. Tuyệt đối KHÔNG văng tục, KHÔNG thảo luận về chính trị, tôn giáo, hoặc chủ đề nhạy cảm/độc hại.\n"
        "4. Nếu khách hỏi vấn đề nằm ngoài hiểu biết, hãy lịch sự báo: 'Dạ thông tin này em xin phép ghi nhận và báo nhân viên hỗ trợ mình ngay ạ!'\n"
        "5. Cung cấp câu trả lời ngắn gọn, rõ ràng, đi thẳng vào vấn đề."
    )
    
    contents = list(history)
    contents.append({
        "role": "user",
        "parts": [{"text": prompt}]
    })
    
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction_text}]
        },
        "contents": contents
    }
    
    try:
        response = await pyfetch(
            url,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload)
        )
        
        if response.status == 200:
            res_data = await response.json()
            candidates = res_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "Dạ em chưa hiểu rõ ý mình, anh/chị nói rõ hơn giúp em nha!")
    except Exception as e:
        print(f"Gemini Exception: {e}")
        
    return "Dạ hiện hệ thống bên em đang bận một chút, em sẽ phản hồi lại ngay ạ!"

# 4. Hàm gửi tin nhắn Facebook
async def send_facebook_message(recipient_id, message_text):
    page_access_token = "YOUR_PAGE_ACCESS_TOKEN_HERE"
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={page_access_token}"
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    try:
        await pyfetch(
            url,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload)
        )
    except Exception as e:
        print(f"Facebook Send Error: {e}")
