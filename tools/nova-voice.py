"""
Nova's narration for the mascot explainer (tools/make-nova-explainer.py).

    python tools/nova-voice.py        # -> build/nova_vo/<scene>.mp3 + durations.json

Uses edge-tts (Microsoft neural voices, online): the script below is the
only thing sent. Edit SCRIPT here; the explainer reads the same list.
"""
import asyncio
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "nova_vo")
VOICE, RATE, PITCH = "id-ID-ArdiNeural", "+4%", "+14Hz"

# scene key, mascot clip, narration
SCRIPT = [
    ("intro", "wave", "Hai! Aku Nova, maskot Nova-Band. Yuk, kenalan sama band pintar yang dipakai di lengan atas!"),
    ("problem", "talk", "Banyak pelari berlatih terlalu keras tanpa tahu kondisi tubuhnya. Akibatnya kelelahan, cedera, "
                        "bahkan risiko gangguan jantung."),
    ("device", "flex", "Nova-Band dipasang di lengan atas. Di sini ayunan tangan paling kecil, jadi sinyal detak jantung "
                       "lebih stabil dan datanya lebih akurat."),
    ("live", "run", "Saat kamu lari, Nova-Band membaca detak jantung, kadensi, pace, dan jarak secara real-time, "
                    "langsung di layar band dan di aplikasi."),
    ("alert", "alert", "Kalau detak jantung melewati batas aman, band langsung memberi peringatan. Pelatih dan grup larimu "
                       "juga ikut menerima notifikasi."),
    ("ready", "thumbs", "Setiap pagi, AI menghitung Readiness Score dari variabilitas detak jantung, detak istirahat, "
                        "dan beban latihan. Jadi kamu tahu kapan harus gas, dan kapan harus istirahat."),
    ("app", "talk", "Semua datamu tersimpan di aplikasi web Nova-Band. Bisa dipasang di HP, dan tersambung lewat Bluetooth."),
    ("outro", "cheer", "Nova-Band. Monitor, analyze, improve. Lari lebih cepat, lebih sehat, lebih kuat. Bersama!"),
]


async def speak(key, text):
    import edge_tts
    path = os.path.join(OUT, key + ".mp3")
    await edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH).save(path)
    return path


def ffprobe():
    import glob
    import shutil
    c = [shutil.which("ffprobe")] + glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet",
                                                            "Packages", "Gyan.FFmpeg*", "*", "bin", "ffprobe.exe"))
    return next(p for p in c if p and os.path.exists(p))


def duration(path):
    r = subprocess.run([ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    os.makedirs(OUT, exist_ok=True)
    durs = {}
    for key, _, text in SCRIPT:
        p = os.path.join(OUT, key + ".mp3")
        if "--force" in sys.argv or not os.path.exists(p):
            asyncio.run(speak(key, text))
        durs[key] = duration(p)
        print("%-8s %5.2fs" % (key, durs[key]))
    json.dump(durs, open(os.path.join(OUT, "durations.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
