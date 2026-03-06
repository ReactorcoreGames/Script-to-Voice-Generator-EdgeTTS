"""
Extract Edge-TTS voice metadata and save to text file
Output format: ShortName | CleanedFriendlyName - Language/Region | Gender (VoicePersonalities) - ContentCategories
"""
import asyncio
import edge_tts
from pathlib import Path


async def extract_voice_metadata():
    """Extract metadata for all Edge-TTS voices and save to file"""
    print("Fetching Edge-TTS voices...")
    voices = await edge_tts.list_voices()

    print(f"Found {len(voices)} voices")
    print("Extracting metadata...\n")

    output_lines = []

    for voice in voices:
        # Extract basic info
        short_name = voice.get('ShortName', 'Unknown')
        locale = voice.get('Locale', 'Unknown')
        gender = voice.get('Gender', 'Unknown')
        friendly_name = voice.get('FriendlyName', 'Unknown')

        # Clean up FriendlyName by removing "Microsoft" and "Online (Natural)"
        cleaned_name = friendly_name.replace('Microsoft ', '').replace(' Online (Natural)', '').strip()
        # Remove leading " - " if present
        if cleaned_name.startswith('- '):
            cleaned_name = cleaned_name[2:].strip()

        # Extract VoiceTag information
        voice_tag = voice.get('VoiceTag', {})

        # Get personalities (list) and join with commas
        personalities = voice_tag.get('VoicePersonalities', [])
        personalities_str = ', '.join(personalities) if personalities else ''

        # Get content categories (list) and join with commas
        categories = voice_tag.get('ContentCategories', [])
        categories_str = ', '.join(categories) if categories else ''

        # Format: ShortName | CleanedName - Language/Region | Gender (Personalities) - Categories
        if personalities_str:
            line = f"{short_name} | {cleaned_name} | {gender} ({personalities_str}) - {categories_str}"
        else:
            # If no personalities, don't show empty parentheses
            line = f"{short_name} | {cleaned_name} | {gender} - {categories_str}"

        output_lines.append(line)

        # Print first 5 as preview
        if len(output_lines) <= 5:
            print(f"Example {len(output_lines)}: {line}")

    # Save to file in same directory as script
    script_dir = Path(__file__).parent
    output_file = script_dir / "voice_metadata_output.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        for line in output_lines:
            f.write(line + '\n')

    print(f"\n{'='*80}")
    print(f"Successfully saved {len(output_lines)} voice entries to:")
    print(f"{output_file}")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(extract_voice_metadata())
