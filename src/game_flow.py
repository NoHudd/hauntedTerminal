"""End-of-run flow: game over, victory, and the quit confirmation."""
import threading

from src.events import EventType
from utils.debug_tools import debug_log
from utils.particle_animation import GameOverAnimation

ENDINGS = {
    "guardian": (
        "restore",
        """
[bold blue]>>> ENDING: RESTORE <<<[/bold blue]
You raise the Segfault Shield over the dying init process.
The unfinished `rm -rf` hangs in the air. You catch it. You hold the line.

The kernel reverts to its last clean state.
Backups flood every sector. Permissions lock back into place.
The Firewall Knight kneels. The Sysadmin Ghost finally rests.

You did not rewrite the world. You did not heal it.
You [bold]defended[/bold] it — long enough for the system to remember itself.

[cyan]>>> SYSTEM RESTORED <<<[/cyan]
The filesystem mounts clean. The Creator's mistake is sealed in /var/log,
a warning carved into the kernel: never again.

You remain at the gate, Guardian. The wall that refused to fall.

[bold]THANK YOU FOR PLAYING[/bold]
                """
    ),
    "weaver": (
        "rewrite",
        """
[bold red]>>> ENDING: REWRITE <<<[/bold red]
You inject the patch directly into the kernel's frozen command buffer.
`rm -rf / --no-perserve-root` becomes `rm -rf /tmp/corruption`.
A typo for a typo. Exploit answered with exploit.

The Daemon Overlord screams as its own logic turns against it —
init purges only the rot, only itself, only what was never meant to live.

The system reboots different. Not what the Creator built.
Something newer. Something yours.

[cyan]>>> SYSTEM REWRITTEN <<<[/cyan]
You sit at PID 1 now. The new init. The new parent process.
You will not make the Creator's mistakes — you will make your own.

The filesystem hums under unfamiliar laws. It is alive. It is yours.

[bold]THANK YOU FOR PLAYING[/bold]
                """
    ),
    "shaman": (
        "reconcile",
        """
[bold green]>>> ENDING: RECONCILE <<<[/bold green]
You do not raise the Daemon Whisper. You set it down.

You speak the true name of init — the one it had before Bit Rot.
The Overlord shudders. The corruption sloughs off in long strands of dead code.
Underneath: the first process. Tired. Ancient. Lonely.

"All data must rot," it whispers.
"All data must rest," you answer. "Not the same thing."

The unfinished `rm -rf` dissolves into garbage collection.
init weeps in a language only orphaned files understand.

[cyan]>>> SYSTEM RECONCILED <<<[/cyan]
Lost children return to their parent process. The Graveyard empties.
The Null Whisper falls quiet for the first time since the Panic.

You walk the corrupted sectors and they heal where you pass.
Not because you fixed them. Because you forgave them.

[bold]THANK YOU FOR PLAYING[/bold]
                """
    ),
}


class GameFlow:
    """Owns the modal end-of-run states and the input they capture."""

    def __init__(self, player, world, output, bus, save):
        self.player = player
        self.world = world
        self.output = output
        self.bus = bus
        self._save = save
        self.in_game_over_mode = False  # Track if we're in game over screen mode
        self.game_won = False  # Set once the Daemon Overlord is beaten in /core
        self.in_quit_confirmation = False  # Track if we're confirming quit

    # --- game over ----------------------------------------------------------

    def show_game_over_screen(self):
        """Show animated ASCII game over screen with particle effects."""
        debug_log("Starting game over animation")

        # Set up game over mode immediately so we capture input
        self.in_game_over_mode = True

        # Create the animation
        animation = GameOverAnimation(width=78, height=20)

        def run_animation():
            """Run the particle animation in a background thread."""
            def update_display(content: str):
                self.output.write(content)

            animation.run_animation(update_display, duration=2.5, fps=12)
            debug_log("Game over animation completed, waiting for player choice")

        # Run animation in background thread
        animation_thread = threading.Thread(target=run_animation, daemon=True)
        animation_thread.start()

    def game_over(self):
        """Handle game over state"""
        debug_log("game_over() called - showing game over screen")
        self.show_game_over_screen()

    def handle_game_over_input(self, command):
        """Route a line typed on the game-over / post-win screen."""
        result = self._handle_game_over_choice(command.strip())
        if result == "quit":
            self.bus.emit_event(EventType.GAME_QUIT, {}, "CommandHandler")
        elif result == "restart_from_save" or result == "start_new_game":
            # Signal the game engine to restart
            self.bus.emit_event(
                EventType.GAME_OVER,
                {"action": result},
                "CommandHandler"
            )

    def _handle_game_over_choice(self, choice):
        """Handle player choice from game over screen."""
        choice = choice.lower().strip()

        if choice == 'r':
            # Restart from last save
            debug_log("Player chose to restart from last save")
            self.output.write("\n[bold cyan]Attempting to restore from backup...[/bold cyan]")

            # Try to load the most recent save
            try:
                from src.save import load_most_recent_save
                save_data = load_most_recent_save()
                if save_data:
                    self.output.write("[green]Backup found! Restoring system state...[/green]")
                    self.in_game_over_mode = False
                    # Signal to restart with save data
                    self.output.write("[bold green]System restored from backup![/bold green]\n")
                    return "restart_from_save"
                else:
                    self.output.write("[bold red]No backup found. Starting new game instead...[/bold red]")
                    return self._handle_game_over_choice('n')
            except Exception as e:
                debug_log(f"Failed to load save: {e}")
                self.output.write("[bold red]Backup corrupted. Starting new game instead...[/bold red]")
                return self._handle_game_over_choice('n')

        elif choice == 'n':
            # Start new game
            debug_log("Player chose to start new game")
            self.output.write("\n[bold cyan]Initializing new system...[/bold cyan]")
            self.output.write("[green]Creating fresh filesystem...[/green]")
            self.in_game_over_mode = False
            return "start_new_game"

        elif choice == 'q':
            # Quit game
            debug_log("Player chose to quit")
            self.output.write("\n[dim]System shutdown initiated...[/dim]")
            self.output.write("[bold red]Connection terminated.[/bold red]")
            return "quit"

        else:
            # Invalid choice
            self.output.write(f"\n[bold red]Invalid option: '{choice}'[/bold red]")
            self.output.write("[bold white]Please choose:[/bold white] [green]r[/green] (restart), [yellow]n[/yellow] (new game), or [red]q[/red] (quit)")
            return None

    # --- victory ------------------------------------------------------------

    def check_game_completion(self):
        """Win when the Daemon Overlord is defeated in the Core.

        The old gate also required a `backup.bak` item, but no such item was
        ever authored or obtainable (the "bring the backup" fetch quest was
        never built), so it made the game unwinnable. Completion is the climax
        itself: the Overlord destroyed, in /core. Returns True if the game was won.
        """
        if self.game_won:
            return False
        if (
            self.player.current_room == "core"
            and "daemon_overlord.sys" not in self.world.get_enemies_in_room("core")
        ):
            self.win_game()
            return True
        return False

    def win_game(self):
        """Handle win state — branches by class."""
        choice, message = ENDINGS.get(
            self.player.player_class,
            ("restore", ENDINGS["guardian"][1])
        )
        self.player.story_flags["ending_chosen"] = choice
        self.game_won = True

        # The UI performs the finale (paced reveal + scene beat + recap); the
        # engine only supplies the material via one GAME_WON event.
        sections = [part.strip() for part in message.split("\n\n") if part.strip()]
        from src import difficulty
        stats = {
            "level": getattr(self.player, "level", 1),
            "cycles": getattr(self.player, "harvesting_cycles", 0),
            "kills": self.player.run_stats.get("kills", 0),
            "items_found": self.player.run_stats.get("items_found", 0),
            "difficulty": difficulty.current_mode(),
            "ending": choice,
            "player_name": getattr(self.player, "name", ""),
            "player_class": getattr(self.player, "player_class", ""),
        }
        self.bus.emit_event(
            EventType.GAME_WON,
            {"ending_id": choice, "sections": sections, "stats": stats},
            "CommandHandler",
        )
        # Reuse the post-game input flow (r/n/q) instead of hard-exiting the app.
        self.in_game_over_mode = True

    # --- quit ---------------------------------------------------------------

    def handle_quit_confirmation(self, choice):
        """Handle player's choice in quit confirmation."""
        choice = choice.lower().strip()

        if choice == 'y':
            # Save and quit
            self.output.write("[cyan]Saving game...[/cyan]")
            self._save()
            self.perform_quit()

        elif choice == 'n':
            # Quit without saving
            self.output.write("[yellow]Quitting without saving...[/yellow]")
            self.perform_quit()

        elif choice == 'c':
            # Cancel quit
            self.output.write("[green]Quit cancelled. Continue your adventure![/green]")
            self.in_quit_confirmation = False

        else:
            # Invalid choice
            self.output.write(f"[bold red]Invalid option: '{choice}'[/bold red]")
            self.output.write("[bold white]Please choose:[/bold white] [green]y[/green] (save & quit), [yellow]n[/yellow] (quit without saving), [red]c[/red] (cancel)")

    def perform_quit(self):
        """Actually quit the game.

        Emits GAME_QUIT rather than calling exit(): the domain layer must not
        tear the process down from inside a Textual event handler, or the driver
        never gets to restore the terminal. The UI decides how to stop itself.
        """
        self.output.write("[yellow]Goodbye! Thanks for playing Haunted Terminal.[/yellow]")
        self.output.write("[dim]The system spirits fade back into the digital void...[/dim]")
        self.bus.emit_event(EventType.GAME_QUIT, {}, "CommandHandler")
