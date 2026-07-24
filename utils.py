import json
from pyodide.http import pyfetch

# 1. Cắt văn bản thành các đoạn ngắn dưới 1800 ký tự
def split_text_chunks(text, max_length=1800):
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    while len(text) > max_length:
        # Ưu tiên cắt theo dấu xuống dòng hoặc khoảng trắng
        split_idx = text.rfind('\n', 0, max_length)
        if split_idx == -1:
            split_idx = text.rfind(' ', 0, max_length)
        if split_idx == -1:
            split_idx = max_length
            
        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
        
    if text:
        chunks.append(text)
    return chunks

# 2. Gửi tin nhắn qua Facebook (Tự động chia nhỏ nếu dài)
async def send_split_facebook_message(recipient_id, message_text, env):
    page_access_token = env.PAGE_ACCESS_TOKEN
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={page_access_token}"
    
    chunks = split_text_chunks(message_text)
    for chunk in chunks:
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": chunk}
        }
        try:
            await pyfetch(
                url,
                method="POST",
                headers={"Content-Type": "application/json"},
                body=json.dumps(payload)
            )
        except Exception as e:
            print(f"Lỗi gửi tin nhắn Facebook: {e}")
