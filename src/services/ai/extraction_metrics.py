"""Metrics and monitoring for requirements extraction."""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ExtractionMetrics:
    """Metrics for a single extraction operation."""

    document_id: str
    document_type: str
    extraction_method: str
    num_requirements: int
    processing_time_ms: int
    confidence_avg: float
    api_calls: int = 0
    cache_hit: bool = False
    errors: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "document_id": self.document_id,
            "document_type": self.document_type,
            "extraction_method": self.extraction_method,
            "num_requirements": self.num_requirements,
            "processing_time_ms": self.processing_time_ms,
            "confidence_avg": self.confidence_avg,
            "api_calls": self.api_calls,
            "cache_hit": self.cache_hit,
            "errors": self.errors,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(
                self.timestamp,
                tz=timezone.utc
            ).isoformat()
        }

    @property
    def is_successful(self) -> bool:
        """Check if extraction was successful."""
        return len(self.errors) == 0 and self.num_requirements > 0

    @property
    def performance_rating(self) -> str:
        """Rate performance based on processing time."""
        if self.processing_time_ms < 1000:
            return "excellent"
        elif self.processing_time_ms < 3000:
            return "good"
        elif self.processing_time_ms < 5000:
            return "acceptable"
        else:
            return "slow"

    @property
    def confidence_rating(self) -> str:
        """Rate confidence level."""
        if self.confidence_avg >= 0.9:
            return "very_high"
        elif self.confidence_avg >= 0.7:
            return "high"
        elif self.confidence_avg >= 0.5:
            return "medium"
        else:
            return "low"


class ExtractionMonitor:
    """Monitor and track extraction operations."""

    def __init__(self, max_history: int = 1000):
        """
        Initialize extraction monitor.

        Args:
            max_history: Maximum number of metrics to keep in memory
        """
        self.metrics: List[ExtractionMetrics] = []
        self.max_history = max_history

        # Aggregated stats
        self._total_extractions = 0
        self._total_api_calls = 0
        self._total_cache_hits = 0
        self._total_errors = 0
        self._total_processing_time = 0
        self._total_requirements = 0

        # By document type
        self._stats_by_type: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "requirements": 0,
                "processing_time": 0,
                "errors": 0,
                "cache_hits": 0
            }
        )

        # Performance alerts
        self._slow_threshold_ms = 5000
        self._low_confidence_threshold = 0.5

    async def record(self, metrics: ExtractionMetrics) -> None:
        """
        Record extraction metrics.

        Args:
            metrics: Metrics to record
        """
        # Add to history
        self.metrics.append(metrics)

        # Maintain max history
        if len(self.metrics) > self.max_history:
            self.metrics.pop(0)

        # Update aggregated stats
        self._total_extractions += 1
        self._total_api_calls += metrics.api_calls
        self._total_processing_time += metrics.processing_time_ms
        self._total_requirements += metrics.num_requirements

        if metrics.cache_hit:
            self._total_cache_hits += 1

        if metrics.errors:
            self._total_errors += 1

        # Update by document type
        type_stats = self._stats_by_type[metrics.document_type]
        type_stats["count"] += 1
        type_stats["requirements"] += metrics.num_requirements
        type_stats["processing_time"] += metrics.processing_time_ms
        if metrics.errors:
            type_stats["errors"] += 1
        if metrics.cache_hit:
            type_stats["cache_hits"] += 1

        # Log alerts
        if metrics.processing_time_ms > self._slow_threshold_ms:
            logger.warning(
                f"Slow extraction: {metrics.processing_time_ms}ms "
                f"for document {metrics.document_id}"
            )

        if metrics.confidence_avg < self._low_confidence_threshold:
            logger.warning(
                f"Low confidence extraction: {metrics.confidence_avg:.2f} "
                f"for document {metrics.document_id}"
            )

        if metrics.errors:
            logger.error(
                f"Extraction errors for document {metrics.document_id}: "
                f"{', '.join(metrics.errors)}"
            )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get overall statistics.

        Returns:
            Dictionary with aggregated statistics
        """
        if self._total_extractions == 0:
            return {
                "total_extractions": 0,
                "status": "no_data"
            }

        return {
            "total_extractions": self._total_extractions,
            "total_requirements": self._total_requirements,
            "avg_requirements_per_doc": (
                self._total_requirements / self._total_extractions
            ),
            "avg_processing_time_ms": (
                self._total_processing_time / self._total_extractions
            ),
            "total_api_calls": self._total_api_calls,
            "cache_hit_rate": (
                self._total_cache_hits / self._total_extractions
            ),
            "error_rate": (
                self._total_errors / self._total_extractions
            ),
            "stats_by_document_type": dict(self._stats_by_type),
            "recent_metrics": [
                m.to_dict() for m in self.metrics[-10:]
            ]
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary.

        Returns:
            Performance metrics summary
        """
        if not self.metrics:
            return {"status": "no_data"}

        # Performance distribution
        performance_dist = defaultdict(int)
        confidence_dist = defaultdict(int)

        for m in self.metrics:
            performance_dist[m.performance_rating] += 1
            confidence_dist[m.confidence_rating] += 1

        # Processing time percentiles
        processing_times = sorted([m.processing_time_ms for m in self.metrics])
        n = len(processing_times)

        return {
            "performance_distribution": dict(performance_dist),
            "confidence_distribution": dict(confidence_dist),
            "processing_time_percentiles": {
                "p50": processing_times[n // 2] if n > 0 else 0,
                "p90": processing_times[int(n * 0.9)] if n > 0 else 0,
                "p95": processing_times[int(n * 0.95)] if n > 0 else 0,
                "p99": processing_times[int(n * 0.99)] if n > 0 else 0,
                "max": processing_times[-1] if n > 0 else 0,
                "min": processing_times[0] if n > 0 else 0
            },
            "avg_confidence": (
                sum(m.confidence_avg for m in self.metrics) / len(self.metrics)
            ),
            "success_rate": (
                sum(1 for m in self.metrics if m.is_successful) / len(self.metrics)
            )
        }

    def get_cost_analysis(self) -> Dict[str, float]:
        """
        Analyze extraction costs.

        Returns:
            Cost analysis dictionary
        """
        # Estimated costs (adjust based on your pricing)
        COST_PER_API_CALL = 0.02  # Example: $0.02 per Mistral API call
        COST_PER_CACHE_HIT = 0.0001  # Minimal Redis cost

        total_api_cost = self._total_api_calls * COST_PER_API_CALL
        total_cache_cost = self._total_cache_hits * COST_PER_CACHE_HIT
        total_cost = total_api_cost + total_cache_cost

        savings_from_cache = (
            self._total_cache_hits * COST_PER_API_CALL - total_cache_cost
        )

        return {
            "total_cost_usd": total_cost,
            "api_cost_usd": total_api_cost,
            "cache_cost_usd": total_cache_cost,
            "savings_from_cache_usd": savings_from_cache,
            "avg_cost_per_document": (
                total_cost / self._total_extractions
                if self._total_extractions > 0
                else 0
            ),
            "cost_per_requirement": (
                total_cost / self._total_requirements
                if self._total_requirements > 0
                else 0
            )
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self.metrics.clear()
        self._total_extractions = 0
        self._total_api_calls = 0
        self._total_cache_hits = 0
        self._total_errors = 0
        self._total_processing_time = 0
        self._total_requirements = 0
        self._stats_by_type.clear()

        logger.info("Extraction monitor statistics reset")


# Global monitor instance
_monitor_instance: Optional[ExtractionMonitor] = None


def get_extraction_monitor() -> ExtractionMonitor:
    """
    Get or create global extraction monitor.

    Returns:
        ExtractionMonitor instance
    """
    global _monitor_instance

    if _monitor_instance is None:
        _monitor_instance = ExtractionMonitor()
        logger.info("Extraction monitor initialized")

    return _monitor_instance