import os

from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import (
	ScrapeWebsiteTool,
	SerperDevTool,
	FileReadTool
)






@CrewBase
class Project132kvSolarConnectionFeasibilityAnalyzerCrew:
    """Project132kvSolarConnectionFeasibilityAnalyzer crew"""

    agents_config = os.path.join(os.path.dirname(__file__), 'config', 'agents.yaml')
    tasks_config = os.path.join(os.path.dirname(__file__), 'config', 'tasks.yaml')

    
    @agent
    def medium_voltage_substation_data_specialist(self) -> Agent:
        
        
        return Agent(
            config=self.agents_config["medium_voltage_substation_data_specialist"],
            
            
            tools=[				ScrapeWebsiteTool(),
				SerperDevTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                
                
            ),
            
        )
        
    
    @agent
    def medium_voltage_grid_integration_analyst(self) -> Agent:
        
        
        return Agent(
            config=self.agents_config["medium_voltage_grid_integration_analyst"],
            
            
            tools=[				FileReadTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                
                
            ),
            
        )
        
    
    @agent
    def medium_voltage_solar_connection_expert(self) -> Agent:
        
        
        return Agent(
            config=self.agents_config["medium_voltage_solar_connection_expert"],
            
            
            tools=[				SerperDevTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                
                
            ),
            
        )
        
    
    @agent
    def medium_voltage_infrastructure_tracker(self) -> Agent:
        
        
        return Agent(
            config=self.agents_config["medium_voltage_infrastructure_tracker"],
            
            
            tools=[				ScrapeWebsiteTool(),
				SerperDevTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                
                
            ),
            
        )
        
    

    
    @task
    def scrape_132kv_substation_data(self) -> Task:
        return Task(
            config=self.tasks_config["scrape_132kv_substation_data"],
            markdown=False,
            
            
        )
    
    @task
    def analyze_132kv_infrastructure_development_plans(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_132kv_infrastructure_development_plans"],
            markdown=False,
            
            
        )
    
    @task
    def analyze_132kv_technical_connection_parameters(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_132kv_technical_connection_parameters"],
            markdown=False,
            
            
        )
    
    @task
    def assess_132kv_solar_project_connection_feasibility(self) -> Task:
        return Task(
            config=self.tasks_config["assess_132kv_solar_project_connection_feasibility"],
            markdown=False,
            
            
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the Project132kvSolarConnectionFeasibilityAnalyzer crew"""

        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,

            
        )


