#!/usr/bin/env python3
"""
Particle Animation System for HFSE

Provides ASCII particle effects for dramatic moments like game over screens.
Respects DISABLE_ANIMATIONS setting from dev config.
"""

import time
import random
import math
import threading
from typing import Callable, List, Tuple, Optional
from dataclasses import dataclass
import config.dev_config as _dev_cfg


# Particle character sets
DEATH_SYMBOLS = ['☠', '†', '✝', '⚰', '💀', '☆', '★', '✖', '✗', '⚔']
DIGITAL_GLITCH = ['0', '1', '#', '@', '*', '%', '░', '▒', '▓', '█', '/', '\\', '|', '-', '+', '=', '<', '>', '^', 'v']
MIXED_PARTICLES = DEATH_SYMBOLS + DIGITAL_GLITCH


@dataclass
class Particle:
    """A single particle in the animation."""
    x: float
    y: float
    vx: float  # velocity x
    vy: float  # velocity y
    char: str
    color: str  # Rich markup color
    life: float  # remaining life (0-1)
    decay: float  # how fast life decreases


class ParticleSystem:
    """Manages a collection of particles for animation."""

    def __init__(self, width: int = 70, height: int = 20):
        self.width = width
        self.height = height
        self.particles: List[Particle] = []
        self.gravity = 0.1
        self.friction = 0.98

    def spawn_explosion(self, center_x: float, center_y: float,
                        count: int = 50, power: float = 2.0,
                        particle_chars: List[str] = None):
        """Spawn particles in an explosion pattern from center point."""
        if particle_chars is None:
            particle_chars = MIXED_PARTICLES

        colors = ['red', 'yellow', 'bright_red', 'bright_yellow', 'white', 'magenta']

        for _ in range(count):
            # Random angle for explosion direction
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.5, power)

            particle = Particle(
                x=center_x,
                y=center_y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed * 0.5,  # Slower vertical for terminal aspect ratio
                char=random.choice(particle_chars),
                color=random.choice(colors),
                life=1.0,
                decay=random.uniform(0.02, 0.05)
            )
            self.particles.append(particle)

    def spawn_rain(self, count: int = 30, particle_chars: List[str] = None):
        """Spawn particles falling from top."""
        if particle_chars is None:
            particle_chars = DIGITAL_GLITCH

        colors = ['red', 'dim red', 'bright_red']

        for _ in range(count):
            particle = Particle(
                x=random.uniform(0, self.width),
                y=random.uniform(-5, 0),
                vx=random.uniform(-0.1, 0.1),
                vy=random.uniform(0.3, 0.8),
                char=random.choice(particle_chars),
                color=random.choice(colors),
                life=1.0,
                decay=random.uniform(0.01, 0.03)
            )
            self.particles.append(particle)

    def update(self, dt: float = 0.1):
        """Update all particles for one frame."""
        for particle in self.particles:
            # Apply velocity
            particle.x += particle.vx
            particle.y += particle.vy

            # Apply gravity
            particle.vy += self.gravity * dt

            # Apply friction
            particle.vx *= self.friction
            particle.vy *= self.friction

            # Decay life
            particle.life -= particle.decay

            # Bounce off floor
            if particle.y >= self.height - 1:
                particle.y = self.height - 1
                particle.vy *= -0.3  # Dampen bounce

        # Remove dead particles
        self.particles = [p for p in self.particles if p.life > 0]

    def render(self) -> List[List[Tuple[str, str]]]:
        """Render particles to a 2D grid with colors."""
        # Grid of (char, color) tuples
        grid = [[(' ', 'white') for _ in range(self.width)] for _ in range(self.height)]

        for particle in self.particles:
            x = int(particle.x)
            y = int(particle.y)

            if 0 <= x < self.width and 0 <= y < self.height:
                # Adjust color based on life for fade effect
                color = particle.color
                if particle.life < 0.3:
                    color = 'dim ' + color if not color.startswith('dim') else color
                grid[y][x] = (particle.char, color)

        return grid

    def render_to_string(self, overlay_text: str = None,
                         overlay_y: int = None,
                         overlay_color: str = 'bold red') -> str:
        """Render particles to a Rich-formatted string."""
        grid = self.render()
        lines = []

        # Parse overlay text into lines if provided
        overlay_lines = []
        if overlay_text:
            overlay_lines = overlay_text.split('\n')
            if overlay_y is None:
                overlay_y = (self.height - len(overlay_lines)) // 2

        for row_idx, row in enumerate(grid):
            line_parts = []

            # Check if this row has overlay text
            overlay_row = None
            if overlay_lines and overlay_y is not None:
                rel_row = row_idx - overlay_y
                if 0 <= rel_row < len(overlay_lines):
                    overlay_row = overlay_lines[rel_row]

            for col_idx, (char, color) in enumerate(row):
                # Check if overlay covers this position
                if overlay_row and col_idx < len(overlay_row):
                    overlay_char = overlay_row[col_idx]
                    if overlay_char != ' ':
                        line_parts.append(f'[{overlay_color}]{overlay_char}[/{overlay_color}]')
                        continue

                if char != ' ':
                    line_parts.append(f'[{color}]{char}[/{color}]')
                else:
                    line_parts.append(' ')

            lines.append(''.join(line_parts))

        return '\n'.join(lines)


class GameOverAnimation:
    """Handles the full game over animation sequence."""

    GAME_OVER_ASCII = """
 ██████╗  █████╗ ███╗   ███╗███████╗     ██████╗ ██╗   ██╗███████╗██████╗
██╔════╝ ██╔══██╗████╗ ████║██╔════╝    ██╔═══██╗██║   ██║██╔════╝██╔══██╗
██║  ███╗███████║██╔████╔██║█████╗      ██║   ██║██║   ██║█████╗  ██████╔╝
██║   ██║██╔══██║██║╚██╔╝██║██╔══╝      ██║   ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗
╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗    ╚██████╔╝ ╚████╔╝ ███████╗██║  ██║
 ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝     ╚═════╝   ╚═══╝  ╚══════╝╚═╝  ╚═╝
"""

    SEGFAULT_TEXT = """
                    >>> SEGMENTATION FAULT <<<

          Your essence scatters through broken memory.
       The filesystem quakes as the Daemon Overlord grows...
"""

    OPTIONS_TEXT = """
[dim]The digital void echoes with the sound of your defeat.[/dim]
[italic cyan]Even the greatest sysadmins must sometimes face corruption...[/italic cyan]

[bold white]Options:[/bold white]
  [bold green]r[/bold green] - Restart from your last save
  [bold yellow]n[/bold yellow] - Start a new game
  [bold red]q[/bold red] - Quit to shell

[bold white]What would you like to do?[/bold white] """

    def __init__(self, width: int = 75, height: int = 22):
        self.width = width
        self.height = height
        self.particle_system = ParticleSystem(width, height)
        self._stop_flag = False

    def run_animation(self, output_callback: Callable[[str], None],
                      duration: float = 2.5, fps: float = 15):
        """
        Run the full game over animation sequence.

        Args:
            output_callback: Function to call with each frame (Rich-formatted string)
            duration: How long the particle animation runs
            fps: Frames per second for animation
        """
        if _dev_cfg.DISABLE_ANIMATIONS:
            # Skip animation, show final result immediately.
            # Dynamic read so settings toggled at runtime are respected.
            output_callback(self._get_final_frame())
            return

        self._stop_flag = False
        frame_time = 1.0 / fps

        # Phase 1: Initial explosion burst
        center_x = self.width // 2
        center_y = self.height // 2

        # Spawn initial explosion
        self.particle_system.spawn_explosion(
            center_x, center_y,
            count=80,
            power=3.0,
            particle_chars=MIXED_PARTICLES
        )

        # Add some extra bursts offset from center
        self.particle_system.spawn_explosion(center_x - 15, center_y, count=30, power=2.0)
        self.particle_system.spawn_explosion(center_x + 15, center_y, count=30, power=2.0)

        start_time = time.time()

        while time.time() - start_time < duration and not self._stop_flag:
            # Calculate animation progress (0-1)
            progress = (time.time() - start_time) / duration

            # Update particles
            self.particle_system.update(frame_time)

            # Add occasional new particles for sustained effect
            if random.random() < 0.3:
                self.particle_system.spawn_explosion(
                    center_x + random.uniform(-20, 20),
                    center_y + random.uniform(-3, 3),
                    count=5,
                    power=1.0
                )

            # Render frame with GAME OVER text fading in
            if progress > 0.3:
                # Start showing text after initial explosion
                text_alpha = min(1.0, (progress - 0.3) / 0.3)
                frame = self.particle_system.render_to_string(
                    overlay_text=self.GAME_OVER_ASCII,
                    overlay_y=4,
                    overlay_color='bold red' if text_alpha > 0.5 else 'red'
                )
            else:
                frame = self.particle_system.render_to_string()

            output_callback(frame)
            time.sleep(frame_time)

        # Final frame with full text
        output_callback(self._get_final_frame())

    def _get_final_frame(self) -> str:
        """Get the final static game over screen."""
        return f"""[bold red]
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║  ██████╗  █████╗ ███╗   ███╗███████╗     ██████╗ ██╗   ██╗███████╗██████╗ ║
║ ██╔════╝ ██╔══██╗████╗ ████║██╔════╝    ██╔═══██╗██║   ██║██╔════╝██╔══██╗║
║ ██║  ███╗███████║██╔████╔██║█████╗      ██║   ██║██║   ██║█████╗  ██████╔╝║
║ ██║   ██║██╔══██║██║╚██╔╝██║██╔══╝      ██║   ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗║
║ ╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗    ╚██████╔╝ ╚████╔╝ ███████╗██║  ██║║
║  ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝     ╚═════╝   ╚═══╝  ╚══════╝╚═╝  ╚═╝║
║                                                                          ║
║                      >>> SEGMENTATION FAULT <<<                          ║
║                                                                          ║
║            Your essence scatters through broken memory.                  ║
║         The filesystem quakes as the Daemon Overlord grows...            ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
[/bold red]
{self.OPTIONS_TEXT}"""

    def stop(self):
        """Stop the animation early."""
        self._stop_flag = True


def run_game_over_animation(output_callback: Callable[[str], None],
                            call_from_thread: Callable = None):
    """
    Convenience function to run game over animation.

    Args:
        output_callback: Function to update the display
        call_from_thread: Optional thread-safe callback wrapper (for Textual)
    """
    animation = GameOverAnimation()

    def safe_callback(content: str):
        if call_from_thread:
            call_from_thread(output_callback, content)
        else:
            output_callback(content)

    # Run in current thread (caller should use threading if needed)
    animation.run_animation(safe_callback)
