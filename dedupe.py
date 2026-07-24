import json
from pyodide.http import pyfetch

# Bộ nhớ tạm để lọc nhanh trong cùng 1 đợt xử lý
PROCESSED_MIDS = set()

async def is_duplicate_message(mid, env):
    if not mid:
        return False
        
    if mid in PROCESSED_MIDS:
        return True
        
    # Kiểm tra trong bảng 'processed_messages' trên Supabase
    url = f"{env.SUPABASE_URL}/rest/v1/processed_messages?mid=eq.{mid}&select=mid"
    headers = {
        "apikey": env.SUPABASE_KEY,
        "Authorization": f"Bearer {env.SUPABASE_KEY}"
    }
    
    try:
        res = await pyfetch(url, method="GET", headers=headers)
        if res.status == 200:
            data = await res.json()
            if data and len(data) > 0:
                PROCESSED_MIDS.add(mid)
                return True
    except Exception as e:
        print(f"Lỗi kiểm tra trùng lặp: {e}")
        
    return False

async def mark_message_processed(mid, env):
    if not mid:
        return
        
    PROCESSED_MIDS.add(mid)
    if len(PROCESSED_MIDS) > 1000:
        PROCESSED_MIDS.clear()
        
    url = f"{env.SUPABASE_URL}/rest/v1/processed_messages"
    headers = {
        "apikey": env.SUPABASE_KEY,
        "Authorization": f"Bearer {env.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    payload = {"mid": mid}
    
    try:
        await pyfetch(url, method="POST", headers=headers, body=json.dumps(payload))
    except Exception as e:
        print(f"Lỗi lưu mid trùng lặp: {e}")
