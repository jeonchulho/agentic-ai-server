"""
Translation agent using LangChain.
"""
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from app.config import get_settings

settings = get_settings()


class TranslateAgent:
    """Agent for text translation."""
    
    LANGUAGE_NAMES = {
        "en": "English",
        "ko": "Korean",
        "ja": "Japanese",
        "zh": "Chinese",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "ru": "Russian",
        "ar": "Arabic",
        "pt": "Portuguese"
    }
    
    def __init__(self):
        """Initialize translation agent."""
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.3,  # Lower temperature for more consistent translations
            api_key=settings.OPENAI_API_KEY
        )
        self._setup_chain()
    
    def _setup_chain(self):
        """Setup LangChain chain for translation."""
        translation_template = """
        Translate the following text from {source_language} to {target_language}.
        Maintain the original meaning, tone, and context as much as possible.
        
        Text to translate:
        {text}
        
        Translation:
        """
        self.translation_prompt = PromptTemplate(
            input_variables=["text", "source_language", "target_language"],
            template=translation_template
        )
        self.translation_chain = LLMChain(
            llm=self.llm,
            prompt=self.translation_prompt
        )
    
    def _get_language_name(self, code: str) -> str:
        """Get full language name from code."""
        return self.LANGUAGE_NAMES.get(code.lower(), code)
    
    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> Dict[str, Any]:
        """
        Translate text from source language to target language.
        
        Args:
            text: Text to translate
            source_language: Source language code (e.g., 'en', 'ko')
            target_language: Target language code (e.g., 'en', 'ko')
            
        Returns:
            Dictionary with translation and metadata
        """
        try:
            source_lang_name = self._get_language_name(source_language)
            target_lang_name = self._get_language_name(target_language)
            
            result = await self.translation_chain.arun(
                text=text,
                source_language=source_lang_name,
                target_language=target_lang_name
            )
            
            return {
                "source_text": text,
                "translated_text": result.strip(),
                "source_language": source_language,
                "target_language": target_language,
                "success": True
            }
        except Exception as e:
            return {
                "source_text": text,
                "translated_text": "",
                "source_language": source_language,
                "target_language": target_language,
                "error": str(e),
                "success": False
            }
    
    async def detect_and_translate(
        self,
        text: str,
        target_language: str
    ) -> Dict[str, Any]:
        """
        Detect source language and translate to target language.
        
        Args:
            text: Text to translate
            target_language: Target language code
            
        Returns:
            Dictionary with translation and metadata
        """
        # Use LLM to detect source language
        detect_template = """
        Detect the language of the following text and respond with only the language name.
        
        Text:
        {text}
        
        Language:
        """
        detect_prompt = PromptTemplate(
            input_variables=["text"],
            template=detect_template
        )
        detect_chain = LLMChain(llm=self.llm, prompt=detect_prompt)
        
        try:
            detected_lang = await detect_chain.arun(text=text)
            detected_lang = detected_lang.strip().lower()
            
            # Try to find language code
            source_code = None
            for code, name in self.LANGUAGE_NAMES.items():
                if name.lower() in detected_lang:
                    source_code = code
                    break
            
            if not source_code:
                source_code = "auto"
            
            return await self.translate(text, source_code, target_language)
        except Exception as e:
            return {
                "source_text": text,
                "translated_text": "",
                "source_language": "unknown",
                "target_language": target_language,
                "error": str(e),
                "success": False
            }


# Global agent instance
translate_agent = TranslateAgent()
