import os, traceback
from voice_of_the_doctor import text_to_speech_with_elevenlabs

print("ELEVENLABS_API_KEY present?:", bool(os.getenv("ELEVENLABS_API_KEY")))
try:
    out = text_to_speech_with_elevenlabs("This is a short test from local environment", "final_test.mp3")
    print("Wrote:", out)
except Exception:
    traceback.print_exc()
