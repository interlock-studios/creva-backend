from google.cloud import vision
import structlog
from typing import List, Optional
import io

logger = structlog.get_logger()


class VisionService:
    def __init__(self):
        self.client = vision.ImageAnnotatorClient()
    
    async def extract_text_from_images(self, image_contents: List[bytes]) -> List[str]:
        try:
            extracted_texts = []
            
            for i, image_content in enumerate(image_contents):
                image = vision.Image(content=image_content)
                
                response = self.client.text_detection(image=image)
                texts = response.text_annotations
                
                if texts:
                    # First annotation contains the full text
                    extracted_text = texts[0].description
                    extracted_texts.append(extracted_text)
                    
                    logger.debug(
                        "Text extracted from image",
                        image_index=i,
                        text_length=len(extracted_text)
                    )
                else:
                    extracted_texts.append("")
                
                # Check for errors
                if response.error.message:
                    logger.warning(
                        "Vision API error",
                        image_index=i,
                        error=response.error.message
                    )
            
            total_text_length = sum(len(text) for text in extracted_texts)
            logger.info(
                "OCR completed",
                images_processed=len(image_contents),
                total_text_length=total_text_length
            )
            
            return extracted_texts
            
        except Exception as e:
            logger.error("Vision API failed", error=str(e))
            raise
    
    async def extract_text_batch(self, image_contents: List[bytes], batch_size: int = 20) -> List[str]:
        all_texts = []
        
        for i in range(0, len(image_contents), batch_size):
            batch = image_contents[i:i + batch_size]
            batch_texts = await self.extract_text_from_images(batch)
            all_texts.extend(batch_texts)
            
            logger.info(
                "Batch OCR completed",
                batch_start=i,
                batch_size=len(batch),
                total_batches=(len(image_contents) + batch_size - 1) // batch_size
            )
        
        return all_texts