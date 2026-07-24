# File: notify.py
import json
from pyodide.http import pyfetch

async def send_email_alert(title, user_id, content, env):
    # Dùng dịch vụ Resend.com (Miễn phí 3.000 email/tháng)
    resend_api_key = getattr(env, "RESEND_API_KEY", "")
    owner_email = getattr(env, "OWNER_EMAIL", "")  # Email của chủ shop
    
    if not resend_api_key or not owner_email:
        return

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }
    
    # Nội dung Email gửi cho chủ shop
    payload = {
        "from": "Bot Ban Hang <onboarding@resend.dev>",
        "to": [owner_email],
        "subject": f"🔔 [{title}] - Khách hàng {user_id}",
        "html": f"""
            <h3>🔔 Thông báo từ Bot Bán Hàng</h3>
            <p><b>Khách hàng ID:</b> {user_id}</p>
            <p><b>Nội dung tin nhắn:</b> {content}</p>
            <hr>
            <p><i>Hãy vào Fanpage kiểm tra và phản hồi khách ngay nhé!</i></p>
        """
    }
    
    try:
        await pyfetch(url, method="POST", headers=headers, body=json.dumps(payload))
    except Exception as e:
        print(f"Lỗi gửi Email: {e}")
