# k0RE Release Manager

Outil d'automatisation de releases pour trackers privés. Génère le NFO, récupère les métadonnées TMDB, uploade la cover, prend des screenshots, et crée optionnellement un `.torrent` BT v1 privé.

---

## Fonctionnalités

- Génération du NFO via `mediainfo`
- Récupération automatique des métadonnées TMDB (film ou série TV)
- Détection automatique des langues audio / sous-titres (VFF, VFQ, etc.)
- Upload de la cover redimensionnée sur freeimage.host
- Génération de 5 screenshots via `ffmpeg` et upload automatique
- Création d'un `.torrent` BT v1 privé (pièces 16 MiB) via `bencode3`
- Génération de la présentation finale à partir d'un `template.txt`

---

## Dépendances

```bash
pip install requests Pillow bencode3
```

`mediainfo` et `ffmpeg` doivent être installés et accessibles dans le PATH.

---

## Fichiers requis

| Fichier | Description |
|---|---|
| `template.txt` | Template de la présentation avec placeholders `{{VARIABLE}}` |
| `trackers.txt` | Liste des trackers au format `NOM\|URL` |
| `MediaInfo.exe` | Binaire MediaInfo (Windows) |

### Format `trackers.txt`

```
YGG|http://tracker.exemple.net:8080/PASSKEY/announce
SHAREWOOD|https://www.sharewood.tv/announce/PASSKEY
```

---

## Utilisation

```bash
# Basique
py getRELEASE.py NOM-DU-FICHIER.mkv

# Avec année et source
py getRELEASE.py NOM-DU-FICHIER.mkv 2024 WEB-DL

# Avec création du .torrent
py getRELEASE.py NOM-DU-FICHIER.mkv 2024 WEB-DL --torrent
```

---

## Fichiers générés

| Fichier | Description |
|---|---|
| `NOM.nfo` | Infos MediaInfo brutes |
| `NOM.txt` | Présentation formatée (BBCode) |
| `NOM.torrent` | Torrent BT v1 privé (si `--torrent`) |
| `NOM_screenshots/` | Dossier des screenshots |

---

## Placeholders du template

| Placeholder | Description |
|---|---|
| `{{TMDB_TITLE}}` | Titre du film / de la série |
| `{{TMDB_YEAR}}` | Année de sortie |
| `{{TMDB_RATING}}` | Note TMDB |
| `{{TMDB_SYPNOSIS}}` | Synopsis |
| `{{TMDB_DIRECTOR}}` | Réalisateur |
| `{{TMDB_CAST}}` | Casting (5 premiers) |
| `{{TMDB_GENRES}}` | Genres |
| `{{TMDB_RUNTIME}}` | Durée |
| `{{NFO_AUDIO}}` | Bloc audio avec drapeaux |
| `{{NFO_SUBS}}` | Bloc sous-titres avec drapeaux |
| `{{URL_COVER}}` | URL de la cover uploadée |
| `{{SCREENSHOTS}}` | Screenshots en BBCode `[img]` |
| `{{SOURCE}}` | Source (WEB-DL, BluRay, etc.) |
