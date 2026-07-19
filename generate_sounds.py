import wave
import struct
import math
import os

def write_ticking(filename):
    sample_rate = 44100
    duration = 1.0
    num_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        
        for i in range(num_samples):
            t = i / sample_rate
            # A soft woodblock-like tick at the start
            if t < 0.05:
                val = math.sin(2 * math.pi * 800 * t) * math.exp(-150 * t)
            else:
                val = 0
            sample = int(val * 16384)
            w.writeframes(struct.pack('<h', sample))

def write_chime(filename, freqs, duration=1.5):
    sample_rate = 44100
    num_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        
        for i in range(num_samples):
            t = i / sample_rate
            val = 0
            
            # Mix the harmonics/notes with their respective onset delays
            for start_time, freq, decay in freqs:
                if t >= start_time:
                    t_note = t - start_time
                    val += math.sin(2 * math.pi * freq * t_note) * math.exp(-decay * t_note)
            
            val = max(-1.0, min(1.0, val))
            sample = int(val * 12000)  # Avoid clipping
            w.writeframes(struct.pack('<h', sample))

if __name__ == "__main__":
    print("Generating sound assets...")
    os.makedirs("assets", exist_ok=True)
    write_ticking("assets/ticking.wav")
    
    # Elegant double-tone chime for Pomo finish
    pomo_freqs = [
        (0.0, 523.25, 4.0),  # C5
        (0.15, 659.25, 4.0), # E5
        (0.3, 783.99, 3.0),  # G5
        (0.45, 1046.5, 2.0)  # C6
    ]
    write_chime("assets/finish_sound.wav", pomo_freqs, duration=2.0)
    
    # Calmer descending chime for Break finish
    break_freqs = [
        (0.0, 880.0, 4.0),   # A5
        (0.15, 698.46, 4.0), # F5
        (0.3, 587.33, 3.0),  # D5
        (0.45, 523.25, 2.0)  # C5
    ]
    write_chime("assets/break_finish_sound.wav", break_freqs, duration=2.0)
    print("Sound assets generated successfully!")
