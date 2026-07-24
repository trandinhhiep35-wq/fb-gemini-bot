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
        console.log("Webhook received:", JSON.stringify(body));

        if (body.object === "page") {
          for (const entry of body.entry) {
            const webhookEvent = entry.messaging?.[0];
            if (webhookEvent && webhookEvent.message && webhookEvent.message.text) {
              const senderPsid = webhookEvent.sender.id;
              const messageText = webhookEvent.message.text;

              // Gọi Gemini API để lấy câu trả lời
              const aiReply = await callGeminiAPI(messageText, env.GEMINI_API_KEY);

              // Gửi tin nhắn trả lại Facebook Messenger
              await sendFacebookMessage(senderPsid, aiReply, env.PAGE_ACCESS_TOKEN);
            }
          }
        }
        return new Response("EVENT_RECEIVED", { status: 200 });
      } catch (err) {
        console.error("Error processing request:", err);
        return new Response("Internal Error", { status: 500 });
      }
    }

    return new Response("Not Found", { status: 404 });
  },
};

// Hàm gọi Gemini API
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

  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}
