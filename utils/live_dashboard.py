#!/usr/bin/env python3
"""
Live metrics dashboard using Textual for real-time monitoring.
"""

from textual.app import App, ComposeResult
from textual.widgets import Static, DataTable, Header, Footer
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import var
from textual import on
import asyncio
from rich.text import Text
from rich.table import Table
try:
    from utils.metrics import metrics_collector
except ImportError:
    from metrics import metrics_collector

class LiveMetricsDashboard(App):
    """Live dashboard for game metrics."""
    
    CSS = """
    #summary {
        height: 6;
        border: solid blue;
        padding: 1;
    }
    
    #events-table {
        height: 1fr;
        border: solid green;
    }
    
    #slow-events {
        height: 8;
        border: solid red;
        padding: 1;
    }
    
    #recent-activity {
        height: 8;
        border: solid yellow;
        padding: 1;
    }
    """
    
    def __init__(self):
        super().__init__()
        self._auto_refresh = True
        
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical():
                yield Static("", id="summary")
                yield DataTable(id="events-table")
            with Vertical():
                yield Static("", id="slow-events")  
                yield Static("", id="recent-activity")
        yield Footer()
    
    def on_mount(self) -> None:
        """Setup the dashboard when mounted."""
        self.title = "HFSE Live Metrics Dashboard"
        
        # Setup events table
        table = self.query_one("#events-table", DataTable)
        table.add_column("Event Type", width=20)
        table.add_column("Count", width=8)
        table.add_column("Avg Time", width=10) 
        table.add_column("Error Rate", width=10)
        table.add_column("Events/sec", width=10)
        
        # Start refresh timer
        self.set_interval(1.0, self.refresh_data)
        
    def refresh_data(self):
        """Refresh all dashboard data."""
        if not self._auto_refresh:
            return
            
        summary = metrics_collector.get_performance_summary()
        
        # Update summary
        summary_text = Text()
        summary_text.append(f"Runtime: {summary['runtime_seconds']:.1f}s | ", style="white")
        summary_text.append(f"Total Events: {summary['total_events']} | ", style="cyan") 
        summary_text.append(f"Events/sec: {summary['events_per_second']:.2f} | ", style="green")
        error_style = "red" if summary['overall_error_rate'] > 0.1 else "green"
        summary_text.append(f"Error Rate: {summary['overall_error_rate']:.1%}", style=error_style)
        
        self.query_one("#summary").update(summary_text)
        
        # Update events table
        table = self.query_one("#events-table", DataTable)
        table.clear()
        
        for event_name, stats in summary.get("event_breakdown", {}).items():
            table.add_row(
                event_name,
                str(stats['count']),
                f"{stats['avg_processing_time']*1000:.1f}ms",
                f"{stats['error_rate']:.1%}",
                f"{stats['events_per_second']:.2f}"
            )
        
        # Update slow events
        slow_events = metrics_collector.get_slow_events()
        slow_text = Text()
        slow_text.append(f"SLOW EVENTS ({len(slow_events)} detected)\n", style="bold red")
        
        for event in slow_events[-5:]:
            slow_text.append(f"• {event.event_type.name} ", style="yellow")
            slow_text.append(f"({event.processing_time*1000:.1f}ms)\n", style="red")
        
        self.query_one("#slow-events").update(slow_text)
        
        # Update recent activity  
        recent_events = metrics_collector.get_recent_events(10)
        activity_text = Text()
        activity_text.append("RECENT ACTIVITY (last 10s)\n", style="bold yellow")
        
        for event in recent_events[-8:]:
            status = "✓" if event.success else "✗"
            status_style = "green" if event.success else "red"
            activity_text.append(f"{status} ", style=status_style)
            activity_text.append(f"{event.event_type.name}\n", style="white")
        
        self.query_one("#recent-activity").update(activity_text)
    
    def action_toggle_auto_refresh(self) -> None:
        """Toggle auto refresh."""
        self._auto_refresh = not self._auto_refresh
        self.notify(f"Auto refresh: {'ON' if self._auto_refresh else 'OFF'}")
    
    def action_reset_metrics(self) -> None:
        """Reset all metrics."""
        metrics_collector.reset_metrics()
        self.notify("Metrics reset")
    
    def action_export_metrics(self) -> None:
        """Export metrics to file."""
        summary = metrics_collector.get_performance_summary()
        filename = f"metrics_export_{int(summary['runtime_seconds'])}.json"
        
        import json
        json_summary = {}
        for key, value in summary.items():
            if key == "event_breakdown":
                json_summary[key] = {str(k): v for k, v in value.items()}
            else:
                json_summary[key] = value
        
        with open(filename, 'w') as f:
            json.dump(json_summary, f, indent=2)
        
        self.notify(f"Exported to {filename}")

if __name__ == "__main__":
    app = LiveMetricsDashboard()
    app.run()