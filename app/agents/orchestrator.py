"""
LangGraph orchestrator for coordinating multiple agents.
"""
from typing import Dict, Any, List, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from app.config import get_settings

settings = get_settings()


class AgentState(TypedDict):
    """State shared between agents in the graph."""
    task_type: str
    input_data: Dict[str, Any]
    output: Dict[str, Any]
    error: str | None
    completed: bool


class AgentOrchestrator:
    """Orchestrator for managing multiple AI agents using LangGraph."""
    
    def __init__(self):
        """Initialize orchestrator with LLM."""
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            api_key=settings.OPENAI_API_KEY
        )
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the agent workflow graph."""
        workflow = StateGraph(AgentState)
        
        # Add nodes for different agent types
        workflow.add_node("router", self._route_task)
        workflow.add_node("summarize", self._summarize_task)
        workflow.add_node("translate", self._translate_task)
        workflow.add_node("document", self._document_task)
        workflow.add_node("analyze", self._analyze_task)
        workflow.add_node("complete", self._complete_task)
        
        # Define edges
        workflow.set_entry_point("router")
        
        # Conditional routing based on task type
        workflow.add_conditional_edges(
            "router",
            self._determine_next_node,
            {
                "summarize": "summarize",
                "translate": "translate",
                "document": "document",
                "analyze": "analyze",
                "end": END
            }
        )
        
        # All tasks go to complete
        workflow.add_edge("summarize", "complete")
        workflow.add_edge("translate", "complete")
        workflow.add_edge("document", "complete")
        workflow.add_edge("analyze", "complete")
        workflow.add_edge("complete", END)
        
        return workflow.compile()
    
    def _route_task(self, state: AgentState) -> AgentState:
        """Route task to appropriate agent."""
        return state
    
    def _determine_next_node(self, state: AgentState) -> str:
        """Determine which node to execute next based on task type."""
        task_type = state.get("task_type", "")
        
        if task_type == "summarize":
            return "summarize"
        elif task_type == "translate":
            return "translate"
        elif task_type == "document":
            return "document"
        elif task_type == "analyze":
            return "analyze"
        else:
            return "end"
    
    def _summarize_task(self, state: AgentState) -> AgentState:
        """Handle summarization task."""
        # This will be delegated to summarize_agent
        return state
    
    def _translate_task(self, state: AgentState) -> AgentState:
        """Handle translation task."""
        # This will be delegated to translate_agent
        return state
    
    def _document_task(self, state: AgentState) -> AgentState:
        """Handle document processing task."""
        # This will be delegated to document_agent
        return state
    
    def _analyze_task(self, state: AgentState) -> AgentState:
        """Handle analysis task."""
        # This will be delegated to analysis_agent
        return state
    
    def _complete_task(self, state: AgentState) -> AgentState:
        """Mark task as completed."""
        state["completed"] = True
        return state
    
    async def execute(self, task_type: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task using agent workflow.
        
        Args:
            task_type: Type of task to execute
            input_data: Input data for the task
            
        Returns:
            Task execution result
        """
        initial_state: AgentState = {
            "task_type": task_type,
            "input_data": input_data,
            "output": {},
            "error": None,
            "completed": False
        }
        
        # Execute workflow
        result = await self.graph.ainvoke(initial_state)
        
        return result.get("output", {})


# Global orchestrator instance
orchestrator = AgentOrchestrator()
