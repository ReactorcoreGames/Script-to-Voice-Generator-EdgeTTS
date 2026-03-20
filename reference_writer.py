"""
Reference sheet writer for Script to Voice Generator (Edge-TTS edition).
Generates project_reference.txt after a successful generation run.
"""

from datetime import datetime

from config import MERGED_AUDIO_PAUSE_DEFAULTS, CONTEXTUAL_MODIFIER_DEFAULTS, SILENCE_TRIM_DEFAULTS


# Abbreviated display codes for audio effects
EFFECT_ABBREVS = {
    "radio":       "RAD",
    "reverb":      "RVB",
    "distortion":  "DIST",
    "telephone":   "TEL",
    "robot_voice": "ROBO",
    "cheap_mic":   "CHP",
    "underwater":  "UNDR",
    "megaphone":   "MEGA",
    "worn_tape":   "TAPE",
    "intercom":    "ICOM",
    "alien":       "ALN",
    "cave":        "CAVE",
}

# Pause display labels (key, symbol) — order matches reference sheet output
_PAUSE_LABELS = [
    ("period",       "."),
    ("comma",        ","),
    ("exclamation",  "!"),
    ("question",     "?"),
    ("hyphen",       "-"),
    ("ellipsis",     "..."),
    ("double_power", "!!"),
    ("triple_power", "!!!"),
]


def _effects_string(effects: dict) -> str:
    """
    Build a compact display string for a speaker's active effects.
    Returns '| NONE |' if no effects are active.
    """
    parts = []

    for key, abbrev in EFFECT_ABBREVS.items():
        val = effects.get(key, "off")
        if val and val != "off":
            parts.append(f"{abbrev}:{val}")

    # pitch_shift is not used in Edge-TTS (pitch is pitch_hz via Edge API)
    if effects.get("fmsu"):
        parts.append("FMSU:on")
    if effects.get("reverse"):
        parts.append("REV:on")

    if not parts:
        return "| NONE |"
    return "| " + " | ".join(parts) + " |"


def _format_speaker_block(speaker_id: str, sp: dict) -> list:
    """
    Build display lines for one speaker's profile.
    Returns a list of strings (4 lines).
    """
    lines = []
    lines.append(speaker_id)

    voice_name = sp.get("voice_name", "unknown")
    lines.append(f"  Voice     : | {voice_name} |")

    pitch_hz = sp.get("pitch_hz", 0)
    speed_pct = sp.get("speed_percent", 0)
    yell = sp.get("yell_impact", 0)
    volume = sp.get("volume", 100)
    lines.append(
        f"  Settings  : | Pitch {pitch_hz:+d}Hz | Speed {speed_pct:+d}% | "
        f"Level : {volume}% | Yell : {yell:+d}% |"
    )

    effects_str = _effects_string(sp.get("effects", {}))
    lines.append(f"  Effects   : {effects_str}")

    return lines


def _format_parameters_section(config_manager, sfx_effects: dict) -> list:
    """
    Build the PARAMETERS section lines.
    """
    lines = []

    # SFX filters
    sfx_parts = []
    for key, abbrev in EFFECT_ABBREVS.items():
        val = sfx_effects.get(key, "off")
        if val and val != "off":
            sfx_parts.append(f"{abbrev}:{val}")
    if sfx_effects.get("fmsu"):
        sfx_parts.append("FMSU:on")
    if sfx_effects.get("reverse"):
        sfx_parts.append("REV:on")
    sfx_str = "| " + " | ".join(sfx_parts) + " |" if sfx_parts else "| NONE |"
    lines.append(f"SFX Filters : {sfx_str}")

    # Pause values
    pause_parts = []
    for key, symbol in _PAUSE_LABELS:
        val = config_manager.get_pause(key) if config_manager else MERGED_AUDIO_PAUSE_DEFAULTS.get(key, 0.0)
        pause_parts.append(f"{symbol}  {val:.1f}s")
    lines.append("Punctuations: | " + " | ".join(pause_parts) + " |")

    # Contextual modifiers
    def _mod(key):
        if config_manager:
            return config_manager.get_modifier(key)
        return CONTEXTUAL_MODIFIER_DEFAULTS.get(key, 0)

    mod_parts = [
        f"Change {_mod('speaker_change_bonus'):.1f}s",
        f"Short {int(_mod('short_line_threshold_chars'))}/{_mod('short_line_reduction_s'):.1f}s",
        f"Long {int(_mod('long_line_threshold_chars'))}/{_mod('long_line_addition_s'):.1f}s",
        f"IT-pad {_mod('inner_thought_padding_s'):.1f}s",
        f"Same-spk -{_mod('same_speaker_reduction_s'):.1f}s",
        f"First {_mod('first_line_padding_s'):.1f}s",
        f"Last {_mod('last_line_padding_s'):.1f}s",
    ]
    lines.append("Contextuals : | " + " | ".join(mod_parts) + " |")

    # Inner thoughts preset
    it_preset = config_manager.get_inner_thoughts_preset() if config_manager else "Dissociated"
    lines.append(f"Inner thgts : | {it_preset} |")

    # Silence trim
    trim = config_manager.get_silence_trim("mode") if config_manager else SILENCE_TRIM_DEFAULTS["mode"]
    lines.append(f"Silence trim: | {trim} |")

    return lines


def _format_clip_list(ref_entries: list) -> list:
    """
    Build the CLIPS section — one entry per generated clip.

    ref_entries: list of (filename, speaker_id, spoken_text, is_inner_thought)
    """
    lines = []
    for filename, speaker_id, spoken_text, is_inner_thought in ref_entries:
        # Extract zero-padded line number from filename (e.g. "proj_0003_Alice_hello.mp3" → "0003")
        import re
        m = re.search(r'_(\d{4})_', filename)
        num_str = m.group(1) if m else "????"

        it_tag = " [IT]" if is_inner_thought else ""
        lines.append(f"{num_str}. {filename}")
        lines.append(f"      {speaker_id}{it_tag}: {spoken_text}")
        lines.append("")

    # Remove trailing blank line
    if lines and lines[-1] == "":
        lines.pop()

    return lines


def write_reference_sheet(
    output_path: str,
    project_name: str,
    output_format: str,
    speaker_settings: dict,
    ref_entries: list,
    config_manager,
    sfx_effects: dict,
    sound_count: int,
) -> None:
    """
    Write a full project reference sheet to output_path.

    Args:
        output_path:      Full path for the .txt file.
        project_name:     User's project name string.
        output_format:    "mp3" (always for this app).
        speaker_settings: Dict of speaker_id -> settings dict from gui_generation.
        ref_entries:      List of (filename, speaker_id, spoken_text, is_inner_thought).
        config_manager:   ConfigManager instance (or None for defaults).
        sfx_effects:      Dict of effect_name -> preset for SFX panel settings.
        sound_count:      Number of unique SFX files referenced in the script.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    clip_count = len(ref_entries)
    speaker_count = len(speaker_settings)
    speaker_list = ", ".join(sorted(speaker_settings.keys()))

    out = []

    # Header
    out.append("# SCRIPT TO VOICE GENERATOR — EDGE-TTS — SESSION REFERENCE")
    out.append("")
    out.append(
        f"Project  : | {project_name} | {timestamp} | {output_format.upper()} | "
        f"{clip_count} Clips | {sound_count} Sound(s) |"
    )
    out.append(f"Speakers : | {speaker_count} | {speaker_list} |")
    out.append("")
    out.append("---")
    out.append("")

    # Speakers section
    out.append("## SPEAKERS")
    out.append("")
    for speaker_id in sorted(speaker_settings.keys()):
        sp = speaker_settings[speaker_id]
        out.extend(_format_speaker_block(speaker_id, sp))
        out.append("")

    out.append("---")
    out.append("")

    # Parameters section
    out.append("## PARAMETERS")
    out.append("")
    out.extend(_format_parameters_section(config_manager, sfx_effects))
    out.append("")
    out.append("---")
    out.append("")

    # Clips section
    out.append("## CLIPS")
    out.append("")
    out.extend(_format_clip_list(ref_entries))
    out.append("")
    out.append("---")
    out.append("")
    out.append("EoF")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
