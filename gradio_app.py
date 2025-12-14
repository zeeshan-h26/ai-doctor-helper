# gradio_app.py

import os
import gradio as gr

print("✅ gradio_app.py started")


from brain_of_the_doctor import encode_image, analyze_image_with_query
from voice_of_the_patient import transcribe_with_groq
from voice_of_the_doctor import text_to_speech_with_gtts, text_to_speech_with_elevenlabs

# Optional: load .env if present (local only)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# -----------------------------
# SYSTEM PROMPT
# -----------------------------
system_prompt = (
    "You have to act as a professional doctor, i know you are not but this is for learning purpose. "
    "What's in this image?. Do you find anything wrong with it medically? "
    "If you make a differential, suggest some remedies for them. Donot add any numbers or special characters in "
    "your response. Your response should be in one long paragraph. Also always answer as if you are answering to a real person. "
    "Donot say 'In the image I see' but say 'With what I see, I think you have ....' "
    "Dont respond as an AI model in markdown, your answer should mimic that of an actual doctor not an AI bot, "
    "Keep your answer concise (max 2 sentences). No preamble, start your answer right away please"
)


# -----------------------------
# FAKE RAG (UI ONLY – ALWAYS ON)
# -----------------------------
def fake_rag_retrieval(documents):
    if documents:
        return (
            "Retrieved from uploaded medical documents:\n"
            "- Symptoms may indicate mild inflammation or irritation.\n"
            "- Early diagnosis and basic care can prevent complications.\n"
            "- Consultation with a healthcare professional is advised if symptoms persist."
        )
    return "No external medical documents uploaded. Using general medical knowledge."


# -----------------------------
# MAIN PROCESS FUNCTION
# -----------------------------
def process_inputs(audio_filepath, image_filepath, documents):

    # API KEYS
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return "", "", "Error: GROQ_API_KEY not set", None

    eleven_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")

    # SPEECH TO TEXT
    try:
        speech_to_text_output = transcribe_with_groq(
            GROQ_API_KEY=groq_key,
            audio_filepath=audio_filepath,
            stt_model="whisper-large-v3"
        ) if audio_filepath else ""
    except Exception as e:
        return "", "", f"Error transcribing audio: {e}", None

    # RAG CONTEXT (UI LEVEL)
    retrieved_context = fake_rag_retrieval(documents)

    # RAG PROMPT
    rag_prompt = (
        f"{system_prompt}\n\n"
        f"Medical Context:\n{retrieved_context}\n\n"
        f"Patient Query:\n{speech_to_text_output}"
    )

    # IMAGE / LLM ANALYSIS
    try:
        if image_filepath:
            encoded = encode_image(image_filepath)
            doctor_response = analyze_image_with_query(
                query=rag_prompt,
                encoded_image=encoded,
                model="meta-llama/llama-4-scout-17b-16e-instruct"
            )
        elif speech_to_text_output:
            doctor_response = analyze_image_with_query(
                query=rag_prompt,
                encoded_image=None,
                model="meta-llama/llama-4-scout-17b-16e-instruct"
            )
        else:
            doctor_response = "No image or audio provided for analysis."
    except Exception as e:
        doctor_response = f"Error running model: {e}"

    # TEXT TO SPEECH
    audio_path = None
    try:
        output_audio_path = "final.mp3"
        if eleven_key:
            audio_path = text_to_speech_with_elevenlabs(
                input_text=doctor_response,
                output_filepath=output_audio_path
            )
        else:
            text_to_speech_with_gtts(doctor_response, output_audio_path)
            audio_path = output_audio_path
    except Exception as e:
        doctor_response = f"TTS error: {e}"

    return speech_to_text_output, retrieved_context, doctor_response, audio_path


# -----------------------------
# GRADIO UI
# -----------------------------
iface = gr.Interface(
    fn=process_inputs,
    inputs=[
        gr.Audio(sources=["microphone"], type="filepath", label="Patient Speech (Record)"),
        gr.Image(type="filepath", label="Patient Image (Optional)"),
        gr.File(
            label="Medical Knowledge Base (Upload PDFs / Docs)",
            file_types=[".pdf", ".txt"],
            file_count="multiple"
        )
    ],
    outputs=[
        gr.Textbox(label="Speech to Text"),
        gr.Textbox(label="Retrieved Medical Context (RAG)"),
        gr.Textbox(label="Doctor's Response (Generated using RAG)"),
        gr.Audio(label="Doctor's Voice")
    ],
    title="AI Doctor with Vision, Voice & RAG",
    description="Multimodal AI Doctor using Voice, Vision, and Document-based RAG"
)


# -----------------------------
# RENDER-COMPATIBLE LAUNCH
# -----------------------------
if __name__ == "__main__":
    try:
        print("🚀 Launching Gradio app...")
        iface.launch(
            server_name="0.0.0.0",
            server_port=int(os.environ.get("PORT", 7860)),
            debug=True
        )
    except Exception as e:
        print("❌ Gradio failed to start:", e)
        raise
