#!/usr/bin/env python3
"""
Simple metrics dashboard for HFSE game performance monitoring.
"""

import time
import json
import sys
try:
    from utils.metrics import metrics_collector
except ImportError:
    from metrics import metrics_collector

def print_header():
    print("=" * 60)
    print("    HAUNTED FILESYSTEM METRICS DASHBOARD")
    print("=" * 60)

def print_performance_summary():
    """Display current performance metrics."""
    summary = metrics_collector.get_performance_summary()
    
    print(f"Runtime: {summary['runtime_seconds']:.1f}s")
    print(f"Total Events: {summary['total_events']}")
    print(f"Events/sec: {summary['events_per_second']:.2f}")
    print(f"Overall Error Rate: {summary['overall_error_rate']:.1%}")
    print()
    
    if summary["event_breakdown"]:
        print("EVENT BREAKDOWN:")
        print("-" * 50)
        for event_name, stats in summary["event_breakdown"].items():
            print(f"{event_name:20} | {stats['count']:4d} events | "
                  f"{stats['avg_processing_time']*1000:6.1f}ms avg | "
                  f"{stats['error_rate']:5.1%} errors")
    
    # Show slow events
    slow_events = metrics_collector.get_slow_events()
    if slow_events:
        print(f"\nSLOW EVENTS ({len(slow_events)} detected):")
        print("-" * 40)
        for event in slow_events[-5:]:  # Last 5 slow events
            print(f"{event.event_type.name:20} | {event.source:15} | "
                  f"{event.processing_time*1000:6.1f}ms")
    
    # Show recent activity
    recent_events = metrics_collector.get_recent_events(10)
    if recent_events:
        print(f"\nRECENT ACTIVITY (last 10s):")
        print("-" * 40)
        for event in recent_events[-5:]:
            status = "✓" if event.success else "✗"
            print(f"{status} {event.event_type.name:20} | {event.source:15}")

def export_metrics(filename="metrics_export.json"):
    """Export metrics to JSON file."""
    summary = metrics_collector.get_performance_summary()
    
    # Convert enum names to strings for JSON serialization
    json_summary = {}
    for key, value in summary.items():
        if key == "event_breakdown":
            json_summary[key] = {str(k): v for k, v in value.items()}
        else:
            json_summary[key] = value
    
    with open(filename, 'w') as f:
        json.dump(json_summary, f, indent=2)
    
    print(f"Metrics exported to {filename}")

def main():
    """Run the metrics dashboard."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "export":
            export_metrics()
            return
        elif command == "summary":
            metrics_collector.log_performance_summary()
            return
        elif command == "reset":
            metrics_collector.reset_metrics()
            print("Metrics reset successfully")
            return
    
    print_header()
    print("Commands:")
    print("  python metrics_dashboard.py export   - Export metrics to JSON")
    print("  python metrics_dashboard.py summary  - Log summary to console")
    print("  python metrics_dashboard.py reset    - Reset all metrics")
    print("  python metrics_dashboard.py          - Show current metrics")
    print()
    
    print_performance_summary()

if __name__ == "__main__":
    main()