"""
Script generation from scratch endpoints (no template required)
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
import logging
import time

from src.utils.logging import StructuredLogger
from src.models.requests import (
    GenerateScriptsFromScratchRequest,
    RefineBeatRequest,
)
from src.models.responses import (
    GenerateScriptsFromScratchResponse,
    RefineBeatResponse,
    ScriptOption,
    ScriptBeats,
)
from src.services.openai_service import OpenAIService
from src.auth import optional_appcheck_token
from src.exceptions import ProcessingError

logger = StructuredLogger(__name__)
router = APIRouter(prefix="", tags=["script-from-scratch"])

# Initialize service
openai_service = OpenAIService()


@router.post(
    "/generate-scripts-from-scratch",
    response_model=GenerateScriptsFromScratchResponse,
)
async def generate_scripts_from_scratch(
    request: GenerateScriptsFromScratchRequest,
    req: Request,
    appcheck_claims: dict = Depends(optional_appcheck_token),
) -> GenerateScriptsFromScratchResponse:
    """
    Generate 3 meaningfully different scripts from user inputs (no template required).
    
    Returns 3 script options, each with 4 beats: hook, context, value, cta.
    """
    request_id = getattr(req.state, "request_id", "unknown")
    start_time = time.time()

    logger.info(
        f"Script from scratch request - Request ID: {request_id}, "
        f"Topic: {request.topic[:50]}..., Hook: {request.hook_style.value}, "
        f"Tone: {request.tone.value}, Length: {request.length_seconds}s"
    )

    try:
        result = await openai_service.generate_scripts_from_scratch(
            topic=request.topic,
            hook_style=request.hook_style.value,
            cta_type=request.cta_type.value,
            tone=request.tone.value,
            video_format=request.format.value,
            length_seconds=request.length_seconds,
            reading_speed=request.reading_speed.value,
            audience=request.audience,
            proof=request.proof,
            cta_keyword=request.cta_keyword,
        )

        if not result or "options" not in result:
            raise ProcessingError(
                message="Failed to generate scripts. Please try again.",
                operation="script_from_scratch",
            )

        # Build response with proper models
        options = []
        for opt_data in result["options"]:
            beats_data = opt_data.get("beats", {})
            options.append(
                ScriptOption(
                    option_id=opt_data.get("option_id", "opt_unknown"),
                    beats=ScriptBeats(
                        hook=beats_data.get("hook", ""),
                        context=beats_data.get("context", ""),
                        value=beats_data.get("value", ""),
                        cta=beats_data.get("cta", ""),
                    ),
                    full_text=opt_data.get("full_text", ""),
                    estimated_seconds=opt_data.get("estimated_seconds", 0),
                    word_count=opt_data.get("word_count", 0),
                    tags=opt_data.get("tags", {}),
                )
            )

        generation_time_ms = int((time.time() - start_time) * 1000)

        response = GenerateScriptsFromScratchResponse(
            success=True,
            options=options,
            meta={
                "generation_time_ms": generation_time_ms,
                "model": "gpt-4o",
            },
        )

        logger.info(
            f"Script from scratch completed - Request ID: {request_id}, "
            f"Time: {generation_time_ms}ms, Options: {len(options)}"
        )
        return response

    except ProcessingError as e:
        logger.error(f"Script from scratch failed - Request ID: {request_id}, Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "GENERATION_FAILED",
                    "message": str(e),
                },
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error in script from scratch - Request ID: {request_id}, Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "GENERATION_FAILED",
                    "message": "Failed to generate scripts. Please try again.",
                },
            },
        )


@router.post("/refine-beat", response_model=RefineBeatResponse)
async def refine_beat(
    request: RefineBeatRequest,
    req: Request,
    appcheck_claims: dict = Depends(optional_appcheck_token),
) -> RefineBeatResponse:
    """
    Refine a single beat with a specific action.
    
    Available actions vary by beat type:
    - hook: punchier, more_curiosity, shorter, new_hook
    - context: shorter, clearer, add_one_line
    - value: add_example, make_simpler, cut_fluff, add_pattern_interrupt
    - cta: swap_cta, add_keyword_prompt, less_salesy
    """
    request_id = getattr(req.state, "request_id", "unknown")
    start_time = time.time()

    logger.info(
        f"Refine beat request - Request ID: {request_id}, "
        f"Beat: {request.beat_type.value}, Action: {request.action.value}"
    )

    try:
        result = await openai_service.refine_beat(
            beat_type=request.beat_type.value,
            current_text=request.current_text,
            action=request.action.value,
            context=request.context,
        )

        if not result or "refined_text" not in result:
            raise ProcessingError(
                message="Failed to refine beat. Please try again.",
                operation="refine_beat",
            )

        response = RefineBeatResponse(
            success=True,
            refined_text=result["refined_text"],
            estimated_seconds=result.get("estimated_seconds", 0),
            word_count=result.get("word_count", 0),
            action_applied=result.get("action_applied", request.action.value),
        )

        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"Refine beat completed - Request ID: {request_id}, "
            f"Time: {generation_time_ms}ms, Action: {request.action.value}"
        )
        return response

    except ProcessingError as e:
        logger.error(f"Refine beat failed - Request ID: {request_id}, Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "GENERATION_FAILED",
                    "message": str(e),
                },
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error in refine beat - Request ID: {request_id}, Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "GENERATION_FAILED",
                    "message": "Failed to refine beat. Please try again.",
                },
            },
        )

