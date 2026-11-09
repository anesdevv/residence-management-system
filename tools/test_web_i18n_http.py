import urllib.request
import urllib.parse
import sys

def fetch(url, headers=None, follow_redirects=False):
    req = urllib.request.Request(url, headers=headers or {})
    opener = urllib.request.build_opener(NoRedirectHandler if not follow_redirects else urllib.request.HTTPRedirectHandler)
    try:
        with opener.open(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else ''
        return e.code, dict(e.headers), body

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

base = "http://localhost:4329"

print("--- Testing 1: Root / (English default) ---")
status, headers, body = fetch(f"{base}/", {"Accept-Language": "en-US,en;q=0.9"})
print(f"Status: {status}")
assert status == 200, f"Expected 200, got {status}"
assert 'lang="en"' in body, "Expected lang=\"en\" in root HTML"
assert "Resident services" in body or "Resident registration" in body or "Sign in" in body, "Expected English landing strings"
print("PASS: Root renders English successfully!")

print("\n--- Testing 2: French Root /fr ---")
status, headers, body = fetch(f"{base}/fr")
print(f"Status: {status}")
assert status == 200, f"Expected 200, got {status}"
assert 'lang="fr"' in body, f"Expected lang=\"fr\" in /fr HTML, body starts with: {body[:300]}"
assert "Direction des Œuvres Universitaires" in body, "Expected DOU in body"
assert "Services aux résidents" in body or "Inscription" in body or "Connexion" in body or "Processus d’admission" in body, "Expected French landing strings"
print("PASS: /fr renders French successfully!")

print("\n--- Testing 3: Login in English /login ---")
status, headers, body = fetch(f"{base}/login")
print(f"Status: {status}")
assert status == 200, f"Expected 200, got {status}"
assert 'lang="en"' in body, "Expected lang=\"en\" on /login"
assert "Resident sign in" in body or "Sign in to portal" in body, "Expected English login strings"
print("PASS: /login renders English successfully!")

print("\n--- Testing 4: Login in French /fr/login ---")
status, headers, body = fetch(f"{base}/fr/login")
print(f"Status: {status}")
assert status == 200, f"Expected 200, got {status}"
assert 'lang="fr"' in body, f"Expected lang=\"fr\" on /fr/login"
assert "Connexion" in body or "Se connecter" in body, "Expected French login strings"
print("PASS: /fr/login renders French successfully!")

print("\n--- Testing 5: Query parameter ?lang=fr redirection ---")
status, headers, body = fetch(f"{base}/?lang=fr")
print(f"Status: {status}, Location: {headers.get('Location') or headers.get('location')}")
assert status in (301, 302, 307, 308), f"Expected redirect, got {status}"
loc = headers.get('Location') or headers.get('location')
assert loc and "/fr" in loc, f"Expected redirect to /fr, got {loc}"
print("PASS: ?lang=fr redirects to /fr correctly!")

print("\n--- Testing 6: Cookie persistence (resivo_locale=fr) ---")
status, headers, body = fetch(f"{base}/login", {"Cookie": "resivo_locale=fr"})
print(f"Status: {status}, Location: {headers.get('Location') or headers.get('location')}")
assert status in (301, 302, 307, 308), f"Expected redirect when user has fr cookie, got {status}"
loc = headers.get('Location') or headers.get('location')
assert loc and "/fr/login" in loc, f"Expected redirect to /fr/login, got {loc}"
print("PASS: Cookie resivo_locale=fr redirects English URLs to French equivalent!")

print("\nALL HTTP VERIFICATION CHECKS PASSED PERFECTLY!")
