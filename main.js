export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Xác thực Webhook với Facebook (GET)
    if (request.method === "GET") {
      const mode = url.searchParams.get("hub.mode");
      const token = url.searchParams.get("hub.verify_token");
      const challenge = url.searchParams.get("hub.challenge");

      if (mode === "subscribe" && token === env.VERIFY_TOKEN) {
        return new Response(challenge, { status: 200 });
      }
      return new Response("Forbidden", { status: 403 });
    }

    // 2. Nhận và xử lý tin nhắn từ Facebook gửi sang (POST)
    if (request.method === "POST") {
      try {
        const body = await request.json();

        if (body.object === "page") {
          for (const entry of body.entry) {
            const webhookEvent = entry.messaging?.[0];
            
            if (webhookEvent?.sender?.id) {
              const senderPsid = webhookEvent.sender.id;
              
              // Lấy nội dung tin nhắn văn bản hoặc tệp đính kèm
              let messageText = "Xin chào";
              if (webhookEvent.message?.text) {
                messageText = webhookEvent.message.text;
              } else if (webhookEvent.message?.attachments) {
                messageText = "Người dùng vừa gửi tệp đính kèm hoặc hình ảnh.";
              }

              // Gọi Gemini API để lấy câu trả lời
              const aiReply = await callGeminiAPI(messageText, env.GEMINI_API_KEY);

              // Gửi phản hồi ngược lại Facebook Messenger
              await sendFacebookMessage(senderPsid, aiReply, env.PAGE_ACCESS_TOKEN);
            }
          }
        }
        return new Response("EVENT_RECEIVED", { status: 200 });
      } catch (err) {
        console.error("Worker Error:", err);
        return new Response("Internal Error", { status: 500 });
      }
    }

    return new Response("Not Found", { status: 404 });
  },
};

// Hàm gọi Google Gemini API
async function callGeminiAPI(prompt, apiKey) {
  try {
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }]
      })
    });
    
    const data = await response.json();
    
    if (data.error) {
      return "Lỗi từ Gemini: " + data.error.message;
    }
    
    return data.candidates?.[0]?.content?.parts?.[0]?.text || "Bot hiện không có câu trả lời.";
  } catch (error) {
    console.error("Gemini fetch error:", error);
    return "Lỗi kết nối tới Google Gemini.";
  }
}

// Hàm gửi tin nhắn qua Facebook Send API
async function sendFacebookMessage(senderPsid, responseText, accessToken) {
  try {
    const url = `https://graph.facebook.com/v21.0/me/messages?access_token=${accessToken}`;
    const body = {
      recipient: { id: senderPsid },
      message: { text: responseText }
    };

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    
    const resData = await res.json();
    if (resData.error) {
      console.error("Facebook Send Error:", resData.error);
    }
  } catch (err) {
    console.error("Facebook fetch error:", err);
  }
}
