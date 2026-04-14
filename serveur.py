#!/usr/bin/env python3
"""
Serveur local pour Dragons Capital Adventure.
- Sert les fichiers statiques (index.html, etc.)
- Agit comme proxy pour les APIs publiques (évite les blocages CORS)
- Lance automatiquement le navigateur
"""
import http.server
import urllib.request
import urllib.parse
import urllib.error
import time
_last_call = {}
_cache = {}
import webbrowser
import threading
import json
import os
import sys

PORT = 8742
DIR  = os.path.dirname(os.path.abspath(__file__))

# APIs autorisées à proxyfier
PROXY_ALLOWED = [
    "recherche-entreprises.api.gouv.fr",
    "annuaire-entreprises.api.gouv.fr",
    "data.inpi.fr",
    "api.inpi.fr",
    "registre-national-entreprises.inpi.fr",
    "formalites.entreprises.gouv.fr",
]

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # silencieux

    def do_GET(self):
        # Route proxy : /proxy?url=https://...
        if self.path.startswith('/proxy?'):
            self.handle_proxy()
            return
        # Sinon fichiers statiques normaux
        super().do_GET()

    def handle_proxy(self):
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            target = params.get('url', [''])[0]
            if not target:
                self.send_error(400, "Paramètre url manquant")
                return

            # Vérifier que l'URL est dans la liste autorisée
            parsed = urllib.parse.urlparse(target)
            if not any(parsed.netloc.endswith(d) for d in PROXY_ALLOWED):
                self.send_error(403, f"Domaine non autorisé: {parsed.netloc}")
                return

            # Faire la requête
            # Cache 5 min
            cached = _cache.get(target)
            if cached and (time.time() - cached[0]) < 300:
                data = cached[1]
            else:
                # Délai anti rate-limit : 1s entre appels vers le même domaine
                last = _last_call.get(parsed.netloc, 0)
                wait = 1.1 - (time.time() - last)
                if wait > 0:
                    time.sleep(wait)
                req = urllib.request.Request(
                    target,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (compatible; DragonsCapital/1.0)',
                        'Accept': 'application/json',
                        'Accept-Language': 'fr-FR,fr;q=0.9',
                    }
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                _last_call[parsed.netloc] = time.time()
                _cache[target] = (time.time(), data)

            # Renvoyer avec headers CORS
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

def open_browser():
    import time
    time.sleep(0.8)
    webbrowser.open(f"http://localhost:{PORT}/index.html")

print("╔══════════════════════════════════════════════════════╗")
print("║  Dragons Capital Adventure — Interface Acquisitions  ║")
print("╚══════════════════════════════════════════════════════╝")
print(f"\n  Démarrage du serveur sur le port {PORT}…")
print(f"  Proxy API activé (data.gouv.fr, annuaire-entreprises)")
print(f"\n  Pour arrêter : appuyez sur Ctrl+C\n")

threading.Thread(target=open_browser, daemon=True).start()

try:
    with http.server.HTTPServer(("localhost", PORT), Handler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n  Serveur arrêté.")
    sys.exit(0)
except OSError as e:
    if "Address already in use" in str(e):
        print(f"  Port {PORT} déjà utilisé — ouverture du navigateur.")
        webbrowser.open(f"http://localhost:{PORT}/index.html")
    else:
        raise
