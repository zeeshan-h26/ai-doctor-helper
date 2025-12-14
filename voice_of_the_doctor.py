# if you dont use pipenv uncomment the following:
# from dotenv import load_dotenv
# load_dotenv()

# Step1a: Setup Text to Speechâ€“TTSâ€“model with gTTS
import os
import platform
import subprocess
import traceback
import types

# Optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from gtts import gTTS

def text_to_speech_with_gtts(input_text, output_filepath):
    language = "en"
    audioobj = gTTS(text=input_text, lang=language, slow=False)
    audioobj.save(output_filepath)


# quick gTTS generation (kept as in your original)
input_text = "Hi this is Ai with Hassan!"
text_to_speech_with_gtts(input_text=input_text, output_filepath="gtts_testing.mp3")


# Step1b: Setup Text to Speechâ€“TTSâ€“model with ElevenLabs (modern usage)
# We'll prefer environment variable ELEVENLABS_API_KEY (also accept ELEVEN_API_KEY)
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")

def _autoplay(output_filepath: str):
    """Play the saved audio file (best-effort); used after successful generation.

    - On macOS: uses afplay (sync)
    - On Windows:
        - uses Media.SoundPlayer.PlaySync() only for .wav files
        - uses Start (default associated app) for other extensions (mp3)
    - On Linux: tries aplay (may not support mp3; user can install mpg123/ffplay)
    """
    os_name = platform.system()
    try:
        _, ext = os.path.splitext(output_filepath or "")
        ext = (ext or "").lower()

        if os_name == "Darwin":
            subprocess.run(['afplay', output_filepath], check=False)
            return

        if os_name == "Windows":
            # Use SoundPlayer only for WAV (synchronous). For mp3, open default app.
            if ext == ".wav":
                # synchronous playback for .wav files
                subprocess.run(['powershell', '-c', f'(New-Object Media.SoundPlayer \"{output_filepath}\").PlaySync();'], check=False)
            else:
                # For mp3 (and other non-wav), open the default associated player (non-blocking).
                # Use cmd start via subprocess so it works from both PowerShell and cmd.
                # The empty title "" after start is required when the filename might be quoted.
                subprocess.run(['cmd', '/c', 'start', '', output_filepath], check=False, shell=False)
            return

        if os_name == "Linux":
            subprocess.run(['aplay', output_filepath], check=False)
            return

    except Exception as e:
        # Don't fail the overall flow just because autoplay failed
        print(f"An error occurred while trying to play the audio: {e}")


def _write_audio_result(res, output_filepath):
    """
    Write audio from a variety of SDK response shapes:
      - bytes / bytearray
      - object with .content
      - object with .save_to_file
      - generator/iterable yielding bytes (stream)
      - iterable of chunks (non-bytes) coerced to bytes
    Returns True on success, raises on failure.
    """
    # Direct bytes
    if isinstance(res, (bytes, bytearray)):
        with open(output_filepath, "wb") as f:
            f.write(res)
        _autoplay(output_filepath)
        return True

    # Object with .content
    if hasattr(res, "content"):
        with open(output_filepath, "wb") as f:
            f.write(res.content)
        _autoplay(output_filepath)
        return True

    # Object with save_to_file
    if hasattr(res, "save_to_file"):
        try:
            res.save_to_file(output_filepath)
            _autoplay(output_filepath)
            return True
        except Exception:
            # continue to other strategies if save_to_file fails
            pass

    # Generator/iterable streaming chunks
    # Detect generator specifically
    if isinstance(res, types.GeneratorType) or (hasattr(res, "__iter__") and not isinstance(res, (str, bytes, bytearray))):
        try:
            chunks = []
            # If object has an iterator producing chunks
            for chunk in res:
                if chunk is None:
                    continue
                if isinstance(chunk, (bytes, bytearray)):
                    chunks.append(chunk)
                elif hasattr(chunk, "content"):
                    chunks.append(chunk.content)
                else:
                    # try to coerce to bytes
                    try:
                        chunks.append(bytes(chunk))
                    except Exception:
                        # fallback to string encoding
                        chunks.append(str(chunk).encode("utf-8"))
            data = b"".join(chunks)
            with open(output_filepath, "wb") as f:
                f.write(data)
            _autoplay(output_filepath)
            return True
        except Exception as e_stream:
            # re-raise with context
            raise RuntimeError("Failed while consuming streamed TTS response: " + repr(e_stream)) from e_stream

    # Last resort: try bytes coercion
    try:
        b = bytes(res)
        with open(output_filepath, "wb") as f:
            f.write(b)
        _autoplay(output_filepath)
        return True
    except Exception:
        raise RuntimeError("Unknown response type from ElevenLabs TTS call: " + repr(type(res)))


# Legacy wrapper kept for reference (not recommended)
def text_to_speech_with_elevenlabs(input_text, output_filepath):
    import elevenlabs
    from elevenlabs.client import ElevenLabs as LegacyElevenLabs
    ELEVENLABS_API_KEY_LOCAL = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")
    client = LegacyElevenLabs(api_key=ELEVENLABS_API_KEY_LOCAL)
    audio = client.generate(
        text=input_text,
        voice="Aria",
        output_format="mp3_22050_32",
        model="eleven_turbo_v2"
    )
    try:
        elevenlabs.save(audio, output_filepath)
    except Exception:
        if isinstance(audio, (bytes, bytearray)):
            with open(output_filepath, "wb") as f:
                f.write(audio)
        elif hasattr(audio, "content"):
            with open(output_filepath, "wb") as f:
                f.write(audio.content)
        else:
            raise


# Modern, robust ElevenLabs TTS function
def text_to_speech_with_elevenlabs(input_text, output_filepath="elevenlabs_output.mp3"):
    """
    Modern ElevenLabs TTS helper using elevenlabs.client.ElevenLabs.
    Voice selection order:
      1) ELEVEN_VOICE_ID env var
      2) client.voices.get_all() (if allowed)
      3) guaranteed default voice '21m00Tcm4TlvDq8ikWAM' (Rachel)
    """
    api_key = ELEVENLABS_API_KEY
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set in environment (or ELEVEN_API_KEY).")

    try:
        from elevenlabs.client import ElevenLabs  # type: ignore
    except Exception as e:
        print("DEBUG: failed to import ElevenLabs from elevenlabs.client:", repr(e))
        raise

    client = ElevenLabs(api_key=api_key)
    print("DEBUG: ElevenLabs client created:", type(client))

    # ------------------------------
    # Voice selection (robust)
    # ------------------------------
    # 1) env var
    voice_id = os.environ.get("ELEVEN_VOICE_ID") or os.environ.get("ELEVEN_VOICEID")
    if voice_id:
        print("DEBUG: using voice_id from env ELEVEN_VOICE_ID:", voice_id)
    else:
        # 2) try list voices (may raise ApiError / be blocked)
        try:
            voices_resp = client.voices.get_all()
            voices_list = getattr(voices_resp, "voices", None) or voices_resp
            if voices_list and len(voices_list) > 0:
                first = voices_list[0]
                voice_id = getattr(first, "voice_id", None) or getattr(first, "id", None) or getattr(first, "voiceId", None)
                print("DEBUG: Auto-discovered voice_id:", voice_id, "name:", getattr(first, "name", None) or getattr(first, "voice_name", None))
        except Exception as e:
            print("DEBUG: Voice listing failed:", repr(e))

    # 3) final fallback: guaranteed default voice (Rachel)
    if not voice_id:
        voice_id = "21m00Tcm4TlvDq8ikWAM"
        print("DEBUG: Using DEFAULT fallback voice_id:", voice_id)

    # ------------------------------
    # Call TTS convert (voice_id guaranteed)
    # ------------------------------
    try:
        if hasattr(client, "text_to_speech") and hasattr(client.text_to_speech, "convert"):
            print("DEBUG: calling client.text_to_speech.convert() with voice_id:", voice_id)
            kwargs = {
                "text": input_text,
                "voice_id": voice_id,
                "model_id": "eleven_multilingual_v2",
                "output_format": "mp3_44100_128",
            }
            res = client.text_to_speech.convert(**kwargs)

            # Use helper to handle all response shapes (bytes, object, generator, etc.)
            _write_audio_result(res, output_filepath)
            return output_filepath

        # fallback probing (if convert isn't present)
        print("DEBUG: client.text_to_speech.convert not found â€” falling back to probing methods")
        if hasattr(client, "text_to_speech"):
            tts_obj = getattr(client, "text_to_speech")
            if callable(tts_obj):
                res = _call_with_fallback(tts_obj, input_text)
            else:
                res = _try_methods_on_obj(tts_obj, input_text)
        else:
            found = False
            for nm in ("generate", "synthesize", "create", "stream", "speak"):
                if hasattr(client, nm):
                    method = getattr(client, nm)
                    if callable(method):
                        try:
                            res = _call_with_fallback(method, input_text)
                            found = True
                            break
                        except Exception as e_method:
                            print(f"DEBUG: client.{nm} failed: {repr(e_method)}")
            if not found:
                raise RuntimeError("No TTS entrypoint found on client. Available names: " + ", ".join([n for n in dir(client) if not n.startswith('_')]))

        # save fallback result shapes using the same helper
        _write_audio_result(res, output_filepath)
        return output_filepath

    except Exception as e:
        print("DEBUG: TTS call failed:", repr(e))
        traceback.print_exc()
        raise RuntimeError("All attempts to call ElevenLabs TTS failed. See debug above.") from e


# helper functions used by probing fallback - kept as simple fallbacks
def _call_with_fallback(fn, text):
    last_exc = None
    # try kwargs signature
    try:
        return fn(text=text, voice="Aria", model="eleven_turbo_v2", output_format="mp3_22050_32")
    except Exception as e:
        last_exc = e
    # try positional signature
    try:
        return fn(text)
    except Exception as e:
        last_exc = e
    # try calling without voice/model if earlier attempts failed
    try:
        return fn(text=text)
    except Exception as e:
        last_exc = e

    # nothing worked
    raise last_exc


def _try_methods_on_obj(obj, text, method_names=("convert", "synthesize", "create", "stream", "speak", "generate")):
    last_exc = None
    for name in method_names:
        if hasattr(obj, name):
            method = getattr(obj, name)
            if callable(method):
                try:
                    # prefer voice_id when available
                    try:
                        return method(text=text, voice="Aria", model="eleven_turbo_v2", output_format="mp3_22050_32")
                    except TypeError:
                        return method(text)
                except Exception as e_method:
                    last_exc = e_method
                    print(f"DEBUG: method {name} on object failed: {repr(e_method)}")
    raise RuntimeError("No suitable method on object produced audio. Checked methods: " + ", ".join(method_names)) from last_exc


# Step2: Use Model for Text output to Voice (example usage)
if __name__ == "__main__":
    # example gTTS usage (already generated earlier; comment if you don't want it repeated)
    # text_to_speech_with_gtts("Hello from gTTS", "gtts_test.mp3")

    # ElevenLabs modern test
    try:
        out = text_to_speech_with_elevenlabs("This is a short test from local environment", "final_test.mp3")
        print("Wrote:", out)
    except Exception as e:
        print("ElevenLabs TTS failed:", e)
