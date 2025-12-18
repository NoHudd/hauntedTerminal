#!/usr/bin/env python3
"""
Enhanced Combat Widgets for Textual UI

Custom widgets specifically designed for dynamic combat interactions,
maintaining the CLI aesthetic while providing rich visual feedback.
"""

from textual.widgets import Static, Button, ProgressBar
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive, var
from textual.app import ComposeResult
from rich.text import Text
from rich.console import Console
from rich.align import Align
import asyncio
import random
from typing import Optional, Dict, Any, List, Tuple
import threading
import time

class AnimatedHealthBar(Static):
    """An animated health bar that smoothly transitions between values."""
    
    current_health = reactive(100)
    max_health = reactive(100)
    bar_length = reactive(20)
    
    def __init__(self, 
                 initial_health: int = 100, 
                 max_health: int = 100,
                 bar_length: int = 20,
                 entity_name: str = "Entity",
                 bar_color: str = "green",
                 **kwargs):
        super().__init__(**kwargs)
        self.current_health = initial_health
        self.max_health = max_health
        self.bar_length = bar_length
        self.entity_name = entity_name
        self.bar_color = bar_color
        self.animation_thread = None
        self.target_health = initial_health
        
    def update_health(self, new_health: int, animate: bool = True):
        """Update health with optional animation."""
        new_health = max(0, min(new_health, self.max_health))
        self.target_health = new_health
        
        if animate and new_health != self.current_health:
            self._start_health_animation()
        else:
            self.current_health = new_health
    
    def _start_health_animation(self):
        """Start smooth health animation in background thread."""
        if self.animation_thread and self.animation_thread.is_alive():
            return  # Animation already running
            
        def animate():
            start_health = self.current_health
            target_health = self.target_health
            steps = 20
            step_size = (target_health - start_health) / steps
            
            for i in range(steps + 1):
                new_health = start_health + (step_size * i)
                self.call_from_thread(setattr, self, 'current_health', int(new_health))
                time.sleep(0.025)  # 500ms total animation
        
        self.animation_thread = threading.Thread(target=animate, daemon=True)
        self.animation_thread.start()
    
    def watch_current_health(self, current: int) -> None:
        """React to health changes and update display."""
        self._update_display()
    
    def watch_max_health(self, maximum: int) -> None:
        """React to max health changes."""
        self._update_display()
    
    def _update_display(self):
        """Update the visual representation of the health bar."""
        if self.max_health <= 0:
            health_ratio = 0
        else:
            health_ratio = self.current_health / self.max_health
        
        # Calculate bar segments
        filled_segments = int(health_ratio * self.bar_length)
        empty_segments = self.bar_length - filled_segments
        
        # Choose color based on health percentage
        if health_ratio > 0.7:
            color = "green"
        elif health_ratio > 0.3:
            color = "yellow" 
        else:
            color = "red"
        
        # Create the bar
        filled_bar = "█" * filled_segments
        empty_bar = "▒" * empty_segments
        
        # Format the complete display
        health_text = Text()
        health_text.append(f"{self.entity_name}: ", style="bold")
        health_text.append(f"{self.current_health}/{self.max_health}", style="bold white")
        health_text.append(" [")
        health_text.append(filled_bar, style=f"bold {color}")
        health_text.append(empty_bar, style="dim white")
        health_text.append("]")
        
        # Add health percentage
        percentage = int(health_ratio * 100)
        health_text.append(f" {percentage}%", style="dim")
        
        self.update(health_text)

class CombatActionButton(Button):
    """Enhanced button for combat actions with hotkey support."""
    
    def __init__(self, 
                 action_id: str,
                 label: str, 
                 hotkey: str = "",
                 damage_info: str = "",
                 cooldown: int = 0,
                 accuracy: int = 100,
                 **kwargs):
        # Format label with hotkey if provided
        if hotkey:
            display_label = f"[{hotkey}] {label}"
        else:
            display_label = label
            
        super().__init__(display_label, **kwargs)
        self.action_id = action_id
        self.original_label = label
        self.hotkey = hotkey
        self.damage_info = damage_info
        self.cooldown = cooldown
        self.accuracy = accuracy
        self.is_on_cooldown = False
        self.cooldown_remaining = 0
        
    def update_button_state(self, on_cooldown: bool = False, cooldown_remaining: int = 0):
        """Update button state based on cooldown status."""
        self.is_on_cooldown = on_cooldown
        self.cooldown_remaining = cooldown_remaining
        
        if on_cooldown:
            # Show cooldown in label
            cooldown_label = f"[{self.hotkey}] {self.original_label} ({cooldown_remaining}t)"
            self.label = cooldown_label
            self.add_class("combat-action-button-disabled")
            self.disabled = True
        else:
            # Show normal label with damage info
            if self.damage_info:
                normal_label = f"[{self.hotkey}] {self.original_label} {self.damage_info}"
            else:
                normal_label = f"[{self.hotkey}] {self.original_label}"
            self.label = normal_label
            self.remove_class("combat-action-button-disabled")
            self.disabled = False

class FloatingDamageNumber(Static):
    """Widget that displays floating damage/healing numbers with animation."""
    
    def __init__(self, 
                 value: int, 
                 is_healing: bool = False, 
                 is_critical: bool = False,
                 **kwargs):
        super().__init__(**kwargs)
        self.value = value
        self.is_healing = is_healing
        self.is_critical = is_critical
        self.animation_complete = False
        
    def on_mount(self) -> None:
        """Start the floating animation when mounted."""
        self._create_damage_display()
        self._start_float_animation()
    
    def _create_damage_display(self):
        """Create the damage number display."""
        if self.is_healing:
            prefix = "+"
            color = "green" 
            style_class = "heal-number"
        else:
            prefix = "-"
            color = "red"
            style_class = "damage-number"
        
        if self.is_critical:
            style_class = "critical-hit"
            display_text = f"CRITICAL! {prefix}{self.value}"
        else:
            display_text = f"{prefix}{self.value}"
        
        damage_text = Text(display_text, style=style_class)
        self.update(damage_text)
        
    def _start_float_animation(self):
        """Animate the floating effect with simple timer."""
        def animate():
            # Show for 1.5 seconds then signal completion
            time.sleep(1.5)
            self.animation_complete = True
            # Try to signal parent to remove - if it fails, that's okay
            try:
                self.post_message(self.AnimationComplete())
            except:
                pass
        
        animation_thread = threading.Thread(target=animate, daemon=True)
        animation_thread.start()
    
    class AnimationComplete:
        """Message sent when animation is complete."""
        pass

class CombatLogPanel(Static):
    """Scrolling combat log with colored entries."""
    
    def __init__(self, max_entries: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.max_entries = max_entries
        self.log_entries: List[Tuple[str, str, str]] = []  # (message, actor, style)
        
    def add_log_entry(self, message: str, actor: str = "system", style: str = ""):
        """Add a new entry to the combat log."""
        # Determine style based on actor
        if not style:
            if actor == "player":
                style = "combat-log-player"
            elif actor == "enemy":
                style = "combat-log-enemy"
            else:
                style = "combat-log-system"
        
        # Add timestamp prefix
        import time
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_entries.append((formatted_message, actor, style))
        
        # Keep only the latest entries
        if len(self.log_entries) > self.max_entries:
            self.log_entries.pop(0)
        
        self._update_display()
    
    def _update_display(self):
        """Update the log display."""
        if not self.log_entries:
            self.update("Combat log will appear here...")
            return
        
        log_text = Text()
        for i, (message, actor, style) in enumerate(self.log_entries):
            if i > 0:
                log_text.append("\n")
            log_text.append(message, style=style)
        
        self.update(log_text)
    
    def clear_log(self):
        """Clear all log entries."""
        self.log_entries.clear()
        self._update_display()

class AttackEffectDisplay(Static):
    """Widget for displaying attack effects and animations."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.effect_queue: List[Dict[str, Any]] = []
        self.current_effect = None
        
    def show_attack_effect(self, attack_type: str, attack_name: str, hit: bool = True):
        """Display attack effect based on type."""
        effect_data = {
            "attack_type": attack_type,
            "attack_name": attack_name,
            "hit": hit,
            "timestamp": time.time()
        }
        
        self.effect_queue.append(effect_data)
        
        if not self.current_effect:
            self._process_next_effect()
    
    def _process_next_effect(self):
        """Process the next effect in the queue."""
        if not self.effect_queue:
            self.current_effect = None
            self.update("")
            return
        
        self.current_effect = self.effect_queue.pop(0)
        self._display_effect()
    
    def _display_effect(self):
        """Display the current effect."""
        if not self.current_effect:
            return
        
        attack_type = self.current_effect["attack_type"]
        attack_name = self.current_effect["attack_name"]
        hit = self.current_effect["hit"]
        
        # Create ASCII effect based on attack type
        effects = self._get_attack_ascii_effects(attack_type, hit)
        
        def animate_effect():
            for effect in effects:
                self.call_from_thread(self.update, Text(effect, style="bold cyan"))
                time.sleep(0.2)
            
            # Clear effect after animation
            time.sleep(0.5)
            self.call_from_thread(self._process_next_effect)
        
        effect_thread = threading.Thread(target=animate_effect, daemon=True)
        effect_thread.start()
    
    def _get_attack_ascii_effects(self, attack_type: str, hit: bool) -> List[str]:
        """Get ASCII effects for different attack types."""
        if not hit:
            return ["MISS!", ""]
        
        if attack_type == "physical":
            return [
                "⚔️  ⚡ STRIKE! ⚡  ⚔️",
                "   💥 IMPACT! 💥   ",
                ""
            ]
        elif attack_type == "magical":
            return [
                "✨  🔥 MAGIC! 🔥  ✨",
                "  ⭐ ARCANE! ⭐  ",
                ""
            ]
        elif attack_type == "nature":
            return [
                "🌿  🌟 NATURE! 🌟  🌿",
                "   🍃 POWER! 🍃   ",
                ""
            ]
        else:
            return [
                "💫  ⚡ ATTACK! ⚡  💫",
                ""
            ]

class CombatActionPanel(Container):
    """Container for combat action buttons with hotkey support."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.action_buttons: Dict[str, CombatActionButton] = {}
        
    def compose(self) -> ComposeResult:
        """Create the action button layout."""
        with Vertical():
            yield Static("Combat Actions:", classes="combat-panel-title")
            with Horizontal(classes="combat-actions-row"):
                # Placeholder buttons - will be populated dynamically
                pass
    
    def update_actions(self, available_actions: Dict[str, Any]):
        """Update available actions and create buttons."""
        # Clear existing buttons
        self.action_buttons.clear()
        
        # Remove existing action buttons
        actions_row = self.query_one(".combat-actions-row")
        actions_row.remove_children()
        
        # Create new buttons for available actions
        for i, (action_id, action_data) in enumerate(available_actions.items()):
            hotkey = str(i + 1) if i < 9 else ""
            
            # Format damage info
            damage_bonus = action_data.get('bonus_damage', 0)
            damage_info = f"({damage_bonus} dmg)" if damage_bonus > 0 else ""
            
            button = CombatActionButton(
                action_id=action_id,
                label=action_data.get('name', action_id),
                hotkey=hotkey,
                damage_info=damage_info,
                cooldown=action_data.get('cooldown', 0),
                accuracy=action_data.get('accuracy', 100),
                classes="combat-action-button"
            )
            
            # Update button state based on cooldown
            on_cooldown = action_data.get('on_cooldown', False)
            cooldown_remaining = action_data.get('cooldown_remaining', 0)
            button.update_button_state(on_cooldown, cooldown_remaining)
            
            self.action_buttons[action_id] = button
            actions_row.mount(button)