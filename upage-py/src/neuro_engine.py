import asyncio
import random
import logging
import time
from enum import Enum
from typing import Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field

log = logging.getLogger("upage.neuro")


class StreamState(Enum):
    IDLE = "idle"
    WARMUP = "warmup"
    INTERACTION = "interaction"
    PERFORMANCE = "performance"
    GOODBYE = "goodbye"


@dataclass
class LiveEvent:
    type: str  # danmaku, gift, follow, enter, leave
    viewer: str
    content: Optional[str] = None
    value: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ViewerProfile:
    name: str
    mood: float = 0.5
    loyalty: float = random.uniform(0.0, 0.3)
    activity_level: float = field(default_factory=lambda: random.uniform(0.1, 1.0))
    messages: List[str] = field(default_factory=list)
    gifts_sent: int = 0
    is_following: bool = False


DANMAKU_TEMPLATES = [
    "你好！今天做什么？", "好可爱！", "唱首歌吧~",
    "讲个故事？", "主播加油！", "哈哈哈", "太棒了！",
    "这个有意思", "再来一个", "666", "111",
    "来了来了", "前排围观", "主播好美", "笑死我了",
    "好听！", "好专业！", "爱了爱了", "已关注",
]

GIFT_TABLE = {
    "小星星": 1.0,
    "花花": 5.0,
    "点赞": 0.5,
    "比心": 2.0,
    "跑车": 100.0,
    "火箭": 500.0,
    "城堡": 1000.0,
}


class NeuroEngine:
    def __init__(self, config: Dict, crew_manager):
        self.cfg = config
        self.crew = crew_manager
        self.active = False
        self.state = StreamState.IDLE
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.viewers: Dict[str, ViewerProfile] = {}
        self._load_viewers()
        self._event_processor_task: Optional[asyncio.Task] = None
        self._simulation_task: Optional[asyncio.Task] = None
        self._state_machine_task: Optional[asyncio.Task] = None
        self.on_utterance: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_event: Optional[Callable[[LiveEvent], Awaitable[None]]] = None

    def _load_viewers(self):
        names = [
            "Alice", "Bob", "Charlie", "Diana", "Eve",
            "Frank", "Grace", "Henry", "Ivy", "Jack",
            "Kevin", "Lisa", "Mike", "Nancy", "Oscar",
            "Paul", "Quinn", "Rose", "Sam", "Tina",
        ]
        count = min(self.cfg.get("audience_size", 10), len(names))
        self.viewers = {n: ViewerProfile(name=n) for n in names[:count]}

    async def start(self):
        if self.active:
            log.warning("NeuroEngine already running")
            return
        self.active = True
        self.state = StreamState.WARMUP
        self._event_processor_task = asyncio.create_task(self._process_events())
        self._simulation_task = asyncio.create_task(self._simulation_loop())
        self._state_machine_task = asyncio.create_task(self._state_machine_loop())
        log.info("NeuroEngine started")

    async def stop(self):
        self.active = False
        self.state = StreamState.GOODBYE
        for task in [self._event_processor_task, self._simulation_task, self._state_machine_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.state = StreamState.IDLE
        log.info("NeuroEngine stopped")

    async def _simulation_loop(self):
        while self.active:
            if self.state in (StreamState.INTERACTION, StreamState.PERFORMANCE, StreamState.WARMUP):
                await self._simulate_audience_behavior()
            await asyncio.sleep(random.uniform(1.5, 4.0))

    async def _simulate_audience_behavior(self):
        if not self.viewers:
            return

        viewer = random.choice(list(self.viewers.values()))
        viewer.mood += random.uniform(-0.08, 0.12)
        viewer.mood = max(0.0, min(1.0, viewer.mood))
        viewer.loyalty += random.uniform(0, 0.01)

        event_type = random.choices(
            ["danmaku", "gift", "follow", "enter", "leave", None],
            weights=[0.35, 0.05, 0.05, 0.15, 0.02, 0.38],
            k=1,
        )[0]

        if event_type is None:
            return

        event = LiveEvent(
            type=event_type,
            viewer=viewer.name,
        )

        if event_type == "danmaku":
            event.content = random.choice(DANMAKU_TEMPLATES)
            viewer.messages.append(event.content)

        elif event_type == "gift":
            gift_name = random.choice(list(GIFT_TABLE.keys()))
            event.content = gift_name
            event.value = GIFT_TABLE[gift_name]
            viewer.gifts_sent += 1

        elif event_type == "follow":
            if not viewer.is_following:
                viewer.is_following = True
                event.content = f"{viewer.name} followed the stream!"

        elif event_type == "enter":
            viewer.mood = max(viewer.mood, 0.5)

        elif event_type == "leave":
            viewer.mood = min(viewer.mood, 0.3)

        await self.event_queue.put(event)

        if self.on_event:
            try:
                await self.on_event(event)
            except Exception as e:
                log.error(f"on_event callback error: {e}")

        log.debug(f"[{viewer.name}] {event_type}: {event.content or ''}")

    async def _process_events(self):
        while self.active:
            try:
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                if event.type == "danmaku" and self.cfg.get("auto_reply", True):
                    response = self.crew.run_task(
                        f"[Audience {event.viewer}]: {event.content}\n"
                        f"Respond naturally as a live stream host talking to the viewer.",
                        agent_name="stream",
                    )
                    if self.on_utterance:
                        await self.on_utterance(response)
                elif event.type == "gift" and event.value and event.value >= 100:
                    response = self.crew.run_task(
                        f"[Gift] {event.viewer} sent {event.content} (value: {event.value})!\n"
                        f"Thank the viewer enthusiastically!",
                        agent_name="stream",
                    )
                    if self.on_utterance:
                        await self.on_utterance(response)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Event processing error: {e}")

    async def _state_machine_loop(self):
        state_durations = {
            StreamState.IDLE: 0,
            StreamState.WARMUP: random.uniform(20, 40),
            StreamState.INTERACTION: random.uniform(90, 180),
            StreamState.PERFORMANCE: random.uniform(60, 120),
            StreamState.GOODBYE: random.uniform(20, 40),
        }

        state_flow = {
            StreamState.WARMUP: StreamState.INTERACTION,
            StreamState.INTERACTION: StreamState.PERFORMANCE,
            StreamState.PERFORMANCE: StreamState.INTERACTION,
        }

        while self.active:
            duration = state_durations.get(self.state, 60)
            log.info(f"Stream state: {self.state.value} (next in {duration:.0f}s)")
            await asyncio.sleep(duration)

            if not self.active:
                break

            next_state = state_flow.get(self.state)
            if next_state:
                self.state = next_state
                try:
                    script = await self.crew.generate_stream_script({
                        "scene": self.state.value,
                        "viewers": len(self.viewers),
                        "active_viewers": sum(1 for v in self.viewers.values() if v.mood > 0.3),
                        "total_messages": sum(len(v.messages) for v in self.viewers.values()),
                    })
                    if script and self.on_utterance:
                        for line in script.lines[:5]:
                            await self.on_utterance(line)
                            await asyncio.sleep(2.0)
                except Exception as e:
                    log.error(f"State transition script error: {e}")

    async def generate_live_script(self) -> str:
        context = {
            "state": self.state.value,
            "viewer_count": len(self.viewers),
            "follower_count": sum(1 for v in self.viewers.values() if v.is_following),
            "average_mood": sum(v.mood for v in self.viewers.values()) / max(len(self.viewers), 1),
        }
        script = await self.crew.generate_stream_script(context)
        return "\n".join(script.lines[:10])

    async def get_status(self) -> Dict:
        return {
            "active": self.active,
            "state": self.state.value,
            "viewer_count": len(self.viewers),
            "followers": sum(1 for v in self.viewers.values() if v.is_following),
            "total_gifts": sum(v.gifts_sent for v in self.viewers.values()),
            "total_messages": sum(len(v.messages) for v in self.viewers.values()),
            "average_mood": (
                sum(v.mood for v in self.viewers.values()) / max(len(self.viewers), 1)
            ),
            "event_queue_size": self.event_queue.qsize(),
        }
