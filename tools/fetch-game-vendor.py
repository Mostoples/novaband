"""
Download the libraries Nova Run (game.html) uses, so the game runs offline at a
booth: Three.js and MediaPipe Pose Landmarker (wasm + lite model), ~25 MB.
They live in assets/game/vendor/ (git-ignored, but deployed with the site).
Without them the game falls back to the CDNs.

    python tools/fetch-game-vendor.py
"""
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "assets", "game", "vendor")
MP = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/"
FILES = {
    "three.module.min.js": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.min.js",
    "mediapipe/vision_bundle.mjs": MP + "vision_bundle.mjs",
    "mediapipe/pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
}
for f in ("vision_wasm_internal.js", "vision_wasm_internal.wasm", "vision_wasm_nosimd_internal.js", "vision_wasm_nosimd_internal.wasm"):
    FILES["mediapipe/" + f] = MP + "wasm/" + f

for rel, url in FILES.items():
    dst = os.path.join(V, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        print("ok  ", rel)
        continue
    urllib.request.urlretrieve(url, dst)
    print("got ", rel, os.path.getsize(dst) // 1024, "KB")
