"""Local static server with correct MIME types (Windows maps .js to text/plain,
which blocks service workers and module scripts).   python tools/serve.py [port]"""
import http.server
import sys

H = http.server.SimpleHTTPRequestHandler
H.extensions_map.update({".js": "text/javascript", ".mjs": "text/javascript", ".webmanifest": "application/manifest+json",
                         ".webp": "image/webp", ".glb": "model/gltf-binary", ".wasm": "application/wasm"})
port = int(sys.argv[1]) if len(sys.argv) > 1 else 5174
http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
