"""
Nova's English narration for the portrait reel (tools/make-portrait-reel.py).

    python tools/portrait-vo.py      # -> build/portrait_vo/<key>.mp3 + words.json (word timings)

edge-tts (Microsoft neural voices, online): only the lines below are sent.
Each line: key, segment (1-4), mascot clip, spoken text, on-screen caption.
Numbers in the captions come from the website (MAPE 2.5-3.5 % vs reference,
SUS 84.5 from 60 users) and the support letters (Dinkes Surakarta, Klinik
Haunaa) — keep them in step with those sources.
"""
import asyncio
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "portrait_vo")
VOICE, RATE, PITCH = "en-US-GuyNeural", "+6%", "+12Hz"

LINES = [
    # 0 · urgency (sources on screen: WHO CVD fact sheet; GBD via PMC10723707; Kim et al. NEJM 2012; Morgan et al. 1987)
    ("u1", 0, "alert", "Running is booming. But many runners push too hard, chasing the crowd, the medal and the photo, without knowing their limits.",
     "Running is booming. But many push too hard — chasing the crowd, the medal, the photo — without knowing their limits."),
    ("u2", 0, "talk", "Heart and blood-vessel disease is the world's number one killer. Nineteen point eight million deaths, in a single year.",
     "Cardiovascular disease is the world's No. 1 killer: 19.8 million deaths in 2022."),
    ("u3", 0, "talk", "In Indonesia, these deaths more than doubled in thirty years.",
     "In Indonesia, cardiovascular deaths more than doubled in 30 years."),
    ("u4", 0, "alert", "And in long-distance races, a hidden heart problem can become a sudden cardiac arrest. Rare, but devastating, and often preventable.",
     "In long-distance races, a hidden heart problem can turn into sudden cardiac arrest. Rare, devastating — often preventable."),
    ("u5", 0, "flex", "That's why we built Nova-Band.",
     "That's why we built Nova-Band."),
    ("s1a", 1, "wave", "Hi there! I'm Nova, the cheerful cheetah behind Nova-Band!",
     "Hi there! I'm Nova, the cheerful cheetah behind Nova-Band!"),
    ("s1b", 1, "talk", "Nova-Band is a smart band you wear on your upper arm, where your arm swings the least, so your heart-rate signal stays clean.",
     "Nova-Band is a smart band for your upper arm, where your arm swings the least, so the heart-rate signal stays clean."),
    ("s1c", 1, "talk", "Morning runs, treadmill sessions, strength training. It tracks your heart rate and every move, in real time.",
     "Morning runs, treadmill, strength training: it tracks your heart rate and every move in real time."),
    ("s1d", 1, "alert", "And if your heart rate crosses the safe limit, your coach is alerted right away!",
     "Heart rate over the safe limit? Your coach is alerted right away!"),
    ("s2a", 2, "talk", "We built Nova-Band together with real runners.",
     "We built Nova-Band together with real runners."),
    ("s2b", 2, "talk", "We tested it with the Surakarta running community, and listened to experts from Sebelas Maret University, and doctors at Moewardi Hospital.",
     "Field tests with the Surakarta running community, plus feedback from Sebelas Maret University experts and Moewardi Hospital doctors."),
    ("s2c", 2, "cheer", "The Surakarta Health Office and Haunaa Clinic even sent us letters of support. Thank you, partners!",
     "Letters of support from the Surakarta Health Office and Haunaa Clinic. Thank you, partners!"),
    ("s3a", 3, "wave", "Now, let's open the Nova-Band app!",
     "Now, let's open the Nova-Band app!"),
    ("s3b", 3, "talk", "Your home screen shows your live heart rate, your heart-rate zone and your cadence, with tips from me, your A.I. coach.",
     "Live heart rate, heart-rate zone and cadence, with tips from me, your AI coach."),
    ("s3c", 3, "thumbs", "Slow down when it warns you! Then check your Readiness Score, and keep your whole running group safe.",
     "Slow down when it warns you, check your Readiness Score, and keep your whole running group safe."),
    ("s4a", 4, "talk", "Nova-Band is made by six student researchers from S.M.A. Negeri 1 Surakarta.",
     "Made by six student researchers from SMA Negeri 1 Surakarta."),
    ("s4b", 4, "flex", "In tests, it stayed within two and a half to three and a half percent of a reference device, and sixty users rated it eighty-four point five for ease of use.",
     "2.5–3.5% error vs. a reference device · usability score 84.5 (Grade A) from 60 users."),
    ("s4c", 4, "cheer", "Nova-Band. Monitor. Analyze. Improve. Let's run faster, healthier and stronger, together!",
     "Nova-Band. Monitor. Analyze. Improve. Faster, healthier, stronger — together!"),
]


async def speak(key, text):
    import edge_tts
    words = []
    com = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, boundary="WordBoundary")
    with open(os.path.join(OUT, key + ".mp3"), "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append([round(ch["offset"] / 1e7, 3), round(ch["duration"] / 1e7, 3), ch["text"]])
    return words


def duration(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("reel", os.path.join(ROOT, "tools", "make-showreel2.py"))
    R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
    probe = os.path.join(os.path.dirname(R.find_ffmpeg()), "ffprobe.exe" if os.name == "nt" else "ffprobe")
    return float(subprocess.check_output([probe, "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).decode())


async def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {}
    for key, seg, clip, text, cap in LINES:
        w = await speak(key, text)
        meta[key] = {"seg": seg, "clip": clip, "caption": cap, "words": w, "dur": duration(os.path.join(OUT, key + ".mp3"))}
        print("%-4s %5.2fs  %s" % (key, meta[key]["dur"], text[:60]))
    json.dump(meta, open(os.path.join(OUT, "words.json"), "w"), indent=1)
    for s in (0, 1, 2, 3, 4):
        print("segment", s, "speech %.1f s" % sum(m["dur"] for m in meta.values() if m["seg"] == s))


if __name__ == "__main__":
    asyncio.run(main())
