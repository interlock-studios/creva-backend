"""
Script generation endpoints
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from typing import Dict, Any
import logging

from src.utils.logging import StructuredLogger, set_request_context
from src.models.requests import GenerateScriptRequest
from src.models.responses import GeneratedScript, ScriptParts
from src.services.genai_service import GenAIService
from src.auth import optional_appcheck_token
from src.exceptions import ProcessingError

logger = StructuredLogger(__name__)
router = APIRouter(prefix="", tags=["script"])

# Initialize service
genai_service = GenAIService()


@router.post("/generate-script", response_model=GeneratedScript)
async def generate_script(
    request: GenerateScriptRequest,
    req: Request,
    appcheck_claims: dict = Depends(optional_appcheck_token),
) -> GeneratedScript:
    """Generate a script from a template and topic"""

    request_id = getattr(req.state, "request_id", "unknown")

    logger.info(
        f"Script generation request - Request ID: {request_id}, Topic: {request.topic}, Creator: {request.creator_role}, Template: {request.template[:50]}..."
    )

    try:
        # Generate script using GenAI service with simplified context
        result = await genai_service.generate_script(
            template=request.template,
            topic=request.topic,
            creator_role=request.creator_role,
            main_message=request.main_message,
            niche=request.niche,
            style=request.style or "conversational",
            length=request.length or "short",
        )

        if not result:
            raise ProcessingError(
                message="Failed to generate script. Please try again.",
                operation="script_generation",
            )

        # Validate and structure the response
        if "script" not in result:
            raise ProcessingError(
                message="Invalid response from script generation service",
                operation="script_generation",
            )

        # Ensure variations is a list
        variations = result.get("variations", [])
        if not isinstance(variations, list):
            variations = []

        # Build response - handle both snake_case and camelCase from GenAI
        script_data = result["script"]
        
        # Helper to get field with fallback to camelCase
        def get_field(data: Dict[str, Any], snake_key: str, camel_key: str = None) -> str:
            if camel_key is None:
                camel_key = "".join(word.capitalize() if i > 0 else word for i, word in enumerate(snake_key.split("_")))
            return data.get(snake_key) or data.get(camel_key) or ""
        
        response = GeneratedScript(
            success=True,
            script=ScriptParts(
                hook=script_data.get("hook", ""),
                body=script_data.get("body", ""),
                call_to_action=get_field(script_data, "call_to_action", "callToAction"),
            ),
            full_script=result.get("full_script") or result.get("fullScript", ""),
            variations=[
                ScriptParts(
                    hook=var.get("hook", ""),
                    body=var.get("body", ""),
                    call_to_action=get_field(var, "call_to_action", "callToAction"),
                )
                for var in variations
            ],
            estimated_duration=result.get("estimated_duration") or result.get("estimatedDuration", "unknown"),
        )

        logger.info(f"Script generation completed - Request ID: {request_id}")
        return response

    except ProcessingError as e:
        logger.error(f"Script generation failed - Request ID: {request_id}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in script generation - Request ID: {request_id}, Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate script. Please try again.",
        )

