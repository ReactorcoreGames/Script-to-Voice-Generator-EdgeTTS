"""
Quick test script to examine Edge-TTS voice metadata structure
"""
import asyncio
import edge_tts
import json


async def test_voice_metadata():
    """Print detailed metadata for a few voices"""
    voices = await edge_tts.list_voices()

    print(f"Total voices found: {len(voices)}\n")
    print("=" * 80)

    # Show first 3 voices in detail
    for i, voice in enumerate(voices[:3]):
        print(f"\nVoice {i+1} - All available fields:")
        print(json.dumps(voice, indent=2))
        print("-" * 80)

    # Check if VoiceTag exists in all voices
    voices_with_voicetag = 0
    voices_with_content_categories = 0
    voices_with_personalities = 0

    for voice in voices:
        if 'VoiceTag' in voice:
            voices_with_voicetag += 1
            if 'ContentCategories' in voice['VoiceTag']:
                voices_with_content_categories += 1
            if 'VoicePersonalities' in voice['VoiceTag']:
                voices_with_personalities += 1

    print(f"\n\nStatistics:")
    print(f"Voices with VoiceTag: {voices_with_voicetag}/{len(voices)}")
    print(f"Voices with ContentCategories: {voices_with_content_categories}/{len(voices)}")
    print(f"Voices with VoicePersonalities: {voices_with_personalities}/{len(voices)}")

    # Show unique fields across all voices
    all_fields = set()
    for voice in voices:
        all_fields.update(voice.keys())

    print(f"\nAll unique fields found across voices:")
    print(sorted(all_fields))


if __name__ == "__main__":
    asyncio.run(test_voice_metadata())
