import os
import threading
import time
import traceback
import json

class WakeWordListener:
    def __init__(self, keyword="jarvis", on_wake=None):
        self.keyword = keyword.lower()
        self.on_wake = on_wake
        self.pa = None
        self.audio_stream = None
        self._stop_event = threading.Event()
        self._thread = None
        self.is_listening = False
        
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "vosk_model")

    def is_configured(self):
        return os.path.exists(self.model_path)

    def start(self):
        if not self.is_configured():
            print(f"[WakeWord] Model bulunamadı: {self.model_path}. Wake word devre dışı.")
            return

        if self._thread and self._thread.is_alive():
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def pause_listening(self):
        self.is_listening = False

    def resume_listening(self):
        self.is_listening = True

    def _run(self):
        try:
            import pyaudio
            # suppress vosk logs
            import vosk
            vosk.SetLogLevel(-1)
            from vosk import Model, KaldiRecognizer
            
            print("[WakeWord] Vosk modeli yükleniyor... İlk açılışta biraz zaman alabilir.")
            model = Model(self.model_path)
            
            recognizer = KaldiRecognizer(model, 16000)

            self.pa = pyaudio.PyAudio()

            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            CHUNK = 4000

            self.audio_stream = self.pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

            print(f"[WakeWord] '{self.keyword}' kelimesi bekleniyor... (Tamamen çevrimdışı, API anahtarı gerekmez)")
            self.is_listening = True

            while not self._stop_event.is_set():
                if not self.is_listening:
                    time.sleep(0.1)
                    continue
                    
                data = self.audio_stream.read(CHUNK, exception_on_overflow=False)
                
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").lower()
                    if text:
                        print(f"[WakeWord Debug] Duyulan tam metin: '{text}'")
                    
                    aliases = {"jarvis", "james", "jammies", "janice", "journalist", "jealous", "jamie", "jamies", "geez", "travis", "charvis", "service", "harvest", "charlotte", "chavez", "jervis", "garbage", "drivers", "darvis", "jerry"}
                    if any(alias in text for alias in aliases):
                        print(f"[WakeWord] Uyanma kelimesi algılandı! ({text})")
                        if self.on_wake:
                            self.on_wake()
                            time.sleep(2)
                else:
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = partial.get("partial", "").lower()
                    aliases = {"jarvis", "james", "jammies", "janice", "journalist", "jealous", "jamie", "jamies", "geez", "travis", "charvis", "service", "harvest", "charlotte", "chavez", "jervis", "garbage", "drivers", "darvis", "jerry"}
                    if any(alias in partial_text for alias in aliases):
                        print(f"\n[WakeWord] Uyanma kelimesi algılandı! ({partial_text})")
                        if self.on_wake:
                            self.on_wake()
                            recognizer.Reset()
                            time.sleep(2)

        except Exception as e:
            print(f"[WakeWord] Hata: {e}")
            traceback.print_exc()
        finally:
            if self.audio_stream is not None:
                self.audio_stream.close()
            if self.pa is not None:
                self.pa.terminate()
