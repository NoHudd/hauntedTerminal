#!/usr/bin/env python3
"""
Performance monitoring and metrics for the game engine.
"""

import time
import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from src.events import EventType

logger = logging.getLogger(__name__)

@dataclass
class EventMetric:
    """Represents metrics for a single event."""
    event_type: 'EventType'
    source: str
    timestamp: float
    processing_time: float
    success: bool
    error: Optional[str] = None

class MetricsCollector:
    """Collects and analyzes performance metrics."""
    
    def __init__(self, max_events: int = 1000):
        """Initialize metrics collector."""
        self.max_events = max_events
        self.event_metrics: deque = deque(maxlen=max_events)
        self.event_counts: Dict = defaultdict(int)
        self.processing_times: Dict = defaultdict(list)
        self.error_counts: Dict = defaultdict(int)
        self.start_time = time.time()
        
        # Performance thresholds (in seconds)
        self.slow_event_threshold = 0.1  # 100ms
        self.warning_error_rate = 0.1  # 10% error rate
    
    def record_event(self, event_type: 'EventType', source: str, processing_time: float, 
                     success: bool = True, error: Optional[str] = None):
        """Record metrics for an event."""
        timestamp = time.time()
        
        metric = EventMetric(
            event_type=event_type,
            source=source,
            timestamp=timestamp,
            processing_time=processing_time,
            success=success,
            error=error
        )
        
        self.event_metrics.append(metric)
        self.event_counts[event_type] += 1
        self.processing_times[event_type].append(processing_time)
        
        if not success:
            self.error_counts[event_type] += 1
        
        # Check for performance issues
        if processing_time > self.slow_event_threshold:
            logger.warning(f"Slow event detected: {event_type} took {processing_time:.3f}s")
        
        # Check for error rate issues
        error_rate = self.get_error_rate(event_type)
        if error_rate > self.warning_error_rate:
            logger.warning(f"High error rate for {event_type}: {error_rate:.1%}")
    
    def get_event_count(self, event_type: 'EventType') -> int:
        """Get total count for an event type."""
        return self.event_counts[event_type]
    
    def get_average_processing_time(self, event_type: 'EventType') -> float:
        """Get average processing time for an event type."""
        times = self.processing_times[event_type]
        return sum(times) / len(times) if times else 0.0
    
    def get_error_rate(self, event_type: 'EventType') -> float:
        """Get error rate for an event type."""
        total_count = self.event_counts[event_type]
        error_count = self.error_counts[event_type]
        return error_count / total_count if total_count > 0 else 0.0
    
    def get_events_per_second(self, event_type: Optional['EventType'] = None) -> float:
        """Get events per second rate."""
        current_time = time.time()
        runtime = current_time - self.start_time
        
        if event_type:
            count = self.event_counts[event_type]
        else:
            count = sum(self.event_counts.values())
        
        return count / runtime if runtime > 0 else 0.0
    
    def get_slow_events(self, threshold: Optional[float] = None) -> List[EventMetric]:
        """Get events that exceeded the processing time threshold."""
        if threshold is None:
            threshold = self.slow_event_threshold
        
        return [metric for metric in self.event_metrics if metric.processing_time > threshold]
    
    def get_recent_events(self, seconds: int = 60) -> List[EventMetric]:
        """Get events from the last N seconds."""
        cutoff_time = time.time() - seconds
        return [metric for metric in self.event_metrics if metric.timestamp > cutoff_time]
    
    def get_performance_summary(self) -> Dict:
        """Get a comprehensive performance summary."""
        total_events = sum(self.event_counts.values())
        total_errors = sum(self.error_counts.values())
        
        summary = {
            "total_events": total_events,
            "total_errors": total_errors,
            "overall_error_rate": total_errors / total_events if total_events > 0 else 0.0,
            "events_per_second": self.get_events_per_second(),
            "runtime_seconds": time.time() - self.start_time,
            "event_breakdown": {}
        }
        
        for event_type in self.event_counts:
            summary["event_breakdown"][event_type.name] = {
                "count": self.get_event_count(event_type),
                "avg_processing_time": self.get_average_processing_time(event_type),
                "error_rate": self.get_error_rate(event_type),
                "events_per_second": self.get_events_per_second(event_type)
            }
        
        return summary
    
    def log_performance_summary(self):
        """Log a performance summary."""
        summary = self.get_performance_summary()
        
        logger.info("=== Performance Summary ===")
        logger.info(f"Runtime: {summary['runtime_seconds']:.1f}s")
        logger.info(f"Total Events: {summary['total_events']}")
        logger.info(f"Events/sec: {summary['events_per_second']:.2f}")
        logger.info(f"Error Rate: {summary['overall_error_rate']:.1%}")
        
        if summary["event_breakdown"]:
            logger.info("Event Breakdown:")
            for event_name, stats in summary["event_breakdown"].items():
                logger.info(
                    f"  {event_name}: {stats['count']} events, "
                    f"{stats['avg_processing_time']:.3f}s avg, "
                    f"{stats['error_rate']:.1%} errors"
                )
        
        # Log slow events
        slow_events = self.get_slow_events()
        if slow_events:
            logger.warning(f"{len(slow_events)} slow events detected:")
            for event in slow_events[-5:]:  # Show last 5 slow events
                logger.warning(
                    f"  {event.event_type.name} from {event.source}: {event.processing_time:.3f}s"
                )
    
    def reset_metrics(self):
        """Reset all collected metrics."""
        self.event_metrics.clear()
        self.event_counts.clear()
        self.processing_times.clear()
        self.error_counts.clear()
        self.start_time = time.time()
        logger.info("Metrics reset")

# Global metrics collector instance
metrics_collector = MetricsCollector()

class EventTimer:
    """Context manager for timing event processing."""
    
    def __init__(self, event_type: 'EventType', source: str):
        self.event_type = event_type
        self.source = source
        self.start_time = None
        self.success = True
        self.error = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            processing_time = time.time() - self.start_time
            
            if exc_type is not None:
                self.success = False
                self.error = str(exc_val)
            
            metrics_collector.record_event(
                self.event_type,
                self.source,
                processing_time,
                self.success,
                self.error
            )
        
        # Don't suppress exceptions
        return False

def time_event(event_type: 'EventType', source: str):
    """Decorator to time event processing."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with EventTimer(event_type, source):
                return func(*args, **kwargs)
        return wrapper
    return decorator