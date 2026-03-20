"""
Tab 4: Settings
For Script to Voice Generator GUI.
Controls for merged audio pause timings, contextual modifiers,
and the inner thoughts audio effect preset.
"""

import os
import subprocess
import sys
import tkinter as tk
import ttkbootstrap as ttk
from tkinter import ttk as _tk_ttk
from pathlib import Path
from ttkbootstrap.constants import *

from config import (
    MERGED_AUDIO_PAUSE_DEFAULTS,
    CONTEXTUAL_MODIFIER_DEFAULTS,
    INNER_THOUGHTS_PRESET_NAMES,
    INNER_THOUGHTS_DEFAULT_PRESET,
    INNER_THOUGHTS_PRESETS,
    SILENCE_TRIM_DEFAULTS,
)

try:
    from ttkbootstrap.tooltip import ToolTip
    _HAS_TOOLTIP = True
except ImportError:
    _HAS_TOOLTIP = False


def _tip(widget, text, position=None):
    """Attach a tooltip if ttkbootstrap tooltips are available."""
    if _HAS_TOOLTIP:
        try:
            kwargs = {"text": text, "delay": 400}
            if position:
                kwargs["position"] = position
            ToolTip(widget, **kwargs)
        except Exception:
            pass


class Tab4Builder:
    """Mixin class for building Tab 4 (Settings) UI"""

    def build_tab4(self, parent):
        """Build the complete Tab 4 interface."""

        # Main scrollable container
        canvas = ttk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas, padding=15)

        scrollable.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scrolling — forward from any child widget up to canvas
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_mousewheel_tab4(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel_tab4(child)

        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable.bind("<MouseWheel>", on_mousewheel)
        self._tab4_bind_mousewheel = bind_mousewheel_tab4

        # Title
        ttk.Label(scrollable, text="Settings",
                  font=("Consolas", 18, "bold")).pack(pady=(0, 5))
        ttk.Label(scrollable,
                  text="Adjust merged audio pause timings and the inner thoughts audio effect.",
                  font=("Consolas", 10), wraplength=900, justify="center").pack(pady=(0, 15))

        # --- Quick Access ---
        self._build_quick_access_section(scrollable)

        # --- Section 1: Merged Audio Pauses ---
        self._build_pauses_section(scrollable)

        # --- Section 2: Contextual Modifiers ---
        self._build_contextual_modifiers_section(scrollable)

        # --- Section 3: Inner Thoughts Effect ---
        self._build_inner_thoughts_section(scrollable)

        # --- Section 4: Silence Trimming ---
        self._build_silence_trim_section(scrollable)

        # Bind mousewheel to all child widgets
        bind_mousewheel_tab4(scrollable)

    # ── Quick Access ──────────────────────────────────────────

    def _build_quick_access_section(self, parent):
        """Build the Quick Access buttons rows."""
        frame = _tk_ttk.LabelFrame(parent, text="Quick Access", padding=10)
        frame.pack(fill=X, pady=(0, 10))

        ttk.Label(frame,
                  text="Open data files and folders directly.",
                  font=("Consolas", 10), foreground="#9AAF88").pack(anchor=W, pady=(0, 8))

        # Row 1: files / popups
        row1 = ttk.Frame(frame)
        row1.pack(anchor=W, pady=(0, 6))

        row1_buttons = [
            ("README",                 self._on_open_readme_tab4,        "secondary"),
            ("Intro Popup",            self._on_open_intro_popup_tab4,   "secondary"),
            ("character_profiles.json", self._on_open_profiles_tab4,     "secondary"),
            ("config.json",            self._on_open_config_json_tab4,   "secondary"),
            ("Test Output Folder",     self._on_open_test_output_tab4,   "secondary"),
        ]

        for label, cmd, style in row1_buttons:
            ttk.Button(row1, text=label, command=cmd,
                       bootstyle=style).pack(side=LEFT, padx=(0, 8))

        # Row 2: !docs subfolders
        ttk.Label(frame, text="Docs folders:",
                  font=("Consolas", 10), foreground="#9AAF88").pack(anchor=W, pady=(0, 4))

        row2 = ttk.Frame(frame)
        row2.pack(anchor=W)

        if getattr(sys, 'frozen', False):
            _app_base = Path(sys.executable).parent
        else:
            _app_base = Path(__file__).parent
        docs_base = _app_base / "!docs"
        docs_buttons = [
            ("Guides",            docs_base / "guides"),
            ("Example Scripts",   docs_base / "example_scripts"),
            ("Prompt Templates",  docs_base / "prompt_templates"),
        ]

        for label, folder in docs_buttons:
            ttk.Button(row2, text=label,
                       command=lambda p=folder: self._open_path(p),
                       bootstyle="secondary").pack(side=LEFT, padx=(0, 8))

    def _open_path(self, path):
        """Open a file or folder in the system default handler."""
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)])
            else:
                subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Could not open:\n{path}\n\n{e}")

    def _on_open_readme_tab4(self):
        if getattr(sys, 'frozen', False):
            readme = Path(sys.executable).parent / "README.md"
        else:
            readme = Path(__file__).parent / "README.md"
        if not readme.exists():
            from tkinter import messagebox
            messagebox.showinfo("Not Found", "README.md not found.")
            return
        self._open_path(readme)

    def _on_open_intro_popup_tab4(self):
        self._show_welcome_popup()

    def _on_open_profiles_tab4(self):
        self.char_profiles.open_in_editor()

    def _on_open_config_json_tab4(self):
        self._open_path(self.config_manager.path)

    def _on_open_test_output_tab4(self):
        from file_manager import FileManager
        self._open_path(FileManager.get_test_output_dir())

    # ── Section 1: Merged Audio Pauses ───────────────────────

    def _build_pauses_section(self, parent):
        """Build sliders for all 8 punctuation pause values."""
        frame = _tk_ttk.LabelFrame(parent, text="Merged Audio Pauses", padding=10)
        frame.pack(fill=X, pady=(0, 10))

        ttk.Label(frame,
                  text="Silence duration (seconds) inserted after each punctuation type "
                       "when merging clips into a single audio file.",
                  font=("Consolas", 10), foreground="#9AAF88",
                  wraplength=880).pack(anchor=W, pady=(0, 8))

        # Labels and descriptions for the 8 pause types
        pause_meta = {
            "period":        ("Period  ( . )",       "Statement/Normal"),
            "comma":         ("Comma  ( , )",         "Shortcut/Shorter"),
            "exclamation":   ("Exclamation  ( ! )",  "Exclamation"),
            "question":      ("Question  ( ? )",     "Question"),
            "hyphen":        ("Hyphen  ( - )",        "Interruption"),
            "ellipsis":      ("Ellipsis  ( … )",     "Trailing off"),
            "double_power":  ("Double power  ( !! / ?! )", "Urgent shock/surprise"),
            "triple_power":  ("Triple power  ( !!! )", "Paralysing shock/surprise"),
        }

        self._pause_vars = {}

        grid = ttk.Frame(frame)
        grid.pack(fill=X)

        for row_idx, (key, (label_text, desc)) in enumerate(pause_meta.items()):
            default_val = MERGED_AUDIO_PAUSE_DEFAULTS[key]
            current_val = self.config_manager.get_pause(key)

            var = tk.DoubleVar(value=current_val)
            self._pause_vars[key] = var

            # Column 0: label
            lbl = ttk.Label(grid, text=label_text, font=("Consolas", 10, "bold"))
            lbl.grid(row=row_idx, column=0, sticky=W, pady=3, padx=(0, 10))
            _tip(lbl, desc)

            # Column 1: slider
            slider = ttk.Scale(grid, from_=0.0, to=5.0, variable=var,
                                orient=HORIZONTAL, length=350,
                                command=lambda v, k=key: self._on_pause_slider_changed(k))
            slider.grid(row=row_idx, column=1, sticky=EW, padx=(0, 8))
            _tip(slider, f"Range: 0.0 – 5.0 s  |  Default: {default_val} s")

            # Column 2: value display
            val_label = ttk.Label(grid, text=f"{current_val:.2f} s",
                                  font=("Consolas", 10), width=7)
            val_label.grid(row=row_idx, column=2, sticky=W)
            # Store ref so slider callback can update it
            var._val_label = val_label

        grid.columnconfigure(0, minsize=200)
        grid.columnconfigure(1, weight=1)

        # Reset button
        ttk.Button(frame, text="Reset Pauses to Defaults",
                   command=self._on_reset_pauses,
                   bootstyle="warning-outline", width=24).pack(anchor=W, pady=(10, 0))

    def _on_pause_slider_changed(self, key):
        """Called when a pause slider moves; saves to config and updates label."""
        var = self._pause_vars.get(key)
        if var is None:
            return
        # Round to nearest 0.05
        raw = var.get()
        rounded = round(round(raw / 0.05) * 0.05, 2)
        var.set(rounded)
        # Update value label
        if hasattr(var, '_val_label'):
            var._val_label.config(text=f"{rounded:.2f} s")
        self.config_manager.set_pause(key, rounded)

    def _on_reset_pauses(self):
        """Reset pause sliders to config defaults."""
        for key, var in self._pause_vars.items():
            default_val = MERGED_AUDIO_PAUSE_DEFAULTS[key]
            var.set(default_val)
            if hasattr(var, '_val_label'):
                var._val_label.config(text=f"{default_val:.2f} s")
            self.config_manager.set_pause(key, default_val)

    # ── Section 2: Contextual Modifiers ──────────────────────

    def _build_contextual_modifiers_section(self, parent):
        """Build controls for all contextual modifier values."""
        frame = _tk_ttk.LabelFrame(parent, text="Contextual Modifiers", padding=10)
        frame.pack(fill=X, pady=(0, 10))

        ttk.Label(frame,
                  text="Fine-tune how pauses are adjusted based on context "
                       "(speaker changes, line length, inner thoughts, etc.).",
                  font=("Consolas", 10), foreground="#9AAF88",
                  wraplength=880).pack(anchor=W, pady=(0, 8))

        # Metadata: key -> (label, description, is_int, slider_min, slider_max)
        mod_meta = {
            "speaker_change_bonus":        ("Speaker change bonus (s)",
                                            "Extra silence added between lines from different speakers",
                                            False, 0.0, 2.0),
            "short_line_threshold_chars":  ("Short line threshold (chars)",
                                            "Lines shorter than this get a reduced pause",
                                            True, 0, 100),
            "short_line_reduction_s":      ("Short line reduction (s)",
                                            "How much to reduce the pause for short lines",
                                            False, 0.0, 2.0),
            "long_line_threshold_chars":   ("Long line threshold (chars)",
                                            "Lines longer than this get an extended pause",
                                            True, 50, 500),
            "long_line_addition_s":        ("Long line addition (s)",
                                            "How much to add to the pause for long lines",
                                            False, 0.0, 2.0),
            "inner_thought_padding_s":     ("Inner thought padding (s)",
                                            "Extra silence before and after inner thought lines",
                                            False, 0.0, 2.0),
            "same_speaker_reduction_s":        ("Same speaker reduction (s)",
                                                "Pause reduction when the next line is from the same speaker. "
                                                "Opposite of speaker change bonus — keeps same-speaker runs tighter.",
                                                False, 0.0, 2.0),
            "first_line_padding_s":        ("First line padding (s)",
                                            "Extra silence before the very first line",
                                            False, 0.0, 3.0),
            "last_line_padding_s":         ("Last line padding (s)",
                                            "Extra silence after the very last line",
                                            False, 0.0, 3.0),
        }

        self._modifier_vars = {}

        grid = ttk.Frame(frame)
        grid.pack(fill=X)

        for row_idx, (key, (label_text, desc, is_int, lo, hi)) in enumerate(mod_meta.items()):
            current_val = self.config_manager.get_modifier(key)

            if is_int:
                var = tk.IntVar(value=int(current_val))
                self._modifier_vars[key] = var

                # Label
                lbl = ttk.Label(grid, text=label_text, font=("Consolas", 10, "bold"))
                lbl.grid(row=row_idx, column=0, sticky=W, pady=3, padx=(0, 10))
                _tip(lbl, desc)

                # Spinbox for integer values
                spin = ttk.Spinbox(grid, from_=lo, to=hi, textvariable=var,
                                   width=7, font=("Consolas", 10))
                spin.grid(row=row_idx, column=1, sticky=W, padx=(0, 8))
                _tip(spin, f"Range: {lo}–{hi}  |  Default: {CONTEXTUAL_MODIFIER_DEFAULTS[key]}")

                # Save on change
                var.trace_add("write",
                              lambda *a, k=key, v=var: self._on_modifier_changed(k, v, True))
            else:
                var = tk.DoubleVar(value=float(current_val))
                self._modifier_vars[key] = var

                # Label
                lbl = ttk.Label(grid, text=label_text, font=("Consolas", 10, "bold"))
                lbl.grid(row=row_idx, column=0, sticky=W, pady=3, padx=(0, 10))
                _tip(lbl, desc)

                # Slider for float values
                slider = ttk.Scale(grid, from_=lo, to=hi, variable=var,
                                   orient=HORIZONTAL, length=280,
                                   command=lambda v, k=key: self._on_modifier_slider_changed(k))
                slider.grid(row=row_idx, column=1, sticky=EW, padx=(0, 8))

                default_val = CONTEXTUAL_MODIFIER_DEFAULTS[key]
                _tip(slider, f"Range: {lo}–{hi}  |  Default: {default_val}")

                # Value label
                val_label = ttk.Label(grid, text=f"{float(current_val):.2f}",
                                      font=("Consolas", 10), width=6)
                val_label.grid(row=row_idx, column=2, sticky=W)
                var._val_label = val_label

        grid.columnconfigure(0, minsize=220)
        grid.columnconfigure(1, weight=1)

        ttk.Button(frame, text="Reset Modifiers to Defaults",
                   command=self._on_reset_modifiers,
                   bootstyle="warning-outline", width=28).pack(anchor=W, pady=(10, 0))

    def _on_modifier_slider_changed(self, key):
        """Called when a modifier slider moves."""
        var = self._modifier_vars.get(key)
        if var is None:
            return
        raw = var.get()
        default_val = CONTEXTUAL_MODIFIER_DEFAULTS[key]
        rounded = round(round(raw / 0.05) * 0.05, 2)
        var.set(rounded)
        if hasattr(var, '_val_label'):
            var._val_label.config(text=f"{rounded:.2f}")
        self.config_manager.set_modifier(key, rounded)

    def _on_modifier_changed(self, key, var, is_int):
        """Called when a modifier spinbox changes."""
        try:
            val = var.get()
        except tk.TclError:
            return
        self.config_manager.set_modifier(key, val)

    def _on_reset_modifiers(self):
        """Reset contextual modifier controls to defaults."""
        for key, var in self._modifier_vars.items():
            default_val = CONTEXTUAL_MODIFIER_DEFAULTS[key]
            try:
                var.set(default_val)
            except tk.TclError:
                pass
            if hasattr(var, '_val_label'):
                var._val_label.config(text=f"{float(default_val):.2f}")
            self.config_manager.set_modifier(key, default_val)

    # ── Section 3: Inner Thoughts Effect ─────────────────────

    def _build_inner_thoughts_section(self, parent):
        """Build the inner thoughts effect preset picker and custom controls."""
        frame = _tk_ttk.LabelFrame(parent, text="Inner Thoughts Effect", padding=10)
        frame.pack(fill=X, pady=(0, 10))

        ttk.Label(frame,
                  text="Audio effect applied to lines enclosed in double parentheses (( like this )). "
                       "Creates a distinct sound for internal monologue.",
                  font=("Consolas", 10), foreground="#9AAF88",
                  wraplength=880).pack(anchor=W, pady=(0, 8))

        # Preset descriptions
        preset_descs = {
            "Whisper":      "Muffled and stuffy — heavy lowpass cuts clarity, subtle echo tags it as unreal",
            "Dreamlike":    "Floaty and dissolving — dual trailing echoes at 150 ms and 280 ms, warm low-end kept",
            "Dissociated":  "Cold and detached (default) — tight single echo, narrowband, slightly hollow",
            "Custom":       "Set your own filter parameters below",
        }

        current_preset = self.config_manager.get_inner_thoughts_preset()
        self._it_preset_var = tk.StringVar(value=current_preset)

        # Preset radio buttons
        preset_row = ttk.Frame(frame)
        preset_row.pack(fill=X, pady=(0, 6))

        for preset_name in INNER_THOUGHTS_PRESET_NAMES:
            desc = preset_descs.get(preset_name, "")
            rb = ttk.Radiobutton(preset_row, text=preset_name,
                                 variable=self._it_preset_var, value=preset_name,
                                 command=self._on_it_preset_changed,
                                 bootstyle="info")
            rb.pack(side=LEFT, padx=(0, 15))
            _tip(rb, desc)

        # Preset description label (updates when selection changes)
        self._it_desc_label = ttk.Label(frame,
                                        text=preset_descs.get(current_preset, ""),
                                        font=("Consolas", 10, "italic"),
                                        foreground="#9AAF88", wraplength=860)
        self._it_desc_label.pack(anchor=W, pady=(0, 8))

        # Custom parameters frame (shown only when "Custom" is selected)
        self._it_custom_frame = _tk_ttk.LabelFrame(frame, text="Custom Parameters", padding=8)
        self._it_custom_frame.pack(fill=X, pady=(0, 8))

        self._build_it_custom_controls(self._it_custom_frame)

        # Reset button
        ttk.Button(frame, text="Reset Inner Thoughts to Defaults",
                   command=self._on_reset_inner_thoughts,
                   bootstyle="warning-outline", width=33).pack(anchor=W, pady=(4, 0))

        # Show/hide custom panel based on initial preset
        self._update_it_custom_visibility()

    def _build_it_custom_controls(self, parent):
        """Build custom parameter sliders for the inner thoughts effect."""
        custom = self.config_manager.get_inner_thoughts_custom()

        # highpass Hz
        self._it_highpass_var = tk.IntVar(value=int(custom.get("highpass", 300)))
        # lowpass Hz
        self._it_lowpass_var = tk.IntVar(value=int(custom.get("lowpass", 3000)))
        # echo delay ms (0 = off)
        self._it_echo_delay_var = tk.IntVar(value=int(custom.get("echo_delay_ms", 80)))
        # echo wet amount
        self._it_echo_wet_var = tk.DoubleVar(value=float(custom.get("echo_wet", 0.2)))
        # volume multiplier
        self._it_volume_var = tk.DoubleVar(value=float(custom.get("volume", 0.75)))

        grid = ttk.Frame(parent)
        grid.pack(fill=X)

        # Helper: build a slider row — returns (slider, label) so tooltips can be applied to both
        def add_slider_row(row, label, var, lo, hi, step, key, is_int=False, unit=""):
            lbl = ttk.Label(grid, text=label, font=("Consolas", 10, "bold"))
            lbl.grid(row=row, column=0, sticky=W, pady=2, padx=(0, 10))

            slider = ttk.Scale(grid, from_=lo, to=hi, variable=var,
                                orient=HORIZONTAL, length=280,
                                command=lambda v, k=key, iv=is_int, s=step, u=unit,
                                               lv=var: self._on_it_custom_changed(k, lv, iv, s, u))
            slider.grid(row=row, column=1, sticky=EW, padx=(0, 8))

            val_text = f"{int(var.get())}{unit}" if is_int else f"{var.get():.2f}{unit}"
            val_lbl = ttk.Label(grid, text=val_text, font=("Consolas", 10), width=8)
            val_lbl.grid(row=row, column=2, sticky=W)
            var._val_label = val_lbl
            var._unit = unit
            var._is_int = is_int
            return slider, lbl

        def add_tipped_row(row, label, var, lo, hi, step, key, tip_text, is_int=False, unit=""):
            s, lbl = add_slider_row(row, label, var, lo, hi, step, key, is_int=is_int, unit=unit)
            _tip(s, tip_text)
            _tip(lbl, tip_text)

        add_tipped_row(0, "Highpass filter (Hz)", self._it_highpass_var,
                       50, 800, 10, "highpass",
                       "Cuts frequencies below this — higher = thinner/more muffled. "
                       "Typical range: 150–500 Hz",
                       is_int=True, unit=" Hz")

        add_tipped_row(1, "Lowpass filter (Hz)", self._it_lowpass_var,
                       1000, 8000, 100, "lowpass",
                       "Cuts frequencies above this — lower = more muffled/stuffy. "
                       "Typical range: 1000–5000 Hz. Below 1500 Hz gives a heavy occluded quality.",
                       is_int=True, unit=" Hz")

        add_tipped_row(2, "Echo delay (ms, 0 = off)", self._it_echo_delay_var,
                       0, 300, 10, "echo_delay_ms",
                       "Delay of the echo/reverb tail. 0 disables echo entirely. "
                       "60–120 ms sounds natural; 40 ms sounds metallic. "
                       "Note: Custom uses a single echo tap — the Dreamlike dual-tap effect is preset-only.",
                       is_int=True, unit=" ms")

        add_tipped_row(3, "Echo wet amount", self._it_echo_wet_var,
                       0.0, 1.0, 0.05, "echo_wet",
                       "How much of the echo is mixed in. 0 = none, 1 = maximum. "
                       "0.15–0.3 sounds natural.")

        add_tipped_row(4, "Volume multiplier", self._it_volume_var,
                       0.1, 1.5, 0.05, "volume",
                       "Overall volume of inner thought lines. < 1.0 = quieter (recommended for realism).",
                       unit="×")

        grid.columnconfigure(0, minsize=200)
        grid.columnconfigure(1, weight=1)

    def _on_it_custom_changed(self, key, var, is_int, step, unit):
        """Called when a custom inner thoughts slider moves."""
        raw = var.get()
        if is_int:
            rounded = int(round(raw / step) * step)
            var.set(rounded)
            if hasattr(var, '_val_label'):
                var._val_label.config(text=f"{rounded}{unit}")
        else:
            rounded = round(round(raw / step) * step, 2)
            var.set(rounded)
            if hasattr(var, '_val_label'):
                var._val_label.config(text=f"{rounded:.2f}{unit}")

        self.config_manager.set_inner_thoughts_custom(key, rounded)

    def _on_it_preset_changed(self):
        """Called when the inner thoughts preset radio button changes."""
        preset = self._it_preset_var.get()
        self.config_manager.set_inner_thoughts_preset(preset)
        self._update_it_custom_visibility()

        # Update description label
        preset_descs = {
            "Whisper":      "Muffled and stuffy — heavy lowpass cuts clarity, subtle echo tags it as unreal",
            "Dreamlike":    "Floaty and dissolving — dual trailing echoes at 150 ms and 280 ms, warm low-end kept",
            "Dissociated":  "Cold and detached (default) — tight single echo, narrowband, slightly hollow",
            "Custom":       "Set your own filter parameters below",
        }
        self._it_desc_label.config(text=preset_descs.get(preset, ""))

    def _update_it_custom_visibility(self):
        """Show or hide the custom parameters frame based on selected preset."""
        if self._it_preset_var.get() == "Custom":
            self._it_custom_frame.pack(fill=X, pady=(0, 8))
        else:
            self._it_custom_frame.pack_forget()

    def _on_reset_inner_thoughts(self):
        """Reset inner thoughts preset and custom values to defaults."""
        self.config_manager.reset_inner_thoughts_to_defaults()

        # Reset preset radio
        self._it_preset_var.set(INNER_THOUGHTS_DEFAULT_PRESET)

        # Reset custom sliders
        defaults_preset = INNER_THOUGHTS_PRESETS[INNER_THOUGHTS_DEFAULT_PRESET]
        self._it_highpass_var.set(defaults_preset["highpass"])
        self._it_lowpass_var.set(defaults_preset["lowpass"])
        self._it_echo_delay_var.set(defaults_preset["echo_delay_ms"])
        self._it_echo_wet_var.set(defaults_preset["echo_wet"])
        self._it_volume_var.set(defaults_preset["volume"])

        # Update value labels
        for var, val, unit, is_int in [
            (self._it_highpass_var, defaults_preset["highpass"], " Hz", True),
            (self._it_lowpass_var, defaults_preset["lowpass"], " Hz", True),
            (self._it_echo_delay_var, defaults_preset["echo_delay_ms"], " ms", True),
            (self._it_echo_wet_var, defaults_preset["echo_wet"], "", False),
            (self._it_volume_var, defaults_preset["volume"], "×", False),
        ]:
            if hasattr(var, '_val_label'):
                if is_int:
                    var._val_label.config(text=f"{int(val)}{unit}")
                else:
                    var._val_label.config(text=f"{float(val):.2f}{unit}")

        self._on_it_preset_changed()

    # ── Section 4: Silence Trimming ───────────────────────────

    def _build_silence_trim_section(self, parent):
        """Build radio-button controls for silence trim mode."""
        current_mode = self.config_manager.get_silence_trim("mode") or "beginning_end"
        self._silence_trim_mode_var = tk.StringVar(value=current_mode)

        frame = _tk_ttk.LabelFrame(parent, text="Silence Trimming", padding=(10, 6))
        frame.pack(fill=X, pady=(0, 10))

        ttk.Label(frame,
                  text="Controls how silence is trimmed from the start/end of each generated "
                       "voice clip before effects are applied. Removes Edge-TTS padding artifacts.",
                  font=("Consolas", 10), foreground="#9AAF88",
                  wraplength=880).pack(anchor=W, pady=(0, 8))

        modes = [
            ("beginning_end", "Trim beginning + end  (default — removes Edge-TTS padding from both sides)"),
            ("beginning",     "Trim beginning only"),
            ("end",           "Trim end only"),
            ("all",           "Trim beginning, end, and mid-clip gaps  (warning: removes pauses inside a clip)"),
            ("off",           "Off  (no trimming)"),
        ]

        for value, label in modes:
            ttk.Radiobutton(frame, text=label,
                            variable=self._silence_trim_mode_var, value=value,
                            command=self._on_silence_trim_mode_changed,
                            bootstyle="info").pack(anchor=W, pady=1)

        ttk.Button(frame, text="Reset to Default",
                   command=self._on_reset_silence_trim,
                   bootstyle="warning-outline", width=20).pack(anchor=W, pady=(10, 0))

    def _on_silence_trim_mode_changed(self):
        """Save selected silence trim mode to config."""
        mode = self._silence_trim_mode_var.get()
        self.config_manager.set_silence_trim("mode", mode)

    def _on_reset_silence_trim(self):
        """Reset silence trim mode to default."""
        default = SILENCE_TRIM_DEFAULTS["mode"]
        self._silence_trim_mode_var.set(default)
        self.config_manager.set_silence_trim("mode", default)
