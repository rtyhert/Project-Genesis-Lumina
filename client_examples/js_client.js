/**
 * Lumina JavaScript Client — Example Usage
 *
 * Demonstrates how to interact with Lumina's REST API from Node.js / browser.
 *
 * Usage:
 *   node js_client.js
 */

const BASE_URL = "http://localhost:8000";

async function healthCheck() {
  const resp = await fetch(`${BASE_URL}/health`);
  return resp.json();
}

async function sendChat(message, sessionId) {
  const payload = { message };
  if (sessionId) payload.session_id = sessionId;
  const resp = await fetch(`${BASE_URL}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return resp.json();
}

async function* streamChat(message) {
  const resp = await fetch(`${BASE_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
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
        yield line.slice(6);
      }
    }
  }
}

async function synthesizeSpeech(text, voice = "zh-CN-XiaoxiaoNeural") {
  const resp = await fetch(`${BASE_URL}/api/v1/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice }),
  });
  return resp.arrayBuffer();
}

async function getStatus() {
  const resp = await fetch(`${BASE_URL}/api/v1/status`);
  return resp.json();
}

/* ── Demo ───────────────────────────────────────── */
async function main() {
  console.log("Lumina Health:", await healthCheck());

  console.log("\n--- Chat ---");
  const result = await sendChat("你好！");
  console.log(`  Response: ${result.response}`);
  console.log(`  Emotion: ${result.emotion}`);

  console.log("\n--- Stream Chat ---");
  process.stdout.write("  ");
  for await (const token of streamChat("今天天气怎么样？")) {
    process.stdout.write(token);
  }
  console.log();

  console.log("\n--- Status ---");
  const status = await getStatus();
  console.log(`  Mock mode: ${status.mock_mode}`);
  console.log(`  Uptime: ${(status.uptime || 0).toFixed(1)}s`);
}

main().catch(console.error);
