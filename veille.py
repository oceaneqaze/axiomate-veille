"""
AXIOMATE — Veille IA v4
========================
Ce script scrape + résume SEULEMENT.
Il ne génère PAS les threads — c'est toi qui valides dans l'interface.

Lance la veille :
    python veille.py

Lance le serveur (interface + validation) :
    python server.py

INSTALLATION :
    pip install requests feedparser anthropic yagmail python-dotenv flask
"""

import os, json, re, time, datetime, hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATA_FILE     = Path(__file__).parent / "data.json"
LOG_FILE      = Path(__file__).parent / "veille_log.txt"
MAX_ITEMS     = 500
RELEVANCE_MIN = 60

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
GMAIL_USER    = os.getenv("GMAIL_USER")
GMAIL_PASS    = os.getenv("GMAIL_APP_PASSWORD")
DEST_EMAIL    = os.getenv("DEST_EMAIL", GMAIL_USER)
YT_API_KEY    = os.getenv("YOUTUBE_API_KEY", "")
BASE_URL      = os.getenv("BASE_URL", "http://localhost:8080")

TODAY = datetime.date.today().isoformat()

# ── SOURCES ──────────────────────────────────────────────────────────────────

REDDIT_SUBS = [
    "artificial", "AItools", "automation", "ChatGPT",
    "midjourney", "StableDiffusion", "MachineLearning",
    "socialmedia", "marketing", "ecommerce",
    "passive_income", "EntrepreneurRideAlong",
]

YT_CHANNELS = [
    ("UCbmNph6atAoGfqLoCL_duAg", "Fireship"),
    ("UCWX3yGbODI3HMCOBQKnGdAA", "Matt Wolfe"),
    ("UCnUYZLuoy1rq1aVMwx4aTzw", "Two Minute Papers"),
    ("UCVls1GmFKf6WlTraIb_IaJg", "Greg Isenberg"),
    ("UCsTcErHg8oDvUnTzoqsYeNw", "Andrej Karpathy"),
    ("UCJXGnMfCNLnNBbqCzgRJZeA", "Wes Roth"),
    ("UC2eYFnH61tmytImy1mTYvhA", "Luke Miani"),
    ("UCddiUEpeqJcYeBxX1IVBKvQ", "The Futur"),
]

YT_SEARCH_QUERIES = [
    "AI automation tutorial 2026", "make money with AI tools",
    "AI video generation marketing", "n8n automation workflow",
    "ChatGPT business tips", "AI content creation strategy",
    "UGC video AI generator", "prompt engineering tricks",
    "AI tools ecommerce 2026", "social media AI automation",
]

BLOGS_RSS = [
    "https://openai.com/blog/rss.xml",
    "https://anthropic.com/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://aiparabellum.beehiiv.com/feed",
    "https://www.synthesia.io/blog/feed.xml",
    "https://blog.runway.com/feed",
    "https://elevenlabs.io/blog/rss.xml",
]

TWITTER_ACCOUNTS = [
    "sama", "gdb", "karpathy", "emollick", "levelsio",
    "danshipper", "swyx", "mattshumer_", "rowancheung",
    "aibreakfast", "bentossell", "heykahn", "minchoi",
]

NICHE_KEYWORDS = [
    "automation", "automatisation", "workflow", "n8n", "make", "zapier",
    "content creation", "ugc", "marketing", "ecommerce", "monetize",
    "ai tool", "outil ia", "video generation", "image generation",
    "prompt", "chatgpt", "claude", "midjourney", "runway", "sora",
    "kling", "elevenlabs", "revenue", "income", "business", "freelance",
    "tiktok", "instagram", "facebook", "social media", "viral", "growth",
    "agent", "llm", "gpt", "gemini", "llama", "stable diffusion",
    "money", "sell", "vendre", "client", "sales", "conversion",
    "tutorial", "astuce", "tip", "trick", "hack",
    "generate", "créer", "create", "build", "launch",
]

# ── UTILS ─────────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def item_id(title, url):
    return hashlib.md5(f"{title}{url}".encode()).hexdigest()[:10]

def load_db():
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "seen_ids": [], "last_sync": None}

def save_db(db):
    db["items"] = sorted(db["items"], key=lambda x: x["date"], reverse=True)[:MAX_ITEMS]
    db["last_sync"] = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def quick_relevance(text):
    t = text.lower()
    return min(sum(7 for kw in NICHE_KEYWORDS if kw in t), 100)

# ── SCRAPERS ──────────────────────────────────────────────────────────────────

def scrape_reddit(seen_ids):
    import requests
    items = []
    headers = {"User-Agent": "AxiomateVeille/4.0"}
    for sub in REDDIT_SUBS:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=10", headers=headers, timeout=10)
            if r.status_code != 200: continue
            for p in r.json()["data"]["children"]:
                d = p["data"]
                title = d.get("title", "")
                url_post = f"https://reddit.com{d.get('permalink','')}"
                text = d.get("selftext", "") or title
                iid = item_id(title, url_post)
                if iid in seen_ids: continue
                score = quick_relevance(title + " " + text[:500])
                if score < 20: continue
                items.append({"_id":iid,"_raw_title":title,"_raw_text":text[:800],"_source":"reddit","_url":url_post,"_score_raw":score})
            time.sleep(1.2)
        except Exception as e:
            log(f"Reddit r/{sub}: {e}")
    log(f"Reddit: {len(items)} candidats")
    return items

def scrape_youtube(seen_ids):
    import requests
    if not YT_API_KEY:
        return scrape_youtube_rss(seen_ids)
    items = []
    base = "https://www.googleapis.com/youtube/v3"
    for ch_id, ch_name in YT_CHANNELS:
        try:
            r = requests.get(f"{base}/search?channelId={ch_id}&part=snippet&order=date&maxResults=5&type=video&key={YT_API_KEY}", timeout=10).json()
            if "error" in r: continue
            for item in r.get("items", []):
                s = item["snippet"]
                pub_str = s.get("publishedAt","")
                if pub_str:
                    pub = datetime.datetime.fromisoformat(pub_str.replace("Z","+00:00"))
                    if (datetime.datetime.now(datetime.timezone.utc)-pub).days > 3: continue
                title = s["title"]
                vid_url = f"https://youtube.com/watch?v={item['id']['videoId']}"
                iid = item_id(title, vid_url)
                if iid in seen_ids: continue
                score = quick_relevance(title+" "+s.get("description","")[:400])
                if score < 15: continue
                items.append({"_id":iid,"_raw_title":title,"_raw_text":s.get("description","")[:600],"_source":"youtube","_url":vid_url,"_score_raw":score})
            time.sleep(0.3)
        except Exception as e:
            log(f"YouTube {ch_name}: {e}")
    pub_after = (datetime.date.today()-datetime.timedelta(days=3)).isoformat()+"T00:00:00Z"
    for q in YT_SEARCH_QUERIES:
        try:
            r = requests.get(f"{base}/search?q={requests.utils.quote(q)}&part=snippet&order=relevance&maxResults=5&type=video&publishedAfter={pub_after}&key={YT_API_KEY}", timeout=10).json()
            if "error" in r: continue
            for item in r.get("items",[]):
                if item["id"].get("kind")!="youtube#video": continue
                s=item["snippet"]; title=s["title"]
                vid_url=f"https://youtube.com/watch?v={item['id']['videoId']}"
                iid=item_id(title,vid_url)
                if iid in seen_ids: continue
                score=quick_relevance(title+" "+s.get("description","")[:400])
                if score<20: continue
                items.append({"_id":iid,"_raw_title":title,"_raw_text":s.get("description","")[:600],"_source":"youtube","_url":vid_url,"_score_raw":score})
            time.sleep(0.3)
        except Exception as e:
            log(f"YouTube search '{q}': {e}")
    seen_l=set(); unique=[]
    for i in items:
        if i["_id"] not in seen_l: seen_l.add(i["_id"]); unique.append(i)
    log(f"YouTube: {len(unique)} candidats")
    return unique

def scrape_youtube_rss(seen_ids):
    import feedparser
    items=[]
    for ch_id, ch_name in YT_CHANNELS:
        try:
            feed=feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}")
            for entry in feed.entries[:5]:
                title=entry.get("title",""); vid_url=entry.get("link","")
                if hasattr(entry,'published_parsed') and entry.published_parsed:
                    if (datetime.datetime.now()-datetime.datetime(*entry.published_parsed[:6])).days>3: continue
                iid=item_id(title,vid_url)
                if iid in seen_ids: continue
                score=quick_relevance(title)
                if score<15: continue
                items.append({"_id":iid,"_raw_title":title,"_raw_text":entry.get("summary","")[:600],"_source":"youtube","_url":vid_url,"_score_raw":score})
            time.sleep(0.5)
        except Exception as e:
            log(f"YouTube RSS {ch_name}: {e}")
    log(f"YouTube RSS: {len(items)} candidats")
    return items

def scrape_blogs(seen_ids):
    import feedparser
    items=[]
    for rss_url in BLOGS_RSS:
        try:
            feed=feedparser.parse(rss_url)
            for entry in feed.entries[:8]:
                title=entry.get("title",""); url_post=entry.get("link","")
                text=entry.get("summary","") or ""
                if not text and entry.get("content"): text=entry["content"][0].get("value","")
                text=re.sub(r'<[^>]+>',' ',text)[:800]
                if hasattr(entry,'published_parsed') and entry.published_parsed:
                    if (datetime.datetime.now()-datetime.datetime(*entry.published_parsed[:6])).days>4: continue
                iid=item_id(title,url_post)
                if iid in seen_ids: continue
                score=quick_relevance(title+" "+text)
                if score<15: continue
                items.append({"_id":iid,"_raw_title":title,"_raw_text":text,"_source":"blog","_url":url_post,"_score_raw":score})
            time.sleep(0.3)
        except Exception as e:
            log(f"Blog {rss_url[:40]}: {e}")
    log(f"Blogs: {len(items)} candidats")
    return items

def scrape_twitter(seen_ids):
    import feedparser
    items=[]
    nitter=["https://nitter.net","https://nitter.privacydev.net","https://nitter.poast.org","https://nitter.cz"]
    for account in TWITTER_ACCOUNTS:
        fetched=False
        for inst in nitter:
            try:
                feed=feedparser.parse(f"{inst}/{account}/rss")
                if not feed.entries: continue
                for entry in feed.entries[:5]:
                    title=entry.get("title","")
                    url_post=entry.get("link","").replace(inst,"https://twitter.com")
                    text=re.sub(r'<[^>]+>',' ',entry.get("summary","") or title)[:600]
                    if hasattr(entry,'published_parsed') and entry.published_parsed:
                        if (datetime.datetime.now()-datetime.datetime(*entry.published_parsed[:6])).days>2: continue
                    iid=item_id(title,url_post)
                    if iid in seen_ids: continue
                    score=quick_relevance(title+" "+text)
                    if score<20: continue
                    items.append({"_id":iid,"_raw_title":title[:200],"_raw_text":text,"_source":"twitter","_url":url_post,"_score_raw":score})
                fetched=True; time.sleep(0.5); break
            except Exception: continue
        if not fetched: log(f"Twitter @{account}: indisponible")
    log(f"Twitter/X: {len(items)} candidats")
    return items

# ── AI RÉSUMÉ (SANS thread) ───────────────────────────────────────────────────

def ai_summarize_batch(candidates):
    """Résume et classe les candidats. NE génère PAS de thread. Statut = pending."""
    import anthropic
    if not ANTHROPIC_KEY:
        log("⚠️  Pas de clé Anthropic")
        return [basic_item(c) for c in candidates]

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    results_out = []

    for i in range(0, len(candidates), 5):
        batch = candidates[i:i+5]
        batch_text = "\n\n---\n\n".join([
            f"[{j+1}] SOURCE: {c['_source'].upper()}\nTITRE: {c['_raw_title']}\nCONTENU: {c['_raw_text'][:500]}\nURL: {c['_url']}"
            for j, c in enumerate(batch)
        ])
        prompt = f"""Tu es un expert en IA et marketing digital pour entrepreneurs africains francophones.

Analyse ces {len(batch)} contenus. Retourne UNIQUEMENT un tableau JSON valide.

Format :
[{{
  "idx": 1,
  "title": "Titre accrocheur français max 100 chars",
  "summary": "Résumé 2-3 phrases clair et pratique en français",
  "key_points": ["Point concret 1", "Point actionnable 2", "Point chiffré 3"],
  "category": "Génération Vidéo | Génération Image | Automatisation | UGC & Contenu | Outils IA | Marketing IA | Audio IA | LLM & Prompts | Revenus IA",
  "tags": ["tag1", "tag2", "tag3"],
  "relevance_score": 85,
  "is_relevant": true
}}]

Critères is_relevant=true : parle d'IA, automatisation, contenu, marketing, revenus. Score >= 60.

CONTENUS :
{batch_text}

JSON UNIQUEMENT :"""

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text.strip()
            raw = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
            results = json.loads(raw)

            for res in results:
                idx = res.get("idx", 1) - 1
                if idx < 0 or idx >= len(batch): continue
                c = batch[idx]
                if not res.get("is_relevant", True): continue
                if res.get("relevance_score", 0) < RELEVANCE_MIN: continue
                numeric_id = int(hashlib.md5(c["_id"].encode()).hexdigest()[:8], 16) % 1_000_000
                results_out.append({
                    "id": numeric_id,
                    "title": res.get("title", c["_raw_title"]),
                    "source": c["_source"],
                    "category": res.get("category", "Outils IA"),
                    "date": TODAY,
                    "summary": res.get("summary", ""),
                    "key_points": res.get("key_points", []),
                    "tags": res.get("tags", []),
                    "relevance_score": res.get("relevance_score", 70),
                    "url": c["_url"],
                    "status": "pending",        # ← EN ATTENTE DE VALIDATION
                    "facebook_thread": [],
                    "_db_id": c["_id"],
                })

            log(f"Résumé batch {i//5+1} : {len([r for r in results if r.get('is_relevant') and r.get('relevance_score',0)>=RELEVANCE_MIN])} retenus")
            time.sleep(0.8)

        except Exception as e:
            log(f"Erreur résumé batch {i//5+1}: {e}")
            for c in batch:
                results_out.append(basic_item(c))

    return results_out

def basic_item(c):
    numeric_id = int(hashlib.md5(c["_id"].encode()).hexdigest()[:8], 16) % 1_000_000
    return {
        "id": numeric_id, "title": c["_raw_title"][:100], "source": c["_source"],
        "category": "Outils IA", "date": TODAY, "summary": c["_raw_text"][:300],
        "key_points": [], "tags": [], "relevance_score": c["_score_raw"],
        "url": c["_url"], "status": "pending", "facebook_thread": [], "_db_id": c["_id"],
    }

# ── EMAIL DIGEST avec liens de validation ─────────────────────────────────────

def send_email_digest(new_items):
    if not GMAIL_USER or not GMAIL_PASS or not new_items:
        log("Email non envoyé (config manquante ou 0 items)")
        return
    try:
        import yagmail
        cards = ""
        for item in new_items[:20]:
            validate_url = f"{BASE_URL}/validate?id={item['id']}&action=validate"
            reject_url   = f"{BASE_URL}/validate?id={item['id']}&action=reject"
            score_color  = "#00C896" if item['relevance_score']>=80 else "#E8A020" if item['relevance_score']>=65 else "#888"
            cards += f"""
            <div style="background:#0D1017;border:1px solid #1E2530;border-radius:12px;
                        padding:18px 22px;margin-bottom:14px;">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                <span style="color:#888;font-size:10px;text-transform:uppercase;letter-spacing:1px;">
                  {item['source']} • {item['category']}
                </span>
                <span style="color:{score_color};font-size:11px;font-weight:700;">⚡ {item['relevance_score']}%</span>
              </div>
              <div style="color:#E8EAF0;font-size:15px;font-weight:700;margin-bottom:10px;">{item['title']}</div>
              <div style="color:#8892A4;font-size:12px;line-height:1.7;margin-bottom:16px;">{item['summary']}</div>
              <div style="margin-bottom:10px;">
                {''.join([f'<span style="background:rgba(232,160,32,0.12);color:#F0C060;font-size:10px;padding:3px 9px;border-radius:4px;margin-right:5px;">{t}</span>' for t in item.get('tags',[])])}
              </div>
              <div style="display:flex;gap:10px;">
                <a href="{validate_url}"
                   style="flex:1;text-align:center;padding:11px 16px;background:#00C896;
                          border-radius:8px;color:white;text-decoration:none;
                          font-size:12px;font-weight:700;font-family:sans-serif;">
                  ✅ Valider — Générer le thread
                </a>
                <a href="{reject_url}"
                   style="padding:11px 16px;background:#1E2530;border-radius:8px;
                          color:#8892A4;text-decoration:none;font-size:12px;font-family:sans-serif;">
                  ❌ Rejeter
                </a>
              </div>
            </div>"""

        html = f"""
        <html><body style="background:#080A0F;padding:32px;font-family:sans-serif;">
          <div style="max-width:680px;margin:0 auto;">
            <div style="margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid #1E2530;">
              <div style="color:#E8A020;font-size:22px;font-weight:800;letter-spacing:2px;">
                AXIOMATE <span style="color:#E8EAF0;font-weight:400;font-size:16px;">/ Veille IA</span>
              </div>
              <div style="color:#6B7385;font-size:12px;margin-top:6px;">
                {TODAY} — {len(new_items)} nouveaux insights à valider
              </div>
            </div>

            <div style="background:rgba(0,200,150,0.08);border:1px solid rgba(0,200,150,0.2);
                        border-radius:12px;padding:14px 18px;margin-bottom:24px;">
              <div style="color:#00C896;font-size:12px;font-weight:700;margin-bottom:4px;">
                👆 Clique sur "Valider" pour générer le thread Facebook 10 posts
              </div>
              <div style="color:#8892A4;font-size:11px;">
                Le thread est généré immédiatement et disponible dans ta bibliothèque.
              </div>
            </div>

            {cards}

            <div style="text-align:center;margin-top:24px;">
              <a href="{BASE_URL}"
                 style="display:inline-block;padding:14px 28px;background:rgba(232,160,32,0.12);
                        border:1px solid rgba(232,160,32,0.3);border-radius:10px;
                        color:#E8A020;text-decoration:none;font-size:13px;font-weight:700;">
                Ouvrir la bibliothèque complète →
              </a>
            </div>

            <div style="color:#6B7385;font-size:11px;text-align:center;
                        padding-top:24px;margin-top:24px;border-top:1px solid #1E2530;">
              Axiomate Intelligence System v4 • axiomate.site
            </div>
          </div>
        </body></html>"""

        yag = yagmail.SMTP(GMAIL_USER, GMAIL_PASS)
        yag.send(
            to=DEST_EMAIL,
            subject=f"🤖 Axiomate Veille — {len(new_items)} insights à valider ({TODAY})",
            contents=[html]
        )
        log(f"✅ Email envoyé à {DEST_EMAIL} ({len(new_items)} items)")
    except Exception as e:
        log(f"Erreur email: {e}")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    log("=" * 55)
    log(f"🚀 AXIOMATE Veille IA v4 — {TODAY}")
    log("   Scraping + résumé uniquement (pas de thread)")
    log("   Valide les insights dans l'interface ou par email")
    log("=" * 55)

    db = load_db()
    seen_ids = set(db.get("seen_ids", []))

    all_candidates = []
    all_candidates += scrape_reddit(seen_ids)
    all_candidates += scrape_youtube(seen_ids)
    all_candidates += scrape_blogs(seen_ids)
    all_candidates += scrape_twitter(seen_ids)

    log(f"\n📊 {len(all_candidates)} candidats bruts")
    if not all_candidates:
        log("Aucun candidat — fin")
        return

    all_candidates.sort(key=lambda x: x["_score_raw"], reverse=True)
    top = all_candidates[:40]

    log(f"🧠 Résumé de {len(top)} items avec Claude…")
    new_items = ai_summarize_batch(top)
    log(f"✅ {len(new_items)} insights résumés — statut : EN ATTENTE DE VALIDATION")

    existing_db_ids = {item.get("_db_id") for item in db["items"]}
    truly_new = [i for i in new_items if i.get("_db_id") not in existing_db_ids]

    db["items"] = truly_new + db["items"]
    db["seen_ids"] = list(seen_ids | {c["_id"] for c in all_candidates})[-5000:]
    save_db(db)

    log(f"💾 data.json mis à jour — {len(db['items'])} items total")
    send_email_digest(truly_new)

    log(f"\n🎉 Veille terminée !")
    log(f"👉 Lance le serveur : python server.py")
    log(f"👉 Puis ouvre : {BASE_URL}")

if __name__ == "__main__":
    main()