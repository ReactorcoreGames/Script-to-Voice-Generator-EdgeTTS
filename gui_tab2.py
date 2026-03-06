"""
Tab 2: Voice Settings & Audio Effects
For Script to Voice Generator GUI.
Per-speaker voice/effect panels, "Apply to All", SFX folder management.
Layout/build methods only — state/event methods are in gui_tab2_state.py.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from config import APP_THEME, AUDIO_EFFECTS, EFFECT_LEVELS, PITCH_PRESETS, ALIEN_VARIANTS, CAVE_VARIANTS

try:
    from ttkbootstrap.tooltip import ToolTip
    _TOOLTIP_AVAILABLE = True
except ImportError:
    _TOOLTIP_AVAILABLE = False


def _tip(widget, text, position=None):
    """Attach a tooltip to a widget if ToolTip is available."""
    if _TOOLTIP_AVAILABLE and widget:
        kwargs = {"text": text, "delay": 400}
        if position:
            kwargs["position"] = position
        ToolTip(widget, **kwargs)


class Tab2Builder:
    """Mixin class for building Tab 2 (Voice Settings) UI"""

    def build_tab2(self, parent):
        """Build the complete Tab 2 interface (static structure)."""
        # Initialize state BEFORE building widgets (build methods populate these)
        self._speaker_vars = {}       # {speaker_id: {var_name: tkvar}}
        self._speaker_widgets = {}    # {speaker_id: {widget_name: widget}}
        self._apply_all_vars = {}     # {effect_name: StringVar} - filled by _build_apply_to_all
        self._sfx_effect_vars = {}    # {effect_name: StringVar} - effects for SFX files
        self._sfx_fmsu_var = tk.BooleanVar(value=False)
        self._sfx_reverse_var = tk.BooleanVar(value=False)
        self._voices_loaded = False
        self._available_voices = []

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

        def bind_mousewheel_tab2(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel_tab2(child)

        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable.bind("<MouseWheel>", on_mousewheel)

        self._tab2_canvas = canvas
        self._tab2_scrollable = scrollable
        self._tab2_bind_mousewheel = bind_mousewheel_tab2

        # Title
        ttk.Label(scrollable, text="Voice Settings & Audio Effects",
                 font=("Consolas", 18, "bold")).pack(pady=(0, 5))
        ttk.Label(scrollable,
                 text="Configure each speaker's voice, pitch, speed, and audio effects.",
                 font=("Consolas", 10), wraplength=900, justify="center").pack(pady=(0, 15))

        # --- Apply to All Section ---
        self._build_apply_to_all_section(scrollable)

        # --- Dynamic speaker panels container ---
        self._speaker_panels_frame = ttk.Frame(scrollable)
        self._speaker_panels_frame.pack(fill=X, pady=(0, 10))

        # Placeholder shown when no speakers loaded
        self._no_speakers_label = ttk.Label(self._speaker_panels_frame,
                                            text="Load a script in Tab 1 to see speaker panels here.",
                                            font=("Consolas", 11, "italic"),
                                            foreground="#7A8F70")
        self._no_speakers_label.pack(pady=30)

        # --- SFX Section ---
        self._build_sfx_section(scrollable)

        # --- Bottom buttons ---
        bottom_frame = ttk.Frame(scrollable)
        bottom_frame.pack(fill=X, pady=(10, 10))

        profiles_btn = ttk.Button(bottom_frame, text="Speaker Library",
                                  command=self.on_open_profiles,
                                  bootstyle=INFO, width=18)
        profiles_btn.pack(side=LEFT, padx=(0, 10))
        _tip(profiles_btn, "Opens the speaker settings library (character_profiles.json) in your\n"
                           "system text editor. Stores all saved voice and effect settings per speaker.\n"
                           "Changes are saved automatically as you adjust settings in the panels above.")

        self.btn_continue_to_tab3 = ttk.Button(bottom_frame,
                                               text="Continue to Generate  >>",
                                               command=self.on_continue_to_tab3,
                                               bootstyle=SUCCESS, width=28,
                                               state="disabled")
        self.btn_continue_to_tab3.pack(side=RIGHT)

        # Bind mousewheel to all current child widgets
        bind_mousewheel_tab2(scrollable)

    def _build_apply_to_all_section(self, parent):
        """Build the 'Apply to All' effects section."""
        frame = ttk.LabelFrame(parent, text="Apply Audio Effects to All Speakers", padding=10)
        frame.pack(fill=X, pady=(0, 10))

        ttk.Label(frame,
                 text="Set audio effects here and click 'Apply to All' to propagate "
                      "to every speaker below. This only affects FFMPEG audio effects, "
                      "not Edge-TTS voice settings.",
                 font=("Consolas", 9), foreground="#9AAF88",
                 wraplength=900).pack(anchor=W, pady=(0, 8))

        # Effects grid (2 columns of 6)
        effects_container = ttk.Frame(frame)
        effects_container.pack(fill=X)

        left_col = ttk.Frame(effects_container)
        left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

        ttk.Separator(effects_container, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)

        right_col = ttk.Frame(effects_container)
        right_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 0))

        self._apply_all_vars = {}
        effect_keys = list(AUDIO_EFFECTS.keys())

        for i, effect_name in enumerate(effect_keys):
            col = left_col if i < 6 else right_col
            var = tk.StringVar(value="off")
            self._apply_all_vars[effect_name] = var
            levels = _get_effect_levels(effect_name)
            self._build_effect_row(col, effect_name, AUDIO_EFFECTS[effect_name], var, levels=levels)

        # Apply button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=X, pady=(8, 0))

        ttk.Button(btn_frame, text="Apply to All Speakers",
                  command=self.on_apply_to_all,
                  bootstyle=PRIMARY, width=24).pack(side=LEFT)

    def _build_sfx_section(self, parent):
        """Build the sound effects folder/file section."""
        frame = ttk.LabelFrame(parent, text="Sound Effects", padding=10)
        frame.pack(fill=X, pady=(0, 10))

        # Folder picker row
        folder_row = ttk.Frame(frame)
        folder_row.pack(fill=X, pady=(0, 5))

        sfx_folder_label = ttk.Label(folder_row, text="SFX Folder:",
                                     font=("Consolas", 10))
        sfx_folder_label.pack(side=LEFT, padx=(0, 5))
        _tip(sfx_folder_label, "Folder containing the sound effect files referenced in the script.\n"
                                "After selecting a folder, each SFX file will be scanned and marked "
                                "Found or Missing.")

        self._sfx_folder_var = tk.StringVar(value="")
        self._sfx_folder_entry = ttk.Entry(folder_row, textvariable=self._sfx_folder_var,
                                            width=50, state="readonly",
                                            font=("Consolas", 9))
        self._sfx_folder_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))

        browse_btn = ttk.Button(folder_row, text="Browse...",
                                command=self.on_pick_sfx_folder,
                                bootstyle=INFO, width=10)
        browse_btn.pack(side=LEFT)
        _tip(browse_btn, "Choose the folder where your SFX files are stored.")

        # Subfolder checkbox
        self._sfx_subfolders_var = tk.BooleanVar(value=True)
        subfolder_cb = ttk.Checkbutton(frame, text="Search subfolders",
                                       variable=self._sfx_subfolders_var,
                                       command=self._on_sfx_subfolder_changed)
        subfolder_cb.pack(anchor=W, pady=(0, 5))
        _tip(subfolder_cb, "When enabled, SFX files are searched recursively in all subfolders.\n"
                           "Disable to search only the top-level SFX folder.")

        # SFX file list container (dynamic)
        self._sfx_list_frame = ttk.Frame(frame)
        self._sfx_list_frame.pack(fill=X)

        self._sfx_no_files_label = ttk.Label(self._sfx_list_frame,
                                             text="No sound effects in current script.",
                                             font=("Consolas", 9, "italic"),
                                             foreground="#7A8F70")
        self._sfx_no_files_label.pack(pady=5)

        self._sfx_check_vars = {}     # {filename: BooleanVar}
        self._sfx_status_labels = {}  # {filename: Label}

        # --- SFX Audio Effects panel ---
        ttk.Separator(frame, orient=HORIZONTAL).pack(fill=X, pady=(10, 5))
        ttk.Label(frame, text="Audio Effects for Sound Effects",
                 font=("Consolas", 9, "bold")).pack(anchor=W, pady=(0, 3))
        ttk.Label(frame,
                 text="These effects are applied to SFX files during generation.",
                 font=("Consolas", 9), foreground="#9AAF88").pack(anchor=W, pady=(0, 6))

        sfx_effects_container = ttk.Frame(frame)
        sfx_effects_container.pack(fill=X)

        sfx_left = ttk.Frame(sfx_effects_container)
        sfx_left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

        ttk.Separator(sfx_effects_container, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)

        sfx_right = ttk.Frame(sfx_effects_container)
        sfx_right.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 0))

        self._sfx_effect_vars = {}
        effect_keys = list(AUDIO_EFFECTS.keys())
        for i, effect_name in enumerate(effect_keys):
            col = sfx_left if i < 6 else sfx_right
            var = tk.StringVar(value="off")
            self._sfx_effect_vars[effect_name] = var
            var.trace_add("write", lambda *_: self._on_sfx_settings_changed())
            levels = _get_effect_levels(effect_name)
            self._build_effect_row(col, effect_name, AUDIO_EFFECTS[effect_name], var, levels=levels)

        # SFX flags row — FMSU + Reverse
        sfx_flags_row = ttk.Frame(frame)
        sfx_flags_row.pack(fill=X, pady=(6, 0))

        sfx_fmsu_cb = ttk.Checkbutton(sfx_flags_row, text="FMSU",
                                       variable=self._sfx_fmsu_var)
        sfx_fmsu_cb.pack(side=LEFT, padx=(0, 20))
        sfx_fmsu_cb.config(command=self._on_sfx_settings_changed)
        _tip(sfx_fmsu_cb, "F*** My Sh** Up\n"
                          "Apply FMSU corruption to all SFX files.\n"
                          "Target sound: talking toy with a dying battery.")

        sfx_reverse_cb = ttk.Checkbutton(sfx_flags_row, text="Reverse",
                                          variable=self._sfx_reverse_var)
        sfx_reverse_cb.pack(side=LEFT, padx=(0, 20))
        sfx_reverse_cb.config(command=self._on_sfx_settings_changed)
        _tip(sfx_reverse_cb, "Reverse all SFX clips.")

    def populate_tab2_speakers(self, speakers, parse_result):
        """
        Populate Tab 2 with speaker panels from parse results.
        Called from gui_handlers after a successful parse.
        """
        # Clear existing speaker panels
        for widget in self._speaker_panels_frame.winfo_children():
            widget.destroy()
        self._speaker_vars = {}
        self._speaker_widgets = {}

        if not speakers:
            ttk.Label(self._speaker_panels_frame,
                     text="No speakers found in script.",
                     font=("Consolas", 11, "italic"),
                     foreground="#7A8F70").pack(pady=30)
            self.btn_continue_to_tab3.config(state="disabled")
            return

        # Build a panel for each speaker
        for speaker_id in speakers:
            profile = self.char_profiles.get_or_create_profile(speaker_id)
            self._build_speaker_panel(self._speaker_panels_frame, speaker_id, profile)

        # Populate SFX section
        self._populate_sfx_list(parse_result.sound_effects)

        # Enable continue button
        self.btn_continue_to_tab3.config(state="normal")

        # If voices are already loaded, populate comboboxes
        if self._voices_loaded:
            self._set_voices_on_comboboxes()

        # Re-bind mousewheel to newly created speaker panel widgets
        if hasattr(self, '_tab2_bind_mousewheel'):
            self._tab2_bind_mousewheel(self._tab2_scrollable)

    def _build_speaker_panel(self, parent, speaker_id, profile):
        """Build a single speaker configuration panel."""
        frame = ttk.LabelFrame(parent, text=f"  {speaker_id}  ", padding=10)
        frame.pack(fill=X, pady=(0, 8))

        # Create tkinter variables for this speaker
        vars_dict = self._create_speaker_vars(speaker_id, profile)
        self._speaker_vars[speaker_id] = vars_dict

        widgets_dict = {}
        self._speaker_widgets[speaker_id] = widgets_dict

        # --- Row 1: Voice + Pitch preset ---
        row1 = ttk.Frame(frame)
        row1.pack(fill=X, pady=(0, 5))

        voice_label = ttk.Label(row1, text="Voice:", font=("Consolas", 9, "bold"))
        voice_label.pack(side=LEFT, padx=(0, 5))
        _tip(voice_label, "Select the Edge-TTS voice actor for this speaker.\n"
                          "Voices are loaded in the background — if the list is empty, wait a moment.\n"
                          "Format: ShortName | Display Name | Gender (Personalities) - Categories")
        voice_combo = ttk.Combobox(row1, textvariable=vars_dict["voice"],
                                    width=45, state="readonly",
                                    font=("Consolas", 9), height=15)
        voice_combo.pack(side=LEFT, padx=(0, 15))
        widgets_dict["voice_combo"] = voice_combo

        # Prevent combobox scroll from propagating to canvas
        voice_combo.bind("<MouseWheel>", lambda e: "break")

        pitch_label = ttk.Label(row1, text="Pitch:", font=("Consolas", 9, "bold"))
        pitch_label.pack(side=LEFT, padx=(0, 5))
        _tip(pitch_label, "Deep: -40Hz (lower pitch, -10% speed)\n"
                          "Normal: default (0Hz, 0% speed)\n"
                          "High: +30Hz (higher pitch, +5% speed)\n"
                          "Custom: use the Hz and speed sliders below")

        for preset_name in PITCH_PRESETS:
            ttk.Radiobutton(row1, text=preset_name, value=preset_name,
                           variable=vars_dict["pitch_preset"],
                           command=lambda sid=speaker_id: self._on_preset_change(sid)
                           ).pack(side=LEFT, padx=2)

        # --- Row 2: Custom pitch/speed (shown only when Custom selected) ---
        custom_frame = ttk.Frame(frame)
        widgets_dict["custom_frame"] = custom_frame

        ttk.Label(custom_frame, text="Pitch Hz:", font=("Consolas", 9)).pack(side=LEFT, padx=(0, 3))
        ttk.Scale(custom_frame, from_=-50, to=50, variable=vars_dict["pitch_hz"],
                 orient=HORIZONTAL, length=120,
                 command=lambda v, sv=vars_dict["pitch_hz"]: sv.set(int(float(v)))
                 ).pack(side=LEFT, padx=(0, 3))
        ttk.Label(custom_frame, textvariable=vars_dict["pitch_hz"],
                 font=("Consolas", 9), width=4).pack(side=LEFT, padx=(0, 15))

        ttk.Label(custom_frame, text="Speed %:", font=("Consolas", 9)).pack(side=LEFT, padx=(0, 3))
        ttk.Scale(custom_frame, from_=-20, to=20, variable=vars_dict["speed_percent"],
                 orient=HORIZONTAL, length=120,
                 command=lambda v, sv=vars_dict["speed_percent"]: sv.set(int(float(v)))
                 ).pack(side=LEFT, padx=(0, 3))
        ttk.Label(custom_frame, textvariable=vars_dict["speed_percent"],
                 font=("Consolas", 9), width=4).pack(side=LEFT)

        # Show/hide based on current preset
        if vars_dict["pitch_preset"].get() == "Custom":
            custom_frame.pack(fill=X, pady=(0, 5))

        # --- Row 3: Volume + Yell Impact ---
        row3 = ttk.Frame(frame)
        row3.pack(fill=X, pady=(0, 5))

        vol_label = ttk.Label(row3, text="Level:", font=("Consolas", 9, "bold"))
        vol_label.pack(side=LEFT, padx=(0, 3))
        _tip(vol_label, "Volume level for this speaker relative to others.\n"
                        "100% = full normalized output (default).\n"
                        "Reduce to make this speaker quieter in the mix.\n"
                        "Range: 5%–100%, step 5.")

        ttk.Scale(row3, from_=5, to=100, variable=vars_dict["volume_percent"],
                 orient=HORIZONTAL, length=140,
                 command=lambda v, sv=vars_dict["volume_percent"]: sv.set(round(float(v) / 5) * 5)
                 ).pack(side=LEFT, padx=(0, 3))
        ttk.Label(row3, textvariable=vars_dict["volume_percent"],
                 font=("Consolas", 9), width=4).pack(side=LEFT)
        ttk.Label(row3, text="%", font=("Consolas", 9)).pack(side=LEFT, padx=(0, 20))

        yell_label = ttk.Label(row3, text="Yell Impact:", font=("Consolas", 9, "bold"))
        yell_label.pack(side=LEFT, padx=(0, 3))
        _tip(yell_label, "Extra speed reduction applied to single-word exclamatory lines.\n"
                         "Triggers on lines that are one word ending with ! or mixed ?!/!? "
                         "(e.g. AAARGH!, YES!!, NO?!, HELP?!?)\n"
                         "Does NOT trigger on lines ending with ? only, or multi-word lines.\n"
                         "Negative values slow the TTS rate for a punchier, more deliberate delivery.")

        ttk.Scale(row3, from_=0, to=-80, variable=vars_dict["yell_impact_percent"],
                 orient=HORIZONTAL, length=140).pack(side=LEFT, padx=(0, 3))
        ttk.Label(row3, textvariable=vars_dict["yell_impact_percent"],
                 font=("Consolas", 9), width=4).pack(side=LEFT)
        ttk.Label(row3, text="%", font=("Consolas", 9)).pack(side=LEFT)

        # --- Audio Effects ---
        ttk.Separator(frame, orient=HORIZONTAL).pack(fill=X, pady=5)
        ttk.Label(frame, text="Audio Effects", font=("Consolas", 9, "bold")).pack(anchor=W, pady=(0, 3))

        effects_container = ttk.Frame(frame)
        effects_container.pack(fill=X)

        left_col = ttk.Frame(effects_container)
        left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

        ttk.Separator(effects_container, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)

        right_col = ttk.Frame(effects_container)
        right_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 0))

        effect_keys = list(AUDIO_EFFECTS.keys())
        for i, effect_name in enumerate(effect_keys):
            col = left_col if i < 6 else right_col
            levels = _get_effect_levels(effect_name)
            self._build_effect_row(col, effect_name, AUDIO_EFFECTS[effect_name],
                                   vars_dict[effect_name], levels=levels)

        # --- Flags row: FMSU + Reverse + Test buttons ---
        flags_row = ttk.Frame(frame)
        flags_row.pack(fill=X, pady=(5, 0))

        fmsu_cb = ttk.Checkbutton(flags_row, text="FMSU",
                                   variable=vars_dict["fmsu"])
        fmsu_cb.pack(side=LEFT, padx=(0, 20))
        _tip(fmsu_cb, "F*** My Sh** Up\n"
                      "Applies a final destructive corruption pass on top of all other effects.\n"
                      "Target sound: talking toy with a dying battery.\n"
                      "Semi-intelligible — speech rhythms survive, quality does not.\n"
                      "Combines with everything. Chaos encouraged.")

        reverse_cb = ttk.Checkbutton(flags_row, text="Reverse",
                                      variable=vars_dict["reverse"])
        reverse_cb.pack(side=LEFT, padx=(0, 20))
        _tip(reverse_cb, "Reverses the clip — speech plays backwards.\n"
                         "Applied absolutely last, after all other effects including FMSU.\n"
                         "Use for demonic chanting, alien speech, dreamlike sequences.")

        test_it_btn = ttk.Button(flags_row, text="Test + Inner Thoughts",
                                 command=lambda sid=speaker_id: self.on_test_voice_inner_thoughts(sid),
                                 bootstyle=INFO, width=22)
        test_it_btn.pack(side=RIGHT, padx=(0, 8))
        _tip(test_it_btn, 'Generates a test clip with the speaker\'s current effects PLUS\n'
                          'the Inner Thoughts filter from Tab 4 applied on top.\n'
                          'Useful for auditioning how a character sounds as an inner thought.\n\n'
                          "Tip: Stop the previous clip in your media player before clicking again,\n"
                          "or the file may still be locked and the test will be blocked.",
             position="bottom left")

        test_btn = ttk.Button(flags_row, text="Test Voice",
                              command=lambda sid=speaker_id: self.on_test_voice(sid),
                              bootstyle=WARNING, width=14)
        test_btn.pack(side=RIGHT)
        _tip(test_btn, 'Generates a test clip: "The quick brown fox jumps over the lazy dog."\n'
                       "Saved to output_test/ and opened in your default media player.\n\n"
                       "Tip: Stop the previous clip in your media player before clicking again,\n"
                       "or the file may still be locked and the test will be blocked.",
             position="bottom left")

    def _build_effect_row(self, parent, effect_name, effect_data, var, levels=None):
        """Build a single effect control row with radio buttons."""
        if levels is None:
            levels = EFFECT_LEVELS

        row = ttk.Frame(parent)
        row.pack(fill=X, pady=2)

        label = ttk.Label(row, text=f"{effect_data['name']}:",
                         font=("Consolas", 9), width=14, anchor=W)
        label.pack(side=LEFT, padx=(0, 3))
        _tip(label, effect_data.get("description", ""))

        for level in levels:
            label_text = _LEVEL_DISPLAY_LABELS.get(level, level.capitalize())
            ttk.Radiobutton(row, text=label_text, value=level,
                           variable=var).pack(side=LEFT, padx=2)


def _get_effect_levels(effect_name):
    """Return the correct level list for a given effect name."""
    if effect_name == "alien":
        return ALIEN_VARIANTS
    if effect_name == "cave":
        return CAVE_VARIANTS
    return None  # caller will use EFFECT_LEVELS default


# Short display labels for radio buttons where the preset key is too long to fit
_LEVEL_DISPLAY_LABELS = {
    "insectoid": "Insect",
    "dimensional": "Dim.",
}
