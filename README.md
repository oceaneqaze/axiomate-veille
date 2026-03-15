# 🤖 AXIOMATE — Bibliothèque de Veille IA Automatisée

## Ce que fait ce système

Chaque jour, le script Python :
1. **Scrape** Reddit (11 sous-reddits), YouTube (4 chaînes), 7 blogs IA, Twitter/X (10 comptes)
2. **Filtre** automatiquement les contenus pertinents pour ta niche (IA, automatisation, marketing)
3. **Résume** chaque item avec Claude AI en français, avec points clés actionnables
4. **Met à jour** `data.json` → ta bibliothèque web se met à jour automatiquement
5. **Envoie** un digest email HTML avec tous les nouveaux insights

---

## Installation (5 minutes)

### 1. Installe les dépendances Python

```bash
pip install requests feedparser anthropic yagmail python-dotenv
```

### 2. Configure tes clés API

```bash
# Copie le fichier template
cp .env.example .env

# Ouvre .env et remplis :
# - ANTHROPIC_API_KEY  (obligatoire)
# - GMAIL_USER + GMAIL_APP_PASSWORD  (pour le digest email)
# - YOUTUBE_API_KEY  (optionnel)
```

### 3. Lance le script

```bash
python veille.py
```

### 4. Ouvre ta bibliothèque

Double-clique sur `index.html` dans ton navigateur 🎉

---

## Automatisation quotidienne

### Sur Windows (Planificateur de tâches)
1. Ouvre "Planificateur de tâches"
2. Créer une tâche basique → Déclencheur : Tous les jours à 08h00
3. Action : `python C:\chemin\vers\veille.py`

### Sur Mac/Linux (cron)
```bash
# Ouvre crontab
crontab -e

# Ajoute cette ligne (lance à 8h chaque jour)
0 8 * * * /usr/bin/python3 /chemin/vers/veille.py >> /chemin/vers/veille_log.txt 2>&1
```

---

## Structure des fichiers

```
ai_veille/
├── index.html        ← Ta bibliothèque web
├── veille.py         ← Le script Python autonome
├── data.json         ← La base de données (créée automatiquement)
├── .env              ← Tes clés API (NE PAS partager !)
├── .env.example      ← Template de config
└── veille_log.txt    ← Logs d'exécution
```

---

## Personnalisation

### Ajouter des sources Reddit
Dans `veille.py`, ligne `REDDIT_SUBS`, ajoute les sous-reddits :
```python
REDDIT_SUBS = ["artificial", "AItools", "ton_sub_ici", ...]
```

### Ajouter des chaînes YouTube
Trouve le `channel_id` sur YouTube (clic droit → code source → cherche "channelId"),
puis ajoute dans `YT_CHANNELS` :
```python
YT_CHANNELS = [
    ("CHANNEL_ID_ICI", "Nom de la chaîne"),
    ...
]
```

### Ajouter des blogs RSS
Trouve l'URL du flux RSS du blog et ajoute dans `BLOGS_RSS` :
```python
BLOGS_RSS = [
    "https://tonblog.com/feed.xml",
    ...
]
```

### Modifier les mots-clés de pertinence
Dans `NICHE_KEYWORDS`, ajoute les termes de ta niche :
```python
NICHE_KEYWORDS = [
    "chariow", "benin", "afrique", "francophone", ...
]
```

---

## Coûts estimés

| Usage | Coût estimé |
|-------|------------|
| 30 items/jour analysés par Claude | ~$0.05/jour |
| 900 items/mois | ~$1.50/mois |
| Gmail (avec mot de passe d'appli) | Gratuit |

---

## Support

Site : axiomate.site
Système créé avec Claude AI (Anthropic)
