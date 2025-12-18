#!/usr/bin/env python3
"""
Metrics dashboard utility for monitoring game performance.
"""

import sys
import os
import time
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from metrics import metrics_collector
from events import EventType

class MetricsDashboard:
    """Real-time metrics dashboard."""
    
    def __init__(self):
        self.console = Console()
        self.last_refresh = time.time()
        
    def create_events_table(self) -> Table:
        """Create a table showing event statistics."""
        table = Table(title="Event Statistics")
        
        table.add_column("Event Type", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Avg Time", style="yellow")
        table.add_column("Error Rate", style="red")
        table.add_column("Events/sec", style="blue")
        
        summary = metrics_collector.get_performance_summary()
        
        for event_name, stats in summary.get("event_breakdown", {}).items():
            table.add_row(
                event_name,
                str(stats["count"]),
                f"{stats['avg_processing_time']:.3f}s",
                f"{stats['error_rate']:.1%}",
                f"{stats['events_per_second']:.2f}"
            )
        
        return table
    
    def create_performance_panel(self) -> Panel:
        """Create a panel showing overall performance metrics."""
        summary = metrics_collector.get_performance_summary()
        
        content = f"""
Runtime: {summary['runtime_seconds']:.1f}s
Total Events: {summary['total_events']}
Events/sec: {summary['events_per_second']:.2f}
Overall Error Rate: {summary['overall_error_rate']:.1%}
        """.strip()
        
        return Panel(content, title="Overall Performance", border_style="green")
    
    def create_recent_events_table(self) -> Table:
        """Create a table showing recent events."""
        table = Table(title="Recent Events (Last 60s)")
        
        table.add_column("Time", style="dim")
        table.add_column("Event", style="cyan")
        table.add_column("Source", style="yellow")
        table.add_column("Duration", style="green")
        table.add_column("Status", style="red")
        
        recent_events = metrics_collector.get_recent_events(60)
        
        # Show last 10 events
        for event in recent_events[-10:]:
            timestamp = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
            status = "✓" if event.success else "✗"
            status_style = "green" if event.success else "red"
            
            table.add_row(
                timestamp,
                event.event_type.name,
                event.source,
                f"{event.processing_time:.3f}s",
                f"[{status_style}]{status}[/{status_style}]"
            )
        
        return table
    
    def create_slow_events_panel(self) -> Panel:
        """Create a panel showing slow events."""
        slow_events = metrics_collector.get_slow_events()
        
        if not slow_events:
            content = "No slow events detected"
        else:
            content = f"Detected {len(slow_events)} slow events:\n\n"
            for event in slow_events[-5:]:  # Show last 5
                content += f"• {event.event_type.name}: {event.processing_time:.3f}s\n"
        
        return Panel(content, title="Slow Events", border_style="yellow")
    
    def create_layout(self) -> Layout:
        """Create the dashboard layout."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        layout["header"].update(
            Panel(
                f"HFSE Metrics Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                style="bold blue"
            )
        )
        
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        layout["left"].split_column(
            Layout(name="performance", size=8),
            Layout(name="events_table")
        )
        
        layout["right"].split_column(
            Layout(name="recent_events"),
            Layout(name="slow_events", size=10)
        )
        
        # Update content
        layout["performance"].update(self.create_performance_panel())
        layout["events_table"].update(self.create_events_table())
        layout["recent_events"].update(self.create_recent_events_table())
        layout["slow_events"].update(self.create_slow_events_panel())
        
        layout["footer"].update(
            Panel("Press Ctrl+C to exit | Updates every 2 seconds", style="dim")
        )
        
        return layout
    
    def run_dashboard(self, update_interval: int = 2):
        """Run the live dashboard."""
        self.console.print("Starting HFSE Metrics Dashboard...")
        
        try:
            with Live(self.create_layout(), console=self.console, refresh_per_second=0.5) as live:
                while True:
                    time.sleep(update_interval)
                    live.update(self.create_layout())
        except KeyboardInterrupt:
            self.console.print("\nDashboard stopped.")
    
    def print_summary(self):
        """Print a one-time summary."""
        self.console.print(self.create_performance_panel())
        self.console.print()
        self.console.print(self.create_events_table())
        self.console.print()
        self.console.print(self.create_slow_events_panel())
    
    def export_metrics(self, filename: str = None):
        """Export metrics to JSON file."""
        if filename is None:
            filename = f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = metrics_collector.get_performance_summary()
        
        # Add additional data
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "summary": summary,
            "recent_events": [
                {
                    "event_type": event.event_type.name,
                    "source": event.source,
                    "timestamp": event.timestamp,
                    "processing_time": event.processing_time,
                    "success": event.success,
                    "error": event.error
                }
                for event in metrics_collector.get_recent_events(3600)  # Last hour
            ],
            "slow_events": [
                {
                    "event_type": event.event_type.name,
                    "source": event.source,
                    "timestamp": event.timestamp,
                    "processing_time": event.processing_time,
                    "error": event.error
                }
                for event in metrics_collector.get_slow_events()
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        self.console.print(f"Metrics exported to {filename}")

def main():
    """Main entry point for the metrics dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(description="HFSE Metrics Dashboard")
    parser.add_argument("--live", action="store_true", help="Run live dashboard")
    parser.add_argument("--export", type=str, help="Export metrics to JSON file")
    parser.add_argument("--summary", action="store_true", help="Show summary and exit")
    
    args = parser.parse_args()
    
    dashboard = MetricsDashboard()
    
    if args.export:
        dashboard.export_metrics(args.export)
    elif args.live:
        dashboard.run_dashboard()
    elif args.summary:
        dashboard.print_summary()
    else:
        # Default: show summary
        dashboard.print_summary()

if __name__ == "__main__":
    main()