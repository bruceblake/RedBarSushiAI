#!/usr/bin/env python3
"""
Test with static audio to verify ConversationRelay connection.
"""

import base64

# This is 1 second of silence in PCMU format (8kHz, mono)
# PCMU silence is 0xFF (255) repeated
SILENCE_PCMU = b'\xff' * 8000

# This is a simple test pattern that should produce some sound
# Alternating between loud and quiet values
TEST_PATTERN_PCMU = b''.join([b'\x00\xff' * 4000])

def get_test_audio():
    """Return test PCMU audio bytes."""
    # For now, just return silence to test if Twilio accepts it
    return SILENCE_PCMU

def get_hex_preview(data, length=20):
    """Get hex preview of audio data."""
    return data[:length].hex()

if __name__ == "__main__":
    audio = get_test_audio()
    print(f"Test audio: {len(audio)} bytes")
    print(f"First 20 bytes (hex): {get_hex_preview(audio)}")
    
    # Save to file for inspection
    with open('test_audio.pcmu', 'wb') as f:
        f.write(audio)
    print("Saved to test_audio.pcmu")