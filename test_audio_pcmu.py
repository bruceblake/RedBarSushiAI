#!/usr/bin/env python3
"""
Create a test PCMU audio file for debugging ConversationRelay.
"""

import wave
import audioop
import struct

def create_test_pcmu():
    """Create a simple test PCMU audio file with a sine wave."""
    import math
    
    # Parameters
    sample_rate = 8000  # 8kHz for PCMU
    duration = 1.0      # 1 second
    frequency = 440     # A4 note
    
    # Generate sine wave
    num_samples = int(sample_rate * duration)
    samples = []
    
    for i in range(num_samples):
        t = i / sample_rate
        # Generate 16-bit PCM sample
        sample = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack('<h', sample))
    
    # Convert to bytes
    pcm_data = b''.join(samples)
    
    # Convert to μ-law
    mulaw_data = audioop.lin2ulaw(pcm_data, 2)
    
    # Save to file
    with open('test_audio.mulaw', 'wb') as f:
        f.write(mulaw_data)
    
    print(f"Created test_audio.mulaw: {len(mulaw_data)} bytes")
    print(f"First 20 bytes (hex): {mulaw_data[:20].hex()}")
    
    return mulaw_data

if __name__ == "__main__":
    create_test_pcmu()