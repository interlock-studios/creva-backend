import time
import structlog
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager, contextmanager
from google.cloud import monitoring_v3
import os

logger = structlog.get_logger()


class MetricsCollector:
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if self.project_id:
            self.client = monitoring_v3.MetricServiceClient()
            self.project_name = f"projects/{self.project_id}"
        else:
            self.client = None
            self.project_name = None
    
    def record_processing_time(self, job_id: str, step: str, duration: float):
        try:
            if not self.client:
                logger.debug("Metrics recording skipped (no GCP project)")
                return
            
            series = monitoring_v3.TimeSeries()
            series.metric.type = "custom.googleapis.com/tiktok_parser/processing_time"
            series.resource.type = "global"
            
            series.metric.labels["job_id"] = job_id
            series.metric.labels["step"] = step
            
            now = time.time()
            seconds = int(now)
            nanos = int((now - seconds) * 10**9)
            interval = monitoring_v3.TimeInterval(
                {"end_time": {"seconds": seconds, "nanos": nanos}}
            )
            
            point = monitoring_v3.Point({
                "interval": interval,
                "value": {"double_value": duration}
            })
            series.points = [point]
            
            self.client.create_time_series(
                name=self.project_name,
                time_series=[series]
            )
            
            logger.debug("Metric recorded", metric="processing_time", step=step, duration=duration)
            
        except Exception as e:
            logger.warning("Failed to record metric", error=str(e))
    
    def record_cost(self, job_id: str, service: str, cost: float):
        try:
            if not self.client or cost <= 0:
                return
            
            series = monitoring_v3.TimeSeries()
            series.metric.type = "custom.googleapis.com/tiktok_parser/cost"
            series.resource.type = "global"
            
            series.metric.labels["job_id"] = job_id
            series.metric.labels["service"] = service
            
            now = time.time()
            seconds = int(now)
            nanos = int((now - seconds) * 10**9)
            interval = monitoring_v3.TimeInterval(
                {"end_time": {"seconds": seconds, "nanos": nanos}}
            )
            
            point = monitoring_v3.Point({
                "interval": interval,
                "value": {"double_value": cost}
            })
            series.points = [point]
            
            self.client.create_time_series(
                name=self.project_name,
                time_series=[series]
            )
            
            logger.debug("Cost metric recorded", service=service, cost=cost)
            
        except Exception as e:
            logger.warning("Failed to record cost metric", error=str(e))
    
    def record_error(self, job_id: str, error_type: str, step: str):
        try:
            if not self.client:
                return
            
            series = monitoring_v3.TimeSeries()
            series.metric.type = "custom.googleapis.com/tiktok_parser/errors"
            series.resource.type = "global"
            
            series.metric.labels["job_id"] = job_id
            series.metric.labels["error_type"] = error_type
            series.metric.labels["step"] = step
            
            now = time.time()
            seconds = int(now)
            nanos = int((now - seconds) * 10**9)
            interval = monitoring_v3.TimeInterval(
                {"end_time": {"seconds": seconds, "nanos": nanos}}
            )
            
            point = monitoring_v3.Point({
                "interval": interval,
                "value": {"int64_value": 1}
            })
            series.points = [point]
            
            self.client.create_time_series(
                name=self.project_name,
                time_series=[series]
            )
            
            logger.debug("Error metric recorded", error_type=error_type, step=step)
            
        except Exception as e:
            logger.warning("Failed to record error metric", error=str(e))


# Global metrics collector instance
metrics = MetricsCollector()


@asynccontextmanager
async def measure_time(job_id: str, step: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics.record_processing_time(job_id, step, duration)
        logger.info("Step completed", job_id=job_id, step=step, duration=duration)


@contextmanager
def measure_time_sync(job_id: str, step: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics.record_processing_time(job_id, step, duration)
        logger.info("Step completed", job_id=job_id, step=step, duration=duration)