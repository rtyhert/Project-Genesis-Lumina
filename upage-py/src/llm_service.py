import logging
from typing import Optional

log = logging.getLogger("upage.llm")

class LLMService:
    def __init__(self, config):
        self.cfg = config
        self.provider = config.get("provider", "openai")
        self.model = config.get("model", "gpt-4")

    async def chat(self, prompt: str, system: Optional[str] = None) -> str:
        log.info(f"LLM[{self.model}]: {prompt[:60]}...")
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI()
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.cfg.get("temperature", 0.7),
                max_tokens=self.cfg.get("max_tokens", 1024),
            )
            return resp.choices[0].message.content or ""
        except ImportError:
            return f"[Mock] Processed: {prompt}"

    async def stream_chat(self, prompt: str):
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI()
            stream = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except ImportError:
            yield f"[Mock stream] {prompt}"
