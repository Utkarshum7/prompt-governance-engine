"""Edge case reasoning service using o1-mini for ambiguous clustering decisions."""

import json
import uuid
from typing import Any, Dict, List, Optional

from structlog import get_logger

from src.clients.portkey import AsyncPortkeyClient, PortkeyClientError, get_async_portkey_client
from src.config.settings import get_settings

logger = get_logger(__name__)


class ReasoningService:
    """Service for handling ambiguous clustering decisions using o1-mini."""

    def __init__(self, client: Optional[AsyncPortkeyClient] = None):
        """
        Initialize reasoning service.

        Args:
            client: Optional AsyncPortkeyClient instance
        """
        settings = get_settings()
        self.model = settings.models.reasoning.model
        self.max_tokens = settings.models.reasoning.max_tokens

        self.client = client or get_async_portkey_client(provider=self.model)

        logger.info("Reasoning service initialized", model=self.model)

    def _build_reasoning_prompt(
        self,
        prompt_content: str,
        candidate_clusters: List[Dict[str, Any]],
        similarity_scores: List[float],
    ) -> str:
        """
        Build prompt for edge case reasoning.

        Args:
            prompt_content: Prompt content to classify
            candidate_clusters: List of candidate cluster information
            similarity_scores: List of similarity scores for candidates

        Returns:
            Reasoning prompt
        """
        candidates_info = []
        for i, (cluster, score) in enumerate(zip(candidate_clusters, similarity_scores)):
            candidates_info.append(
                {
                    "cluster_id": str(cluster.get("id", "")),
                    "cluster_name": cluster.get("name", ""),
                    "similarity_score": score,
                    "prompt_count": cluster.get("prompt_count", 0),
                }
            )

        return f"""You are an expert at making clustering decisions for ambiguous cases.

Given a prompt and multiple candidate clusters with borderline similarity scores, determine the best cluster assignment.

Prompt to Classify:
{prompt_content}

Candidate Clusters:
{json.dumps(candidates_info, indent=2)}

Task:
1. Analyze the semantic similarity between the prompt and each candidate cluster
2. Consider the context and meaning, not just surface-level similarity
3. Determine the best cluster assignment
4. Provide detailed reasoning for your decision
5. Calculate a confidence score (0.0-1.0)

Return a JSON object with:
- recommended_cluster_id: ID of the best matching cluster
- confidence: confidence score (0.0-1.0)
- reasoning: detailed explanation of why this cluster was chosen
- alternative_clusters: array of alternative cluster IDs with scores (if applicable)
- should_create_new: boolean indicating if a new cluster should be created instead

Example output:
{{
  "recommended_cluster_id": "cluster-uuid-here",
  "confidence": 0.75,
  "reasoning": "The prompt semantically matches Cluster A's theme of translation requests, despite a lower similarity score. The prompt's intent and structure align better with Cluster A than Cluster B.",
  "alternative_clusters": [
    {{"cluster_id": "cluster-b-uuid", "score": 0.68, "reason": "Similar structure but different intent"}}
  ],
  "should_create_new": false
}}
"""

    async def classify_edge_case(
        self,
        prompt_content: str,
        candidate_clusters: List[Dict[str, Any]],
        similarity_scores: List[float],
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Classify an edge case prompt with ambiguous clustering.

        Args:
            prompt_content: Prompt content to classify
            candidate_clusters: List of candidate cluster information
            similarity_scores: List of similarity scores for candidates
            trace_id: Optional trace ID

        Returns:
            Classification result with reasoning
        """
        try:
            if not candidate_clusters or not similarity_scores:
                return {
                    "recommended_cluster_id": None,
                    "confidence": 0.0,
                    "reasoning": "No candidate clusters provided",
                    "alternative_clusters": [],
                    "should_create_new": True,
                }

            # Build reasoning prompt
            reasoning_prompt = self._build_reasoning_prompt(
                prompt_content, candidate_clusters, similarity_scores
            )

            # Use with_options for request-level overrides
            client_with_options = (
                self.client.with_options(trace_id=trace_id) if trace_id else self.client
            )

            # Call o1-mini for reasoning
            response = await client_with_options.chat_completions_create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at making clustering decisions for ambiguous cases. Always return valid JSON.",
                    },
                    {"role": "user", "content": reasoning_prompt},
                ],
                max_tokens=self.max_tokens,
            )

            # Parse response
            content = response.choices[0].message.content

            # Extract JSON from response
            import re

            json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

            classification = json.loads(content)

            logger.info(
                "Edge case classification completed",
                recommended_cluster=classification.get("recommended_cluster_id"),
                confidence=classification.get("confidence"),
                should_create_new=classification.get("should_create_new", False),
                trace_id=trace_id,
            )

            return classification

        except json.JSONDecodeError as e:
            logger.error("JSON decode error in edge case reasoning", error=str(e), trace_id=trace_id)
            raise PortkeyClientError(f"Invalid JSON response from reasoning: {e}") from e
        except Exception as e:
            logger.error("Error classifying edge case", error=str(e), trace_id=trace_id)
            raise

    async def analyze_borderline_similarity(
        self,
        prompt_content: str,
        cluster_scores: Dict[uuid.UUID, float],
        threshold: float = 0.85,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze borderline similarity scores to determine best cluster assignment.

        Args:
            prompt_content: Prompt content
            cluster_scores: Dictionary mapping cluster_id to similarity score
            threshold: Similarity threshold
            trace_id: Optional trace ID

        Returns:
            Analysis result with reasoning
        """
        try:
            # Filter clusters near threshold (within 0.05)
            borderline_clusters = {
                cid: score
                for cid, score in cluster_scores.items()
                if abs(score - threshold) < 0.05
            }

            if not borderline_clusters:
                # No borderline cases, return highest scoring cluster
                if cluster_scores:
                    best_cluster_id = max(cluster_scores, key=cluster_scores.get)
                    best_score = cluster_scores[best_cluster_id]

                    return {
                        "recommended_cluster_id": str(best_cluster_id),
                        "confidence": 1.0 if best_score >= threshold else 0.5,
                        "reasoning": f"Clear assignment to cluster with score {best_score:.3f}",
                        "alternative_clusters": [],
                        "should_create_new": best_score < threshold,
                    }
                else:
                    return {
                        "recommended_cluster_id": None,
                        "confidence": 0.0,
                        "reasoning": "No clusters found",
                        "alternative_clusters": [],
                        "should_create_new": True,
                    }

            # Get cluster information for borderline cases
            # Note: This would typically fetch from database, simplified here
            candidate_clusters = [
                {"id": cid, "name": f"Cluster-{str(cid)[:8]}", "prompt_count": 0}
                for cid in borderline_clusters.keys()
            ]

            similarity_scores = list(borderline_clusters.values())

            # Use reasoning service for borderline cases
            return await self.classify_edge_case(
                prompt_content, candidate_clusters, similarity_scores, trace_id=trace_id
            )

        except Exception as e:
            logger.error("Error analyzing borderline similarity", error=str(e), trace_id=trace_id)
            raise


# Global reasoning service instance
_reasoning_service: Optional[ReasoningService] = None


def get_reasoning_service(client: Optional[AsyncPortkeyClient] = None) -> ReasoningService:
    """
    Get global reasoning service instance.

    Args:
        client: Optional AsyncPortkeyClient instance

    Returns:
        ReasoningService instance
    """
    global _reasoning_service
    if _reasoning_service is None:
        _reasoning_service = ReasoningService(client=client)
    return _reasoning_service

