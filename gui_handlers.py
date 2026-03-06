"""
Event handlers for Script to Voice Generator GUI.
Tab 1 handlers for script loading, parsing, and navigation.
Tab 2 handlers for voice testing, apply-to-all, SFX scanning, profiles.
Tab 3 handlers for generation controls, output folder, open output.
"""

import asyncio
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

import re

from config import AUDIO_EFFECTS, APP_THEME, ICON_FILENAME, INVALID_FILENAME_CHARS
from script_parser import parse_script


class GUIHandlers:
    """Mixin class containing event handlers"""

    # ── Tab 1 handlers ──────────────────────────────────────────

    def on_load_script(self):
        """Handle 'Open Script File' button click."""
        initial_dir = self.config_manager.get_ui("last_script_folder")
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = os.getcwd()

        filepath = filedialog.askopenfilename(
            title="Select Script File",
            initialdir=initial_dir,
            filetypes=[
                ("Script files", "*.txt *.md"),
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("All files", "*.*"),
            ]
        )

        if not filepath:
            return

        # Remember the folder
        self.config_manager.set_ui("last_script_folder", str(Path(filepath).parent))

        self._current_script_path = filepath
        self._run_parse(filepath)

    def on_reload_script(self):
        """Handle 'Reload Script' button click."""
        if hasattr(self, '_current_script_path') and self._current_script_path:
            self._run_parse(self._current_script_path)
        else:
            messagebox.showinfo("No Script", "No script file has been loaded yet.")

    def on_open_script_folder(self):
        """Open the folder containing the currently loaded script file."""
        if not hasattr(self, '_current_script_path') or not self._current_script_path:
            return
        folder = str(Path(self._current_script_path).parent)
        try:
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def _run_parse(self, filepath):
        """Run the parser on a script file and update the UI."""
        self.clear_log()
        self.reset_stats()

        # Update file label
        filename = Path(filepath).name
        self.loaded_file_label.config(text=f"File: {filepath}",
                                     foreground="#C0D4A8")

        # Prefill Tab 3 project name from filename (first 20 chars, sanitized)
        stem = Path(filepath).stem
        sanitized = re.sub(f"[{''.join(re.escape(c) for c in INVALID_FILENAME_CHARS)}]",
                           "_", stem)
        sanitized = re.sub(r"[\s_]+", "_", sanitized).strip("_")
        prefill = sanitized[:20]
        if prefill:
            self._gen_project_name_var.set(prefill)

        self.log_message(f"Parsing: {filename}", "header")
        self.log_message("-" * 60)

        # Parse the script
        result = parse_script(filepath)
        self._last_parse_result = result

        # Log errors
        if result.errors:
            self.log_message(f"\n{len(result.errors)} error(s) found:", "error")
            for err in result.errors:
                self.log_message(f"  Line {err.line_number}: {err.message}", "error")
                if err.line_content:
                    content = err.line_content[:80]
                    if len(err.line_content) > 80:
                        content += "..."
                    self.log_message(f"    > {content}", "warning")
            self.log_message("")

        # Log speakers found
        if result.speakers:
            self.log_message(f"Found {len(result.speakers)} unique speaker(s):", "info")
            for i, speaker in enumerate(result.speakers, 1):
                existing = self.char_profiles.get_profile(speaker)
                status = " (known)" if existing else " (new)"
                self.log_message(f"  {i}. {speaker}{status}", "info")
            self.log_message("")

        # Log sound effects
        if result.sound_effects:
            self.log_message(f"Found {len(result.sound_effects)} sound effect file(s) referenced:", "info")
            for sfx in result.sound_effects:
                lines_str = ", ".join(str(ln) for ln in sfx.line_numbers)
                self.log_message(f"  - {sfx.filename} (lines: {lines_str})", "info")
            self.log_message("")

        # Summary
        if result.errors:
            self.log_message(
                f"Script has {len(result.errors)} error(s). "
                f"Fix them and reload to continue.",
                "error"
            )
        else:
            self.log_message(
                f"Script parsed successfully! "
                f"{result.total_dialogue_lines} dialogue lines, "
                f"{len(result.speakers)} speakers, "
                f"{len(result.sound_effects)} sound effects.",
                "success"
            )

        # Update stats panel
        self.update_stats(result)

        # Enable/disable buttons
        self.btn_reload_script.config(state="normal")

        if not result.errors and result.total_dialogue_lines > 0:
            self.btn_continue_to_tab2.config(state="normal")
            # Auto-register speakers in character profiles
            self.char_profiles.ensure_speakers(result.speakers)
            # Populate Tab 2 with speaker panels
            self.populate_tab2_speakers(result.speakers, result)
        else:
            self.btn_continue_to_tab2.config(state="disabled")

        # Enable the open-script-folder button now that a script is loaded
        self.btn_open_script_folder.config(state="normal")

        # Re-scan SFX folder so found/missing statuses stay current after reload
        sfx_folder = self._sfx_folder_var.get() if hasattr(self, '_sfx_folder_var') else ""
        if sfx_folder and os.path.isdir(sfx_folder):
            self._scan_sfx_folder(sfx_folder)
        elif result.sound_effects and not sfx_folder:
            self.log_message(
                f"Warning: script references {len(result.sound_effects)} sound effect file(s) "
                f"but no SFX folder is set. Go to Tab 2 to select one.",
                "warning"
            )

        # Mark Tab 3 summary as outdated
        if hasattr(self, '_summary_status_label'):
            self._summary_status_label.config(text="Summary outdated — click Refresh",
                                              foreground="#FFD43B")

    def on_continue_to_tab2(self):
        """Navigate to Tab 2."""
        self.notebook.select(1)

    def on_help(self):
        """Open the README in the system default text editor."""
        if getattr(sys, 'frozen', False):
            app_path = Path(sys.executable).parent
        else:
            app_path = Path(__file__).parent
        readme_path = app_path / "README.md"
        if not readme_path.exists():
            messagebox.showinfo("Help",
                              "README.md not found.\n\n"
                              "Load a script file (.txt or .md) with the correct format:\n"
                              "  SpeakerID: Dialogue text here.\n\n"
                              "Each non-blank line needs a speaker ID followed by a colon.\n"
                              "Use // or # for comments, (1.5s) for pauses,\n"
                              "and {play file.mp3} for sound effects.")
            return

        try:
            if sys.platform == 'win32':
                os.startfile(str(readme_path))
            elif sys.platform == 'darwin':
                subprocess.run(["open", str(readme_path)])
            else:
                subprocess.run(["xdg-open", str(readme_path)])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open README: {e}")

    # ── Tab 2 handlers ──────────────────────────────────────────

    def on_apply_to_all(self):
        """Apply the 'Apply to All' effect settings to every speaker panel."""
        if not self._speaker_vars:
            messagebox.showinfo("No Speakers", "No speakers loaded. Load a script first.")
            return

        for effect_name, apply_var in self._apply_all_vars.items():
            value = apply_var.get()
            for speaker_id, vars_dict in self._speaker_vars.items():
                if effect_name in vars_dict:
                    vars_dict[effect_name].set(value)

        if hasattr(self, 'status_label'):
            self.status_label.config(text="Audio effects applied to all speakers.")

    def on_test_voice(self, speaker_id):
        """Generate a test voice clip for a speaker."""
        if speaker_id not in self._speaker_vars:
            return

        vars_dict = self._speaker_vars[speaker_id]

        # Get voice short name
        voice_val = vars_dict["voice"].get()
        if " | " in voice_val:
            voice_name = voice_val.split(" | ")[0]
        elif voice_val:
            voice_name = voice_val
        else:
            messagebox.showwarning("No Voice", f"Select a voice for {speaker_id} first.")
            return

        # Get pitch and speed
        pitch_hz = vars_dict["pitch_hz"].get()
        speed_percent = vars_dict["speed_percent"].get()
        pitch_str = f"{pitch_hz:+d}Hz"
        rate_str = f"{speed_percent:+d}%"

        # Get effect settings
        effect_settings = {}
        for effect_name in AUDIO_EFFECTS:
            effect_settings[effect_name] = vars_dict[effect_name].get()

        volume = vars_dict["volume_percent"].get()
        effect_settings["fmsu"] = vars_dict["fmsu"].get()
        effect_settings["reverse"] = vars_dict["reverse"].get()
        # Note: yell_impact_percent is stored in profile but not applied to the fixed test text

        # Generate in background thread
        test_text = "The quick brown fox jumps over the lazy dog."

        if hasattr(self, 'status_label'):
            self.status_label.config(text=f"Generating test voice for {speaker_id}...")

        def generate():
            try:
                from file_manager import FileManager
                test_dir = FileManager.get_test_output_dir()
                raw_path = test_dir / f"_test_{speaker_id}_raw.mp3"
                final_path = test_dir / f"test_{speaker_id}.mp3"

                # Check if the output file is locked (e.g. still playing in media player)
                if final_path.exists():
                    try:
                        final_path.rename(final_path)
                    except PermissionError:
                        self.root.after(0, lambda: self._on_test_voice_done(
                            speaker_id, None,
                            "The previous test clip is still open in your media player.\n\n"
                            "Close or stop it, then click Test Voice again."))
                        return

                # Generate TTS
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    self.audio_gen.generate_audio(
                        test_text, str(raw_path), voice_name,
                        pitch=pitch_str, rate=rate_str
                    )
                )
                loop.close()

                # Apply effects
                success, error = self.audio_gen.apply_audio_effects(
                    str(raw_path), str(final_path),
                    effect_settings, volume
                )

                # Clean up raw file
                try:
                    raw_path.unlink(missing_ok=True)
                except Exception:
                    pass

                if success:
                    # Peak-normalize to match what Generate All produces
                    success, error = self.audio_gen.apply_peak_normalize(
                        str(final_path), str(final_path)
                    )

                if success:
                    self.root.after(0, lambda p=str(final_path): self._on_test_voice_done(
                        speaker_id, p, None))
                else:
                    self.root.after(0, lambda: self._on_test_voice_done(
                        speaker_id, None, error))

            except Exception as e:
                self.root.after(0, lambda: self._on_test_voice_done(
                    speaker_id, None, str(e)))

        threading.Thread(target=generate, daemon=True).start()

    def on_test_voice_inner_thoughts(self, speaker_id):
        """Generate a test voice clip with the speaker's effects plus the inner thoughts filter."""
        if speaker_id not in self._speaker_vars:
            return

        vars_dict = self._speaker_vars[speaker_id]

        voice_val = vars_dict["voice"].get()
        if " | " in voice_val:
            voice_name = voice_val.split(" | ")[0]
        elif voice_val:
            voice_name = voice_val
        else:
            messagebox.showwarning("No Voice", f"Select a voice for {speaker_id} first.")
            return

        pitch_hz = vars_dict["pitch_hz"].get()
        speed_percent = vars_dict["speed_percent"].get()
        pitch_str = f"{pitch_hz:+d}Hz"
        rate_str = f"{speed_percent:+d}%"

        effect_settings = {}
        for effect_name in AUDIO_EFFECTS:
            effect_settings[effect_name] = vars_dict[effect_name].get()

        volume = vars_dict["volume_percent"].get()
        effect_settings["fmsu"] = vars_dict["fmsu"].get()
        effect_settings["reverse"] = vars_dict["reverse"].get()

        test_text = "The quick brown fox jumps over the lazy dog."

        if hasattr(self, 'status_label'):
            self.status_label.config(
                text=f"Generating inner thoughts test for {speaker_id}...")

        def generate():
            try:
                from file_manager import FileManager
                test_dir = FileManager.get_test_output_dir()
                raw_path = test_dir / f"_test_{speaker_id}_it_raw.mp3"
                final_path = test_dir / f"test_{speaker_id}_it.mp3"

                if final_path.exists():
                    try:
                        final_path.rename(final_path)
                    except PermissionError:
                        self.root.after(0, lambda: self._on_test_voice_done(
                            speaker_id, None,
                            "The previous inner thoughts test clip is still open in your media player.\n\n"
                            "Close or stop it, then click Test + Inner Thoughts again."))
                        return

                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    self.audio_gen.generate_audio(
                        test_text, str(raw_path), voice_name,
                        pitch=pitch_str, rate=rate_str
                    )
                )
                loop.close()

                success, error = self.audio_gen.apply_audio_effects(
                    str(raw_path), str(final_path),
                    effect_settings, volume,
                    is_inner_thought=True,
                    config_manager=self.config_manager
                )

                try:
                    raw_path.unlink(missing_ok=True)
                except Exception:
                    pass

                if success:
                    # Peak-normalize to match what Generate All produces
                    success, error = self.audio_gen.apply_peak_normalize(
                        str(final_path), str(final_path)
                    )

                if success:
                    self.root.after(0, lambda p=str(final_path): self._on_test_voice_done(
                        speaker_id, p, None))
                else:
                    self.root.after(0, lambda: self._on_test_voice_done(
                        speaker_id, None, error))

            except Exception as e:
                self.root.after(0, lambda: self._on_test_voice_done(
                    speaker_id, None, str(e)))

        threading.Thread(target=generate, daemon=True).start()

    def _on_test_voice_done(self, speaker_id, filepath, error):
        """Callback when test voice generation completes."""
        if error:
            messagebox.showerror("Test Voice Error",
                               f"Failed to generate test for {speaker_id}:\n\n{error}")
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"Test voice failed for {speaker_id}.")
        else:
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"Test voice saved: {filepath}")
            # Auto-open in default media player
            try:
                if sys.platform == 'win32':
                    os.startfile(filepath)
                elif sys.platform == 'darwin':
                    subprocess.run(["open", filepath])
                else:
                    subprocess.run(["xdg-open", filepath])
            except Exception:
                pass  # Don't fail if media player can't open

    def on_pick_sfx_folder(self):
        """Handle SFX folder selection."""
        initial_dir = self.config_manager.get_ui("last_sfx_folder")
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = os.getcwd()

        folder = filedialog.askdirectory(
            title="Select Sound Effects Folder",
            initialdir=initial_dir,
        )

        if not folder:
            return

        self.config_manager.set_ui("last_sfx_folder", folder)
        self._sfx_folder_var.set(folder)
        self._scan_sfx_folder(folder)

    def on_open_profiles(self):
        """Open character_profiles.json in the system editor."""
        self.char_profiles.open_in_editor()

    def on_continue_to_tab3(self):
        """Navigate to Tab 3 and refresh the summary."""
        self.notebook.select(2)
        self._refresh_summary()

    # ── Tab 3 handlers ──────────────────────────────────────────

    def _on_pick_output_folder(self):
        """Handle output folder selection for generation."""
        initial_dir = self.config_manager.get_ui("last_output_folder")
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = os.getcwd()

        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=initial_dir,
        )

        if folder:
            self._gen_output_folder_var.set(folder)
            self.config_manager.set_ui("last_output_folder", folder)

    def _on_generate_clicked(self):
        """Handle 'Generate All' button click."""
        from config import MAX_PROJECT_NAME_LENGTH, INVALID_FILENAME_CHARS

        # Validate prerequisites
        result = getattr(self, '_last_parse_result', None)
        if not result or not result.speakers:
            messagebox.showwarning("No Script",
                                   "No script loaded. Go to Tab 1 to load a script.")
            return

        project_name = self._gen_project_name_var.get().strip()
        if not project_name:
            messagebox.showwarning("Project Name",
                                   "Enter a project name before generating.")
            return

        if len(project_name) > MAX_PROJECT_NAME_LENGTH:
            messagebox.showwarning("Project Name",
                                   f"Project name exceeds {MAX_PROJECT_NAME_LENGTH} characters.")
            return

        bad_chars = [ch for ch in project_name if ch in INVALID_FILENAME_CHARS]
        if bad_chars:
            messagebox.showwarning("Project Name",
                                   f"Project name contains invalid characters: "
                                   f"{', '.join(repr(c) for c in bad_chars)}")
            return

        output_folder = self._gen_output_folder_var.get().strip()
        if not output_folder:
            messagebox.showwarning("Output Folder",
                                   "Select an output folder before generating.")
            return

        # Check that all speakers have voices assigned
        for speaker_id in result.speakers:
            vars_dict = self._speaker_vars.get(speaker_id, {})
            voice_val = vars_dict.get("voice")
            if not voice_val or not voice_val.get():
                messagebox.showwarning("Missing Voice",
                                       f"Speaker '{speaker_id}' has no voice assigned.\n"
                                       f"Go to Tab 2 to select a voice.")
                return

        # Confirm with user
        total = result.total_dialogue_lines
        use_subfolder = self._gen_use_project_subfolder_var.get()
        from pathlib import Path as _Path
        resolved_output = str(_Path(output_folder) / project_name) if use_subfolder else output_folder
        confirm = messagebox.askyesno(
            "Start Generation",
            f"Generate {total} voice clips?\n\n"
            f"Project: {project_name}\n"
            f"Output: {resolved_output}\n\n"
            f"This may take several minutes."
        )
        if not confirm:
            return

        # Start generation (defined in gui_generation.py GenerationMixin)
        self.run_generation()

    def _on_cancel_clicked(self):
        """Handle 'Cancel' button click during generation."""
        self._gen_cancel_requested = True
        self._btn_cancel.config(state="disabled")
        self.gen_log("Cancellation requested... finishing current clip.", "warning")

    def _on_open_output_folder(self):
        """Open the output folder in the system file manager."""
        # Prefer the resolved folder (may include project subfolder) set after generation
        folder = getattr(self, '_last_resolved_output_folder', None) or \
                 self._gen_output_folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showinfo("No Folder",
                               "Output folder does not exist yet.")
            return

        try:
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    # ── Voice loading ───────────────────────────────────────────

    def _load_voices_async(self):
        """Start loading Edge-TTS voices in a background thread."""
        def load():
            try:
                loop = asyncio.new_event_loop()
                voices = loop.run_until_complete(self.audio_gen.load_voices())
                loop.close()
                self.root.after(0, self._on_voices_loaded, voices)
            except Exception as e:
                print(f"Failed to load voices: {e}")
                self.root.after(0, self._on_voices_loaded, [])

        threading.Thread(target=load, daemon=True).start()

    def _on_voices_loaded(self, voices):
        """Callback when voices finish loading."""
        self._available_voices = voices
        self._voices_loaded = True

        if hasattr(self, 'status_label'):
            self.status_label.config(text=f"Loaded {len(voices)} voices.")

        # If speakers are already shown, populate their comboboxes
        if self._speaker_vars:
            self._set_voices_on_comboboxes()

    # ── Welcome popup ────────────────────────────────────────────────────────

    def _show_welcome_if_enabled(self):
        """Show the welcome popup if config enables it."""
        if self.config_manager.get_ui("show_welcome_popup"):
            self._show_welcome_popup()

    def _show_welcome_popup(self):
        """
        Display the welcome/orientation Toplevel dialog.
        Uses transient() without grab_set() to avoid Windows minimize/restore softlock.
        """
        colors = APP_THEME["colors"]

        popup = tk.Toplevel(self.root)
        popup.title("Welcome")
        popup.resizable(False, False)
        popup.configure(bg=colors["bg"])
        popup.transient(self.root)  # floats above main window; no modal grab

        try:
            if getattr(sys, 'frozen', False):
                app_path = Path(sys.executable).parent
            else:
                app_path = Path(__file__).parent
            icon_path = app_path / ICON_FILENAME
            if icon_path.exists():
                popup.iconbitmap(str(icon_path))
        except Exception:
            pass

        content = ttk.Frame(popup, padding=24)
        content.pack(fill="both", expand=True)

        # Title
        ttk.Label(
            content,
            text="Welcome to Script to Voice Generator",
            font=("Consolas", 14, "bold"),
            foreground=colors["accent"],
        ).pack(anchor="w", pady=(0, 12))

        # Body
        body_lines = [
            "This app converts formatted script files (.txt / .md)",
            "into fully voiced audio using Microsoft Edge TTS.",
            "",
            "Quick start:",
            "  1.  Tab 1 — Load a script file",
            "  2.  Tab 2 — Assign a voice to each speaker",
            "  3.  Tab 3 — Set an output folder and generate",
            "",
            "New to the app? Click the  Help  button in the",
            "top-right corner to open the full README guide.",
        ]
        for line in body_lines:
            ttk.Label(
                content,
                text=line,
                font=("Consolas", 10),
                foreground=colors["fg"],
                justify="left",
            ).pack(anchor="w")

        ttk.Separator(content, orient="horizontal").pack(fill="x", pady=(16, 12))

        # "Don't show again" checkbox
        dont_show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            content,
            text="Don't show this again",
            variable=dont_show_var,
            bootstyle="secondary",
        ).pack(anchor="w", pady=(0, 12))

        # OK button
        def on_ok():
            if dont_show_var.get():
                self.config_manager.set_ui("show_welcome_popup", False)
            popup.destroy()

        ttk.Button(
            content,
            text="OK",
            command=on_ok,
            bootstyle="primary",
            width=12,
        ).pack(anchor="center", pady=(0, 4))

        # Center over main window after layout is calculated
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - popup.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - popup.winfo_height()) // 2
        popup.geometry(f"+{x}+{y}")
