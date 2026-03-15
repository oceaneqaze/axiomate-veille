"""
AXIOMATE — Serveur de validation v4
====================================
Lance ce fichier pour démarrer l'interface web :
    python server.py

Puis ouvre : http://localhost:8080

INSTALLATION :
    pip install requests feedparser anthropic yagmail python-dotenv flask
"""

import os, json, re, threading, datetime, hashlib
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

BASE_DIR      = Path(__file__).parent
DATA_FILE     = BASE_DIR / "data.json"
LOG_FILE      = BASE_DIR / "veille_log.txt"

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
GMAIL_USER    = os.getenv("GMAIL_USER")
GMAIL_PASS    = os.getenv("GMAIL_APP_PASSWORD")
DEST_EMAIL    = os.getenv("DEST_EMAIL", GMAIL_USER)
BASE_URL      = os.getenv("BASE_URL", "http://localhost:8080")

app = Flask(__name__, static_folder=str(BASE_DIR))

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_db() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "seen_ids": [], "last_sync": None}

def save_db(db):
    """Sauvegarde data.json localement ET sur GitHub."""
    import requests, base64

    db["last_sync"] = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
    content = json.dumps(db, ensure_ascii=False, indent=2)

    # Sauvegarde locale
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    # Push sur GitHub → déclenche le redéploiement Netlify
    token = os.getenv("GITHUB_TOKEN")
    repo  = os.getenv("GITHUB_REPO")  # ex: "aude/axiomate-veille"
    if not token or not repo:
        return

    api_url = f"https://api.github.com/repos/{repo}/contents/data.json"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    # Récupère le SHA actuel du fichier
    r = requests.get(api_url, headers=headers)
    sha = r.json().get("sha", "") if r.status_code == 200 else ""

    # Push le nouveau contenu
    requests.put(api_url, headers=headers, json={
        "message": f"[auto] Veille IA — {datetime.date.today().isoformat()}",
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha
    })

# ── GÉNÉRATION THREAD ─────────────────────────────────────────────────────────

def generate_thread_for_item(item_id: int):
    import anthropic

    db = load_db()
    item = next((i for i in db["items"] if i["id"] == item_id), None)
    if not item:
        log(f"Item {item_id} introuvable")
        return
    if item.get("facebook_thread"):
        log(f"Thread déjà généré pour item {item_id}")
        return

    log(f"🧵 Génération thread pour : {item['title'][:60]}…")

    if not ANTHROPIC_KEY:
        log("⚠️  Pas de clé Anthropic")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    prompt = f"""Tu es Aude, créatrice de contenu IA et experte en marketing digital pour l'Afrique francophone.

Écris un VRAI THREAD FACEBOOK de 10 posts numérotés sur ce sujet :

TITRE : {item['title']}
RÉSUMÉ : {item['summary']}
POINTS CLÉS : {', '.join(item.get('key_points', []))}
SOURCE : {item.get('url', '')}

STRUCTURE OBLIGATOIRE :

Post 1/10 — HOOK
- Emoji fort + révélation choc ou chiffre surprenant
- Curiosité irrésistible
- Termine par "Je t'explique dans ce thread 👇"
- 80-120 mots

Post 2/10 — LE PROBLÈME
- Problème concret que ça résout
- Parle à l'entrepreneur africain
- 150-200 mots

Post 3/10 — LA DÉCOUVERTE
- Présente l'outil ou la méthode
- D'où ça vient, qui l'utilise
- 150-200 mots

Post 4/10 — COMMENT ÇA MARCHE partie 1
- Explication simple, comme à un ami
- 150-200 mots

Post 5/10 — COMMENT ÇA MARCHE partie 2
- Étapes concrètes pour démarrer
- 150-200 mots

Post 6/10 — EXEMPLE CONCRET AFRICAIN
- Entrepreneur de Cotonou, Abidjan, Dakar, Lomé ou Douala
- Chiffres concrets
- 150-200 mots

Post 7/10 — ERREURS À ÉVITER
- 3 erreurs + comment les éviter
- 150-200 mots

Post 8/10 — RÉSULTATS RÉALISTES
- Ce qu'on peut espérer et en combien de temps
- 150-200 mots

Post 9/10 — POUR ALLER PLUS LOIN
- Outils complémentaires + prochaine étape
- 150-200 mots

Post 10/10 — CTA FINAL
- 3 points clés du thread
- Question pour engager les commentaires
- Axiomate / axiomate.site
- Hashtags : #IA #Automatisation #MarketingDigital #BusinessAfrica #EntrepreneurAfricain #AxiomateTips
- 100-150 mots

RÈGLES :
- Chaque post commence par "X/10 [emoji]"
- Chaque post sauf le 10 se termine par "—"
- Français populaire et direct, style Afrique francophone
- Toujours concret et actionnable

Retourne UNIQUEMENT ce tableau JSON :
[
  {{"numero": 1, "contenu": "texte complet post 1"}},
  {{"numero": 2, "contenu": "texte complet post 2"}},
  ...
  {{"numero": 10, "contenu": "texte complet post 10"}}
]

JSON UNIQUEMENT :"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
        posts = json.loads(raw)

        db = load_db()
        for i, db_item in enumerate(db["items"]):
            if db_item["id"] == item_id:
                db["items"][i]["facebook_thread"] = posts
                db["items"][i]["status"] = "approved"
                break
        save_db(db)
        log(f"✅ Thread généré ({len(posts)} posts) — item {item_id}")

    except Exception as e:
        log(f"❌ Erreur thread item {item_id}: {e}")
        db = load_db()
        for i, db_item in enumerate(db["items"]):
            if db_item["id"] == item_id:
                db["items"][i]["status"] = "approved"
                break
        save_db(db)

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "index.html")

@app.route("/data.json")
def data():
    return send_from_directory(str(BASE_DIR), "data.json") if DATA_FILE.exists() else jsonify({"items":[],"seen_ids":[],"last_sync":None})

@app.route("/api/validate", methods=["POST"])
def validate():
    body = request.get_json()
    item_id = body.get("id")
    if not item_id:
        return jsonify({"error": "id requis"}), 400
    db = load_db()
    item = next((i for i in db["items"] if i["id"] == item_id), None)
    if not item:
        return jsonify({"error": "introuvable"}), 404
    for i, db_item in enumerate(db["items"]):
        if db_item["id"] == item_id:
            db["items"][i]["status"] = "generating"
            break
    save_db(db)
    t = threading.Thread(target=generate_thread_for_item, args=(item_id,))
    t.daemon = True
    t.start()
    log(f"✅ Insight {item_id} validé — thread en génération")
    return jsonify({"success": True, "message": "Thread en cours de génération…"})

@app.route("/api/reject", methods=["POST"])
def reject():
    body = request.get_json()
    item_id = body.get("id")
    if not item_id:
        return jsonify({"error": "id requis"}), 400
    db = load_db()
    for i, db_item in enumerate(db["items"]):
        if db_item["id"] == item_id:
            db["items"][i]["status"] = "rejected"
            break
    save_db(db)
    log(f"❌ Insight {item_id} rejeté")
    return jsonify({"success": True})

@app.route("/api/status/<int:item_id>")
def get_status(item_id):
    db = load_db()
    item = next((i for i in db["items"] if i["id"] == item_id), None)
    if not item:
        return jsonify({"error": "introuvable"}), 404
    return jsonify({
        "id": item_id,
        "status": item.get("status", "pending"),
        "has_thread": bool(item.get("facebook_thread")),
        "thread": item.get("facebook_thread", []),
    })

@app.route("/validate")
def validate_from_email():
    item_id = request.args.get("id", type=int)
    action  = request.args.get("action", "validate")
    if not item_id:
        return "<h2>❌ Lien invalide</h2>", 400
    db = load_db()
    item = next((i for i in db["items"] if i["id"] == item_id), None)
    if not item:
        return "<h2>❌ Insight introuvable</h2>", 404

    if action == "reject":
        for i, db_item in enumerate(db["items"]):
            if db_item["id"] == item_id:
                db["items"][i]["status"] = "rejected"
                break
        save_db(db)
        log(f"❌ Insight {item_id} rejeté via email")
        return f"""<html><body style="font-family:sans-serif;background:#080A0F;color:#E8EAF0;text-align:center;padding:60px;">
          <div style="max-width:500px;margin:0 auto;">
            <div style="font-size:48px;margin-bottom:20px;">❌</div>
            <h2 style="color:#E8A020;">Insight rejeté</h2>
            <p style="color:#8892A4;">"{item['title']}"</p>
            <a href="{BASE_URL}" style="color:#E8A020;">← Retour à la bibliothèque</a>
          </div></body></html>"""

    already = item.get("status") in ("approved", "generating")
    if not already:
        for i, db_item in enumerate(db["items"]):
            if db_item["id"] == item_id:
                db["items"][i]["status"] = "generating"
                break
        save_db(db)
        t = threading.Thread(target=generate_thread_for_item, args=(item_id,))
        t.daemon = True
        t.start()
        log(f"✅ Insight {item_id} validé via email")

    return f"""<html><head><meta http-equiv="refresh" content="3;url={BASE_URL}"></head>
    <body style="font-family:sans-serif;background:#080A0F;color:#E8EAF0;text-align:center;padding:60px;">
      <div style="max-width:500px;margin:0 auto;">
        <div style="font-size:48px;margin-bottom:20px;">✅</div>
        <h2 style="color:#E8A020;">{"Déjà en cours !" if already else "Thread en génération !"}</h2>
        <p style="color:#8892A4;">"{item['title']}"</p>
        <p style="color:#6B7385;font-size:13px;">Prêt dans 2-3 min. Redirection automatique…</p>
        <a href="{BASE_URL}" style="color:#E8A020;">Aller à la bibliothèque →</a>
      </div></body></html>"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    log(f"🚀 Serveur Axiomate sur http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
