"""
Summarization agent using LangChain.
"""
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from app.config import get_settings

settings = get_settings()


class SummarizeAgent:
    """Agent for text and document summarization."""
    
    def __init__(self):
        """Initialize summarization agent."""
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY
        )
        self._setup_chains()
    
    def _setup_chains(self):
        """Setup LangChain chains for summarization."""
        # Text summarization prompt
        text_summary_template = """
        Please provide a concise summary of the following text.
        The summary should capture the main points and key information.
        
        Text to summarize:
        {text}
        
        Summary:
        """
        self.text_summary_prompt = PromptTemplate(
            input_variables=["text"],
            template=text_summary_template
        )
        self.text_summary_chain = LLMChain(
            llm=self.llm,
            prompt=self.text_summary_prompt
        )
        
        # Document summarization prompt (with length constraint)
        doc_summary_template = """
        Please provide a summary of the following document content.
        Focus on the main themes, key points, and important information.
        {length_instruction}
        
        Document content:
        {text}
        
        Summary:
        """
        self.doc_summary_prompt = PromptTemplate(
            input_variables=["text", "length_instruction"],
            template=doc_summary_template
        )
        self.doc_summary_chain = LLMChain(
            llm=self.llm,
            prompt=self.doc_summary_prompt
        )
    
    async def summarize_text(
        self,
        text: str,
        max_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Summarize plain text.
        
        Args:
            text: Text to summarize
            max_length: Optional maximum length for summary
            
        Returns:
            Dictionary with summary and metadata
        """
        try:
            if max_length:
                length_instruction = f"Keep the summary under {max_length} words."
                result = await self.doc_summary_chain.arun(
                    text=text,
                    length_instruction=length_instruction
                )
            else:
                result = await self.text_summary_chain.arun(text=text)
            
            return {
                "summary": result.strip(),
                "original_length": len(text),
                "summary_length": len(result.strip()),
                "success": True
            }
        except Exception as e:
            return {
                "summary": "",
                "error": str(e),
                "success": False
            }
    
    async def summarize_document(
        self,
        content: str,
        filename: str,
        max_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Summarize document content.
        
        Args:
            content: Document content to summarize
            filename: Name of the document
            max_length: Optional maximum length for summary
            
        Returns:
            Dictionary with summary and metadata
        """
        length_instruction = ""
        if max_length:
            length_instruction = f"Keep the summary under {max_length} words."
        else:
            length_instruction = "Provide a comprehensive summary."
        
        try:
            result = await self.doc_summary_chain.arun(
                text=content,
                length_instruction=length_instruction
            )
            
            return {
                "filename": filename,
                "summary": result.strip(),
                "original_length": len(content),
                "summary_length": len(result.strip()),
                "success": True
            }
        except Exception as e:
            return {
                "filename": filename,
                "summary": "",
                "error": str(e),
                "success": False
            }
    
    async def summarize_multiple(
        self,
        texts: list[str],
        max_length: Optional[int] = None
    ) -> list[Dict[str, Any]]:
        """
        Summarize multiple texts.
        
        Args:
            texts: List of texts to summarize
            max_length: Optional maximum length for each summary
            
        Returns:
            List of summaries with metadata
        """
        summaries = []
        for text in texts:
            summary = await self.summarize_text(text, max_length)
            summaries.append(summary)
        return summaries


# Global agent instance
summarize_agent = SummarizeAgent()
