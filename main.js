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
        console.log("FULL FACEBOOK PAYLOAD:", JSON.stringify(body));

        if (body.object === "page") {
          for (const entry of body.entry) {
            const webhookEvent = entry.messaging?.[0];
            
            if (webhookEvent && webhookEvent.sender && webhookEvent.sender.id) {
              const senderPsid = webhookEvent.sender.id;
              
              // Lấy nội dung tin nhắn văn bản hoặc tệp đính kèm
              let messageText = "Xin chào";
              if (webhookEvent.message && webhookEvent.message.text) {
                messageText = webhookEvent.message.text;
              } else if (webhookEvent.message && webhookEvent.message.attachments) {
                messageText = "Người dùng vừa gửi một tệp đính kèm hoặc hình ảnh.";
              }

              console.log(`Đang xử lý tin nhắn từ ${senderPsid}: ${messageText}`);

              // Lưu tin nhắn của người dùng vào Supabase (Chạy ngầm không chặn luồng chính)
              if (env.SUPABASE_URL && env.SUPABASE_ANON_KEY) {
                ctx.waitUntil(saveToSupabase(env, senderPsid, messageText, "user"));
              }

              // Gọi Gemini API để lấy câu trả lời
              const aiReply = await callGeminiAPI(messageText, env.GEMINI_API_KEY);

              // Lưu phản hồi của bot vào Supabase (Chạy ngầm)
              if (env.SUPABASE_URL && env.SUPABASE_ANON_KEY) {
                ctx.waitUntil(saveToSupabase(env, senderPsid, aiReply, "bot"));
              }

              // Gửi tin nhắn trả lại Facebook Messenger
              await sendFacebookMessage(senderPsid, aiReply, env.PAGE_ACCESS_TOKEN);
            } else {
              console.log("Webhook nhận được nhưng không phải sự kiện nhắn tin chuẩn.");
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
      return "Lỗi Google Gemini: " + data.error.message;
    }
    return data.candidates?.[0]?.content?.parts?.[0]?.text || "Xin lỗi, tôi không thể trả lời lúc này.";
  } catch (error) {
    console.error("Gemini API error:", error);
    return "Đã xảy ra lỗi khi kết nối với Gemini.";
  }
}

// Hàm gửi tin nhắn qua Facebook Send API
async function sendFacebookMessage(senderPsid, responseText, accessToken) {
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
  console.log("Kết quả gửi tin nhắn cho Facebook:", JSON.stringify(resData));
}

// Hàm lưu trữ lịch sử vào Supabase Database
async function saveToSupabase(env, senderId, message, senderType) {
  try {
    await fetch(`${env.SUPABASE_URL}/rest/v1/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "apikey": env.SUPABASE_ANON_KEY,
        "Authorization": `Bearer ${env.SUPABASE_ANON_KEY}`,
        "Prefer": "return=minimal"
      },
      body: JSON.stringify({
        sender_id: senderId,
        message: message,
        sender_type: senderType,
        created_at: new Date().toISOString()
      })
    });
  } catch (e) {
    console.error("Lỗi kết nối Supabase:", e);
  }
}
