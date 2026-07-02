import asyncio
import random
import logging
import time
from enum import Enum
from typing import Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field

from interfaces import AgentInterface

log = logging.getLogger("lumina.neuro")


class StreamState(Enum):
    IDLE = "idle"
    WARMUP = "warmup"
    INTERACTION = "interaction"
    PERFORMANCE = "performance"
    GOODBYE = "goodbye"


@dataclass
class LiveEvent:
    type: str
    viewer: str
    content: Optional[str] = None
    value: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ViewerProfile:
    name: str
    mood: float = 0.5
    loyalty: float = field(default_factory=lambda: random.uniform(0.0, 0.3))
    activity_level: float = field(default_factory=lambda: random.uniform(0.1, 1.0))
    messages: List[str] = field(default_factory=list)
    gifts_sent: int = 0
    is_following: bool = False


DANMAKU_TEMPLATES = [
    "你好！今天做什么？", "好可爱！", "唱首歌吧~",
    "讲个故事？", "主播加油！", "哈哈哈哈", "太棒了！",
    "这个有意思", "再来一个", "111",
    "来了来了", "前排围观", "主播好美", "笑死我了",
]

PROACTIVE_TEMPLATES = [
    "大家晚上好呀！今天心情特别好~",
    "嗯…我刚刚在想，要不要给大家唱首歌？",
    "诶，你们听说了吗？最近有个很有趣的新闻。",
    "好安静呀，大家怎么都不说话？那我先讲个笑话吧！",
    "外面下雨了，你们那边呢？",
    "我刚刚学会了一个新技能，想看看吗？",
]

GIFT_TABLE = {
    "小星星": 1.0, "花花": 5.0, "点赞": 0.5, "比心": 2.0,
    "跑车": 100.0, "火箭": 500.0, "城堡": 1000.0,
}
GIFT_NAMES = list(GIFT_TABLE.keys())

EVENT_TYPES = ["danmaku", "gift", "follow", "enter", "leave", None]
EVENT_WEIGHTS = [0.35, 0.05, 0.05, 0.15, 0.02, 0.38]

STATE_DURATIONS = {
    StreamState.IDLE: 0,
    StreamState.WARMUP: (20, 40),
    StreamState.INTERACTION: (90, 180),
    StreamState.PERFORMANCE: (60, 120),
    StreamState.GOODBYE: (20, 40),
}

STATE_FLOW = {
    StreamState.WARMUP: StreamState.INTERACTION,
    StreamState.INTERACTION: StreamState.PERFORMANCE,
    StreamState.PERFORMANCE: StreamState.INTERACTION,
    StreamState.GOODBYE: StreamState.IDLE,
}


class NeuroEngine:
    def __init__(self, config: Dict, agent: AgentInterface):
        self.cfg = config
        self.agent = agent
        self.active = False
        self.state = StreamState.IDLE
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.viewers: Dict[str, ViewerProfile] = {}
        self._load_viewers()
        self._event_processor_task: Optional[asyncio.Task] = None
        self._simulation_task: Optional[asyncio.Task] = None
        self._state_machine_task: Optional[asyncio.Task] = None
        self._proactive_task: Optional[asyncio.Task] = None
        self.on_utterance: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_event: Optional[Callable[[LiveEvent], Awaitable[None]]] = None
        self.proactive_templates = list(PROACTIVE_TEMPLATES)
        self.gift_table = dict(GIFT_TABLE)
        self.gift_names = list(self.gift_table.keys())
        self.state_durations = dict(STATE_DURATIONS)

    def _load_viewers(self):
        names = [
            "Alice", "Bob", "Charlie", "Diana", "Eve",
            "Frank", "Grace", "Henry", "Ivy", "Jack",
            "Kevin", "Lisa", "Mike", "Nancy", "Oscar",
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
        self._proactive_task = asyncio.create_task(self._proactive_loop())
        log.info("NeuroEngine started")

    async def stop(self):
        self.active = False
        self.state = StreamState.GOODBYE
        for task in (self._event_processor_task, self._simulation_task,
                     self._state_machine_task, self._proactive_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, StopAsyncIteration):
                    pass
        self.state = StreamState.IDLE
        log.info("NeuroEngine stopped")

    async def _proactive_loop(self):
        interval = self.cfg.get("proactive_interval", 30)
        await asyncio.sleep(interval)
        active_states = (StreamState.INTERACTION, StreamState.PERFORMANCE)
        while self.active:
            if self.state in active_states:
                content = random.choice(self.proactive_templates)
                if self.on_utterance:
                    try:
                        await self.on_utterance(content)
                    except Exception as e:
                        log.error(f"Proactive utterance error: {e}")
            await asyncio.sleep(interval)

    async def _simulation_loop(self):
        active_states = (StreamState.INTERACTION, StreamState.PERFORMANCE, StreamState.WARMUP)
        while self.active:
            if self.state in active_states and self.viewers:
                await self._simulate_audience_behavior()
            await asyncio.sleep(random.uniform(1.5, 4.0))

    async def _simulate_audience_behavior(self):
        viewer = random.choice(list(self.viewers.values()))
        viewer.mood = max(0.0, min(1.0, viewer.mood + random.uniform(-0.08, 0.12)))
        viewer.loyalty += random.uniform(0, 0.01)

        event_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]
        if event_type is None:
            return

        event = LiveEvent(type=event_type, viewer=viewer.name)

        match event_type:
            case "danmaku":
                event.content = random.choice(DANMAKU_TEMPLATES)
                viewer.messages.append(event.content)
            case "gift":
                gift_name = random.choice(self.gift_names)
                event.content = gift_name
                event.value = self.gift_table.get(gift_name, 5.0)
                viewer.gifts_sent += 1
            case "follow" if not viewer.is_following:
                viewer.is_following = True
                event.content = f"{viewer.name} followed the stream!"
            case "enter":
                viewer.mood = max(viewer.mood, 0.5)
            case "leave":
                viewer.mood = min(viewer.mood, 0.3)

        await self.event_queue.put(event)
        if self.on_event:
            try:
                await self.on_event(event)
            except Exception as e:
                log.error(f"on_event callback error: {e}")

    async def _process_events(self):
        while self.active:
            try:
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                match event.type:
                    case "danmaku" if self.cfg.get("auto_reply", True):
                        response = await self.agent.run_task_async(
                            f"[Audience {event.viewer}]: {event.content}\n"
                            f"Respond naturally as a live stream host talking to the viewer.",
                            agent_name="stream",
                        )
                    case "gift" if event.value and event.value >= 100:
                        response = await self.agent.run_task_async(
                            f"[Gift] {event.viewer} sent {event.content} (value: {event.value})!\n"
                            f"Thank the viewer enthusiastically!",
                            agent_name="stream",
                        )
                    case _:
                        continue

                if self.on_utterance:
                    await self.on_utterance(response)
            except Exception as e:
                log.error(f"Event processing error: {e}")

    async def _state_machine_loop(self):
        while self.active:
            dur_range = self.state_durations.get(self.state, (60, 60))
            duration = random.uniform(*dur_range) if isinstance(dur_range, tuple) else dur_range
            log.info(f"Stream state: {self.state.value} (next in {duration:.0f}s)")
            try:
                await asyncio.sleep(duration)
            except asyncio.CancelledError:
                break
            if not self.active:
                break

            next_state = STATE_FLOW.get(self.state)
            if next_state:
                self.state = next_state
                try:
                    script = await self.agent.generate_stream_script({
                        "scene": self.state.value,
                        "viewers": len(self.viewers),
                        "active_viewers": sum(1 for v in self.viewers.values() if v.mood > 0.3),
                        "total_messages": sum(len(v.messages) for v in self.viewers.values()),
                    })
                    if script and self.on_utterance:
                        for line in script.lines[:5]:
                            await self.on_utterance(line)
                            await asyncio.sleep(2.0)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error(f"State transition script error: {e}")

    async def generate_live_script(self) -> str:
        context = {
            "state": self.state.value,
            "viewer_count": len(self.viewers),
            "follower_count": sum(1 for v in self.viewers.values() if v.is_following),
            "average_mood": sum(v.mood for v in self.viewers.values()) / max(len(self.viewers), 1),
        }
        script = await self.agent.generate_stream_script(context)
        return "\n".join(script.lines[:10])

    async def get_status(self) -> Dict:
        return {
            "active": self.active,
            "state": self.state.value,
            "viewer_count": len(self.viewers),
            "followers": sum(1 for v in self.viewers.values() if v.is_following),
            "total_gifts": sum(v.gifts_sent for v in self.viewers.values()),
            "total_messages": sum(len(v.messages) for v in self.viewers.values()),
            "average_mood": sum(v.mood for v in self.viewers.values()) / max(len(self.viewers), 1),
            "event_queue_size": self.event_queue.qsize(),
        }
