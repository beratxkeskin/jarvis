"""
JARVIS - Ses Biyometrisi (Voice Biometrics)
SpeechBrain ECAPA-TDNN tabanlı konuşmacı doğrulama sistemi.

Düzeltmeler:
- VAD eşiği 15 → 30 dB (alçak sesi de yakala)
- Eşik sabit değil, kalibrasyonlu (kendi sesine göre otomatik hesaplanır)
- Outlier rejection ile gürültülü embedding'ler temizlenir
- 10 cümle kayıt (3 yerine) = çok daha güçlü profil
- Kayıt + doğrulama ayrımı netleştirildi
"""

import os
import wave
import numpy as np
import torch
import torchaudio
import librosa
from pathlib import Path
from scipy.spatial.distance import cosine

# SpeechBrain lazy loader monkeypatch
try:
    import speechbrain.utils.importutils as sb_importutils
    _orig = sb_importutils.LazyModule.__getattr__
    sb_importutils.LazyModule.__getattr__ = lambda self, attr: (
        None if attr in {"__file__", "__path__", "__spec__"} else _orig(self, attr)
    )
except Exception:
    pass

from speechbrain.inference.classifiers import EncoderClassifier

# ── Dosya yolları ────────────────────────────────────────────────────────────
_BASE = Path(__file__).parent.parent / "config"
VOICEPRINT_FILE  = _BASE / "master_voiceprint.npy"
THRESHOLD_FILE   = _BASE / "voiceprint_threshold.npy"   # YENİ: kalibrasyonlu eşik
MODEL_DIR        = _BASE / "pretrained_models" / "spkrec-ecapa-voxceleb"

# ── VAD parametreleri ────────────────────────────────────────────────────────
VAD_TOP_DB          = 24     # DÜZELTİLDİ: 30'dan 24'e düşürüldü (gürültüyü almamak için)
MIN_VOICED_SEC      = 0.3    # Minimum aktif konuşma süresi
MIN_AUDIO_BYTES     = 16000 * 2 * 1  # En az 1 saniyelik ham ses (16kHz, 16-bit)

# ── Doğrulama parametreleri ─────────────────────────────────────────────────
DEFAULT_THRESHOLD   = 0.65   # Kalibrasyon yoksa kullanılacak güvenli varsayılan
CALIBRATION_MARGIN  = 0.15   # Eşik = kendi skorlarının min'i - bu marj


_classifier = None


def get_classifier():
    global _classifier
    if _classifier is None:
        try:
            import pathlib, shutil
            pathlib.Path.symlink_to = lambda self, target, target_is_directory=False: (
                shutil.copy(str(target), str(self))
                if Path(target).is_file()
                else shutil.copytree(str(target), str(self), dirs_exist_ok=True)
            )
            _classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(MODEL_DIR),
            )
            print("[VOICE BIOMETRICS] ECAPA-TDNN modeli yüklendi.")
        except Exception as e:
            print(f"[VOICE BIOMETRICS] Model yükleme hatası: {e}")
    return _classifier


# ── Yardımcı: debug WAV kaydet ───────────────────────────────────────────────
def save_debug_wav(audio_bytes: bytes, filename: str, sample_rate: int = 16000):
    try:
        path = _BASE / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        max_val = np.max(np.abs(audio_np))
        if max_val > 10.0:
            scaled = np.clip(audio_np * (30000.0 / max_val), -32768, 32767).astype(np.int16)
            data = scaled.tobytes()
        else:
            data = audio_bytes
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(data)
    except Exception as e:
        print(f"[VOICE BIOMETRICS] Debug WAV hatası: {e}")


# ── Embedding çıkarma ─────────────────────────────────────────────────────────
def extract_voice_embedding(
    audio_data: bytes, sample_rate: int = 16000
) -> tuple[np.ndarray, float]:
    """
    Ham PCM ses → 192-boyutlu normalize ECAPA x-vector.
    Döner: (embedding, voiced_duration_seconds)
    Başarısız olursa (sıfır vektör, 0.0) döner.
    """
    classifier = get_classifier()
    if classifier is None or len(audio_data) < MIN_AUDIO_BYTES:
        return np.zeros(192), 0.0

    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

    # Otomatik kazanç normalizasyonu
    max_val = np.max(np.abs(audio_np))
    if max_val > 0.001:
        audio_np = audio_np / max_val
    else:
        return np.zeros(192), 0.0  # Tamamen sessiz

    # VAD — DÜZELTİLDİ: top_db=30
    intervals = librosa.effects.split(audio_np, top_db=VAD_TOP_DB)
    if len(intervals) == 0:
        print(f"[VOICE BIOMETRICS] VAD: Aktif ses segmenti bulunamadı.")
        return np.zeros(192), 0.0

    voiced = np.concatenate([audio_np[s:e] for s, e in intervals])
    voiced_duration = len(voiced) / sample_rate

    if voiced_duration < MIN_VOICED_SEC:
        print(f"[VOICE BIOMETRICS] VAD: Aktif ses çok kısa ({voiced_duration:.2f}s < {MIN_VOICED_SEC}s)")
        return np.zeros(192), voiced_duration

    signal = torch.from_numpy(voiced).unsqueeze(0)
    if sample_rate != 16000:
        signal = torchaudio.transforms.Resample(sample_rate, 16000)(signal)

    with torch.no_grad():
        emb = classifier.encode_batch(signal).squeeze().cpu().numpy()

    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm

    return emb, voiced_duration


# ── Outlier rejection ─────────────────────────────────────────────────────────
def _reject_outliers(embeddings: list[np.ndarray]) -> list[np.ndarray]:
    """
    Diğer embedding'lerle ortalama cosine similarity'si düşük olanları atar.
    Yani gürültülü veya yanlış kaydedilmiş ses segmentleri otomatik temizlenir.
    """
    if len(embeddings) <= 3:
        return embeddings  # Az örnek varsa temizleme yapma

    n = len(embeddings)
    scores = []
    for i, e in enumerate(embeddings):
        others = [embeddings[j] for j in range(n) if j != i]
        avg_sim = np.mean([1.0 - cosine(e, o) for o in others])
        scores.append(avg_sim)

    mean_score = np.mean(scores)
    std_score  = np.std(scores)
    threshold  = mean_score - 1.5 * std_score  # 1.5 sigma dışındakiler outlier

    clean = [embeddings[i] for i, s in enumerate(scores) if s >= threshold]
    removed = n - len(clean)
    if removed > 0:
        print(f"[VOICE BIOMETRICS] Outlier rejection: {removed} gürültülü segment atıldı, {len(clean)} temiz segment kaldı.")

    return clean if clean else embeddings  # Hepsi atılırsa orijinale dön


# ── Kayıt (Enrollment) ────────────────────────────────────────────────────────
def enroll_voiceprint(audio_chunks: list[bytes], sample_rate: int = 16000) -> bool:
    """
    Ses chunk listesinden master voiceprint oluşturur.
    - Her chunk'tan ayrı embedding çıkarır
    - Outlier rejection uygular
    - Temiz embedding'lerin ortalamasını alır
    - Kalibrasyonlu eşiği hesaplar ve kaydeder
    """
    full_audio = b"".join(audio_chunks)
    save_debug_wav(full_audio, "debug_last_enrollment.wav", sample_rate)

    # Her chunk'tan embedding çıkar
    embeddings = []
    for i, chunk in enumerate(audio_chunks):
        emb, duration = extract_voice_embedding(chunk, sample_rate)
        if not np.all(emb == 0):
            embeddings.append(emb)
            print(f"[VOICE BIOMETRICS] Segment {i+1}: {duration:.2f}s aktif ses ✓")
        else:
            print(f"[VOICE BIOMETRICS] Segment {i+1}: Kullanılabilir ses yok, atlandı.")

    if len(embeddings) < 2:
        print(f"[VOICE BIOMETRICS] Yeterli geçerli segment yok ({len(embeddings)}/2). Kayıt başarısız.")
        return False

    print(f"[VOICE BIOMETRICS] {len(embeddings)} geçerli segment, outlier temizleme başlıyor...")

    # Outlier rejection
    clean_embeddings = _reject_outliers(embeddings)

    # Master voiceprint = temiz embedding'lerin normalize ortalaması
    master = np.mean(clean_embeddings, axis=0)
    norm = np.linalg.norm(master)
    if norm > 0:
        master = master / norm

    # ── Kalibrasyonlu eşik hesapla ──────────────────────────────────────────
    # Kendi embedding'lerinin birbiriyle cosine similarity'sini hesapla.
    # Eşik = bu skorların minimumu - CALIBRATION_MARGIN
    # Bu sayede eşik senin sesinin en zayıf halini bile kapsayacak şekilde ayarlanır.
    self_similarities = []
    for emb in clean_embeddings:
        sim = 1.0 - cosine(master, emb)
        self_similarities.append(sim)

    min_self_sim = float(np.min(self_similarities))
    mean_self_sim = float(np.mean(self_similarities))
    calibrated_threshold = max(0.45, min_self_sim - CALIBRATION_MARGIN)

    print(f"[VOICE BIOMETRICS] Kalibrasyon tamamlandı:")
    print(f"  Kendi min skoru  : {min_self_sim:.4f}")
    print(f"  Kendi ort. skoru : {mean_self_sim:.4f}")
    print(f"  Hesaplanan eşik  : {calibrated_threshold:.4f}")

    # Kaydet
    _BASE.mkdir(parents=True, exist_ok=True)
    np.save(str(VOICEPRINT_FILE), master)
    np.save(str(THRESHOLD_FILE), np.array(calibrated_threshold))

    print(f"[VOICE BIOMETRICS] Master voiceprint ve kalibrasyonlu eşik kaydedildi.")
    return True


# ── Doğrulama (Verification) ─────────────────────────────────────────────────
def verify_speaker(
    audio_data: bytes,
    sample_rate: int = 16000,
    threshold: float | None = None,   # None ise kalibrasyon dosyasından okur
) -> tuple[bool, float]:
    """
    Gelen ses verisini kayıtlı master voiceprint ile karşılaştırır.
    Döner: (is_authorized: bool, similarity_score: float)
    """
    save_debug_wav(audio_data, "debug_last_verification.wav", sample_rate)

    if not VOICEPRINT_FILE.exists():
        print("[VOICE BIOMETRICS] Master kayıt yok — lütfen önce enroll_voiceprint çağır.")
        return False, 0.0

    # Eşiği belirle: parametre > kalibrasyon dosyası > varsayılan
    if threshold is None:
        if THRESHOLD_FILE.exists():
            threshold = float(np.load(str(THRESHOLD_FILE)))
            print(f"[VOICE BIOMETRICS] Kalibrasyonlu eşik kullanılıyor: {threshold:.4f}")
        else:
            threshold = DEFAULT_THRESHOLD
            print(f"[VOICE BIOMETRICS] Kalibrasyon dosyası yok, varsayılan eşik: {threshold:.4f}")

    master = np.load(str(VOICEPRINT_FILE))
    incoming_emb, voiced_duration = extract_voice_embedding(audio_data, sample_rate)

    total_sec = len(audio_data) / (sample_rate * 2)
    print(f"[VOICE BIOMETRICS] Toplam ses: {total_sec:.2f}s | Aktif konuşma: {voiced_duration:.2f}s")

    # Boyut uyumsuzluğu = bozuk kayıt, sil ve False dön
    if len(master) != len(incoming_emb):
        print("[VOICE BIOMETRICS] Vektör boyutu uyumsuz — kayıt yenilenmeli.")
        try:
            VOICEPRINT_FILE.unlink()
            if THRESHOLD_FILE.exists():
                THRESHOLD_FILE.unlink()
        except Exception:
            pass
        return False, 0.0

    if np.all(incoming_emb == 0):
        print("[VOICE BIOMETRICS] Gelen sesten x-vector çıkarılamadı.")
        return False, 0.0

    similarity = 1.0 - cosine(master, incoming_emb)
    is_authorized = bool(similarity >= threshold)

    status = "✓ YETKİLİ" if is_authorized else "✗ REDDEDİLDİ"
    print(f"[VOICE BIOMETRICS] {status} | Skor: {similarity:.4f} | Eşik: {threshold:.4f}")

    return is_authorized, similarity


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────
def has_voiceprint() -> bool:
    return VOICEPRINT_FILE.exists()


def get_calibrated_threshold() -> float:
    """Kayıtlı kalibrasyonlu eşiği döner. Yoksa varsayılanı döner."""
    if THRESHOLD_FILE.exists():
        return float(np.load(str(THRESHOLD_FILE)))
    return DEFAULT_THRESHOLD


def delete_voiceprint():
    """Tüm biyometrik veriyi siler. Yeniden kayıt gerekir."""
    for f in [VOICEPRINT_FILE, THRESHOLD_FILE]:
        try:
            if f.exists():
                f.unlink()
        except Exception:
            pass
    print("[VOICE BIOMETRICS] Tüm biyometrik veri silindi.")
