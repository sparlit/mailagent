import time
import logging
import random
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Orchestrator")

class Agent:
    def __init__(self, name, role="Agent"):
        self.name = name
        self.role = role

    def perform_task(self, task):
        logger.info(f"[{self.role}] {self.name} is executing: {task}")
        time.sleep(0.1) # Simulate work

class Team:
    def __init__(self, team_id, leader_name):
        self.team_id = team_id
        self.leader = Agent(leader_name, role="Team Leader")
        self.agents = [Agent(f"Agent-{team_id}-{i}") for i in range(1, 4)]
        self.sub_agents = [Agent(f"SubAgent-{team_id}-{i}", role="Sub-Agent") for i in range(1, 7)]
        logger.info(f"Team {team_id} created with Leader {leader_name}, 3 Agents, and 6 Sub-Agents.")

    def run_task(self, task_description):
        logger.info(f"[Team {self.team_id}] Leader {self.leader.name} received task: {task_description}")
        # Delegate to agents and sub-agents
        for i, agent in enumerate(self.agents):
            agent.perform_task(f"{task_description} (Part A-{i+1})")
        for i, sub_agent in enumerate(self.sub_agents):
            sub_agent.perform_task(f"{task_description} (Part B-{i+1})")

        # TL might request more agents (simulated)
        if random.random() < 0.1:
            logger.info(f"[Team {self.team_id}] Leader {self.leader.name} is requesting more resources to improve efficiency.")
            return True # Indicates resource request
        return False

class ProjectManager:
    def __init__(self, name):
        self.name = name
        self.teams = []
        logger.info(f"Project Manager {name} initialized.")

    def create_teams(self, count):
        for i in range(1, count + 1):
            self.teams.append(Team(i, f"Leader-{i}"))

    def assign_tasks(self, tasks):
        for task in tasks:
            for team in self.teams:
                request_made = team.run_task(task)
                if request_made:
                    logger.info(f"[Project Manager] {self.name} reviewing and fulfilling resource request from Team {team.team_id}.")

class CEO:
    def __init__(self, name):
        self.name = name
        self.pm = ProjectManager("PM-Alice")
        logger.info(f"CEO {name} is active.")

    def start_project(self):
        logger.info(f"CEO {self.name} assigning Project: Autonomous Mail Agent to PM.")
        self.pm.create_teams(2) # Creating 2 teams as requested (Multiple teams)

        tasks = [
            "Step 1: Analyse and identify gaps/blind spots",
            "Step 2: Fix all gaps and blind spots",
            "Step 3: Continuous improving and enhancing",
            "Step 4: Add features (No removals)",
            "Step 5: Analyse further improvements",
            "Step 6: Suggest improvements/functions",
            "Step 7: Continuous Codebase Improvement",
            "Step 8: Document all processes (README, Summary, HowTo)",
        ]

        iteration = 1
        while True:
            logger.info(f"--- Iteration {iteration} Starting ---")
            self.pm.assign_tasks(tasks)
            logger.info(f"--- Iteration {iteration} Completed. Repeating loop (Step 9) ---")
            iteration += 1
            time.sleep(5) # Delay between iterations for simulation purposes

if __name__ == "__main__":
    ceo = CEO("CEO-Jules")
    try:
        ceo.start_project()
    except KeyboardInterrupt:
        logger.info("Project cancelled by CEO.")
