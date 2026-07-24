import json
from pyodide.http import pyfetch

# Các từ khóa kích hoạt chuyển sang tư vấn viên thật
HANDOFF_KEYWORDS = [
    "gặp nhân viên", "gặp tư vấn", "chuyển người thật", 
    "nói chuyện với người", "gặp chủ shop", "gặp admin", "tư vấn viên"
]

# 1. Kiểm tra khách này đã được nhân viên tiếp quản chưa
async def check_human_takeover(user_id, env):
    url = f"{env.SUPABASE_URL}/rest/v1/user_settings?user_id=eq.{user_id}&select=is_human_took_over"
    headers = {
        "apikey": env.SUPABASE_KEY,
        "Authorization": f"Bearer {env.SUPABASE_KEY}"
    }
    
    try:
        res = await pyfetch(url, method="GET", headers=headers)
        if res.status == 200:
            data = await res.json()
            if data and len(data) > 0:
                return data[0].get("is_human_took_over", False)
    except Exception as e:
        print(f"Lỗi check handoff: {e}")
        
    return False

# 2. Cập nhật trạng thái Tắt/Bật bot cho người dùng
async def set_human_takeover(user_id, status, env):
    url = f"{env.SUPABASE_URL}/rest/v1/user_settings"
    headers = {
        "apikey": env.SUPABASE_KEY,
        "Authorization": f"Bearer {env.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    payload = {"user_id": user_id, "is_human_took_over": status}
    
    try:
        await pyfetch(url, method="POST", headers=headers, body=json.dumps(payload))
    except Exception as e:
        print(f"Lỗi set handoff: {e}")

# 3. Quét từ khóa yêu cầu chuyển người thật
def should_trigger_handoff(message_text):
    text_lower = message_text.lower()
    return any(kw in text_lower for kw in HANDOFF_KEYWORDS)
