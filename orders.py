import re
import json
from pyodide.http import pyfetch

# Quét Số điện thoại chuẩn Việt Nam (10 chữ số)
def extract_phone_number(text):
    clean_text = re.sub(r'[\s\.\-\(\)]', '', text)
    matches = re.findall(r'(?:\+84|0)[3|5|7|8|9][0-9]{8}', clean_text)
    if matches:
        return matches[0]
    return None

# Lưu thông tin đơn hàng / SĐT vào Supabase
async def save_order_to_supabase(user_id, phone_number, full_text, env):
    url = f"{env.SUPABASE_URL}/rest/v1/orders"
    headers = {
        "apikey": env.SUPABASE_KEY,
        "Authorization": f"Bearer {env.SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "user_id": user_id,
        "phone": phone_number,
        "note": full_text
    }
    
    try:
        await pyfetch(url, method="POST", headers=headers, body=json.dumps(payload))
    except Exception as e:
        print(f"Lỗi lưu đơn hàng: {e}")
