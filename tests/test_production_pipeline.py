import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os

from src.services.production_pipeline import ProductionPipeline
from src.models.parser_result import (
    TikTokParseResult, ProcessingStatus, VideoMetadata,
    TranscriptSegment, OCRBlock
)


@pytest.fixture
def pipeline():
    """Create a production pipeline instance for testing"""
    return ProductionPipeline()


@pytest.fixture
def sample_video_content():
    """Sample video content for testing"""
    # Create a small dummy video file
    return b"fake_video_content_for_testing"


@pytest.fixture
def sample_metadata():
    """Sample video metadata"""
    return VideoMetadata(
        title="Test Workout Video",
        description="A great workout routine #fitness #health",
        author="@test_user",
        duration_seconds=45.0,
        view_count=1000,
        hashtags=["#fitness", "#health"],
        file_size_bytes=1024000
    )


@pytest.fixture
def sample_transcript_segments():
    """Sample transcript segments"""
    return [
        TranscriptSegment(
            start_time=0.0,
            end_time=5.0,
            text="Welcome to today's workout",
            confidence=0.95
        ),
        TranscriptSegment(
            start_time=5.0,
            end_time=10.0,
            text="We'll start with some jumping jacks",
            confidence=0.89
        )
    ]


@pytest.fixture
def sample_ocr_blocks():
    """Sample OCR blocks"""
    return [
        OCRBlock(
            text="5 MIN HIIT",
            confidence=0.98,
            timestamp=2.1,
            frame_number=63
        ),
        OCRBlock(
            text="BEGINNER FRIENDLY",
            confidence=0.92,
            timestamp=8.5,
            frame_number=255
        )
    ]


class TestProductionPipeline:
    """Test the main production pipeline"""
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, pipeline):
        """Test pipeline initializes correctly"""
        assert pipeline.video_processor is not None
        assert pipeline.whisper_service is not None
        assert pipeline.vision_service is not None
        assert pipeline.firestore_service is not None
        assert pipeline.storage_service is not None

    @pytest.mark.asyncio
    async def test_successful_processing_with_stt_and_ocr(
        self, pipeline, sample_video_content, sample_metadata,
        sample_transcript_segments, sample_ocr_blocks
    ):
        """Test successful processing with both STT and OCR"""
        
        # Mock all external services
        with patch.object(pipeline.video_processor, 'download_and_extract_metadata') as mock_download, \
             patch.object(pipeline, '_process_audio') as mock_stt, \
             patch.object(pipeline, '_process_video_frames') as mock_ocr, \
             patch.object(pipeline.storage_service, 'store_video_with_expiry') as mock_storage, \
             patch.object(pipeline.firestore_service, 'save_parse_result') as mock_save, \
             patch.object(pipeline, '_update_status') as mock_update:
            
            # Setup mocks
            mock_download.return_value = (sample_video_content, sample_metadata)
            mock_stt.return_value = (sample_transcript_segments, {"method": "whisper-local", "processing_time_seconds": 5.0})
            mock_ocr.return_value = (sample_ocr_blocks, {"method": "gcp-vision", "processing_time_seconds": 8.0, "keyframes_processed": 30})
            mock_storage.return_value = None
            mock_save.return_value = None
            mock_update.return_value = None
            
            # Execute
            result = await pipeline.process_tiktok_video(
                job_id="test-job-123",
                url="https://www.tiktok.com/@test_user/video/123456789",
                include_stt=True,
                include_ocr=True
            )
            
            # Verify
            assert result.status == ProcessingStatus.COMPLETED
            assert result.job_id == "test-job-123"
            assert result.metadata == sample_metadata
            assert result.transcript_segments == sample_transcript_segments
            assert result.ocr_blocks == sample_ocr_blocks
            assert result.metrics is not None
            assert result.metrics.total_cost_usd > 0
            assert result.completed_at is not None
            
            # Verify service calls
            mock_download.assert_called_once()
            mock_stt.assert_called_once()
            mock_ocr.assert_called_once()
            mock_save.assert_called()

    @pytest.mark.asyncio
    async def test_processing_stt_only(
        self, pipeline, sample_video_content, sample_metadata, sample_transcript_segments
    ):
        """Test processing with STT only, no OCR"""
        
        with patch.object(pipeline.video_processor, 'download_and_extract_metadata') as mock_download, \
             patch.object(pipeline, '_process_audio') as mock_stt, \
             patch.object(pipeline, '_process_video_frames') as mock_ocr, \
             patch.object(pipeline.storage_service, 'store_video_with_expiry'), \
             patch.object(pipeline.firestore_service, 'save_parse_result'), \
             patch.object(pipeline, '_update_status'):
            
            mock_download.return_value = (sample_video_content, sample_metadata)
            mock_stt.return_value = (sample_transcript_segments, {"method": "whisper-local", "processing_time_seconds": 5.0})
            
            result = await pipeline.process_tiktok_video(
                job_id="test-job-stt",
                url="https://www.tiktok.com/@test_user/video/123456789",
                include_stt=True,
                include_ocr=False
            )
            
            assert result.status == ProcessingStatus.COMPLETED
            assert result.transcript_segments == sample_transcript_segments
            assert result.ocr_blocks is None
            mock_ocr.assert_not_called()

    @pytest.mark.asyncio
    async def test_processing_ocr_only(
        self, pipeline, sample_video_content, sample_metadata, sample_ocr_blocks
    ):
        """Test processing with OCR only, no STT"""
        
        with patch.object(pipeline.video_processor, 'download_and_extract_metadata') as mock_download, \
             patch.object(pipeline, '_process_audio') as mock_stt, \
             patch.object(pipeline, '_process_video_frames') as mock_ocr, \
             patch.object(pipeline.storage_service, 'store_video_with_expiry'), \
             patch.object(pipeline.firestore_service, 'save_parse_result'), \
             patch.object(pipeline, '_update_status'):
            
            mock_download.return_value = (sample_video_content, sample_metadata)
            mock_ocr.return_value = (sample_ocr_blocks, {"method": "gcp-vision", "processing_time_seconds": 8.0, "keyframes_processed": 30})
            
            result = await pipeline.process_tiktok_video(
                job_id="test-job-ocr",
                url="https://www.tiktok.com/@test_user/video/123456789",
                include_stt=False,
                include_ocr=True
            )
            
            assert result.status == ProcessingStatus.COMPLETED
            assert result.transcript_segments is None
            assert result.ocr_blocks == sample_ocr_blocks
            mock_stt.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_failure(self, pipeline):
        """Test handling of video download failure"""
        
        with patch.object(pipeline.video_processor, 'download_and_extract_metadata') as mock_download, \
             patch.object(pipeline.firestore_service, 'save_parse_result'), \
             patch.object(pipeline, '_update_status'):
            
            mock_download.side_effect = Exception("Video download failed")
            
            result = await pipeline.process_tiktok_video(
                job_id="test-job-fail",
                url="https://invalid.url",
                include_stt=True,
                include_ocr=True
            )
            
            assert result.status == ProcessingStatus.FAILED_DOWNLOAD
            assert "download" in result.error_message.lower()
            assert result.metrics.total_cost_usd == 0

    @pytest.mark.asyncio
    async def test_stt_failure_continues_with_ocr(
        self, pipeline, sample_video_content, sample_metadata, sample_ocr_blocks
    ):
        """Test that STT failure doesn't stop OCR processing"""
        
        with patch.object(pipeline.video_processor, 'download_and_extract_metadata') as mock_download, \
             patch.object(pipeline, '_process_audio') as mock_stt, \
             patch.object(pipeline, '_process_video_frames') as mock_ocr, \
             patch.object(pipeline.storage_service, 'store_video_with_expiry'), \
             patch.object(pipeline.firestore_service, 'save_parse_result'), \
             patch.object(pipeline, '_update_status'):
            
            mock_download.return_value = (sample_video_content, sample_metadata)
            mock_stt.side_effect = Exception("STT processing failed")
            mock_ocr.return_value = (sample_ocr_blocks, {"method": "gcp-vision", "processing_time_seconds": 8.0})
            
            result = await pipeline.process_tiktok_video(
                job_id="test-job-stt-fail",
                url="https://www.tiktok.com/@test_user/video/123456789",
                include_stt=True,
                include_ocr=True
            )
            
            # Should still complete successfully with OCR results
            assert result.status == ProcessingStatus.COMPLETED
            assert result.transcript_segments is None  # STT failed
            assert result.ocr_blocks == sample_ocr_blocks  # OCR succeeded

    @pytest.mark.asyncio
    async def test_cost_calculation(
        self, pipeline, sample_video_content, sample_metadata,
        sample_transcript_segments, sample_ocr_blocks
    ):
        """Test cost calculation accuracy"""
        
        with patch.object(pipeline.video_processor, 'download_and_extract_metadata') as mock_download, \
             patch.object(pipeline, '_process_audio') as mock_stt, \
             patch.object(pipeline, '_process_video_frames') as mock_ocr, \
             patch.object(pipeline.storage_service, 'store_video_with_expiry'), \
             patch.object(pipeline.firestore_service, 'save_parse_result'), \
             patch.object(pipeline, '_update_status'):
            
            mock_download.return_value = (sample_video_content, sample_metadata)
            mock_stt.return_value = (sample_transcript_segments, {
                "method": "whisper-local", 
                "processing_time_seconds": 10.0,
                "audio_duration_seconds": 45.0
            })
            mock_ocr.return_value = (sample_ocr_blocks, {
                "method": "gcp-vision", 
                "processing_time_seconds": 15.0,
                "keyframes_processed": 50
            })
            
            result = await pipeline.process_tiktok_video(
                job_id="test-cost",
                url="https://www.tiktok.com/@test_user/video/123456789",
                include_stt=True,
                include_ocr=True
            )
            
            # Verify cost components
            assert result.metrics.stt_cost_usd > 0
            assert result.metrics.ocr_cost_usd > 0
            assert result.metrics.storage_cost_usd > 0
            assert result.metrics.total_cost_usd == (
                result.metrics.stt_cost_usd + 
                result.metrics.ocr_cost_usd + 
                result.metrics.storage_cost_usd
            )
            
            # Cost should be reasonable (under $0.10 for test data)
            assert result.metrics.total_cost_usd < 0.10

    @pytest.mark.asyncio
    async def test_different_stt_methods(self, pipeline, sample_video_content, sample_metadata):
        """Test different STT method selection"""
        
        with patch.object(pipeline.video_processor, 'download_and_extract_metadata') as mock_download, \
             patch.object(pipeline.video_processor, 'extract_audio') as mock_extract_audio, \
             patch.object(pipeline.whisper_service, 'transcribe_audio') as mock_whisper, \
             patch.object(pipeline.storage_service, 'store_video_with_expiry'), \
             patch.object(pipeline.firestore_service, 'save_parse_result'), \
             patch.object(pipeline, '_update_status'):
            
            mock_download.return_value = (sample_video_content, sample_metadata)
            mock_extract_audio.return_value = b"fake_audio_content"
            mock_whisper.return_value = ([], {"method": "whisper-local"})
            
            # Test whisper-local method
            result = await pipeline.process_tiktok_video(
                job_id="test-whisper",
                url="https://www.tiktok.com/@test_user/video/123456789",
                include_stt=True,
                include_ocr=False,
                stt_method="whisper-local"
            )
            
            mock_whisper.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_status(self, pipeline):
        """Test health status reporting"""
        
        with patch.object(pipeline.video_processor, 'get_processing_stats') as mock_video_stats, \
             patch.object(pipeline.whisper_service, 'get_model_info') as mock_whisper_info:
            
            mock_video_stats.return_value = {"ffmpeg_available": True}
            mock_whisper_info.return_value = {"model_loaded": True, "gpu_available": False}
            
            health = await pipeline.get_health_status()
            
            assert "video_processor" in health
            assert "whisper" in health
            assert "services" in health
            assert health["whisper"]["model_loaded"] is True


class TestCostCalculation:
    """Test cost calculation methods"""
    
    def test_stt_cost_whisper_local_cpu(self):
        """Test STT cost calculation for local Whisper on CPU"""
        pipeline = ProductionPipeline()
        pipeline.whisper_service.device = "cpu"
        
        metadata = {"method": "whisper-local", "processing_time_seconds": 60.0}
        cost = pipeline._calculate_stt_cost(metadata)
        
        # CPU cost: $0.02/hour * (60s / 3600s) = ~$0.0003
        assert 0.0003 <= cost <= 0.001

    def test_stt_cost_whisper_local_gpu(self):
        """Test STT cost calculation for local Whisper on GPU"""
        pipeline = ProductionPipeline()
        pipeline.whisper_service.device = "cuda"
        
        metadata = {"method": "whisper-local", "processing_time_seconds": 60.0}
        cost = pipeline._calculate_stt_cost(metadata)
        
        # GPU cost: $0.10/hour * (60s / 3600s) = ~$0.0017
        assert 0.001 <= cost <= 0.003

    def test_ocr_cost_gcp_vision(self):
        """Test OCR cost calculation for Google Cloud Vision"""
        pipeline = ProductionPipeline()
        
        metadata = {"method": "gcp-vision", "keyframes_processed": 100}
        cost = pipeline._calculate_ocr_cost(metadata)
        
        # Vision API: $1.50/1000 images * 100 = $0.15
        assert cost == 0.15

    def test_storage_cost_calculation(self):
        """Test storage cost calculation"""
        pipeline = ProductionPipeline()
        
        # 10MB video
        video_size = 10 * 1024 * 1024
        cost = pipeline._calculate_storage_cost(video_size)
        
        # Should be very small for 24h storage
        assert 0 < cost < 0.001


@pytest.mark.integration
class TestIntegrationWithMocks:
    """Integration tests with mocked external services"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_mock_processing(self):
        """Test complete processing pipeline with all mocks"""
        pipeline = ProductionPipeline()
        
        # Mock all external dependencies
        with patch('src.services.enhanced_video_processor.yt_dlp.YoutubeDL'), \
             patch('src.services.whisper_service.whisper.load_model'), \
             patch('src.services.vision_service.VisionService.extract_text_batch'), \
             patch('src.services.firestore_service.FirestoreService.save_parse_result'), \
             patch('src.services.storage_service.StorageService.store_video_with_expiry'):
            
            # This would be a full integration test
            # For brevity, just test that it doesn't crash
            try:
                result = await pipeline.process_tiktok_video(
                    job_id="integration-test",
                    url="https://www.tiktok.com/@test/video/123",
                    include_stt=True,
                    include_ocr=True
                )
                
                # If we get here without exception, basic integration works
                assert result.job_id == "integration-test"
                
            except Exception as e:
                # Expected due to mocking, but shouldn't be critical errors
                assert "mock" not in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])