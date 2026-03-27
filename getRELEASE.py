#!/usr/bin/env python3 
# -*- coding: utf-8 -*-

import os, sys, re, subprocess, requests, logging, hashlib, math, time
from io import BytesIO
from PIL import Image
from difflib import SequenceMatcher
from pathlib import Path
try:
    import bencode3 as bencode
except ImportError:
    import bencode


# ==========================
# CONFIGURATION
# ==========================
TMDB_API_KEY = "044d34a6141458e59b6a7ffe909f0f3d"
FREEIMAGE_API_KEY = "6d207e02198a847aa98d0a2a901485a5"
TRACKER_FILE = "trackers.txt"
PIECE_SIZE = 8 * 1024 * 1024
TEMPLATE_FILE = "template.txt"
LOG_FILE = "release.log"

# ==========================
# LOGGER
# ==========================
class Logger:
    COLORS = {
        "STEP": "\033[38;5;19m",
        "INFO": "\033[38;5;57m",
        "HASH": "\033[38;5;93m",
        "SUCCESS": "\033[38;5;129m",
        "ERROR": "\033[38;5;201m",
        "RESET": "\033[0m"
    }
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='[%(levelname)s] %(message)s')

    @staticmethod
    def step(n,msg):
        print(f"{Logger.COLORS['STEP']}[STEP {n}] {msg}{Logger.COLORS['RESET']}")
        logging.info(f"[STEP {n}] {msg}")

    @staticmethod
    def info(msg):
        print(f"{Logger.COLORS['INFO']}[INFO] {msg}{Logger.COLORS['RESET']}")
        logging.info(msg)

    @staticmethod
    def hash(msg):
        print(f"{Logger.COLORS['HASH']}[HASH] {msg}{Logger.COLORS['RESET']}")
        logging.info(msg)

    @staticmethod
    def success(msg):
        print(f"{Logger.COLORS['SUCCESS']}[SUCCESS] {msg}{Logger.COLORS['RESET']}")
        logging.info(msg)

    @staticmethod
    def error(msg):
        print(f"{Logger.COLORS['ERROR']}[ERROR] {msg}{Logger.COLORS['RESET']}")
        logging.error(msg)

# ==========================
# LOGO
# ==========================
def print_logo():
    os.system("cls" if os.name=="nt" else "clear")
    colors=["\033[38;5;19m","\033[38;5;20m","\033[38;5;21m","\033[38;5;57m","\033[38;5;93m","\033[38;5;99m","\033[38;5;129m"]
    logo=[
        "██╗  ██╗ ██████╗ ██████╗ ███████╗",
        "██║ ██╔╝██╔═████╗██╔══██╗██╔════╝",
        "█████╔╝ ██║██╔██║██████╔╝█████╗  ",
        "██╔═██╗ ████╔╝██║██╔══██╗██╔══╝  ",
        "██║  ██╗╚██████╔╝██║  ██║███████╗",
        "╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝",
        "               k0RE"
    ]
    for i,line in enumerate(logo):
        print(f"{colors[i%len(colors)]}{line}\033[0m")
    print()


# ========================== 
# RELEASE MANAGER
# ==========================
class ReleaseManager:
    def __init__(self, video_file, forced_year=None, source="", type_=None, title=None):
        self.video_file = video_file
        self.base = os.path.splitext(video_file)[0]
        self.cover_url = ""
        self.tmdb_data = {}
        self.nfo_data = {}
        self.forced_year = forced_year
        self.source = source
        self.type_ = type_
        self.title = title
        self.release_tag = self.detect_release_tag()

    # ---------------------------
    # RELEASE TAGS
    # ---------------------------
    def detect_release_tag(self):
        tags = ["EXTENDED","DIRECTORS CUT","REPACK","PROPER","UNRATED"]
        name = os.path.basename(self.video_file).upper()
        for tag in tags:
            if tag in name:
                Logger.info(f"Tag détecté : {tag}")
                return tag
        return ""

    # ---------------------------
    # Nettoyage du nom de fichier pour TMDB
    # ---------------------------
    def clean_filename_for_tmdb(self, filename):
        name = os.path.splitext(os.path.basename(filename))[0]
        tags = ["EXTENDED","DIRECTORS CUT","REPACK","PROPER","UNRATED","MULTi","HDR","1080P","2160P",
                "WEB-DL","WEB","BluRay","BRRip","DVDRip","DTS","DDP","ATMOS","x265","x264","HEVC","AVC","H264","H265","VFF","VOSTFR"]
        name = name.replace(".", " ")
        for tag in tags:
            name = re.sub(rf"\b{tag}\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s{2,}", " ", name).strip()
        return name

    # ---------------------------
    # Normalisation codecs vidéo/audio
    # ---------------------------
    def normalize_codec(self, codec):
        codec = codec.upper()
        if codec in ["HEVC", "H.265"]:
            return "H265"
        elif codec in ["AVC", "H.264"]:
            return "H264"
        elif codec in ["TRUEHD"]: 
            return "TrueHD"
        elif codec in ["DTS"]:
            return "DTS"
        elif codec in ["AAC LC"]:
            return "AAC"
        return codec

    # ---------------------------
    # Normalisation des canaux audio
    # ---------------------------
    def normalize_channels(self, channels_str):
        channels_str = str(channels_str).lower()
        if "7.1" in channels_str or "8" in channels_str:
            return "7.1"
        elif "6" in channels_str:
            return "5.1"
        elif "2" in channels_str:
            return "2.0"
        elif "1" in channels_str:
            return "1.0"
        return channels_str

    # ---------------------------
    # NFO parsing amélioré
    # ---------------------------
    def generate_nfo(self):
        Logger.step(1,"Génération NFO")
        nfo_path=self.base+".nfo"
        with open(nfo_path,"w") as f:
            subprocess.run(["mediainfo",self.video_file],stdout=f)
        self.nfo_data=self.parse_nfo(nfo_path)
        self.nfo_data["NFO_VIDEO_FORMAT"] = self.normalize_codec(self.nfo_data.get("NFO_VIDEO_FORMAT",""))
        Logger.success("NFO généré avec succès ✅")

    def parse_nfo(self, path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        def extract_blocks(section_name):
            pattern = rf"{section_name}\n(.*?)(?=\n\n|\Z)"
            return re.findall(pattern, content, re.S)

        def get_value(block, field):
            m = re.search(rf"{field}\s*:\s*(.+)", block, re.I)
            return m.group(1).strip() if m else ""

        nfo_data = {}

        # ---------------- GENERAL ----------------
        general_blocks = extract_blocks("General")
        if general_blocks:
            g = general_blocks[0]
            complete_name = get_value(g, "Complete name")
        if complete_name:
            nfo_data["NFO_COMPLETE_NAME"] = Path(complete_name).name.rsplit(".", 1)[0]
            nfo_data["NFO_GENERAL_DEBIT_GOLBAL"] = get_value(g, "Overall bit rate")
            nfo_data["NFO_GENERAL_TAILLE_DU_FICHIER"] = get_value(g, "File size")

        # ---------------- VIDEO ----------------
        video_blocks = extract_blocks("Video")
        if video_blocks:
            v = video_blocks[0]
            nfo_data["NFO_VIDEO_FORMAT"] = get_value(v, "Format")
            nfo_data["NFO_VIDEO_BIT_RATE"] = get_value(v, "Bit rate")
            nfo_data["NFO_VIDEO_FRAME_RATE"] = get_value(v, "Frame rate")
            nfo_data["NFO_VIDEO_WIDTH"] = get_value(v, "Width").replace(" pixels","").strip()
            nfo_data["NFO_VIDEO_HEIGHT"] = get_value(v, "Height").replace(" pixels","").strip()
            nfo_data["NFO_VIDEO_COLOR_SPACE"] = get_value(v, "Color space")
            nfo_data["NFO_VIDEO_TRANSFER"] = get_value(v, "Transfer characteristics")

        # ---------------- AUDIO ----------------
        audio_blocks = extract_blocks("Audio")
        for idx, block in enumerate(audio_blocks, 1):
            nfo_data[f"NFO_AUDIO_{idx}_CODEC"] = get_value(block, "Format")
            nfo_data[f"NFO_AUDIO_{idx}_CANAUX"] = get_value(block, "Channel\(s\)")
            nfo_data[f"NFO_AUDIO_{idx}_DEBIT"] = get_value(block, "Bit rate")
            nfo_data[f"NFO_AUDIO_{idx}_LANGUE"] = get_value(block, "Language")
            nfo_data[f"NFO_AUDIO_{idx}_TITRE"] = get_value(block, "Title")

        # ---------------- SUBS ----------------
        text_blocks = extract_blocks("Text")
        for idx, block in enumerate(text_blocks, 1):
            nfo_data[f"NFO_TEXT_{idx}_LANGUE"] = get_value(block, "Language")
            nfo_data[f"NFO_TEXT_{idx}_TITRE"] = get_value(block, "Title")
            nfo_data[f"NFO_TEXT_{idx}_DEFAULT"] = get_value(block, "Default")
            nfo_data[f"NFO_TEXT_{idx}_FORCED"] = get_value(block, "Forced")

        return nfo_data

    # ---------------------------
    # Audio / Subs dynamiques améliorés
    # ---------------------------
    LANG_MAPPING = {
        "french":["fr","french","francais","fra"],
        "english":["en","eng","english"],
        "spanish":["es","spa","spanish"],
        "german":["de","ger","german"],
        "italian":["it","ita","italian"],
        "japanese":["ja","jpn","japanese"],
    }

    FLAG_MAPPING = {
        "french":"fr", "english":"us", "spanish":"es", "german":"de", "italian":"it", "japanese":"jp"
    }

    VF_MAPPING = {
        "france":"VFF",
        "canada":"VFQ"
    }

    # 🔥 VERSION FINALE INTÉGRÉE
    def detect_language(self, lang_field, title_field=""):
        combined = f"{lang_field} {title_field}".lower()

        for lang, keywords in self.LANG_MAPPING.items():
            if any(k in combined for k in keywords):

                if lang == "french":

                    # 🔥 VFQ (Canada / Canadien / CA)
                    if any(x in combined for x in [
                        "canada",
                        "canadian",
                        "canadien",
                        "canadienne",
                        "quebec",
                        "québec",
                        "qc",
                        "vfq",
                        "fr-ca",
                        "fr_ca",
                        "(ca)",
                        " ca"
                    ]):
                        return "French (VFQ)", "ca"

                    # 🔥 VFF (France)
                    if any(x in combined for x in [
                        "france",
                        "vff",
                        "fr-fr",
                        "fr_fr",
                        "(fr)"
                    ]):
                        return "French (VFF)", "fr"

                    return "French", "fr"

                return lang.title(), self.FLAG_MAPPING[lang]

        return lang_field.title(), "us"

    # ---------------------------
    # Bloc Vidéo personnalisé pour 1080p / 2160p HDR DV
    # ---------------------------
    def build_video_block(self):
        width = int(self.nfo_data.get("NFO_VIDEO_WIDTH",0))
        height = int(self.nfo_data.get("NFO_VIDEO_HEIGHT",0))
        color = self.nfo_data.get("NFO_VIDEO_COLOR_SPACE","")
        transfer = self.nfo_data.get("NFO_VIDEO_TRANSFER","").lower()
        codec = self.nfo_data.get("NFO_VIDEO_FORMAT","")

        block = ""
        if height == 2160:
            if "dolby vision" in transfer or "dv" in self.video_file.lower():
                block = f"2160p HDR.DV {codec}"
            elif "hdr" in color.lower():
                block = f"2160p HDR {codec}"
            else:
                block = f"2160p {codec}"
        else:
            block = f"{height}p {codec}"

        return block

    # ---------------------------
    # Bloc Audio
    # ---------------------------
    def build_audio_block(self):
        audio_lines = []
        i = 1
        while f"NFO_AUDIO_{i}_CODEC" in self.nfo_data:
            titre = self.nfo_data.get(f"NFO_AUDIO_{i}_TITRE","").replace("FULL","").replace("Forced","").strip()
            codec = self.normalize_codec(self.nfo_data.get(f"NFO_AUDIO_{i}_CODEC",""))
            canaux_raw = self.nfo_data.get(f"NFO_AUDIO_{i}_CANAUX","")
            canaux = self.normalize_channels(canaux_raw)
            debit = self.nfo_data.get(f"NFO_AUDIO_{i}_DEBIT","")
            langue_field = self.nfo_data.get(f"NFO_AUDIO_{i}_LANGUE","")
            lang_label, flag = self.detect_language(langue_field, titre)

            audio_lines.append(
                f'[img]https://flagcdn.com/20x15/{flag}.png[/img] {lang_label} [{canaux}] / {codec} à {debit}'
            )
            i += 1
        return " - ".join(audio_lines) if audio_lines else "Unknown"

    # ---------------------------
    # Bloc Sous-titres
    # ---------------------------
    def build_subs_block(self):
        sub_lines = []
        i = 1
        while f"NFO_TEXT_{i}_TITRE" in self.nfo_data:
            titre = re.sub(r"[\[\]]","",self.nfo_data.get(f"NFO_TEXT_{i}_TITRE","")).strip()
            langue_field = self.nfo_data.get(f"NFO_TEXT_{i}_LANGUE","").replace("(FR)","").replace("(CA)","").strip()
            default = self.nfo_data.get(f"NFO_TEXT_{i}_DEFAULT","No")
            forced = self.nfo_data.get(f"NFO_TEXT_{i}_FORCED","No")

            lang_label, flag = self.detect_language(langue_field, titre)

            # Forced
            if forced.lower() == "yes":
                sub_lines.append(f'[img]https://flagcdn.com/20x15/{flag}.png[/img] {lang_label} [Forced]')

            # FULL → si Default=Yes OU VFQ/VFF et pas Forced
            if default.lower() == "yes" or (lang_label in ["French (VFF)","French (VFQ)"] and forced.lower() != "yes"):
                sub_lines.append(f'[img]https://flagcdn.com/20x15/{flag}.png[/img] {lang_label} [Full]')

            # SDH
            if "sdh" in titre.lower():
                sub_lines.append(f'[img]https://flagcdn.com/20x15/{flag}.png[/img] {lang_label} [SDH]')

            # Aucun type
            if forced.lower() != "yes" and default.lower() != "yes" and "sdh" not in titre.lower() and lang_label not in ["French (VFF)","French (VFQ)"]:
                sub_lines.append(f'[img]https://flagcdn.com/20x15/{flag}.png[/img] {lang_label}')

            i += 1

        return " - ".join(sub_lines) if sub_lines else "Aucun"

    # ---------------------------
    # UTILITAIRES TMDB
    # ---------------------------
    def parse_filename(self):
        name=os.path.basename(self.video_file)
        name=os.path.splitext(name)[0]
        tv_match=re.search(r"(.+?)\.S\d{2}E\d{2}",name,re.IGNORECASE)
        if tv_match: return tv_match.group(1).replace("."," ").strip(),None
        m=re.search(r"(.+?)\.(\d{4})",name)
        if m: return m.group(1).replace("."," ").strip(),m.group(2)
        return name.replace("."," ").strip(),None

    def fetch_tmdb(self,type_,title):
        url=f"https://api.themoviedb.org/3/search/{type_}"
        r=requests.get(url,params={"api_key":TMDB_API_KEY,"query":title,"language":"fr-FR"})
        r.raise_for_status()
        return r.json().get("results",[])

    def similar(self,a,b): return SequenceMatcher(None,a.lower(),b.lower()).ratio()

    def choose_tmdb_result(self,results):
        Logger.info("Plusieurs résultats trouvés, choisissez le bon :")
        for idx,item in enumerate(results):
            title=item.get("title") or item.get("name")
            year=(item.get("release_date") or item.get("first_air_date") or "")[:4]
            country=(item.get("origin_country")[0] if item.get("origin_country") else "")
            print(f"[{idx}] {title} ({year}) {country}")
        while True:
            choice=input("Entrez le numéro du résultat à utiliser : ")
            if choice.isdigit() and 0<=int(choice)<len(results): return results[int(choice)]
            print("Choix invalide, réessayez...")

    def search_tmdb_tv(self,title):
        results=self.fetch_tmdb("tv",title)
        if not results: Logger.error(f"Série introuvable : {title}"); sys.exit(1)
        exact=[r for r in results if r.get("name","").lower()==title.lower()]
        if exact:
            if len(exact)>1: return self.choose_tmdb_result(exact)
            return exact[0]
        best_ratio,best=0,results[0]
        for r in results:
            ratio=self.similar(r.get("name",""),title)
            if ratio>best_ratio: best_ratio,best=ratio,r
        return best

    def search_tmdb_movie(self,title,year=None):
        results=self.fetch_tmdb("movie",title)
        year=year or self.forced_year
        if year:
            filtered=[m for m in results if (m.get("release_date") or "").startswith(str(year))]
            if filtered: results=filtered
        if not results: Logger.error(f"Film introuvable : {title}"); sys.exit(1)
        exact=[r for r in results if r.get("title","").lower()==title.lower()]
        if exact:
            if len(exact)>1: return self.choose_tmdb_result(exact)
            return exact[0]
        best_ratio,best=0,results[0]
        for r in results:
            ratio=self.similar(r.get("title",""),title)
            if ratio>best_ratio: best_ratio,best=ratio,r
        return best

    # ---------------------------
    # TMDB DETAILS / POSTERS
    # ---------------------------
    def get_tmdb_tv_details(self,tv_id):
        r=requests.get(f"https://api.themoviedb.org/3/tv/{tv_id}",params={"api_key":TMDB_API_KEY,"language":"fr-FR"})
        r.raise_for_status(); return r.json()

    def get_tmdb_episode_details(self,tv_id,season,episode):
        r=requests.get(f"https://api.themoviedb.org/3/tv/{tv_id}/season/{season}/episode/{episode}",params={"api_key":TMDB_API_KEY,"language":"fr-FR"})
        r.raise_for_status(); return r.json()

    def get_tmdb_movie_details(self,movie_id):
        r=requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}",params={"api_key":TMDB_API_KEY,"language":"fr-FR","append_to_response":"credits"})
        r.raise_for_status(); return r.json()

    def download_poster(self,path):
        r=requests.get("https://image.tmdb.org/t/p/original"+path)
        return Image.open(BytesIO(r.content))

    def resize_image(self,img):
        w=500
        ratio=w/float(img.size[0])
        return img.resize((w,int(img.size[1]*ratio)),Image.LANCZOS)

    def upload_image(self, img):
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        r = requests.post("https://freeimage.host/api/1/upload",
                          data={"key":FREEIMAGE_API_KEY,"action":"upload"},
                          files={"source":("cover.jpg",buf,"image/jpeg")})
        return r.json()["image"]["url"]
    
    # ---------------------------
    # GENERATE TMDB + COVER
    # ---------------------------
    def generate_tmdb_and_cover(self):
        Logger.step(2,"TMDB + Cover")
        filename=os.path.basename(self.video_file)
        tv_match=re.search(r"S(\d{2})E(\d{2})",filename,re.IGNORECASE)
        is_tv=bool(tv_match)
        title,year=self.parse_filename()
        type_ = self.type_ or ("tv" if is_tv else "movie")
        search_title = self.title or title

        if is_tv:
            Logger.info("Type détecté : Série TV")
            season_number=int(tv_match.group(1))
            episode_number=int(tv_match.group(2))
            search=self.search_tmdb_tv(search_title)
            tv_id=search["id"]
            series_details=self.get_tmdb_tv_details(tv_id)
            episode_details=self.get_tmdb_episode_details(tv_id,season_number,episode_number)
            self.tmdb_data={
                "TMDB_TITLE":series_details.get("name",""),
                "TMDB_YEAR":series_details.get("first_air_date","")[:4],
                "TMDB_ID":str(tv_id),
                "TMDB_COUNTRY":series_details["origin_country"][0] if series_details.get("origin_country") else "",
                "TMDB_RELEASE_DATE":episode_details.get("air_date",""),
                "TMDB_ORIGINAL_TITLE":series_details.get("original_name",""),
                "TMDB_RUNTIME":str(episode_details.get("runtime",""))+" min" if episode_details.get("runtime") else "",
                "TMDB_DIRECTOR":"",
                "TMDB_CAST":"",
                "TMDB_GENRES":", ".join([g["name"] for g in series_details.get("genres",[])]),
                "TMDB_RATING":str(episode_details.get("vote_average","")),
                "TMDB_SYPNOSIS":episode_details.get("overview",""),
                "TMDB_SEASON":season_number,
                "TMDB_EPISODE":episode_number,
                "TMDB_EPISODE_TITLE":episode_details.get("name",""),
                "TMDB_AUDIO":self.get_audio_languages(),
                "SOURCE":self.source
            }
            poster=series_details.get("poster_path")
        else:
            Logger.info("Type détecté : Film")
            search=self.search_tmdb_movie(search_title,year)
            movie_id=search["id"]
            details=self.get_tmdb_movie_details(movie_id)
            director=""
            for crew in details.get("credits",{}).get("crew",[]):
                if crew.get("job")=="Director": director=crew.get("name"); break
            cast=", ".join([c["name"] for c in details.get("credits",{}).get("cast",[])[:5]])
            self.tmdb_data={
                "TMDB_TITLE":details.get("title",""),
                "TMDB_YEAR":details.get("release_date","")[:4],
                "TMDB_ID":str(details.get("id","")),
                "TMDB_COUNTRY":details["production_countries"][0]["name"] if details.get("production_countries") else "",
                "TMDB_RELEASE_DATE":details.get("release_date",""),
                "TMDB_ORIGINAL_TITLE":details.get("original_title",""),
                "TMDB_RUNTIME":str(details.get("runtime",""))+" min",
                "TMDB_DIRECTOR":director,
                "TMDB_CAST":cast,
                "TMDB_GENRES":", ".join([g["name"] for g in details.get("genres",[])]),
                "TMDB_RATING":str(details.get("vote_average","")),
                "TMDB_SYPNOSIS":details.get("overview",""),
                "TMDB_AUDIO":self.get_audio_languages(),
                "SOURCE":self.source
            }
            poster=details.get("poster_path")

        if poster:
            img=self.download_poster(poster)
            img=self.resize_image(img)
            self.cover_url=self.upload_image(img)
            Logger.success(f"Cover uploadée : {self.cover_url} ✅")

    def get_audio_languages(self):
        languages=[]
        for key in self.nfo_data:
            if key.startswith("NFO_AUDIO_") and "_TITRE" in key:
                val=self.nfo_data[key].strip()
                if val: languages.append(val)
        return ", ".join(languages) if languages else "Unknown"

    def generate_screenshots(self, count=2):
        """
        Génère des screenshots de la vidéo, les réduit et upload sur FastPic.
        Retourne une liste des URL uploadées.
        """
        import math
        from pathlib import Path
        from io import BytesIO
        from PIL import Image
        import subprocess
        import requests

        Logger.step(4, f"Génération de {count} screenshots")

        # Récupère la durée en secondes depuis le NFO
        duration_str = self.nfo_data.get("NFO_VIDEO_RUNTIME","")
        duration_sec = 600  # fallback 10 min
        if duration_str:
            if "min" in duration_str.lower(): 
                duration_sec = int(duration_str.split()[0])*60
            elif "h" in duration_str.lower(): 
                duration_sec = int(duration_str.split()[0])*3600
            else: 
                duration_sec = int(duration_str.split()[0])

        out_dir = Path(self.base + "_screenshots")
        out_dir.mkdir(exist_ok=True)

        # Calcul des positions pour les screenshots
        times = [math.floor(duration_sec*(i+1)/(count+1)) for i in range(count)]
        uploaded_screenshots = []

        for idx, t in enumerate(times, 1):
            out_file = out_dir / f"{self.base}_shot{idx}.jpg"

            # Capture screenshot avec ffmpeg
            subprocess.run([
                "ffmpeg", "-y", "-ss", str(t), "-i", self.video_file,
                "-vframes", "1", str(out_file)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Redimensionne l'image avant upload
            img = Image.open(out_file)
            max_width = 400  # largeur maximale pour la PREZ
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

            # Upload sur FastPic
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            r = requests.post(
                "https://freeimage.host/api/1/upload",
                data={"key":FREEIMAGE_API_KEY, "action":"upload"},
                files={"source":("screenshot.jpg", buf, "image/jpeg")}
            )
            url = r.json().get("image", {}).get("url")
            uploaded_screenshots.append(url if url else str(out_file))

        Logger.success(f"Screenshots générés et uploadés : {', '.join(uploaded_screenshots)} ✅")
        return uploaded_screenshots

    # ---------------------------
    # GENERATE TORRENT
    # ---------------------------
    def generate_torrent(self):
        Logger.step(5, "Création du .torrent")
        trackers = []
        if os.path.exists(TRACKER_FILE):
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "|" in line:
                        _, url = line.split("|", 1)
                        trackers.append(url.strip())
        if not trackers:
            Logger.error("Aucun tracker trouvé dans trackers.txt")
            return

        piece_size = 16 * 1024 * 1024  # 16 MiB
        file_path = self.video_file
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        Logger.info(f"Hachage des pièces ({math.ceil(file_size / piece_size)} pièces)...")
        pieces = b""
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(piece_size)
                if not chunk:
                    break
                pieces += hashlib.sha1(chunk).digest()

        info = {
            b"name":         file_name.encode("utf-8"),
            b"piece length": piece_size,
            b"pieces":       pieces,
            b"length":       file_size,
            b"private":      1,
        }

        torrent = {
            b"info":         info,
            b"announce":     trackers[0].encode("utf-8"),
            b"creation date": int(time.time()),
            b"created by":   b"getRELEASE",
            b"encoding":     b"UTF-8",
        }
        if len(trackers) > 1:
            torrent[b"announce-list"] = [[t.encode("utf-8")] for t in trackers]

        out = self.base + ".torrent"
        with open(out, "wb") as f:
            f.write(bencode.encode(torrent))
        Logger.success(f"Torrent créé : {out} ✅")

    # ---------------------------
    # GENERATE PREZ
    # ---------------------------
    def generate_prez(self):
        Logger.step(3,"Génération PREZ")
        if not os.path.exists(TEMPLATE_FILE):
            Logger.error("template.txt introuvable"); sys.exit(1)
        with open(TEMPLATE_FILE,"r",encoding="utf-8") as f: template=f.read()
        data = {**self.nfo_data, **self.tmdb_data, "URL_COVER": self.cover_url, "VIDEO_NAME": os.path.basename(self.video_file)}
        # Remplacement des blocs audio / subs
        data["NFO_AUDIO"] = self.build_audio_block()
        data["NFO_SUBS"] = self.build_subs_block()
        # Avant de remplacer les placeholders
        screenshots = self.generate_screenshots(count=5)
        # Crée une chaîne avec le format [img]URL[/img] pour chaque screenshot
        data["SCREENSHOTS"] = " - ".join(f"[img]{url}[/img]" for url in screenshots)        
        for k,v in data.items():
            template=template.replace("{{"+k+"}}",str(v))
        template=template.replace("!!SOURCE!!",self.source or "Unknown")
        out=self.base+".txt"
        with open(out,"w",encoding="utf-8") as f: f.write(template)
        Logger.success(f"PREZ créée : {out} ✅ ")

# ==========================
# MAIN
# ==========================
if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Release Manager")
    parser.add_argument("video_file", help="Fichier vidéo source")
    parser.add_argument("year", nargs="?", default=None, help="Année optionnelle")
    parser.add_argument("source", nargs="?", default="", help="Source (ex: WEB-DL)")
    parser.add_argument("--torrent", action="store_true", help="Créer un fichier .torrent")
    args = parser.parse_args()

    print_logo()
    manager = ReleaseManager(args.video_file, forced_year=args.year, source=args.source)
    manager.generate_nfo()
    manager.generate_tmdb_and_cover()
    if args.torrent:
        manager.generate_torrent()
    manager.generate_prez()
    Logger.success("🎬 RELEASE READY 🚀")
