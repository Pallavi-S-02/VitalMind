import socketio
import time
import base64

sio = socketio.Client(logger=True, engineio_logger=True)

@sio.on('connect', namespace='/voice')
def on_connect():
    print("Connected to /voice namespace")
    sio.emit('join_voice_session', {'session_mode': 'patient', 'patient_id': 'e34145b4-93f2-4fb2-b767-65568c89fe59'}, namespace='/voice')

@sio.on('voice_session_joined', namespace='/voice')
def on_joined(data):
    print("Session Joined:", data)

@sio.on('live_session_ready', namespace='/voice')
def on_ready(data):
    print("Gemini Live Ready:", data)
    # create some fake PCM 16kHz audio
    empty_audio = b'\x00' * 8000 # 0.25s of silence
    sio.emit('audio_chunk', {'audio_b64': base64.b64encode(empty_audio).decode('ascii')}, namespace='/voice')

@sio.on('live_audio_chunk', namespace='/voice')
def on_audio(data):
    print("Received audio chunk from AI Doctor! length:", len(data['audio_b64']))
    time.sleep(1)
    sio.disconnect()

@sio.on('voice_error', namespace='/voice')
def on_error(data):
    print("Error:", data)

sio.connect('http://localhost:5000', namespaces=['/voice'])
sio.wait()
