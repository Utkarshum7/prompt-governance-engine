"""Canonicalization service for extracting templates from prompt clusters."""

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.clients.llm_client import get_async_llm_client, LLMClientError
from src.interfaces.llm import ILLMProvider
from src.config.settings import get_settings
from src.models.database import CanonicalTemplate, Cluster, TemplateSlot
from src.services.model_router import ModelRouter, get_model_router

logger = get_logger(__name__)

# JSON schema for template extraction response
TEMPLATE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "canonical_template": {
            "type": "string",
            "description": "The canonical template with variable slots in {{variable}} format",
        },
        "slots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Variable slot name"},
                    "type": {
                        "type": "string",
                        "description": "Inferred type (string, number, boolean, etc.)",
                    },
                    "example_values": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Example values for this slot",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence score for slot detection",
                    },
                },
                "required": ["name", "type"],
            },
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Overall confidence in template extraction",
        },
        "explanation": {
            "type": "string",
            "description": "Explanation of how the template was extracted",
        },
    },
    "required": ["canonical_template", "slots", "confidence"],
}


class CanonicalizationService:
    """Service for extracting canonical templates from prompt clusters."""

    def __init__(
        self,
        db: AsyncSession,
        model_router: Optional[ModelRouter] = None,
        client: Optional[ILLMProvider] = None,
    ):
        """
        Initialize canonicalization service.

        Args:
            db: Database session
            model_router: Optional ModelRouter instance
            client: Optional ILLMProvider instance
        """
        self.db = db
        self.model_router = model_router or get_model_router()
        settings = get_settings()
        self.gpt4o_model = settings.models.canonicalization.primary
        self.claude_model = settings.models.canonicalization.alternative
        self.max_tokens = settings.models.canonicalization.max_tokens
        self.temperature = settings.models.canonicalization.temperature

        # Use provided client or create default GPT-4o client
        self.client = client or get_async_llm_client(provider=self.gpt4o_model)

        logger.info(
            "Canonicalization service initialized",
            gpt4o_model=self.gpt4o_model,
            claude_model=self.claude_model,
        )

    def _build_extraction_prompt(self, prompts: List[str]) -> str:
        """
        Build prompt for template extraction.

        Args:
            prompts: List of prompt texts from cluster

        Returns:
            Extraction prompt
        """
        prompts_text = "\n\n".join([f"Prompt {i+1}:\n{p}" for i, p in enumerate(prompts)])

        return f"""You are an expert at analyzing prompts and extracting canonical templates.

Given the following semantically similar prompts, extract a canonical template that captures their common structure while identifying variable parts.

Prompts:
{prompts_text}

Task:
1. Identify the common structure across all prompts
2. Extract variable parts and replace them with {{variable_name}} placeholders
3. Infer the type of each variable (string, number, boolean, etc.)
4. Provide example values for each variable slot
5. Calculate confidence scores for your extraction

Return a JSON object with:
- canonical_template: The template with {{variable}} slots
- slots: Array of variable slots with name, type, example_values, and confidence
- confidence: Overall confidence in the extraction (0-1)
- explanation: Brief explanation of how you extracted the template

Example output format:
{{
  "canonical_template": "Translate {{text}} from {{source_language}} to {{target_language}}",
  "slots": [
    {{
      "name": "text",
      "type": "string",
      "example_values": ["Hello", "How are you?"],
      "confidence": 0.95
    }},
    {{
      "name": "source_language",
      "type": "string",
      "example_values": ["English", "Spanish"],
      "confidence": 0.9
    }},
    {{
      "name": "target_language",
      "type": "string",
      "example_values": ["French", "German"],
      "confidence": 0.9
    }}
  ],
  "confidence": 0.92,
  "explanation": "All prompts follow the same translation pattern with variable text and language pairs"
}}
"""

    async def _extract_template_with_router(
        self,
        prompts: List[str],
        confidence_score: Optional[float] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract template using dynamically routed Portkey configuration.

        Args:
            prompts: List of prompt texts
            confidence_score: Optional previous confidence score (to trigger reasoning upgrade)
            trace_id: Optional trace ID

        Returns:
            Template extraction result
        """
        combined_prompts = "\n\n".join(prompts)
        
        # Get dynamic Portkey routing configuration from the model router
        routing_config = self.model_router.get_portkey_config(
            prompt=combined_prompts,
            confidence_score=confidence_score
        )

        # Instantiate Gemini/LLM client using the dynamic routing configuration dict
        client = get_async_llm_client(config=routing_config)
        if trace_id:
            client = client.with_options(trace_id=trace_id)

        extraction_prompt = self._build_extraction_prompt(prompts)
        primary_model = routing_config["targets"][0]["model"]
        provider = routing_config["targets"][0]["provider"]

        try:
            logger.info(
                "Running routed Portkey template extraction",
                primary_model=primary_model,
                provider=provider,
                is_retry_upgrade=(confidence_score is not None),
                trace_id=trace_id
            )

            response = await client.chat_completions_create(
                model=primary_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting canonical templates from similar prompts. Always return valid JSON matching the schema.",
                    },
                    {"role": "user", "content": extraction_prompt},
                ]
            )

            content = response.choices[0].message.content

            # Clean up potential markdown formatting in response if any (especially from Claude/o1)
            json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

            result = json.loads(content)

            logger.debug(
                "Template extracted via dynamic Portkey router",
                model=primary_model,
                template=result.get("canonical_template", "")[:100],
                slots_count=len(result.get("slots", [])),
                trace_id=trace_id,
            )

            return result

        except json.JSONDecodeError as e:
            logger.error("JSON decode error in template extraction", error=str(e), model=primary_model, trace_id=trace_id)
            raise LLMClientError(f"Invalid JSON response from template extraction: {e}") from e
        except Exception as e:
            logger.error("Error extracting template via LLM router", error=str(e), model=primary_model, trace_id=trace_id)
            raise LLMClientError(f"Template extraction failed: {e}") from e

    def _detect_variable_slots(self, template: str) -> List[Dict[str, Any]]:
        """
        Detect variable slots in template using regex.

        Args:
            template: Template string with {{variable}} slots

        Returns:
            List of detected slots
        """
        # Find all {{variable}} patterns
        pattern = r"\{\{(\w+)\}\}"
        matches = re.findall(pattern, template)

        slots = []
        for var_name in matches:
            slots.append(
                {
                    "name": var_name,
                    "detected": True,
                }
            )

        return slots

    async def extract_template(
        self,
        cluster_id: uuid.UUID,
        prompts: Optional[List[str]] = None,
        force_model: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract canonical template from a cluster.

        Args:
            cluster_id: Cluster ID
            prompts: Optional list of prompt texts. If None, fetches from cluster.
            force_model: Optional model override ("gpt4o" or "claude")
            trace_id: Optional trace ID

        Returns:
            Template extraction result with slots
        """
        try:
            # Get cluster
            cluster = await self.db.get(Cluster, cluster_id)
            if not cluster:
                raise ValueError(f"Cluster {cluster_id} not found")

            # Get prompts if not provided
            if prompts is None:
                from src.services.clustering import get_clustering_service

                clustering_service = get_clustering_service(self.db)
                cluster_prompts = await clustering_service.get_cluster_prompts(cluster_id)
                prompts = [p.content for p in cluster_prompts]

            if not prompts:
                raise ValueError(f"No prompts found in cluster {cluster_id}")

            logger.info(
                "Extracting template from cluster",
                cluster_id=cluster_id,
                prompts_count=len(prompts),
                trace_id=trace_id,
            )

            # Extract template using the dynamic Portkey router
            result = await self._extract_template_with_router(prompts, trace_id=trace_id)

            # Check if confidence is below the threshold. If so, dynamically upgrade to reasoning model!
            settings = get_settings()
            confidence_threshold = settings.app.clustering.confidence_threshold
            extracted_confidence = result.get("confidence", 0.5)

            if extracted_confidence < confidence_threshold:
                logger.info(
                    "Extracted template confidence below threshold, retrying with reasoning model upgrade",
                    confidence=extracted_confidence,
                    threshold=confidence_threshold,
                    cluster_id=cluster_id
                )
                # Retry with previous low confidence score passed, prompting model upgrade in the router
                result = await self._extract_template_with_router(
                    prompts,
                    confidence_score=extracted_confidence,
                    trace_id=trace_id
                )

            # Validate and enhance slots
            canonical_template = result.get("canonical_template", "")
            slots = result.get("slots", [])

            # Detect slots in template if not provided
            detected_slots = self._detect_variable_slots(canonical_template)
            detected_slot_names = {s["name"] for s in detected_slots}

            # Ensure all detected slots are in result
            for detected_slot in detected_slots:
                slot_name = detected_slot["name"]
                if not any(s.get("name") == slot_name for s in slots):
                    slots.append(
                        {
                            "name": slot_name,
                            "type": "string",  # Default type
                            "example_values": [],
                            "confidence": 0.5,  # Lower confidence for auto-detected
                        }
                    )

            # Calculate overall confidence if not provided
            if "confidence" not in result:
                if slots:
                    avg_slot_confidence = sum(s.get("confidence", 0.5) for s in slots) / len(slots)
                    result["confidence"] = avg_slot_confidence
                else:
                    result["confidence"] = 0.5

            logger.info(
                "Template extracted successfully",
                cluster_id=cluster_id,
                template=canonical_template[:100],
                slots_count=len(slots),
                confidence=result.get("confidence"),
                trace_id=trace_id,
            )

            return {
                "cluster_id": str(cluster_id),
                "canonical_template": canonical_template,
                "slots": slots,
                "confidence": result.get("confidence", 0.5),
                "explanation": result.get("explanation", ""),
            }

        except Exception as e:
            logger.error(
                "Error extracting template",
                cluster_id=cluster_id,
                error=str(e),
                trace_id=trace_id,
            )
            raise

    async def save_template(
        self,
        cluster_id: uuid.UUID,
        template_data: Dict[str, Any],
        version: str = "1.0.0",
        trace_id: Optional[str] = None,
    ) -> CanonicalTemplate:
        """
        Save extracted template to database.

        Args:
            cluster_id: Cluster ID
            template_data: Template extraction result
            version: Template version (semantic versioning)
            trace_id: Optional trace ID

        Returns:
            Created CanonicalTemplate object
        """
        try:
            template_id = uuid.uuid4()

            # Create canonical template
            canonical_template = CanonicalTemplate(
                id=template_id,
                cluster_id=cluster_id,
                template_content=template_data["canonical_template"],
                version=version,
                slots=template_data.get("slots", []),
                confidence_score=template_data.get("confidence", 0.5),
            )

            self.db.add(canonical_template)
            await self.db.flush()

            # Create template slots
            for slot_data in template_data.get("slots", []):
                slot = TemplateSlot(
                    template_id=template_id,
                    slot_name=slot_data.get("name"),
                    slot_type=slot_data.get("type", "string"),
                    example_values=slot_data.get("example_values", []),
                    confidence_score=slot_data.get("confidence", 0.5),
                )
                self.db.add(slot)

            await self.db.flush()

            logger.info(
                "Template saved",
                template_id=template_id,
                cluster_id=cluster_id,
                version=version,
                trace_id=trace_id,
            )

            return canonical_template

        except Exception as e:
            logger.error(
                "Error saving template",
                cluster_id=cluster_id,
                error=str(e),
                trace_id=trace_id,
            )
            raise


def get_canonicalization_service(
    db: AsyncSession,
    model_router: Optional[ModelRouter] = None,
    client: Optional[ILLMProvider] = None,
) -> CanonicalizationService:
    """
    Get canonicalization service instance.

    Args:
        db: Database session
        model_router: Optional ModelRouter instance
        client: Optional ILLMProvider instance

    Returns:
        CanonicalizationService instance
    """
    return CanonicalizationService(
        db=db, model_router=model_router, client=client
    )

