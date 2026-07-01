from crewai import Agent, Task, Crew, Process

class CrewManager:
    def __init__(self, config, llm_service):
        self.cfg = config
        self.llm = llm_service
        self.agents = {}
        self._create_agents()

    def _create_agents(self):
        self.agents["chat"] = Agent(
            role="Virtual Human Chat Agent",
            goal="Engage in natural, empathetic conversation",
            backstory="You are a friendly virtual companion",
            verbose=self.cfg["verbose"],
            allow_delegation=False,
        )
        self.agents["stream"] = Agent(
            role="Live Stream Host",
            goal="Keep the audience engaged with dynamic commentary",
            backstory="You are an energetic live stream host",
            verbose=self.cfg["verbose"],
            allow_delegation=True,
        )
        self.agents["planner"] = Agent(
            role="Interaction Planner",
            goal="Plan multi-step interactions and responses",
            backstory="You coordinate complex task sequences",
            verbose=self.cfg["verbose"],
            allow_delegation=True,
        )

    def create_task(self, description, agent_name="chat"):
        return Task(
            description=description,
            agent=self.agents[agent_name],
            expected_output="A complete response string with emotion tag",
        )

    def run_crew(self, task_description: str, agent_name: str = "chat") -> str:
        task = self.create_task(task_description, agent_name)
        crew = Crew(
            agents=[self.agents[agent_name]],
            tasks=[task],
            verbose=self.cfg["verbose"],
            process=Process.sequential,
            max_iterations=self.cfg["max_iterations"],
        )
        result = crew.kickoff()
        return result
