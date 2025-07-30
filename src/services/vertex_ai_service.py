import vertexai
from vertexai.generative_models import GenerativeModel, Part
from typing import Dict, Any, Optional
import json
import base64
import os


class VertexAIService:
    def __init__(self):
        # Get project ID from environment variable
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not set")
        
        # Initialize Vertex AI with project and location
        vertexai.init(project=project_id, location="us-central1")
        self.model = "gemini-2.0-flash"
    
    def analyze_video_with_transcript(self, video_content: bytes, transcript: Optional[str] = None, caption: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Analyze video with Gemini 2.0 Flash"""
        # Prepare multimodal input
        parts = []
        
        # Add video using Part class
        video_part = Part.from_data(video_content, mime_type="video/mp4")
        parts.append(video_part)
        
        # Build prompt
        prompt = "You are an expert fitness instructor analyzing a TikTok workout video."
        
        if transcript:
            prompt += f"\n\nTRANSCRIPT:\n{transcript}"
        
        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"
        
        prompt += """

Analyze this workout video and extract the following information. Return your response as a valid JSON object with NO additional text, explanations, or formatting.

Required JSON structure:
{
  "title": "descriptive workout title",
  "description": "brief description of the workout or null",
  "workout_type": "one of: strength, cardio, hiit, yoga, stretching, bodyweight, mixed",
  "duration_minutes": estimated duration as integer or null,
  "difficulty_level": integer from 1 to 10,
  "exercises": [
    {
      "name": "exercise name",
      "muscle_groups": ["array of: chest, back, shoulders, biceps, triceps, legs, glutes, core, full_body"],
      "equipment": "one of: none, dumbbells, barbell, resistance_bands, kettlebell, machine, bodyweight, other",
      "sets": [
        {
          "reps": integer or null,
          "weight_lbs": number or null,
          "duration_seconds": integer or null,
          "distance_miles": number or null,
          "rest_seconds": integer or null
        }
      ],
      "instructions": "brief instructions or null"
    }
  ],
  "tags": ["array of relevant tags"] or null,
  "creator": "creator name or null"
}

IMPORTANT: Your response must be ONLY the JSON object, with no markdown formatting, no code blocks, no explanations before or after."""
        
        # Add text prompt using Part class
        text_part = Part.from_text(prompt)
        parts.append(text_part)
        
        # Generate content
        model = GenerativeModel(self.model)
        response = model.generate_content(
            parts,
            generation_config={
                "max_output_tokens": 2048,  # Increased for more complex workouts
                "temperature": 0.1,
                "top_p": 0.8,
                "response_mime_type": "application/json"  # Force JSON response
            }
        )
        
        # Parse response
        try:
            # Check if response has candidates and content
            if not response.candidates or not response.candidates[0].content.parts:
                print(f"ERROR - No content in response. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'No candidates'}")
                print(f"ERROR - Usage: {response.usage_metadata}")
                return None
            
            response_text = response.text.strip()
            print(f"DEBUG - Raw Gemini response: {response_text[:500]}...")  # Log first 500 chars
            
            # Try to extract JSON from the response
            # Sometimes Gemini adds markdown formatting or explanations
            if "```json" in response_text:
                # Extract JSON from markdown code block
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                # Extract from generic code block
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            return json.loads(response_text)
        except Exception as e:
            print(f"ERROR - Failed to parse Gemini response: {e}")
            try:
                print(f"ERROR - Response candidates: {len(response.candidates) if response.candidates else 0}")
                if response.candidates:
                    print(f"ERROR - Finish reason: {response.candidates[0].finish_reason}")
                print(f"ERROR - Usage metadata: {response.usage_metadata}")
            except:
                print("ERROR - Could not access response metadata")
            return None