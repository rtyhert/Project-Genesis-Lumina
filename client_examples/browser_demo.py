"""
Lumina JavaScript Client — Browser Example (HTML)
"""
JS_CLIENT_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Lumina Chat Demo</title>
<style>
  body { font-family: sans-serif; max-width: 600px; margin: 2em auto; }
  #chat { border: 1px solid #ccc; height: 400px; overflow-y: auto; padding: 1em; margin-bottom: 1em; }
  .msg { margin-bottom: 0.5em; }
  .user { color: #0066cc; }
  .bot { color: #009900; }
  .emotion { font-size: 0.8em; color: #666; }
</style>
</head>
<body>
<h1>Lumina Chat Demo</h1>
<div id="chat"></div>
<input id="input" type="text" placeholder="输入消息..." style="width: 80%; padding: 0.5em;">
<button id="send">发送</button>
<button id="streamBtn">流式发送</button>
<p id="status">状态: 检查中...</p>

<script>
const BASE = "http://localhost:8000";
const chatDiv = document.getElementById("chat");
const input = document.getElementById("input");
const statusP = document.getElementById("status");

function appendMsg(text, cls, emotion) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  if (emotion) {
    const em = document.createElement("span");
    em.className = "emotion";
    em.textContent = " [" + emotion + "]";
    div.appendChild(em);
  }
  chatDiv.appendChild(div);
  chatDiv.scrollTop = chatDiv.scrollHeight;
}

async function send() {
  const msg = input.value.trim();
  if (!msg) return;
  appendMsg("你: " + msg, "user");
  input.value = "";
  try {
    const resp = await fetch(BASE + "/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    });
    const data = await resp.json();
    appendMsg("Lumina: " + (data.response || data.text), "bot", data.emotion);
  } catch (e) {
    appendMsg("错误: " + e.message, "user");
  }
}

async function streamSend() {
  const msg = input.value.trim();
  if (!msg) return;
  appendMsg("你: " + msg, "user");
  input.value = "";
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg bot";
  chatDiv.appendChild(msgDiv);
  try {
    const resp = await fetch(BASE + "/api/v1/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const token = line.slice(6);
          if (token === "[DONE]") continue;
          try {
            const parsed = JSON.parse(token);
            msgDiv.textContent = "Lumina: " + parsed.text;
          } catch {
            msgDiv.textContent = "Lumina: " + (msgDiv.textContent.replace("Lumina: ", "") + token);
          }
        }
      }
    }
    chatDiv.scrollTop = chatDiv.scrollHeight;
  } catch (e) {
    appendMsg("错误: " + e.message, "user");
  }
}

async function checkStatus() {
  try {
    const resp = await fetch(BASE + "/health");
    const data = await resp.json();
    statusP.textContent = "状态: 已连接 (Mock: " + data.mock_mode + ")";
  } catch {
    statusP.textContent = "状态: 未连接 — 请确保 Lumina 正在运行";
  }
}

document.getElementById("send").onclick = send;
document.getElementById("streamBtn").onclick = streamSend;
input.onkeydown = (e) => { if (e.key === "Enter") send(); };
checkStatus();
</script>
</body>
</html>"""

if __name__ == "__main__":
    with open("chat_demo.html", "w", encoding="utf-8") as f:
        f.write(JS_CLIENT_HTML)
    print("Wrote chat_demo.html — open in browser to test Lumina chat")
