import os
import subprocess
import requests
from pymediainfo import MediaInfo

# ------------------------------------------------
# Mappings
# ------------------------------------------------
# Mapping des langues
LANG_MAP = {
    "fr-fr": "French VFF",
    "fr-ca": "French VFQ",
    "en": "English"
}

# Mapping canaux audio
CHANNELS_MAP = {
    1: "1.0",
    2: "2.0",
    6: "5.1",
    8: "7.1"
}

# Mapping codecs audio
AUDIO_CODEC_MAP = {
    "A_AC3": "AC3",
    "A_EAC3": "E-AC3",
    "A_TRUEHD": "TrueHD",
    "A_DTS": "DTS",
    "A_DTS-HD": "DTS-HD",
    "A_DTS-HD MA": "DTS-HD MA",
    "A_AAC-2": "AAC LC",
    "A_OPUS": "OPUS",
    "A_ATMOS": "Dolby Atmos"
}

# Mapping codecs vidéo
VIDEO_CODEC_MAP = {
    "V_MPEGH/ISO/HEVC": "H265",
    "V_MPEG4/ISO/AVC": "H264",
    "V_MS/VFW/WVC1": "VC-1",
    "V_THEORA": "Theora",
    "V_AV1": "AV1"
}

VIDEO_PROFILE_MAP = {
    "2160p HDR": "2160p HDR",
    "2160p SDR": "2160p SDR",
    "HDR10": "HDR10",
    "DV": "HDR.DV",
    "1080p": "1080p",
    "720p": "720p",
}

# ------------------------------------------------
# Fonctions de formatage
# ------------------------------------------------
def format_video(track):
    if not track:
        return "N/A"

    codec = VIDEO_CODEC_MAP.get(getattr(track, "codec", ""), getattr(track, "codec", "Unknown"))
    width = getattr(track, "width", 0)
    height = getattr(track, "height", 0)
    framerate = getattr(track, "frame_rate", "N/A")
    bitrate = getattr(track, "bit_rate", None)
    bitrate_mbps = f"{int(bitrate)/1000/1000:.1f} Mb/s" if bitrate else "N/A"

    # Détection HDR/SDR/DV et résolution
    profile = ""
    color = getattr(track, "colour_primaries", "").lower()
    transfer = getattr(track, "colour_transfer", "").lower()

    if width >= 3840:  # 4K
        if "dolbyvision" in transfer:
            profile = VIDEO_PROFILE_MAP.get("DV", "2160p HDR")
        elif "bt2020" in color or "hdr10" in transfer:
            profile = VIDEO_PROFILE_MAP.get("2160p HDR", "2160p HDR")
        else:
            profile = VIDEO_PROFILE_MAP.get("2160p SDR", "2160p SDR")
    elif width >= 1920:
        profile = VIDEO_PROFILE_MAP.get("1080p", "1080p")
    elif width >= 1280:
        profile = VIDEO_PROFILE_MAP.get("720p", "720p")
    else:
        profile = f"{width}x{height}"

    return f"{codec} {profile} - {bitrate_mbps} - {framerate} FPS"

def format_audio(track):
    lang = LANG_MAP.get(track.language.lower(), track.language.upper() if track.language else "N/A")
    
    channels_raw = getattr(track, "channel_s", None) or getattr(track, "channels", None)
    if channels_raw:
        try:
            channels = CHANNELS_MAP.get(int(channels_raw), f"{channels_raw}.0")
        except:
            channels = str(channels_raw)
    else:
        channels = "N/A"
    
    codec_id = getattr(track, "codec_id", "")
    codec = AUDIO_CODEC_MAP.get(codec_id, getattr(track, "format", "N/A"))
    
    bitrate = getattr(track, "bit_rate", None)
    if bitrate:
        bitrate = int(int(bitrate)/1000)
    else:
        bitrate = "N/A"
    
    return f"{lang} [{channels}] {codec} ├¿ {bitrate} kb/s"

def format_subtitles(subtitle_tracks):
    """
    Formate les sous-titres en regroupant par langue et type (Forced / Full / SDH / CC)
    """
    SUB_MAP = {
        "fr-fr": "French VFF",
        "fr-ca": "French VFQ",
        "en": "English"
    }

    subs_dict = {}  # clé = (langue, type), valeur = codec

    for track in subtitle_tracks:
        lang = track.language.lower() if track.language else "unknown"
        lang_name = SUB_MAP.get(lang, lang)

        # Déterminer le type
        types = []
        if getattr(track, "forced", False):
            types.append("Forced")
        if getattr(track, "full", False):
            types.append("Full")
        if getattr(track, "sdh", False):
            types.append("SDH")
        if getattr(track, "cc", False):
            types.append("CC")
        type_str = "+".join(types) if types else "Unknown"

        key = (lang_name, type_str)
        subs_dict[key] = getattr(track, "codec", "S_TEXT/UTF8")

    # Formater proprement
    formatted_subs = []
    for (lang_name, type_str), codec in subs_dict.items():
        if type_str != "Unknown":
            formatted_subs.append(f"{lang_name} : ({type_str}) {codec}")
        else:
            formatted_subs.append(f"{lang_name} : {codec}")

    return "\n".join(formatted_subs)

# ------------------------------------------------
# Fonction TMDb manuelle
# ------------------------------------------------
TMDB_API_KEY = '044d34a6141458e59b6a7ffe909f0f3d'

def manual_tmdb_search(title):
    # Films
    url_movie = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}"
    movies = requests.get(url_movie).json().get("results", [])
    # Séries
    url_tv = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={title}"
    tvs = requests.get(url_tv).json().get("results", [])
    
    print(f"\nRésultats pour les films :")
    for idx, m in enumerate(movies, 1):
        release_date = m.get("release_date", "")
        print(f"{idx}. Film : {m['title']} [{release_date}] [https://www.themoviedb.org/movie/{m['id']}]")
    
    offset = len(movies)
    print(f"\nRésultats pour les séries :")
    for idx, s in enumerate(tvs, 1):
        release_date = s.get("first_air_date", "")
        print(f"{idx+offset}. Série : {s['name']} [{release_date}] [https://www.themoviedb.org/tv/{s['id']}]")
    
    choice = int(input("\nChoisissez un film ou une série en entrant son numéro : "))
    if choice <= len(movies):
        return f"https://www.themoviedb.org/movie/{movies[choice-1]['id']}"
    else:
        return f"https://www.themoviedb.org/tv/{tvs[choice - len(movies)-1]['id']}"

# ------------------------------------------------
# Génération NFO
# ------------------------------------------------
def generate_nfo(file_path, output_folder, platform_name):
    file_name = os.path.basename(file_path)
    nfo_path = os.path.join(output_folder, f"{file_name}.nfo")
    
    # Lecture du média
    media_info = MediaInfo.parse(file_path)
    
    # Vidéo
    video_track = next((t for t in media_info.tracks if t.track_type=="Video"), None)
    video_str = format_video(video_track) if video_track else "N/A"
    
    # Audio
    audio_tracks = [t for t in media_info.tracks if t.track_type=="Audio"]
    audio_strs = [format_audio(t) for t in audio_tracks]
    
    # Sous-titres
    subtitle_tracks = [t for t in media_info.tracks if t.track_type=="Text"]
    subtitle_strs = [format_subs(t) for t in subtitle_tracks]
    
    # Taille totale
    general_track = next((t for t in media_info.tracks if t.track_type=="General"), None)
    size = round(int(general_track.file_size)/1024/1024/1024,2) if general_track and getattr(general_track,"file_size",None) else "N/A"
    
    # Recherche TMDb manuelle
    title_for_search = input(f"Entrez le nom d'un film ou d'une série pour TMDb : ").strip()
    tmdb_link = manual_tmdb_search(title_for_search)
    
    # Génération du contenu
    nfo_content = f"""
### Informations supplémentaires ###
Source: {platform_name}
Uploader: TyHD
Date de la release: {general_track.recorded_date if general_track else 'N/A'}

Uploadeur TyHD since 2024-2025 - Team spécialisée dans le WEB-DL de films et séries.

Pour les demandes de contenu : TyHD-demande@proton.me
Plus d'infos : https://rentry.co/TyHD-Informations

                  -----  P R E S E N T S  -----

                           {tmdb_link}

Release : {file_name}
Source : {platform_name}
Vidéo : {video_str}
Audio :
{chr(10).join(audio_strs)}
Sous-titres :
{chr(10).join(subtitle_strs)}
Poids Total : {size} GiB

-------------------------------------------------------------
"""
    with open(nfo_path,"w",encoding="utf-8") as f:
        f.write(nfo_content)
    print(f"NFO généré : {nfo_path}")

# ------------------------------------------------
# Main
# ------------------------------------------------
def main():
    file_path = input("Chemin du fichier MKV : ").strip()
    output_folder = input("Dossier de sortie NFO : ").strip()
    platform_name = input("Nom plateforme : ").strip()
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    generate_nfo(file_path, output_folder, platform_name)

if __name__ == "__main__":
    main()
