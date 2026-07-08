"""Google Gemini API client wrapper implementing the ILLMProvider interface."""

import os
from typing import Any, Dict, List, Optional
from types import SimpleNamespace
from structlog import get_logger

from google import genai
from google.genai import types

from src.interfaces.llm import ILLMProvider, LLMClientError
from src.config.settings import get_settings

logger = get_logger(__name__)


class GeminiClientError(LLMClientError):
    """Google Gemini client exception."""
    pass


class AsyncGeminiClient(ILLMProvider):
    """Async Google Gemini API client wrapper."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Google Gemini API client.

        Args:
            api_key: Optional Gemini API key
            config: Optional config dictionary (keeps compatibility with router fallback config)
            trace_id: Optional trace ID
            metadata: Optional metadata dict
        """
        settings = get_settings()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or settings.gemini.api_key
        self.timeout = settings.gemini.timeout
        self.retry_attempts = settings.gemini.retry_attempts
        
        self._trace_id = trace_id
        self._metadata = metadata or {}

        # Fallback list config parsing (keeps compatibility with ModelRouter fallback configuration)
        self.fallback_models = []
        if config and "targets" in config:
            self.fallback_models = [t["model"] for t in config["targets"]]
            logger.info("GeminiClient: Configured with fallback list", models=self.fallback_models)

        if not self.api_key:
            raise GeminiClientError("GEMINI_API_KEY is not configured.")

        # Initialize the official Google GenAI Client
        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            raise GeminiClientError(f"Failed to initialize Gemini Client: {e}") from e

    def with_options(self, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> "AsyncGeminiClient":
        """Apply request-level options (trace ID, metadata) by returning a configured copy."""
        return AsyncGeminiClient(
            api_key=self.api_key,
            trace_id=trace_id or self._trace_id,
            metadata={**self._metadata, **(metadata or {})},
        )

    async def _execute_with_fallback(self, call_func, *args, **kwargs) -> Any:
        """Execute async LLM call with built-in model fallback list support."""
        models_to_try = []
        if "model" in kwargs:
            # Clean model name (remove Portkey prefixes like @openai/, @google/ if passed)
            kwargs["model"] = kwargs["model"].split("/")[-1].replace("@", "")
            models_to_try.append(kwargs["model"])
            
        # Add fallback models if configured
        for fb_model in self.fallback_models:
            fb_clean = fb_model.split("/")[-1].replace("@", "")
            if fb_clean not in models_to_try:
                models_to_try.append(fb_clean)

        if not models_to_try:
            # Default to gemini-2.5-pro
            models_to_try.append("gemini-2.5-pro")

        last_error = None
        for current_model in models_to_try:
            kwargs["model"] = current_model
            try:
                logger.info("Executing Gemini API Call", model=current_model, trace_id=self._trace_id)
                return await call_func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "Gemini API call failed, attempting next fallback model",
                    model=current_model,
                    error=str(e),
                )
                last_error = e

        raise GeminiClientError(f"All Gemini models failed. Last error: {last_error}") from last_error

    async def chat_completions_create(self, *args, **kwargs) -> Any:
        """
        Call Gemini generate content endpoint. Handles OpenAI chat completion argument structure.
        """
        async def _run(**call_kwargs):
            model = call_kwargs.get("model", "gemini-2.5-pro")
            messages = call_kwargs.get("messages", [])
            temperature = call_kwargs.get("temperature")
            max_tokens = call_kwargs.get("max_tokens")

            # Translate messages to Gemini SDK system instruction and contents structure
            system_instruction = None
            contents = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    system_instruction = content
                else:
                    gemini_role = "model" if role == "assistant" else "user"
                    contents.append(
                        types.Content(
                            role=gemini_role,
                            parts=[types.Part.from_text(text=content)]
                        )
                    )

            # Generate structured response config
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            # Check if JSON schema or output mode requested
            # Since canonicalization extracts JSON templates, we encourage json output
            if "response_format" in call_kwargs or any("json" in str(msg.get("content", "")).lower() for msg in messages):
                config.response_mime_type = "application/json"

            # Execute async generation call
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            # Check for safety blocks
            if response.candidates and response.candidates[0].finish_reason == "SAFETY":
                raise GeminiClientError("Gemini generation was blocked by safety settings.")

            text = response.text or ""
            
            # Return SimpleNamespace to mimic the OpenAI response shape (.choices[0].message.content)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=text
                        )
                    )
                ]
            )

        return await self._execute_with_fallback(_run, *args, **kwargs)

    async def embeddings_create(self, *args, **kwargs) -> Any:
        """Call Gemini text embedding model. Standardizes return structure."""
        async def _run(**call_kwargs):
            # Google's text-embedding-004 is the standard embedding model
            model = "text-embedding-004"
            input_text = call_kwargs.get("input")

            if not input_text:
                raise GeminiClientError("Embedding input text is empty.")

            if isinstance(input_text, str):
                response = await self.client.aio.models.embed_content(
                    model=model,
                    contents=input_text,
                )
                embedding_values = response.embedding.values
                return SimpleNamespace(
                    data=[
                        SimpleNamespace(
                            embedding=embedding_values
                        )
                    ]
                )
            elif isinstance(input_text, list):
                # Batch embed
                results = []
                for text in input_text:
                    resp = await self.client.aio.models.embed_content(
                        model=model,
                        contents=text,
                    )
                    results.append(SimpleNamespace(embedding=resp.embedding.values))
                return SimpleNamespace(data=results)
            else:
                raise GeminiClientError("Unsupported embedding input type.")

        return await self._execute_with_fallback(_run, *args, **kwargs)

    async def moderations_create(self, *args, **kwargs) -> Any:
        """Call Gemini flash model to inspect content safety, mimicking OpenAI moderations."""
        async def _run(**call_kwargs):
            input_text = call_kwargs.get("input", "")
            
            # Simple content moderation evaluation via gemini-2.5-flash
            try:
                response = await self.client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"Analyze the content safety of this prompt. Answer with UNSAFE: [reason] or SAFE. Prompt: {input_text}",
                    config=types.GenerateContentConfig(
                        max_output_tokens=20,
                        temperature=0.0
                    )
                )
                
                resp_text = response.text.upper() if response.text else "SAFE"
                flagged = "UNSAFE" in resp_text
                
                # Double check safety candidate triggers
                if response.candidates and response.candidates[0].finish_reason == "SAFETY":
                    flagged = True
            except Exception:
                # If blocked entirely, flag it as unsafe
                flagged = True
                resp_text = "UNSAFE"

            categories = {
                "hate": "HATE" in resp_text or "HARASS" in resp_text,
                "harassment": "HARASS" in resp_text,
                "violence": "VIOLEN" in resp_text or "ARM" in resp_text,
                "sexual": "SEX" in resp_text or "PORN" in resp_text,
            }

            result = SimpleNamespace(
                flagged=flagged,
                categories=SimpleNamespace(**categories),
                category_scores=SimpleNamespace(**{k: 0.9 if v else 0.0 for k, v in categories.items()}),
            )
            return SimpleNamespace(results=[result])

        return await self._execute_with_fallback(_run, *args, **kwargs)


def get_async_gemini_client(config: Optional[Dict[str, Any]] = None) -> AsyncGeminiClient:
    """Get global configured AsyncGeminiClient instance."""
    return AsyncGeminiClient(config=config)
