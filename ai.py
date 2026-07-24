import json
from pyodide.http import pyfetch
from prompt import SYSTEM_PROMPT  # Nhập kịch bản từ file prompt.py

# 1. Lấy lịch sử chat từ Supabase
async def get_history_from_supabase(user_id, env):
    url = f"{env.SUPABASE_URL}/rest/v1/chat_history?user_id=eq.{user_id}&select=messages"
    headers = {
        "apikey": env.SUPABASE_KEY,
        "Authorization": f"Bearer {env.SUPABASE_KEY}"
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

# 2. Lưu/cập nhật lịch sử chat vào Supabase
async def save_history_to_supabase(user_id, history, env):
    url = f"{env.SUPABASE_URL}/rest/v1/chat_history"
    headers = {
        "apikey": env.SUPABASE_KEY,
        "Authorization": f"Bearer {env.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    payload = {
        "user_id": user_id,
        "messages": history
    }
    
    try:
        await pyfetch(url, method="POST", headers=headers, body=json.dumps(payload))
    except Exception as e:
        print(f"Lỗi lưu Supabase: {e}")

# 3. Gọi Gemini 3.6 xử lý câu trả lời
async def call_gemini(prompt, history, env):
    api_key = env.GEMINI_API_KEY
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6:generateContent?key={api_key}"
    
    contents = list(history)
    contents.append({
        "role": "user",
        "parts": [{"text": prompt}]
    })
    
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]  # Sử dụng Prompt quy tắc chặt chẽ
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
        else:
            err_text = await response.string()
            print(f"Gemini API Error ({response.status}): {err_text}")
            
    except Exception as e:
        print(f"Gemini Exception: {e}")
        
    return "Dạ hiện hệ thống bên em đang bận một chút, em sẽ phản hồi lại ngay ạ!"

# 4. Gửi tin nhắn phản hồi qua Facebook Messenger
async def send_facebook_message(recipient_id, message_text, env):
    page_access_token = env.PAGE_ACCESS_TOKEN
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
