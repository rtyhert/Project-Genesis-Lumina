import asyncio
import random
import logging

log = logging.getLogger("upage.neuro")

class NeuroEngine:
    def __init__(self, config, crew_manager):
        self.cfg = config
        self.crew = crew_manager
        self.audience_size = config.get("audience_size", 10)
        self.auto_reply = config.get("auto_reply", True)
        self.active = False
        self.viewers = self._spawn_viewers()

    def _spawn_viewers(self):
        names = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
        return {n: {"mood": 0.5, "messages": []} for n in names[:self.audience_size]}

    async def run_stream_loop(self, on_utterance):
        self.active = True
        while self.active:
            viewer_msg = self._simulate_chat()
            if viewer_msg and self.auto_reply:
                response = self.crew.run_crew(
                    f"[Audience] {viewer_msg}", agent_name="stream"
                )
                await on_utterance(response)
            await asyncio.sleep(random.uniform(3.0, 8.0))

    def _simulate_chat(self):
        if not self.viewers:
            return None
        viewer = random.choice(list(self.viewers.keys()))
        templates = [
            "你好！今天做什么？",
            "好可爱！",
            "唱首歌吧~",
            "讲个故事？",
            "主播加油！",
        ]
        msg = random.choice(templates)
        self.viewers[viewer]["messages"].append(msg)
        log.info(f"[{viewer}] {msg}")
        return f"{viewer}: {msg}"

    def stop(self):
        self.active = False
