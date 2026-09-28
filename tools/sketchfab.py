"""
Sketchfab helper — search and download downloadable (CC-licensed) models.

    python tools/sketchfab.py search "gym interior" [--count 12]
    python tools/sketchfab.py get <uid> <name>      # -> build/sketchfab/<name>/ (glTF) + credits.json

The token comes from SKETCHFAB_TOKEN (env) or build/sketchfab/.token (never
committed / deployed). Every download appends its attribution to
build/sketchfab/credits.json — CC-BY models must be credited.
"""
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "sketchfab")
os.makedirs(OUT, exist_ok=True)
API = "https://api.sketchfab.com/v3"


def token():
    t = os.environ.get("SKETCHFAB_TOKEN")
    p = os.path.join(OUT, ".token")
    if not t and os.path.exists(p):
        t = open(p).read().strip()
    return t


def call(url, auth=False):
    req = urllib.request.Request(url, headers={"User-Agent": "novaband-tools"})
    if auth:
        req.add_header("Authorization", "Token " + token())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def search(q, count=12):
    qs = urllib.parse.urlencode(dict(type="models", q=q, downloadable="true", count=count,
                                     sort_by="-likeCount"))
    res = call(API + "/search?" + qs)["results"]
    for m in res:
        arch = m.get("archives") or {}
        gl = arch.get("gltf") or {}
        print("%s  %-44.44s %-10s faces=%-8s gltf=%5.1fMB  %s" % (
            m["uid"], m["name"], (m.get("license") or {}).get("label", "?")[:10],
            m.get("faceCount"), (gl.get("size") or 0) / 1e6, m["user"]["username"]))


def get(uid, name):
    info = call(API + "/models/" + uid)
    dl = call(API + "/models/%s/download" % uid, auth=True)
    url = dl["gltf"]["url"]
    dest = os.path.join(OUT, name)
    os.makedirs(dest, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r:
        zipfile.ZipFile(io.BytesIO(r.read())).extractall(dest)
    cred_p = os.path.join(OUT, "credits.json")
    credits = json.load(open(cred_p)) if os.path.exists(cred_p) else {}
    credits[name] = dict(uid=uid, title=info["name"], author=info["user"]["displayName"],
                         username=info["user"]["username"], url=info["viewerUrl"],
                         license=(info.get("license") or {}).get("label"))
    json.dump(credits, open(cred_p, "w"), indent=1)
    print("ok", name, credits[name]["license"], "->", dest)


if __name__ == "__main__":
    if sys.argv[1] == "search":
        n = int(sys.argv[sys.argv.index("--count") + 1]) if "--count" in sys.argv else 12
        search(sys.argv[2], n)
    elif sys.argv[1] == "get":
        get(sys.argv[2], sys.argv[3])
