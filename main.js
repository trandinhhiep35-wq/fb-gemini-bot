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

    // 2. Nhận và xử lý tin nhắn từ Messenger (POST)
    if (request.method === "POST") {
      try {
        const data = await request.json();
        if (data.object === "page") {
          for (const entry of data.entry || []) {
            for (const event of entry.messaging || []) {
              const senderId = event.sender?.id;
              const message = event.message || {};
              const mid = message.mid;
              const userText = message.text;

              if (!senderId || !userText) continue;

              // Chống trùng lặp tin nhắn
              if (await isDuplicateMessage(env, mid)) continue;

              // Kiểm tra chế độ người thật tiếp quản (Handoff)
              const isHumanTaken = await checkHumanTakeover(env, senderId);
              if (isHumanTaken) {
                if (userText.trim().toLowerCase() === "/bot") {
                  await setHumanTakeover(env, senderId, false);
                  await sendFbMessage(env, senderId, "🤖 Bot tự động đã được bật lại!");
                }
                continue;
              }

              // Khách yêu cầu gặp nhân viên / người thật
              const lowerText = userText.toLowerCase();
              if (lowerText.includes("gặp nhân viên") || lowerText.includes("người thật") || lowerText.includes("tắt bot")) {
                await setHumanTakeover(env, senderId, true);
                await sendFbMessage(env, senderId, "Nhân viên sẽ liên hệ lại ngay.");
                await sendEmailAlert(env, `🚨 Khách ${senderId} gọi nhân viên`, userText);
                continue;
              }

              // Trích xuất và lưu đơn hàng tự động (tìm SĐT)
              const phone = await extractAndSaveOrder(env, senderId, userText);
              if (phone) {
                await sendEmailAlert(env, `📦 Đơn hàng mới SĐT: ${phone}`, userText);
              }

              // Gọi Gemini AI xử lý và trả lời
              const aiReply = await callGeminiAI(env, senderId, userText);
              await sendFbMessage(env, senderId, aiReply);
            }
          }
        }
        return new Response("EVENT_RECEIVED", { status: 200 });
      } catch (e) {
        return new Response(`Error: ${e.message}`, { status: 500 });
      }
    }

    return new Response("Method Not Allowed", { status: 405 });
  }
};

// ==========================================
// CÁC HÀM XỬ LÝ HỆ THỐNG
// ==========================================

async function supabaseRequest(env, endpoint, method = "GET", body = null, extraHeaders = {}) {
  const url = `${env.SUPABASE_URL}/rest/v1/${endpoint}`;
  const headers = {
    "apikey": env.SUPABASE_KEY,
    "Authorization": `Bearer ${env.SUPABASE_KEY}`,
    "Content-Type": "application/json",
    "Prefer": "return=representation",
    ...extraHeaders
  };
  const options = { method, headers };
  if (body) options.body = JSON.stringify(body);
  return await fetch(url, options);
}

async function isDuplicateMessage(env, mid) {
  if (!mid) return false;
  const res = await supabaseRequest(env, `processed_messages?mid=eq.${mid}&select=mid`);
  const data = await res.json();
  if (Array.isArray(data) && data.length > 0) return true;
  await supabaseRequest(env, "processed_messages", "POST", { mid });
  return false;
}

async function checkHumanTakeover(env, userId) {
  const res = await supabaseRequest(env, `user_settings?user_id=eq.${userId}&select=is_human_took_over`);
  const data = await res.json();
  return Array.isArray(data) && data.length > 0 ? data[0].is_human_took_over : false;
}

async function setHumanTakeover(env, userId, status = true) {
  await supabaseRequest(env, "user_settings", "POST", { user_id: userId, is_human_took_over: status }, { "Prefer": "resolution=merge-duplicates" });
}

async function getChatHistory(env, userId) {
  const res = await supabaseRequest(env, `chat_history?user_id=eq.${userId}&select=history`);
  const data = await res.json();
  return Array.isArray(data) && data.length > 0 ? data[0].history : [];
}

async function saveChatHistory(env, userId, history) {
  await supabaseRequest(env, "chat_history", "POST", { user_id: userId, history }, { "Prefer": "resolution=merge-duplicates" });
}

async function extractAndSaveOrder(env, userId, text) {
  const match = text.match(/(0[3|5|7|8|9][0-9]{8})/);
  if (match) {
    const phone = match[1];
    await supabaseRequest(env, "orders", "POST", { user_id: userId, phone, note: text });
    return phone;
  }
  return null;
}

async function sendEmailAlert(env, subject, content) {
  if (!env.OWNER_EMAIL || !env.RESEND_API_KEY) return;
  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      from: "BotNotification <onboarding@resend.dev>",
      to: [env.OWNER_EMAIL],
      subject: subject,
      html: `<p>${content}</p>`
    })
  });
}

async function callGeminiAI(env, userId, userText) {
  const systemPrompt = "Bạn là trợ lý bán hàng tự động chuyên nghiệp, thân thiện trên Messenger. Hãy tư vấn ngắn gọn, lịch sự, xin SĐT khi khách mua hàng.";
  const history = await getChatHistory(env, userId);
  
  const contents = [
    { role: "user", parts: [{ text: systemPrompt }] },
    { role: "model", parts: [{ text: "Dạ em đã hiểu nhiệm vụ." }] }
  ];
  
  for (const item of history.slice(-6)) {
    contents.push(item);
  }
  contents.push({ role: "user", parts: [{ text: userText }] });

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${env.GEMINI_API_KEY}`;
  
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contents })
    });
    const data = await res.json();
    const replyText = data.candidates?.[0]?.content?.parts?.[0]?.text || "Cảm ơn bạn đã nhắn tin!";

    history.push({ role: "user", parts: [{ text: userText }] });
    history.push({ role: "model", parts: [{ text: replyText }] });
    await saveChatHistory(env, userId, history.slice(-10));

    return replyText;
  } catch (err) {
    return "Shop sẽ phản hồi bạn trong giây lát nhé!";
  }
}

async function sendFbMessage(env, recipientId, text) {
  const url = `https://graph.facebook.com/v19.0/me/messages?access_token=${env.PAGE_ACCESS_TOKEN}`;
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      recipient: { id: recipientId },
      message: { text: text }
    })
  });
}
