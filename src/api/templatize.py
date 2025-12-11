"""
Transcript templatization endpoints
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from typing import Union
import logging

from src.utils.logging import StructuredLogger
from src.models.requests import TemplatizeTranscriptRequest
from src.models.responses import TemplatizeTranscriptResponse, TemplatizeErrorResponse
from src.services.openai_service import OpenAIService
from src.auth import optional_appcheck_token

logger = StructuredLogger(__name__)
router = APIRouter(prefix="", tags=["templatize"])

# Initialize service
openai_service = OpenAIService()


@router.post(
    "/templatize-transcript",
    response_model=Union[TemplatizeTranscriptResponse, TemplatizeErrorResponse],
)
async def templatize_transcript(
    request: TemplatizeTranscriptRequest,
    req: Request,
    appcheck_claims: dict = Depends(optional_appcheck_token),
) -> Union[TemplatizeTranscriptResponse, TemplatizeErrorResponse]:
    """
    Convert transcript to fill-in-the-blank template.

    Args:
        request: JSON with 'transcript' field
        req: FastAPI request object
        appcheck_claims: Optional App Check claims

    Returns:
        JSON with 'success' and 'template' fields, or error response
    """
    request_id = getattr(req.state, "request_id", "unknown")

    logger.info(
        f"Templatize transcript request - Request ID: {request_id}, Transcript length: {len(request.transcript)}"
    )

    # Validation is handled by Pydantic model (empty check and length limit)
    transcript = request.transcript

    try:
        # Call OpenAI service
        template = await openai_service.templatize_transcript(transcript)

        if not template:
            logger.error(f"OpenAI service returned None - Request ID: {request_id}")
            return TemplatizeErrorResponse(
                success=False,
                error="generation_failed",
                message="Failed to generate template. Please try again.",
            )

        logger.info(f"Templatize transcript completed - Request ID: {request_id}")
        return TemplatizeTranscriptResponse(success=True, template=template)

    except Exception as e:
        logger.error(
            f"Unexpected error in templatize transcript - Request ID: {request_id}, Error: {str(e)}"
        )
        return TemplatizeErrorResponse(
            success=False,
            error="generation_failed",
            message="Failed to generate template. Please try again.",
        )

