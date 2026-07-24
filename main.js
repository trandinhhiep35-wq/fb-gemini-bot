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
      } else {
        return new Response("Forbidden", { status: 403 });
      }
    }

    // 2. Nhận tin nhắn từ Facebook gửi sang (POST)
    if (request.method === "POST") {
      try {
        const body = await request.json();

        if (body.object === "page") {
          for (const entry of body.entry) {
            const webhookEvent = entry.messaging?.[0];
            
            if (webhookEvent && webhookEvent.sender && webhookEvent.sender.id) {
              const senderPsid = webhookEvent.sender.id;
              
              let messageText = "Xin chào";
              if (webhookEvent.message && webhookEvent.message.text) {
                messageText = webhookEvent.message.text;
              } else if (webhookEvent.message && webhookEvent.message.attachments) {
                messageText = "Người dùng vừa gửi một tệp đính kèm hoặc hình ảnh.";
              }

              // Gọi Gemini API
              const aiReply = await callGeminiAPI(messageText, env.GEMINI_API_KEY);

              // Gửi tin nhắn trả lại Facebook Messenger
              await sendFacebookMessage(senderPsid, aiReply, env.PAGE_ACCESS_TOKEN);
            }
          }
        }
        return new Response("EVENT_RECEIVED", { status: 200 });
      } catch (err) {
        console.error("Lỗi khi xử lý request:", err);
        return new Response("Internal Error", { status: 500 });
      }
    }

    return new Response("Not Found", { status: 404 });
  },
};

// Hàm gọi Gemini API (Đã tối ưu bắt lỗi)
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
    console.log("GEMINI RESPONSE:", JSON.stringify(data));

    if (data.candidates && data.candidates.length > 0) {
      return data.candidates[0].content?.parts?.[0]?.text || "Gemini trả về dữ liệu trống.";
    } else {
      console.error("Gemini từ chối hoặc lỗi cấu trúc:", data);
      return "Lỗi từ Google Gemini: " + (data.error?.message || "Không rõ nguyên nhân.");
    }
  } catch (error) {
    console.error("Gemini API error:", error);
    return "Đã xảy ra lỗi kết nối mạng tới Gemini.";
  }
}

// Hàm gửi tin nhắn qua Facebook Send API
async function sendFacebookMessage(senderPsid, responseText, accessToken) {
  const url = `https://graph.facebook.com/v21.0/me/messages?access_token=${accessToken}`;
  const body = {
    recipient: { id: senderPsid },
    message: { text: responseText }
  };

  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}
