import json
import re
import logging
from typing import Dict, List, Optional, Any

from crewai import Agent, Task, Crew, Process
from pydantic import BaseModel, Field

log = logging.getLogger("lumina.crew")


class ChatOutput(BaseModel):
    response: str = Field(description="The chat response text")
    emotion: str = Field(description="Detected emotion: happy/sad/angry/surprised/fearful/disgusted/neutral")
    action: Optional[str] = Field(default=None, description="Suggested action")


class StreamScript(BaseModel):
    scene: str = Field(description="Scene name")
    lines: List[str] = Field(description="Script lines to deliver")
    duration_seconds: int = Field(description="Estimated duration in seconds")
    interaction_prompt: Optional[str] = Field(default=None, description="Prompt to engage audience")


class InteractionPlan(BaseModel):
    steps: List[str] = Field(description="Step-by-step interaction plan")
    expected_outcome: str = Field(description="Expected outcome")
    fallback: str = Field(description="Fallback if plan fails")


class CrewManager:
    def __init__(self, config: Dict, llm_service):
        self.cfg = config
        self.llm = llm_service
        self.agents: Dict[str, Agent] = {}
        self._create_agents()

    def _create_agents(self):
        self.agents["chat"] = Agent(
            role="Virtual Human Chat Agent",
            goal="Engage in natural, empathetic conversation with users, "
                 "detecting emotional cues and responding appropriately",
            backstory=(
                "You are a friendly, emotionally-aware virtual companion "
                "who understands user feelings and responds in a warm, natural way."
            ),
            verbose=self.cfg.get("verbose", False),
            allow_delegation=False,
            max_iter=self.cfg.get("max_iterations", 5),
        )
        self.agents["stream"] = Agent(
            role="Live Stream Host",
            goal="Keep the audience engaged with dynamic, entertaining commentary, "
                 "manage live atmosphere, and handle viewer interactions",
            backstory=(
                "You are an energetic and charismatic live stream host "
                "who interacts with viewers naturally and keeps the show engaging."
            ),
            verbose=self.cfg.get("verbose", False),
            allow_delegation=True,
            max_iter=self.cfg.get("max_iterations", 5),
        )
        self.agents["planner"] = Agent(
            role="Interaction Planner",
            goal="Plan multi-step interactions, design engagement strategies, "
                 "and coordinate responses across different scenarios",
            backstory=(
                "You are a strategic interaction designer who plans complex "
                "task sequences and ensures smooth, natural conversations."
            ),
            verbose=self.cfg.get("verbose", False),
            allow_delegation=True,
            max_iter=self.cfg.get("max_iterations", 8),
        )

    def create_task(
        self,
        description: str,
        agent_name: str = "chat",
        expected_output: str = "A complete response string",
        context: Optional[List[Task]] = None,
    ) -> Task:
        return Task(
            description=description,
            agent=self.agents[agent_name],
            expected_output=expected_output,
            context=context,
        )

    def run_task(self, task_description: str, agent_name: str = "chat") -> str:
        task = self.create_task(task_description, agent_name)
        crew = Crew(
            agents=[self.agents[agent_name]],
            tasks=[task],
            verbose=self.cfg.get("verbose", False),
            process=Process.sequential,
        )
        result = crew.kickoff()
        return str(result)

    def run_chained_tasks(self, tasks_config: List[Dict]) -> List[str]:
        results = []
        previous_tasks = []

        for i, task_cfg in enumerate(tasks_config):
            agent_name = task_cfg.get("agent", "chat")
            task = Task(
                description=task_cfg["description"],
                agent=self.agents[agent_name],
                expected_output=task_cfg.get("expected_output", "A response"),
                context=list(previous_tasks) if previous_tasks else None,
            )
            crew = Crew(
                agents=[self.agents[agent_name]],
                tasks=[task],
                verbose=self.cfg.get("verbose", False),
                process=Process.sequential,
            )
            result = crew.kickoff()
            result_str = str(result)
            results.append(result_str)
            previous_tasks.append(task)

        return results

    async def chat_with_emotion(self, user_input: str, history: Optional[List[Dict]] = None) -> ChatOutput:
        history_text = ""
        if history:
            history_text = "\n".join(
                f"[{m.get('role', 'user')}]: {m.get('content', '')}"
                for m in history[-5:]
            )

        prompt = (
            f"Conversation history:\n{history_text}\n"
            f"User: {user_input}\n"
            "Respond naturally. End with [emotion:<emotion_name>] tag "
            "and optionally [action:<action_name>] tag.\n"
            "Available emotions: happy, sad, angry, surprised, fearful, disgusted, neutral\n"
            "Available actions: smile, laugh, cheer, wave, sigh, frown, nod, blink"
        )

        response = self.run_task(prompt, agent_name="chat")

        emotion = "neutral"
        emotion_match = re.search(r'\[emotion:(\w+)\]', response)
        if emotion_match:
            emotion = emotion_match.group(1)

        action = None
        action_match = re.search(r'\[action:(\w+)\]', response)
        if action_match:
            action = action_match.group(1)

        clean_response = re.sub(r'\[emotion:\w+\]\s*', '', response)
        clean_response = re.sub(r'\[action:\w+\]\s*', '', clean_response).strip()

        return ChatOutput(response=clean_response, emotion=emotion, action=action)

    async def generate_stream_script(self, context: Dict) -> StreamScript:
        prompt = (
            f"Generate a live stream script segment based on context:\n"
            f"{json.dumps(context, ensure_ascii=False)}\n"
            "Output format:\n"
            "scene=<scene_name>\n"
            "- line 1\n"
            "- line 2\n"
            "duration=<seconds>\n"
            "interaction_prompt=<prompt>"
        )

        response = self.run_task(prompt, agent_name="stream")

        try:
            scene = "interaction"
            scene_match = re.search(r'scene=(\w+)', response)
            if scene_match:
                scene = scene_match.group(1)

            lines = [l.strip("- ").strip() for l in response.split("\n")
                     if l.strip().startswith("- ")]

            duration = len(lines) * 10
            dur_match = re.search(r'duration=(\d+)', response)
            if dur_match:
                duration = int(dur_match.group(1))

            interaction_prompt = None
            ip_match = re.search(r'interaction_prompt=(.+)', response)
            if ip_match:
                interaction_prompt = ip_match.group(1).strip()

            if not lines:
                lines = [response]

            return StreamScript(
                scene=scene,
                lines=lines[:10],
                duration_seconds=duration,
                interaction_prompt=interaction_prompt,
            )
        except Exception as e:
            log.error(f"Failed to parse stream script: {e}")
            return StreamScript(
                scene="fallback",
                lines=[response],
                duration_seconds=30,
                interaction_prompt=None,
            )

    async def plan_interaction(self, goal: str, context: Dict) -> InteractionPlan:
        prompt = (
            f"Plan an interaction to achieve this goal: {goal}\n"
            f"Context: {json.dumps(context, ensure_ascii=False)}\n\n"
            "Provide:\n"
            "1. Steps (numbered list)\n"
            "2. Expected outcome\n"
            "3. Fallback plan"
        )

        response = self.run_task(prompt, agent_name="planner")

        steps = [l.strip("- ").strip() for l in response.split("\n")
                 if l.strip().startswith("- ") or re.match(r'^\d+[\.\)]', l.strip())]
        if not steps:
            steps = ["Acknowledge user", "Respond appropriately", "Confirm understanding"]

        return InteractionPlan(
            steps=steps,
            expected_outcome="Goal achieved",
            fallback="Apologize and ask for clarification",
        )
