"""
Data analysis agent for legacy database analysis.
"""
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from app.config import get_settings

settings = get_settings()


class AnalysisAgent:
    """Agent for analyzing legacy database data."""
    
    def __init__(self):
        """Initialize analysis agent."""
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY
        )
        self._setup_chains()
    
    def _setup_chains(self):
        """Setup LangChain chains for analysis."""
        # Data summary analysis prompt
        summary_template = """
        Analyze the following data and provide a comprehensive summary with key insights.
        
        Data type: {data_type}
        Number of records: {record_count}
        
        Sample data:
        {sample_data}
        
        Please provide:
        1. Overview of the data
        2. Key patterns or trends
        3. Notable insights
        4. Recommendations (if applicable)
        
        Analysis:
        """
        self.summary_prompt = PromptTemplate(
            input_variables=["data_type", "record_count", "sample_data"],
            template=summary_template
        )
        self.summary_chain = LLMChain(
            llm=self.llm,
            prompt=self.summary_prompt
        )
        
        # Insight extraction prompt
        insight_template = """
        Extract key insights from the following data.
        Focus on actionable information and important patterns.
        
        Data:
        {data}
        
        Key Insights:
        """
        self.insight_prompt = PromptTemplate(
            input_variables=["data"],
            template=insight_template
        )
        self.insight_chain = LLMChain(
            llm=self.llm,
            prompt=self.insight_prompt
        )
    
    async def analyze_data(
        self,
        data_type: str,
        records: List[Dict[str, Any]],
        max_samples: int = 10
    ) -> Dict[str, Any]:
        """
        Analyze legacy data and provide insights.
        
        Args:
            data_type: Type of data being analyzed
            records: List of data records
            max_samples: Maximum number of samples to include in analysis
            
        Returns:
            Dictionary with analysis results
        """
        try:
            record_count = len(records)
            
            # Sample data for analysis
            sample_records = records[:max_samples]
            sample_data = self._format_records(sample_records)
            
            result = await self.summary_chain.arun(
                data_type=data_type,
                record_count=record_count,
                sample_data=sample_data
            )
            
            return {
                "data_type": data_type,
                "record_count": record_count,
                "analysis": result.strip(),
                "success": True
            }
        except Exception as e:
            return {
                "data_type": data_type,
                "record_count": len(records),
                "analysis": "",
                "error": str(e),
                "success": False
            }
    
    async def extract_insights(self, data: str) -> Dict[str, Any]:
        """
        Extract key insights from data.
        
        Args:
            data: Data to analyze (as string)
            
        Returns:
            Dictionary with extracted insights
        """
        try:
            result = await self.insight_chain.arun(data=data)
            
            return {
                "insights": result.strip(),
                "success": True
            }
        except Exception as e:
            return {
                "insights": "",
                "error": str(e),
                "success": False
            }
    
    def _format_records(self, records: List[Dict[str, Any]]) -> str:
        """Format records for display in prompt."""
        formatted = []
        for i, record in enumerate(records, 1):
            record_str = f"Record {i}:\n"
            for key, value in record.items():
                record_str += f"  {key}: {value}\n"
            formatted.append(record_str)
        return "\n".join(formatted)
    
    async def summarize_legacy_data(
        self,
        data_type: str,
        records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Summarize legacy data of a specific type.
        
        Args:
            data_type: Type of legacy data (messages, chats, etc.)
            records: List of records
            
        Returns:
            Dictionary with summary
        """
        if not records:
            return {
                "data_type": data_type,
                "summary": f"No {data_type} data available.",
                "record_count": 0,
                "success": True
            }
        
        analysis = await self.analyze_data(data_type, records)
        
        return {
            "data_type": data_type,
            "summary": analysis.get("analysis", ""),
            "record_count": len(records),
            "success": analysis.get("success", False)
        }


# Global agent instance
analysis_agent = AnalysisAgent()
