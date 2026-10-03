"""
Mascot clips for the app, from build/mascot_anim/<clip>/f_*.png (blender/mascot_anim.py):
  assets/mascot/nova-<clip>.webm   VP9 with alpha, 360x450, 24 fps   (Chrome, Edge, Firefox, Android)
  assets/mascot/nova-<clip>.webp   animated WebP, 300x375, 12 fps    (Safari fallback; first frame = still)

    python tools/make-mascot-webp.py [clip ...]
"""
import glob
import os
import shutil
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS = ["idle", "wave", "run", "talk", "flex", "thumbs", "cheer", "alert"]


def ffmpeg():
    c = [shutil.which("ffmpeg")] + glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet",
                                                           "Packages", "Gyan.FFmpeg*", "*", "bin", "ffmpeg.exe"))
    return next(p for p in c if p and os.path.exists(p))


for clip in sys.argv[1:] or CLIPS:
    src = os.path.join(ROOT, "build", "mascot_anim", clip)
    fs = sorted(glob.glob(os.path.join(src, "f_*.png")))
    if not fs:
        print("skip", clip)
        continue
    base = os.path.join(ROOT, "assets", "mascot", "nova-" + clip)
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-framerate", "24", "-i", os.path.join(src, "f_%04d.png"),
                    "-vf", "scale=360:450:flags=lanczos", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0",
                    "-crf", "36", "-row-mt", "1", "-an", base + ".webm"], check=True)
    frames = [Image.open(f).convert("RGBA").resize((300, 375), Image.LANCZOS) for f in fs[::2]]
    frames[0].save(base + ".webp", save_all=True, append_images=frames[1:], duration=round(2000 / 24), loop=0,
                   quality=60, method=4)
    print("%-7s %3d frames  webm %4d KB  webp %4d KB" % (clip, len(fs), os.path.getsize(base + ".webm") // 1024,
                                                         os.path.getsize(base + ".webp") // 1024))
