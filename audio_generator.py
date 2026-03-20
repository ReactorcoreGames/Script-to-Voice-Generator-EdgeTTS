"""
Audio generation using Edge-TTS and conversion utilities
"""

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path
import edge_tts


def is_yell_line(spoken_text):
    """
    Check if a spoken text line qualifies for the Yell Impact speed adjustment.

    Qualifies when:
    - The entire text is a single word (no spaces) before trailing punctuation
    - The trailing punctuation characters contain at least one !
    - Patterns like AAARGH!, YES!!, NO?!, HELP?!?, REALLY!!! all qualify
    - Lines ending with ? only, or multi-word lines, do NOT qualify

    Examples that qualify:  AAARGH!  YES!!  NO?!  HELP?!?  REALLY!!!
    Examples that don't:    Why?    Get out!    Help me!!
    """
    text = spoken_text.strip()
    if not text:
        return False

    # Match a single non-punctuation word followed by trailing ?! punctuation
    match = re.match(r'^([^?!\s]+)([?!]+)$', text)
    if not match:
        return False

    punct_part = match.group(2)
    # Trailing punctuation must contain at least one ! (? alone does not qualify)
    return '!' in punct_part


def _build_silence_filter(mode: str) -> str:
    """
    Build an FFMPEG silenceremove filter string for the given trim mode.

    Modes:
        off            — no filter (empty string)
        beginning      — trim leading silence only
        end            — trim trailing silence only (areverse sandwich)
        beginning_end  — trim both (default)
        all            — trim beginning, end, and mid-clip gaps
    """
    START = (
        "silenceremove="
        "start_periods=1:start_silence=0.02:start_threshold=-35dB:stop_periods=0"
    )
    # areverse sandwich: flip → trim start → flip back. Avoids stop_periods bug
    # that prematurely cuts expressive voice tails on Edge-TTS output.
    END = (
        "areverse,"
        "silenceremove="
        "start_periods=1:start_silence=0.02:start_threshold=-35dB:stop_periods=0,"
        "areverse"
    )
    MID = (
        "silenceremove="
        "start_periods=0:stop_periods=-1:stop_silence=0.1:stop_threshold=-80dB"
    )

    if mode == "off":
        return ""
    elif mode == "beginning":
        return START
    elif mode == "end":
        return END
    elif mode == "beginning_end":
        return f"{START},{END}"
    elif mode == "all":
        return f"{START},{END},{MID}"
    else:
        # Unknown mode — fall back to beginning_end
        return f"{START},{END}"


class AudioGenerator:
    """Handles audio generation and conversion"""

    def __init__(self):
        self.available_voices = []

    def _get_subprocess_startupinfo(self):
        """
        Get subprocess startup info to hide console windows on Windows

        Returns:
            subprocess.STARTUPINFO on Windows, None on other platforms
        """
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        return None

    async def load_voices(self):
        """
        Load available Edge-TTS voices with enhanced metadata display

        Format: ShortName | CleanedFriendlyName - Language/Region | Gender (Personalities) - Categories
        Example: en-US-JennyNeural | Jenny - English (United States) | Female (Friendly, Positive) - General

        Returns:
            List of formatted voice strings with ShortName for extraction
        """
        voices = await edge_tts.list_voices()
        formatted_voices = []

        for v in voices:
            # Extract basic fields
            short_name = v.get('ShortName', 'Unknown')
            gender = v.get('Gender', 'Unknown')
            friendly_name = v.get('FriendlyName', 'Unknown')

            # Clean up FriendlyName by removing "Microsoft" and "Online (Natural)"
            # and any extra " - " separators
            cleaned_name = friendly_name.replace('Microsoft ', '').replace(' Online (Natural)', '').strip()
            # Remove leading " - " if present
            if cleaned_name.startswith('- '):
                cleaned_name = cleaned_name[2:].strip()

            # Extract VoiceTag metadata
            voice_tag = v.get('VoiceTag', {})
            personalities = voice_tag.get('VoicePersonalities', [])
            personalities_str = ', '.join(personalities) if personalities else ''
            categories = voice_tag.get('ContentCategories', [])
            categories_str = ', '.join(categories) if categories else ''

            # Format: ShortName | CleanedName - Language/Region | Gender (Personalities) - Categories
            # ShortName is at the front for easy extraction via split(" | ")[0]
            if personalities_str:
                voice_display = f"{short_name} | {cleaned_name} | {gender} ({personalities_str}) - {categories_str}"
            else:
                # If no personalities, don't show empty parentheses
                voice_display = f"{short_name} | {cleaned_name} | {gender} - {categories_str}"

            formatted_voices.append(voice_display)

        self.available_voices = formatted_voices
        return self.available_voices

    async def generate_audio(self, text, output_path, voice_name, pitch="+0Hz", rate="+0%"):
        """
        Generate audio using Edge-TTS

        Args:
            text: Text to synthesize
            output_path: Path to save the audio file
            voice_name: Edge-TTS voice name (short name)
            pitch: Pitch adjustment (e.g., "+0Hz", "-40Hz")
            rate: Speed adjustment (e.g., "+0%", "-20%")
        """
        communicate = edge_tts.Communicate(text, voice_name, pitch=pitch, rate=rate)
        await communicate.save(str(output_path))

    def apply_volume_adjustment(self, input_path, output_path, volume_percent):
        """
        Apply volume adjustment to an audio file using FFMPEG

        Args:
            input_path: Path to input audio file
            output_path: Path to output audio file
            volume_percent: Volume percentage (5–100, where 100 = full normalized output)

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        try:
            # Convert percentage to FFMPEG volume multiplier (1.0 = 100%, 1.5 = 150%, etc.)
            volume_multiplier = volume_percent / 100.0

            subprocess.run([
                "ffmpeg", "-i", str(input_path),
                "-af", f"volume={volume_multiplier}",
                "-y", str(output_path)
            ], check=True, capture_output=True, startupinfo=self._get_subprocess_startupinfo())
            return True, None
        except subprocess.CalledProcessError as e:
            return False, f"Failed to adjust volume: {str(e)}"
        except FileNotFoundError:
            return False, ("FFMPEG not found in PATH. Please install FFMPEG.\n\n"
                          "You can use: https://reactorcore.itch.io/ffmpeg-to-path-installer")

    def apply_audio_effects(self, input_path, output_path, effect_settings,
                            volume_percent=100, is_inner_thought=False,
                            config_manager=None, is_sfx=False,
                            silence_trim_mode="beginning_end"):
        """
        Apply audio effects and volume adjustment to an audio file using FFMPEG

        Pipeline (voice clips):
        0. Silence removal (trims Edge-TTS padding)
        1. Apply all effects (frequency, ring mod, spatial, distortion, inner thoughts)
        2. Soft limiting (prevents encoder clipping)
        3. Final volume adjustment (capped at 100%)

        Per-clip peak normalization is applied separately after this call in gui_generation.py.
        No normalization is done inside this method — effects are allowed to sound naturally.

        Args:
            input_path: Path to input audio file
            output_path: Path to output audio file
            effect_settings: Dictionary mapping effect names to their preset levels
                           e.g., {"radio": "mild", "reverb": "medium", "distortion": "off"}
            volume_percent: Volume percentage (applied after effects, internally capped at 100%)
            is_inner_thought: If True, applies inner thoughts filter (muffled, echo-y effect)
            is_sfx: If True, skips silence removal and normalization stages (preserves SFX levels)

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        from config import AUDIO_EFFECTS, INNER_THOUGHTS_FILTER, FMSU_FILTER
        # Prefer config_manager's live filter (respects user preset) over hardcoded fallback
        if config_manager is not None:
            inner_thoughts_filter = config_manager.get_inner_thoughts_filter()
        else:
            inner_thoughts_filter = INNER_THOUGHTS_FILTER

        try:
            filters = []

            if not is_sfx:
                # STAGE 0: Trim silence from Edge-TTS output.
                # Mode is configurable via Tab 4 (default: beginning_end).
                # Uses -35dB threshold with areverse sandwich for end trim
                # to avoid the stop_periods bug that prematurely cuts expressive tails.
                silence_filter = _build_silence_filter(silence_trim_mode)
                if silence_filter:
                    filters.append(silence_filter)

            # STAGE 2: Apply frequency-based effects first
            # These work best on normalized audio
            for effect_name in ["radio", "telephone", "cheap_mic",
                                "underwater", "megaphone", "worn_tape", "intercom"]:
                if effect_name in effect_settings and effect_settings[effect_name] != "off":
                    level = effect_settings[effect_name]
                    if effect_name in AUDIO_EFFECTS:
                        effect_filter = AUDIO_EFFECTS[effect_name]["presets"].get(level, "")
                        if effect_filter:
                            filters.append(effect_filter)

            # STAGE 3: Ring modulation / pitch-based character effects
            for effect_name in ["robot_voice", "alien"]:
                if effect_name in effect_settings and effect_settings[effect_name] != "off":
                    level = effect_settings[effect_name]
                    if effect_name in AUDIO_EFFECTS:
                        effect_filter = AUDIO_EFFECTS[effect_name]["presets"].get(level, "")
                        if effect_filter:
                            filters.append(effect_filter)

            # STAGE 4: Spatial/echo effects
            for effect_name in ["reverb", "cave"]:
                if effect_name in effect_settings and effect_settings[effect_name] != "off":
                    level = effect_settings[effect_name]
                    if effect_name in AUDIO_EFFECTS:
                        effect_filter = AUDIO_EFFECTS[effect_name]["presets"].get(level, "")
                        if effect_filter:
                            filters.append(effect_filter)

            # STAGE 5: Apply distortion LAST (needs loud signal to clip properly)
            if "distortion" in effect_settings and effect_settings["distortion"] != "off":
                level = effect_settings["distortion"]
                if "distortion" in AUDIO_EFFECTS:
                    effect_filter = AUDIO_EFFECTS["distortion"]["presets"].get(level, "")
                    if effect_filter:
                        filters.append(effect_filter)

            # STAGE 5.5: Inner thoughts filter
            # Applied after all character effects, before post-normalization
            # Creates a muffled, echo-y sound to indicate internal monologue
            if is_inner_thought:
                filters.append(inner_thoughts_filter)

            # STAGE 7: Soft limiting + final volume adjustment
            # level=1 means "enable level limiting" (boolean in FFmpeg 7.x+, was float in older)
            safe_volume_percent = min(volume_percent, 100)
            filters.append("alimiter=level=1:attack=1:release=100")

            # STAGE 8: Final volume adjustment
            # 100% = full normalized output, lower values reduce speaker relative level
            final_volume = safe_volume_percent / 100.0
            filters.append(f"volume={final_volume}")

            # STAGE 8.5: FMSU (F*** My Sh** Up) — applied after normalization so the damage sticks
            # Deliberately destructive: semi-intelligible low-battery-toy corruption.
            # Has its own internal volume=1.3. Followed by alimiter to prevent encoder
            # overflow when combined with effects that already boost the signal (e.g. telephone medium).
            if effect_settings.get("fmsu", False):
                filters.append(FMSU_FILTER)
                filters.append("alimiter=level=1:attack=7:release=100")

            # STAGE 9: Reverse — flip the fully-processed clip end-to-end
            # areverse buffers the whole stream before outputting; fine for short TTS clips.
            # Placed last so reversal is the final state.
            if effect_settings.get("reverse", False):
                filters.append("areverse")

            # Combine all filters into single chain
            filter_chain = ",".join(filters)

            # Intercom static noise: use filter_complex to mix generated noise into voice
            intercom_level = effect_settings.get("intercom", "off")
            intercom_noise_params = {
                "mild":   (0.08, "anoisesrc=amplitude=0.10:color=brown,highpass=f=300,lowpass=f=3500,acrusher=bits=6:mode=log:aa=0"),
                "medium": (0.20, "anoisesrc=amplitude=0.22:color=brown,highpass=f=200,lowpass=f=3000,acrusher=bits=4:mode=log:aa=0"),
                "strong": (0.28, "anoisesrc=amplitude=0.28:color=brown,highpass=f=150,lowpass=f=2800,acrusher=bits=3:mode=log:aa=0"),
            }.get(intercom_level)

            if intercom_noise_params is not None:
                # Build filter_complex graph:
                # [0:a] → voice filters → [voice]
                # anoisesrc → bandpass + bit-crush (coarse crackle) → [noise]
                # [voice][noise] → amix → output
                _, noise_filter = intercom_noise_params
                complex_graph = (
                    f"[0:a]{filter_chain}[voice];"
                    f"{noise_filter}[noise];"
                    f"[voice][noise]amix=inputs=2:weights=1 1:normalize=0:duration=shortest"
                )
                result = subprocess.run([
                    "ffmpeg", "-i", str(input_path),
                    "-filter_complex", complex_graph,
                    "-y", str(output_path)
                ], check=True, capture_output=True, text=True, startupinfo=self._get_subprocess_startupinfo())
            else:
                # Apply all filters in one pass for efficiency
                result = subprocess.run([
                    "ffmpeg", "-i", str(input_path),
                    "-af", filter_chain,
                    "-y", str(output_path)
                ], check=True, capture_output=True, text=True, startupinfo=self._get_subprocess_startupinfo())
            return True, None
        except subprocess.CalledProcessError as e:
            # Decode stderr to show the actual FFMPEG error
            stderr_output = e.stderr if e.stderr else str(e)
            error_msg = (f"Failed to apply audio effects.\n\n"
                        f"FFMPEG Error:\n{stderr_output}\n\n"
                        f"This should not happen with the safety pipeline.\n"
                        f"Please report this error with your effect settings.")
            return False, error_msg
        except FileNotFoundError:
            return False, ("FFMPEG not found in PATH. Please install FFMPEG.\n\n"
                          "You can use: https://reactorcore.itch.io/ffmpeg-to-path-installer")

    def apply_peak_normalize(self, input_path, output_path):
        """
        Peak-normalize an audio file (input → output).

        Two-pass: measure peak via volumedetect, then apply linear gain so the
        loudest sample reaches exactly 0 dBFS. Dynamics are fully preserved.

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        import re
        startupinfo = self._get_subprocess_startupinfo()
        try:
            # Pass 1: measure peak
            result = subprocess.run([
                "ffmpeg", "-i", str(input_path),
                "-af", "volumedetect",
                "-f", "null", "-"
            ], capture_output=True, text=True, startupinfo=startupinfo)

            match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", result.stderr)
            if not match:
                return False, "Peak normalize failed: could not read max_volume from ffmpeg output."

            max_volume_db = float(match.group(1))
            if max_volume_db >= 0.0:
                # Already at or above 0dBFS — just copy
                import shutil
                if str(input_path) != str(output_path):
                    shutil.copy2(str(input_path), str(output_path))
                return True, None

            gain_db = -max_volume_db

            # Pass 2: apply linear gain
            # FFmpeg can't write to the same file it's reading, so use a temp file
            # when input == output (in-place normalization).
            import tempfile
            in_place = str(input_path) == str(output_path)
            if in_place:
                fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
                actual_output = tmp_path
            else:
                actual_output = str(output_path)

            try:
                subprocess.run([
                    "ffmpeg", "-i", str(input_path),
                    "-af", f"volume={gain_db}dB",
                    "-y", actual_output
                ], check=True, capture_output=True, text=True, startupinfo=startupinfo)

                if in_place:
                    os.replace(tmp_path, str(output_path))
            except subprocess.CalledProcessError:
                if in_place:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                raise

            return True, None
        except subprocess.CalledProcessError as e:
            return False, f"Peak normalize failed: {e.stderr}"
        except FileNotFoundError:
            return False, ("FFMPEG not found in PATH. Please install FFMPEG.\n\n"
                          "You can use: https://reactorcore.itch.io/ffmpeg-to-path-installer")

    def get_voice_settings(self, preset_name, custom_pitch=0, custom_speed=0,
                          pitch_presets=None):
        """
        Get voice settings based on preset or custom values.

        Args:
            preset_name: Name of the pitch preset (e.g. "Normal", "Deep", "Custom")
            custom_pitch: Custom pitch Hz value (used when preset is "Custom")
            custom_speed: Custom speed percent value (used when preset is "Custom")
            pitch_presets: Dictionary of pitch presets from config

        Returns:
            tuple: (pitch: str, rate: str) e.g. ("+0Hz", "+0%")
        """
        if preset_name == "Custom":
            pitch = f"{custom_pitch:+d}Hz"
            rate = f"{custom_speed:+d}%"
        else:
            preset = pitch_presets[preset_name]
            pitch = preset["pitch"]
            rate = f"{preset['speed_adjust']:+d}%"

        return pitch, rate
