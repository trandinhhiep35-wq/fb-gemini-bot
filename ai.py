from pyodide.http import pyfetch
import json

async def call_gemini(prompt):
    # Thay API Key Gemini của ông vào đây
    api_key = "YOUR_GEMINI_API_KEY_HERE"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6:generateContent?key={api_key}"
    
    payload = {
        "system_instruction": {
            "parts": [{"text": "Bạn là trợ lý chăm sóc khách hàng thông minh, thân thiện, nói chuyện ngắn gọn, tự nhiên và chuyên nghiệp."}]
        },
        "contents": [{
            "parts": [{"text": prompt}]
        }]
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
                    return parts[0].get("text", "Xin lỗi, shop chưa hiểu rõ ý bạn.")
        else:
            err_text = await response.string()
            print(f"Gemini API Error ({response.status}): {err_text}")
            
    except Exception as e:
        print(f"Gemini Exception: {e}")
        
    return "Dạ shop hiện đang bận, sẽ phản hồi lại ngay ạ!"

async def send_facebook_message(recipient_id, message_text):
    # Thay Page Access Token của Fanpage vào đây
    page_access_token = "EAAVxOcu3ZAtkBSPRUS8FFBTaqiT1RWn4b76VlAeJdpFJ1FjaZB0ctVENnzoGCHNtASE1fKQOZBoFdKcAZBRIC3hf1fGRJcUZAoo2ySCKR4N7dwAEvoTgVES3XoowX4DcnGT0TW9UNzZBcdhsmdF1azYEyitKApDMdHpjP2ZAxRe5NVa6We0hfiYeRbYV0l4MwZA2uoO9dYjG3QZDZD"
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
