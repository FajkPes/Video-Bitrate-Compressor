# -*- coding: utf-8 -*-
"""
Video Bitrate Compressor
------------------------
Dávkový překodér videí, který u každého souboru zjistí jeho vlastní (unikátní)
video bitrate a překóduje ho na zvolené procento originálu (výchozí 70 %).

Vyžaduje ffmpeg.exe + ffprobe.exe (hledá se vedle skriptu, pak v PATH).
"""

import os
import re
import sys
import json
import queue
import ctypes
import shutil
import subprocess
import threading
import time
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Video Bitrate Compressor"
APP_VER = "1.2.0"

HERE = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", HERE))
CONFIG_PATH = HERE / "vbc_settings.json"

# ------------------------------------------------------------ lokalizace ---
LANG = "en"                      # "cs" | "en"; English is the clean-install default
LANG_NAMES = {"cs": "Čeština", "en": "English"}

# klíč -> (čeština, angličtina)
S = {
    "subtitle": ("Každé video se překóduje na zvolené procento svého vlastního bitrate",
                 "Each video is re-encoded to a chosen percentage of its own bitrate"),
    "in_folder": ("Vstupní složka", "Source folder"),
    "out_folder": ("Výstupní složka", "Destination folder"),
    "browse": ("Procházet", "Browse"),
    "recurse": ("Včetně podsložek (zachovat strukturu)",
                "Include subfolders (keep structure)"),
    "ignore_dirs": ("Ignorovat složky:", "Skip folders:"),
    "ignore_hint": ("oddělené čárkou; výstupní složka se přeskakuje vždy",
                    "comma separated; the destination folder is always skipped"),
    "sec_convert": ("Nastavení převodu", "Video"),
    "br_mode": ("Režim bitrate", "Bitrate mode"),
    "target_br": ("Cílový bitrate", "Avg Bitrate"),
    "target_br_pct": ("Cílový bitrate (% originálu)", "Avg Bitrate (% of source)"),
    "fixed_br": ("Pevný bitrate", "Avg Bitrate (kbps)"),
    "max_br": ("Maximální bitrate", "Max Bitrate (kbps)"),
    "rounding": ("Zaokrouhlení bitrate", "Bitrate rounding"),
    "proc_mode": ("Co překódovat", "What to encode"),
    "audio_only_hint": ("● video se kopíruje beze ztráty, mění se jen zvuk",
                        "● video is copied losslessly, only audio changes"),
    "nothing_to_do": ("V režimu „pouze zvuk“ by se nic nezměnilo.\n\n"
                      "Zvol bitrate zvuku nebo zapni normalizaci.",
                      "Nothing would change in audio-only mode.\n\n"
                      "Pick an audio bitrate or enable normalization."),
    "audio_only_novideo": ("Zdroj nemá zvuk", "Source has no audio"),
    "encoder": ("Výstupní kodek / enkodér", "Video Encoder"),
    "depth": ("Bitová hloubka", "Bit Depth"),
    "preset": ("Preset (kvalita / rychlost)", "Encoder Preset"),
    "container": ("Výstupní kontejner", "Format"),
    "audio": ("Zvuk", "Audio"),
    "suffix": ("Přípona k názvu souboru", "Filename suffix"),
    "qname": ("Přidat bitrate do názvu (např. „video q10000.mp4“)",
              "Add bitrate to filename (e.g. \"video q10000.mp4\")"),
    "skip_bigger": ("Přeskočit, pokud by se soubor nezmenšil",
                    "Skip if the file would not get smaller"),
    "overwrite": ("Přepisovat bez ptaní", "Overwrite without asking"),
    "advanced_btn": ("Pokročilé nastavení kodeku…", "Encoder Options…"),
    "changes_vs_default": ("{} změn oproti výchozím", "{} changes from defaults"),
    "denoise_short": ("odšumění", "denoise"),
    # tlačítka
    "scan": ("Načíst složku", "Scan Folder"),
    "add_files": ("Přidat soubory…", "Add Files…"),
    "pick_files_title": ("Vyber videosoubory", "Select video files"),
    "ft_video": ("Videosoubory", "Video files"),
    "ft_all": ("Všechny soubory", "All files"),
    "added_n": ("Přidáno {} videí (celkem {})", "Added {} videos (total {})"),
    "no_new_files": ("Žádné nové videosoubory k přidání.",
                     "No new video files to add."),
    "skipped_nonvideo": (" · {} nevideo souborů přeskočeno",
                         " · {} non-video files skipped"),
    "drop_hint": ("Přetáhni sem videa nebo složky",
                  "Drag & drop videos or folders here"),
    "drop_hint2": ("…nebo použij „Načíst složku“ / „Přidat soubory…“",
                   "…or use \"Scan Folder\" / \"Add Files…\""),
    "drop_none": ("V přetažených položkách nejsou žádná nová videa.",
                  "No new videos among the dropped items."),
    "start": ("Spustit převod", "Start Encode"),
    "pause": ("Pozastavit", "Pause"),
    "resume": ("Pokračovat", "Resume"),
    "stop": ("Zastavit", "Stop Encode"),
    "open_out": ("Otevřít výstup", "Open Destination"),
    "clear": ("Vyčistit seznam", "Clear Queue"),
    # tabulka
    "col_src": ("Zdrojový soubor", "Source"),
    "col_res": ("Rozlišení", "Dimensions"),
    "col_dur": ("Délka", "Duration"),
    "col_obr": ("Původní bitrate", "Source Bitrate"),
    "col_tbr": ("Cílový bitrate", "Avg Bitrate"),
    "col_asrc": ("Zvuk zdroje", "Source Audio"),
    "col_aout": ("Zvuk výstupu", "Output Audio"),
    "col_out": ("Výstupní soubor", "Save As"),
    "same_as_src": ("= beze změny", "= unchanged"),
    "strip_tag": ("Odstranit původní značku z názvu (q…, a…)",
                  "Strip previous tag from filename (q…, a…)"),
    "col_prog": ("Průběh", "Progress"),
    "col_state": ("Stav", "Status"),
    # stavy
    "st_wait": ("Čeká", "Queued"),
    "st_run": ("▶ Převádím…", "▶ Encoding…"),
    "st_exists": ("⏭ Výstup už existuje", "⏭ Output already exists"),
    "st_nosmaller": ("⏭ Nezmenšilo by se", "⏭ Would not shrink"),
    "st_cancelled": ("■ Zrušeno", "■ Cancelled"),
    "st_partial": ("■ Zastaveno — uloženo nedokončené ({})",
                   "■ Stopped — partial saved ({})"),
    "partial_tag": (" (nedokončeno)", " (unfinished)"),
    "keep_partial": ("Při zastavení uložit rozdělaný soubor",
                     "Keep the partial file when stopping"),
    "confirm_stop_keep": ("Opravdu zastavit převod?\n\n"
                          "Rozpracovaný soubor se dokončí tak, aby šel přehrát, "
                          "a uloží se s poznámkou „nedokončeno“.",
                          "Really stop encoding?\n\n"
                          "The file in progress will be finalized so it stays "
                          "playable and saved marked as \"unfinished\"."),
    "finalizing": ("◐ Ukončuji zápis souboru…", "◐ Finalizing the file…"),
    # průběh
    "ready": ("Připraveno", "Ready"),
    "scanning": ("Načítám informace o souborech…", "Reading file information…"),
    "scanning_n": ("Načítám… {}/{}", "Scanning… {}/{}"),
    "scan_load": ("Načítání {}/{}", "Scanning {}/{}"),
    "loaded": ("Načteno {} videí", "Loaded {} videos"),
    "loaded_bad": (" ({} nečitelných)", " ({} unreadable)"),
    "total_progress": ("Celkový průběh", "Overall progress"),
    "remaining": ("zbývá", "left"),
    "elapsed": ("uplynulo", "elapsed"),
    "file_n": ("soubor {}/{}", "file {}/{}"),
    "saved": ("úspora {} ({} %)", "saved {} ({} %)"),
    "avg": ("prům.", "avg"),
    "summary": ("{} videí · {} · {} → odhad ~{}", "{} videos · {} · {} → est. ~{}"),
    "done": ("Hotovo ✓", "Finished ✓"),
    "stopped_by_user": ("Zastaveno uživatelem", "Stopped by user"),
    "detecting_enc": ("● zjišťuji enkodéry…", "● detecting encoders…"),
    "hw_accel": ("● HW akcelerace: {}", "● HW acceleration: {}"),
    "cpu_only": ("● pouze CPU enkodéry", "● CPU encoders only"),
    "unavailable": ("  (nedostupné)", "  (unavailable)"),
    # hlášky
    "no_ffmpeg": ("Nenalezen ffmpeg.exe / ffprobe.exe.\n\n"
                  "Ulož je do stejné složky jako tento skript, nebo je přidej do PATH.",
                  "ffmpeg.exe / ffprobe.exe not found.\n\n"
                  "Put them next to this script, or add them to PATH."),
    "pick_input": ("Vyber platnou vstupní složku.", "Select a valid input folder."),
    "pick_output": ("Vyber výstupní složku.", "Select an output folder."),
    "same_folder": ("Výstupní složka musí být jiná než vstupní.",
                    "The output folder must differ from the input folder."),
    "scan_first": ("Nejdřív načti videa tlačítkem „Načíst videa“.",
                   "Scan videos first using the \"Scan videos\" button."),
    "bad_fixed": ("Zadej platný pevný bitrate.\n\n"
                  "Např. „4000“ nebo „4000k“ = 4000 kb/s, „8M“ = 8 Mb/s.",
                  "Enter a valid fixed bitrate.\n\n"
                  "E.g. \"4000\" or \"4000k\" = 4000 kb/s, \"8M\" = 8 Mb/s."),
    "enc_unavailable": ("Enkodér {} se na tomto počítači nepodařilo inicializovat."
                        "\n\nPřesto spustit?",
                        "Encoder {} could not be initialised on this machine."
                        "\n\nStart anyway?"),
    "mkdir_fail": ("Nelze vytvořit výstupní složku:\n{}",
                   "Cannot create the output folder:\n{}"),
    "no_out_dir": ("Výstupní složka zatím neexistuje.",
                   "The output folder does not exist yet."),
    "would_hit_source": ("Převod byl zastaven — výstup by přepsal zdrojový soubor:\n\n{}"
                         "\n\nZměň výstupní složku, příponu nebo značku v názvu.",
                         "Encoding stopped — the output would overwrite a source file:"
                         "\n\n{}\n\nChange the destination folder, container or name tag."),
    "outside_out": ("Vnitřní kontrola: cíl leží mimo výstupní složku",
                    "Internal check: destination is outside the output folder"),
    "confirm_stop": ("Opravdu zastavit převod?\nRozpracovaný soubor bude smazán.",
                     "Really stop encoding?\nThe file in progress will be deleted."),
    "confirm_close": ("Převod běží. Opravdu ukončit?",
                      "Encoding is running. Really quit?"),
    "res_converted": ("Převedeno: {}", "Encoded: {}"),
    "res_skipped": ("Přeskočeno: {}", "Skipped: {}"),
    "res_errors": ("Chyb: {}", "Errors: {}"),
    "res_before": ("Původně: {}", "Before: {}"),
    "res_after": ("Nyní: {}", "After: {}"),
    "res_saved": ("Úspora: {} ({} %)", "Saved: {} ({} %)"),
    "pick_in_title": ("Vyber vstupní složku s videi", "Select the input folder with videos"),
    "pick_out_title": ("Vyber výstupní složku", "Select the output folder"),
    # kolize
    "coll_title": ("Soubory už ve výstupní složce existují",
                   "Files already exist in the output folder"),
    "coll_head": ("Ve výstupní složce už je {} souborů se stejným názvem",
                  "{} files with the same name already exist in the output folder"),
    "coll_sub": ("Vyber, co se s nimi má stát.", "Choose what should happen to them."),
    "coll_more": ("  … a dalších {}", "  … and {} more"),
    "coll_overwrite": ("Přepsat", "Overwrite"),
    "coll_skip": ("Přeskočit existující", "Skip existing"),
    "coll_rename": ("Uložit pod novým názvem", "Save under a new name"),
    "cancel": ("Zrušit", "Cancel"),
    # pokročilý dialog
    "adv_title": ("Pokročilé nastavení kodeku", "Encoder Options"),
    "adv_encoder": ("Enkodér: {}", "Video Encoder: {}"),
    "sec_profile": ("Profil kvality", "Quality Profile"),
    "prof_label": ("Profil", "Profile"),
    "prof_hint": ("profil nastaví všechny volby níž najednou; režim datového toku zůstává",
                  "a profile sets every option below at once; rate control is left alone"),
    "prof_speed": ("● rychlostní preset: {}", "● speed preset: {}"),
    "sec_rc": ("Řízení datového toku", "Quality"),
    "adv_mode": ("Režim", "Rate Control"),
    "adv_cq": ("Kvalita CQ / CRF", "Constant Quality (CQ / RF)"),
    "adv_cq_hint": ("nižší číslo = vyšší kvalita a větší soubor",
                    "lower value = higher quality, larger file"),
    "adv_maxrate": ("Maxrate (× cíl)", "Peak Bitrate (× avg)"),
    "adv_bufsize": ("Buffer (× cíl)", "VBV Buffer (× avg)"),
    "adv_multipass": ("Vícenásobný průchod", "Multipass Encoding"),
    "sec_gop": ("Struktura snímků", "Frame Structure"),
    "adv_gop": ("Interval klíč. snímků", "Keyframe Interval (GOP)"),
    "adv_gop_hint": ("0 = automaticky (podle FPS)", "0 = automatic (based on framerate)"),
    "adv_bframes": ("B-snímky", "B-Frames"),
    "adv_bref": ("B-snímky jako reference", "B-Frame Reference Mode"),
    "adv_lookahead": ("Lookahead (snímků)", "Lookahead (frames)"),
    "sec_aq": ("Adaptivní kvantizace a profil", "Adaptive Quantization & Profile"),
    "adv_saq": ("Prostorová AQ (spatial AQ)", "Spatial AQ"),
    "adv_aqs": ("Síla AQ", "AQ Strength"),
    "adv_taq": ("Časová AQ (temporal AQ)", "Temporal AQ"),
    "adv_wp": ("Vážená predikce (vypne B-snímky)",
               "Weighted Prediction (disables B-Frames)"),
    "adv_tune": ("Ladění (tune)", "Encoder Tune"),
    "adv_level": ("Úroveň (level)", "Encoder Level"),
    "adv_tier": ("High tier", "High Tier"),
    "sec_image": ("Obraz", "Dimensions & Filters"),
    "adv_scale": ("Rozlišení", "Resolution"),
    "adv_scale_hint": ("zmenšuje se jen směrem dolů, poměr stran zůstává",
                       "downscale only, aspect ratio preserved"),
    "adv_cw": ("Vlastní šířka", "Custom Width"),
    "adv_ch": ("Vlastní výška", "Custom Height"),
    "adv_custom_hint": ("0 = dopočítat podle poměru stran",
                        "0 = keep aspect ratio"),
    "adv_fps": ("Snímková frekvence", "Framerate (FPS)"),
    "adv_rotate": ("Otočení / orientace", "Rotate / Flip"),
    "adv_denoise": ("Odšumění", "Denoise"),
    "adv_deint": ("Odstranit prokládání (deinterlace)", "Deinterlace"),
    "sec_perf": ("Výkon", "Performance"),
    "adv_hwaccel": ("Hardwarové dekódování vstupu", "Hardware Decoding"),
    "adv_threads": ("Vlákna (0 = auto)", "Threads (0 = auto)"),
    "sec_expert": ("Expertní parametry", "Advanced Options"),
    "adv_x265": ("x265/x264 params", "x265/x264 Options"),
    "adv_x265_hint": ("např. aq-mode=3:psy-rd=2.0", "e.g. aq-mode=3:psy-rd=2.0"),
    "adv_extra": ("Vlastní ffmpeg volby", "Extra ffmpeg Options"),
    "adv_extra_hint": ("vloží se před výstupní soubor, např. -g 250 -refs 4",
                       "inserted before the output file, e.g. -g 250 -refs 4"),
    "adv_reset": ("Obnovit výchozí", "Reset Defaults"),
    "adv_apply": ("Použít", "Apply"),
    # pokročilý zvuk
    "audio_btn": ("Pokročilé nastavení zvuku…", "Audio Options…"),
    "aud_title": ("Pokročilé nastavení zvuku", "Audio Options"),
    "sec_acodec": ("Kodek", "Audio Codec"),
    "aud_codec": ("Kodek", "Codec"),
    "aud_codec_hint": ("bitrate se nastavuje v hlavním okně",
                       "bitrate is set in the main window"),
    "aud_channels": ("Kanály", "Mixdown"),
    "aud_rate": ("Vzorkovací frekvence", "Samplerate"),
    "sec_atracks": ("Zvukové stopy", "Audio Tracks"),
    "aud_tracks": ("Které stopy převést", "Tracks to encode"),
    "aud_tracks_hint": ("výchozí zachová všechny stopy i jejich pořadí a jazyky",
                        "the default keeps every track, its order and language"),
    "sec_norm": ("Normalizace hlasitosti", "Loudness Normalization"),
    "aud_norm": ("Režim", "Mode"),
    "aud_lufs": ("Cílová hlasitost (LUFS)", "Target loudness (LUFS)"),
    "aud_tp": ("Max. true peak (dBTP)", "Max true peak (dBTP)"),
    "aud_lra": ("Rozsah hlasitosti (LRA)", "Loudness range (LRA)"),
    "aud_norm_hint": ("normalizace vždy vyžaduje překódování stopy",
                      "normalization always re-encodes the track"),
    "sec_atime": ("Časování", "Timing"),
    "aud_offset": ("Posun zvuku (ms)", "Audio offset (ms)"),
    "aud_offset_hint": ("kladné = zvuk později, záporné = dřív",
                        "positive = audio later, negative = earlier"),
    "aud_forced": ("● překódování vynuceno nastavením",
                   "● re-encode forced by settings"),
    "mp4_audio_warn": ("Kodek {} se do kontejneru MP4 nehodí.\n\n"
                       "Přepnout výstup na MKV?",
                       "Codec {} is a poor fit for the MP4 container.\n\n"
                       "Switch output to MKV?"),
    "st_measuring": ("◐ Měřím hlasitost…", "◐ Analyzing loudness…"),
    # probe
    "err_probe": ("ffprobe selhal", "ffprobe failed"),
    "err_novideo": ("neobsahuje video stopu", "contains no video track"),
    "src_track": ("stopa", "track"),
    "src_tag": ("tag", "tag"),
    "src_est": ("odhad", "estimate"),
}


def L(key, *args):
    """Přeloží klíč do aktuálního jazyka."""
    pair = S.get(key)
    if pair is None:
        return key
    txt = pair[0 if LANG == "cs" else 1]
    return txt.format(*args) if args else txt


def loc(d):
    """Z dvojjazyčného slovníku udělá {klíč: text v aktuálním jazyce}."""
    i = 0 if LANG == "cs" else 1
    return {k: v[i] for k, v in d.items()}


def rev(d, text, fallback):
    """Z lokalizovaného textu zpět na klíč."""
    for k, v in loc(d).items():
        if v == text:
            return k
    return fallback

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".ts", ".m2ts", ".mts",
              ".webm", ".wmv", ".flv", ".mpg", ".mpeg", ".vob", ".3gp", ".ogv"}

# ---------------------------------------------------------------- palette ---
C = {
    "bg":        "#14161b",
    "panel":     "#1c1f27",
    "panel_hi":  "#232733",
    "border":    "#2f3543",
    "border_hi": "#3d4557",
    "text":      "#e8eaf0",
    "muted":     "#8b93a7",
    "dim":       "#5f6779",
    "accent":    "#4f8cff",
    "accent_dk": "#2f6fe0",
    "green":     "#2ecc71",
    "amber":     "#f0a12e",
    "red":       "#ef4d4d",
    "track":     "#2a2f3b",
}

FONT = "Segoe UI"
F_BASE = (FONT, 9)
F_SMALL = (FONT, 8)
F_BOLD = (FONT, 9, "bold")
F_TITLE = (FONT, 15, "bold")
F_MONO = ("Consolas", 9)


# ------------------------------------------------------------ ffmpeg tools --
def find_tool(name):
    exe = name + (".exe" if os.name == "nt" else "")
    local = HERE / exe
    if local.exists():
        return str(local)
    found = shutil.which(name)
    return found


FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def run_hidden(cmd, **kw):
    kw.setdefault("stdout", subprocess.PIPE)
    kw.setdefault("stderr", subprocess.PIPE)
    kw.setdefault("creationflags", CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kw)


# ------------------------------------------------------------ drag & drop --
# Nativní DnD zajišťuje rozšíření tkdnd (balík tkinterdnd2). Leží ve složce
# „libs“ vedle skriptu, takže se nemusí nic instalovat a složka je přenosná.
# Vlastní okenní procedura přes ctypes tu byla dřív, ale Python 3.14 na ní
# tvrdě padá (callback z Windows do Pythonu v době, kdy Tcl drží uvolněný GIL).
sys.path.insert(0, str(RESOURCE_DIR / "libs"))
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception:
    TkinterDnD = None
    DND_FILES = "DND_Files"


# --------------------------------------------------------- encoder presets --
# key -> (label, codec, container-tag, presets, supports_10bit, kind)
ENCODERS = {
    "hevc_nvenc": dict(label="HEVC (H.265) · NVENC — GPU", codec="hevc_nvenc",
                       presets=["p1", "p2", "p3", "p4", "p5", "p6", "p7"], default_preset="p5",
                       ten_bit=True, hw=True),
    "h264_nvenc": dict(label="H.264 · NVENC — GPU", codec="h264_nvenc",
                       presets=["p1", "p2", "p3", "p4", "p5", "p6", "p7"], default_preset="p5",
                       ten_bit=False, hw=True),
    "av1_nvenc":  dict(label="AV1 · NVENC — GPU (RTX 40+)", codec="av1_nvenc",
                       presets=["p1", "p2", "p3", "p4", "p5", "p6", "p7"], default_preset="p5",
                       ten_bit=True, hw=True),
    "hevc_qsv":   dict(label="HEVC · QuickSync — Intel GPU", codec="hevc_qsv",
                       presets=["veryfast", "faster", "fast", "medium", "slow", "slower"],
                       default_preset="slow", ten_bit=True, hw=True),
    "hevc_amf":   dict(label="HEVC · AMF — AMD GPU", codec="hevc_amf",
                       presets=["speed", "balanced", "quality"], default_preset="quality",
                       ten_bit=True, hw=True),
    "libx265":    dict(label="HEVC (H.265) · x265 — CPU", codec="libx265",
                       presets=["ultrafast", "superfast", "veryfast", "faster", "fast",
                                "medium", "slow", "slower", "veryslow"],
                       default_preset="medium", ten_bit=True, hw=False),
    "libx264":    dict(label="H.264 · x264 — CPU", codec="libx264",
                       presets=["ultrafast", "superfast", "veryfast", "faster", "fast",
                                "medium", "slow", "slower", "veryslow"],
                       default_preset="medium", ten_bit=True, hw=False),
}

PRESET_HINT = {
    "p1": ("p1 — nejrychlejší", "p1 — fastest"),
    "p2": ("p2 — velmi rychlý", "p2 — very fast"),
    "p3": ("p3 — rychlý", "p3 — fast"),
    "p4": ("p4 — vyvážený", "p4 — balanced"),
    "p5": ("p5 — kvalitní (doporučeno)", "p5 — quality (recommended)"),
    "p6": ("p6 — pomalý", "p6 — slow"),
    "p7": ("p7 — nejpomalejší / nejlepší", "p7 — slowest / best"),
}

# ------------------------------------------------- pokročilé nastavení -----
RC_MODES = {
    "vbr": ("Průměrný bitrate (VBR) — doporučeno",
            "Average bitrate (VBR) — recommended"),
    "cbr": ("Konstantní bitrate (CBR)", "Constant bitrate (CBR)"),
    "cq":  ("Konstantní kvalita (CQ / CRF) — bitrate se ignoruje",
            "Constant quality (CQ / CRF) — bitrate is ignored"),
}

MULTIPASS = {
    "fullres": ("Dvouprůchodové, plné rozlišení (nejpřesnější)",
                "Two-pass, full resolution (most accurate)"),
    "qres":    ("Dvouprůchodové, čtvrtinové rozlišení (rychlejší)",
                "Two-pass, quarter resolution (faster)"),
    "disabled": ("Vypnuto (nejrychlejší)", "Disabled (fastest)"),
}

BREF_MODES = {
    "middle": ("Prostřední B-snímek jako reference", "Middle B-frame as reference"),
    "each":   ("Každý B-snímek jako reference", "Each B-frame as reference"),
    "disabled": ("Vypnuto", "Disabled"),
}

TUNE_NVENC = {"hq": ("Vysoká kvalita", "High quality"),
              "uhq": ("Nejvyšší kvalita (UHQ)", "Ultra high quality (UHQ)"),
              "ll": ("Nízká latence", "Low latency"),
              "ull": ("Ultra nízká latence", "Ultra low latency")}
TUNE_X265 = {"none": ("Žádné", "None"),
             "grain": ("Zachovat filmové zrno", "Preserve film grain"),
             "animation": ("Animace / kreslené", "Animation / cartoons"),
             "psnr": ("PSNR", "PSNR"), "ssim": ("SSIM", "SSIM"),
             "fastdecode": ("Rychlé dekódování", "Fast decode")}

SCALES = {
    "orig": ("Původní rozlišení (beze změny)", "Original resolution (unchanged)"),
    "2160": ("4K UHD — 2160p", "4K UHD — 2160p"),
    "1440": ("QHD — 1440p", "QHD — 1440p"),
    "1080": ("Full HD — 1080p", "Full HD — 1080p"),
    "720":  ("HD — 720p", "HD — 720p"),
    "480":  ("SD — 480p", "SD — 480p"),
    "custom": ("Vlastní rozměry…", "Custom size…"),
}
SCALE_H = {"2160": 2160, "1440": 1440, "1080": 1080, "720": 720, "480": 480}

FPS_OPTS = {"orig": ("Původní (beze změny)", "Original (unchanged)"),
            "60": ("60", "60"), "50": ("50", "50"), "30": ("30", "30"),
            "25": ("25", "25"), "24": ("24", "24")}

ROTATE = {
    "none":      ("Beze změny", "Unchanged"),
    "landscape": ("Vynutit na šířku (landscape)", "Force landscape"),
    "portrait":  ("Vynutit na výšku (portrait)", "Force portrait"),
    "90cw":      ("Otočit o 90° doprava", "Rotate 90° clockwise"),
    "90ccw":     ("Otočit o 90° doleva", "Rotate 90° counter-clockwise"),
    "180":       ("Otočit o 180°", "Rotate 180°"),
    "hflip":     ("Převrátit vodorovně", "Flip horizontally"),
    "vflip":     ("Převrátit svisle", "Flip vertically"),
}

DENOISE = {"none": ("Vypnuto", "Disabled"), "light": ("Slabé", "Light"),
           "medium": ("Střední", "Medium"), "strong": ("Silné", "Strong")}
DENOISE_ARGS = {"light": "1:1:6:6", "medium": "3:2:8:6", "strong": "6:4:12:9"}

LEVELS_HEVC = ["auto", "3", "3.1", "4", "4.1", "5", "5.1", "5.2", "6", "6.1", "6.2"]
LEVELS_H264 = ["auto", "3", "3.1", "4", "4.1", "4.2", "5", "5.1", "5.2", "6", "6.2"]

ADV_DEFAULTS = dict(
    rc_mode="vbr",
    cq=26.0,
    maxrate_mult=1.5,
    bufsize_mult=2.0,
    multipass="fullres",
    lookahead=32,
    bframes=3,
    bref="middle",
    spatial_aq=True,
    aq_strength=8,
    temporal_aq=True,
    gop=0,                 # 0 = automaticky (ffmpeg default)
    tune="hq",
    tune_x265="none",
    level="auto",
    tier_high=True,
    weighted_pred=False,
    x265_params="",
    extra_args="",
    hwaccel=True,
    scale="orig",
    scale_w=0,
    scale_h=0,
    fps="orig",
    rotate="none",
    denoise="none",
    deinterlace=False,
    threads=0,
)

# ------------------------------------------------------- profily kvality ---
# Profil nastaví najednou všechny „kvalitativní“ volby + rychlostní preset.
# Záměrně nesahá na režim datového toku (rc_mode) ani na obraz (scale/fps/…),
# aby procentní režim bitrate zůstal tím, co uživatel zvolil v hlavním okně.
QUALITY_PROFILES = {
    "turbo":     ("Ultra rychlý — nejrychlejší, nižší kvalita",
                  "Ultra fast — fastest, lower quality"),
    "handbrake": ("Jako HandBrake — stejný kompromis jako výchozí HandBrake",
                  "HandBrake-like — same trade-off as HandBrake's default"),
    "balanced":  ("Vyvážený — dosavadní výchozí nastavení této aplikace",
                  "Balanced — this app's existing default"),
    "ultra":     ("Ultra kvalita — nejpomalejší, nejlepší obraz",
                  "Ultra quality — slowest, best picture"),
    "custom":    ("Vlastní — ručně upravené", "Custom — hand-tweaked"),
}

# hodnoty, které profil přepíše (klíče musí existovat v ADV_DEFAULTS)
PROFILE_ADV = {
    "turbo": dict(cq=30.0, maxrate_mult=1.3, bufsize_mult=1.5, multipass="disabled",
                  lookahead=0, bframes=0, bref="disabled", spatial_aq=False,
                  aq_strength=8, temporal_aq=False, tune="hq", tune_x265="none",
                  weighted_pred=False, tier_high=True),
    "handbrake": dict(cq=22.0, maxrate_mult=1.5, bufsize_mult=2.0, multipass="disabled",
                      lookahead=0, bframes=3, bref="middle", spatial_aq=False,
                      aq_strength=8, temporal_aq=False, tune="hq", tune_x265="none",
                      weighted_pred=False, tier_high=True),
    "balanced": dict(cq=26.0, maxrate_mult=1.5, bufsize_mult=2.0, multipass="fullres",
                     lookahead=32, bframes=3, bref="middle", spatial_aq=True,
                     aq_strength=8, temporal_aq=True, tune="hq", tune_x265="none",
                     weighted_pred=False, tier_high=True),
    "ultra": dict(cq=20.0, maxrate_mult=2.0, bufsize_mult=3.0, multipass="fullres",
                  lookahead=48, bframes=4, bref="each", spatial_aq=True,
                  aq_strength=12, temporal_aq=True, tune="hq", tune_x265="none",
                  weighted_pred=False, tier_high=True),
}

# rychlostní preset v hlavním okně podle rodiny enkodéru
PROFILE_SPEED = {
    "turbo":     dict(nvenc="p1", qsv="veryfast", amf="speed", x26x="veryfast"),
    "handbrake": dict(nvenc="p4", qsv="medium", amf="balanced", x26x="medium"),
    "balanced":  dict(nvenc="p5", qsv="slow", amf="quality", x26x="medium"),
    "ultra":     dict(nvenc="p7", qsv="slower", amf="quality", x26x="slow"),
}


def enc_family(key):
    return ("nvenc" if key.endswith("_nvenc") else
            "qsv" if key.endswith("_qsv") else
            "amf" if key.endswith("_amf") else "x26x")


def detect_profile(adv):
    """Zjistí, kterému profilu odpovídají aktuální hodnoty (jinak „custom“)."""
    for name, over in PROFILE_ADV.items():
        for k, want in over.items():
            have = adv.get(k, ADV_DEFAULTS[k])
            if isinstance(want, float):
                if abs(float(have) - want) > 0.01:
                    break
            elif isinstance(want, bool):
                if bool(have) != want:
                    break
            elif isinstance(want, int):
                if int(have) != want:
                    break
            elif have != want:
                break
        else:
            return name
    return "custom"


BR_MODES = {
    "pct": ("Procento z původního bitrate", "Percentage of original bitrate"),
    "fix": ("Pevný bitrate pro všechna videa", "Fixed bitrate for all videos"),
    "cap": ("Pevný bitrate jako strop (nižší ponechat)",
            "Fixed bitrate as a cap (keep lower ones)"),
}

PROC_MODES = {
    "both":  ("Video i zvuk — překódovat vše", "Video + audio — encode both"),
    "audio": ("Pouze zvuk — video zkopírovat beze změny",
              "Audio only — passthru video"),
}

CONTAINERS = {
    "auto": ("Jako zdroj", "Same as source"),
    "mp4":  ("MP4", "MP4"),
    "mkv":  ("MKV", "MKV"),
}

ROUNDING = {
    "100":  ("Na stovky — např. 64700 (doporučeno)",
             "To hundreds — e.g. 64700 (recommended)"),
    "1000": ("Na tisíce — např. 65000", "To thousands — e.g. 65000"),
    "off":  ("Vypnuto — přesná hodnota", "Off — exact value"),
}


def round_bitrate(bps, mode):
    """Zaokrouhlí bitrate (bit/s) na stovky / tisíce kb/s."""
    if bps <= 0 or mode == "off":
        return bps
    try:
        step = int(mode)
    except ValueError:
        return bps
    kb = bps / 1000.0
    # u malých bitratů by hrubý krok utrhl příliš velkou část, proto minimum
    return max(round(kb / step) * step, step) * 1000.0


AUDIO_BITRATES = ["16", "32", "48", "64", "80", "96", "112", "128",
                  "160", "192", "224", "256", "320"]

AUDIO_MODES = {
    "copy": ("Zkopírovat beze změny (doporučeno)", "Passthru (recommended)"),
    **{b: (f"{b} kb/s", f"{b} kbps") for b in AUDIO_BITRATES},
    "custom": ("Vlastní bitrate…", "Custom bitrate…"),
    "none": ("Bez zvuku", "No audio"),
}

# ------------------------------------------------- pokročilé zvuk ----------
AUDIO_CODECS = {
    "same":       ("Jako v originálu — zachovat kodek i bitrate",
                   "Same as source — keep codec and bitrate"),
    "aac":        ("AAC — nejkompatibilnější", "AAC — most compatible"),
    "libopus":    ("Opus — nejlepší při nízkém bitrate",
                   "Opus — best at low bitrates"),
    "libmp3lame": ("MP3", "MP3"),
    "ac3":        ("Dolby Digital (AC-3)", "Dolby Digital (AC-3)"),
    "eac3":       ("Dolby Digital Plus (E-AC-3)", "Dolby Digital Plus (E-AC-3)"),
    "libvorbis":  ("Vorbis", "Vorbis"),
    "flac":       ("FLAC — bezztrátový", "FLAC — lossless"),
}

# kodeky, které se do MP4 nehodí (ffmpeg je odmítne nebo je nikdo nepřehraje)
AUDIO_MP4_BAD = {"libvorbis", "flac"}

# zdrojový kodek -> enkodér, kterým ho lze vyrobit znovu (režim „jako v originálu“)
SRC_TO_ENCODER = {
    "aac": "aac", "ac3": "ac3", "eac3": "eac3", "mp3": "libmp3lame",
    "opus": "libopus", "vorbis": "libvorbis", "flac": "flac", "alac": "alac",
    "pcm_s16le": "pcm_s16le", "pcm_s24le": "pcm_s24le",
}
# kodeky bez datového toku (bezztrátové) — -b:a se u nich nepoužívá
AUDIO_LOSSLESS = {"flac", "alac", "pcm_s16le", "pcm_s24le"}

AUDIO_TRACKS = {
    "all":   ("Všechny stopy jako v originálu", "All tracks, as in source"),
    "first": ("Pouze první stopu", "First track only"),
}

AUDIO_CHANNELS = {
    "orig": ("Jako v originálu", "Same as source"),
    "1": ("Mono", "Mono"), "2": ("Stereo", "Stereo"),
    "6": ("5.1", "5.1"), "8": ("7.1", "7.1"),
}

AUDIO_RATES = {
    "orig": ("Jako v originálu", "Same as source"),
    "48000": ("48 kHz", "48 kHz"), "44100": ("44,1 kHz", "44.1 kHz"),
}

NORMALIZE = {
    "off":        ("Vypnuto", "Off"),
    "r128_2pass": ("EBU R128 — přesná (dvouprůchodová)",
                   "EBU R128 — accurate (two-pass)"),
    "r128":       ("EBU R128 — rychlá (jednoprůchodová)",
                   "EBU R128 — fast (single-pass)"),
}

ADV_A_DEFAULTS = dict(
    codec="aac",
    tracks="all",
    channels="orig",
    samplerate="orig",
    normalize="off",
    lufs=-14.0,
    tpeak=-1.0,
    lra=11.0,
    offset_ms=0,
)


# ------------------------------------------------------------- media probe --
class NotAVideo(Exception):
    """Soubor sice má videopříponu, ale neobsahuje použitelnou video stopu."""


def probe(path):
    """Vrátí dict s údaji o souboru nebo vyhodí RuntimeError."""
    cmd = [FFPROBE, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    r = run_hidden(cmd)
    if r.returncode != 0 or not r.stdout:
        raise NotAVideo(L("err_probe"))
    try:
        data = json.loads(r.stdout.decode("utf-8", "replace"))
    except ValueError:
        raise NotAVideo(L("err_probe"))

    streams = data.get("streams", [])
    fmt = data.get("format", {})
    v = next((s for s in streams if s.get("codec_type") == "video"
              and s.get("disposition", {}).get("attached_pic", 0) == 0), None)
    if v is None:
        raise NotAVideo(L("err_novideo"))

    audios = [s for s in streams if s.get("codec_type") == "audio"]

    def fnum(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    duration = fnum(v.get("duration")) or fnum(fmt.get("duration"))
    size = fnum(fmt.get("size")) or (os.path.getsize(path) if os.path.exists(path) else 0)

    # --- video bitrate: 1) stopa  2) kontejner mínus audio  3) velikost/čas ---
    vb = fnum(v.get("bit_rate"))
    src = L("src_track")
    if vb <= 0:
        tags = {k.lower(): val for k, val in (v.get("tags") or {}).items()}
        vb = fnum(tags.get("bps") or tags.get("bps-eng"))
        if vb > 0:
            src = L("src_tag")
    if vb <= 0:
        total = fnum(fmt.get("bit_rate"))
        if total <= 0 and duration > 0 and size > 0:
            total = size * 8.0 / duration
        ab = sum(fnum(a.get("bit_rate")) for a in audios)
        if ab <= 0 and audios:
            ab = 128000.0 * len(audios)          # hrubý odhad
        if total > 0:
            vb = max(total - ab, total * 0.5)
            src = L("src_est")

    fps = 0.0
    m = re.match(r"^(\d+)/(\d+)$", v.get("avg_frame_rate") or v.get("r_frame_rate") or "")
    if m and int(m.group(2)):
        fps = int(m.group(1)) / int(m.group(2))

    return dict(
        width=int(v.get("width") or 0),
        height=int(v.get("height") or 0),
        codec=v.get("codec_name") or "?",
        pix_fmt=v.get("pix_fmt") or "",
        duration=duration,
        size=int(size),
        fps=fps,
        vbitrate=vb,             # bit/s
        bsource=src,
        naudio=len(audios),
        acodec=(audios[0].get("codec_name") if audios else ""),
        astreams=[dict(codec=a.get("codec_name") or "?",
                       channels=int(a.get("channels") or 0),
                       rate=int(fnum(a.get("sample_rate"))),
                       lang=((a.get("tags") or {}).get("language") or ""),
                       bitrate=fnum(a.get("bit_rate")))
                  for a in audios],
    )


def human_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024.0


def human_time(sec):
    if sec is None or sec <= 0 or sec != sec or sec == float("inf"):
        return "--:--"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def kbps(bits_per_sec):
    if not bits_per_sec:
        return "—"
    k = bits_per_sec / 1000.0
    return f"{k/1000:.2f} Mb/s" if k >= 1000 else f"{k:.0f} kb/s"


def parse_ff_time(s):
    m = re.match(r"(-?\d+):(\d{2}):(\d{2})(?:\.(\d+))?", s or "")
    if not m:
        return None
    h, mi, se = int(m.group(1)), int(m.group(2)), int(m.group(3))
    frac = float("0." + m.group(4)) if m.group(4) else 0.0
    return h * 3600 + mi * 60 + se + frac


# ---------------------------------------------------------- suspend/resume --
def _proc_suspend_resume(pid, resume=False):
    if os.name != "nt":
        return False
    try:
        PROCESS_SUSPEND_RESUME = 0x0800
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        h = k32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
        if not h:
            return False
        try:
            fn = ntdll.NtResumeProcess if resume else ntdll.NtSuspendProcess
            fn(h)
        finally:
            k32.CloseHandle(h)
        return True
    except Exception:
        return False


# =============================================================== UI widgets ==
class RoundBar(tk.Canvas):
    """Zaoblený progress bar s volitelným popiskem uvnitř."""

    def __init__(self, master, height=22, radius=None, color=C["accent"],
                 track=C["track"], show_text=True, **kw):
        super().__init__(master, height=height, bg=C["panel"], highlightthickness=0,
                         bd=0, **kw)
        self.h = height
        self.r = radius if radius is not None else height / 2
        self.color = color
        self.track = track
        self.show_text = show_text
        self._value = 0.0
        self._label = ""
        self.bind("<Configure>", lambda e: self._redraw())

    def set(self, value, label=""):
        self._value = max(0.0, min(1.0, float(value)))
        self._label = label
        self._redraw()

    def set_color(self, color):
        self.color = color
        self._redraw()

    def _rr(self, x1, y1, x2, y2, r, fill):
        if x2 - x1 < 1:
            return
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, splinesteps=16, fill=fill, outline=fill)

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        self._rr(0, 0, w, self.h, self.r, self.track)
        fw = w * self._value
        if fw > 2:
            self._rr(0, 0, fw, self.h, self.r, self.color)
        if self.show_text:
            txt = self._label or f"{self._value*100:.1f} %"
            self.create_text(w / 2, self.h / 2 + 1, text=txt, fill=C["text"],
                             font=(FONT, max(8, int(self.h * 0.42)), "bold"))


class Card(tk.Frame):
    """Panel s rámečkem a nadpisem."""

    def __init__(self, master, title=None, **kw):
        super().__init__(master, bg=C["panel"], highlightbackground=C["border"],
                         highlightthickness=1, bd=0, **kw)
        if title:
            tk.Label(self, text=title.upper(), bg=C["panel"], fg=C["dim"],
                     font=(FONT, 8, "bold")).pack(anchor="w", padx=12, pady=(9, 0))


class FlowFrame(tk.Frame):
    """Řádek, který při zúžení okna zalomí své prvky na další řádky.

    Prvky se vytvářejí s tímhle rámečkem jako rodičem a přidávají metodou
    add(); rozmístění se přepočítá při každé změně šířky, takže se nikdy
    nepřekrývají ani neuříznou.
    """

    def __init__(self, master, hgap=24, vgap=8, **kw):
        super().__init__(master, bg=master["bg"], **kw)
        self._items = []
        self._hgap, self._vgap = hgap, vgap
        self._lastw = -1
        self.bind("<Configure>", lambda e: self._layout(e.width))

    def add(self, widget, gap=None):
        self._items.append((widget, self._hgap if gap is None else gap))
        self.after_idle(self._relayout)
        return widget

    def _relayout(self):
        self._lastw = -1
        self._layout(self.winfo_width())

    def _layout(self, width):
        if width <= 1 or width == self._lastw:
            return
        self._lastw = width
        x = y = rowh = 0
        for widget, gap in self._items:
            ww, wh = widget.winfo_reqwidth(), widget.winfo_reqheight()
            if x and x + ww > width:
                x, y, rowh = 0, y + rowh + self._vgap, 0
            widget.place(x=x, y=y)
            x += ww + gap
            rowh = max(rowh, wh)
        self.configure(height=y + rowh)


class FlatButton(tk.Frame):
    """Plochý tlačítkový widget s hover efektem (tk.Button na Windows nejde nastylovat)."""

    def __init__(self, master, text, command, kind="normal", width=None, icon=""):
        styles = {
            "primary": (C["accent"], C["accent_dk"], "#ffffff"),
            "normal":  (C["panel_hi"], C["border_hi"], C["text"]),
            "danger":  ("#3a2226", "#5c2b30", "#ff8f8f"),
            "ghost":   (C["panel"], C["panel_hi"], C["muted"]),
        }
        self.bg, self.hbg, self.fg = styles.get(kind, styles["normal"])
        super().__init__(master, bg=self.bg, highlightbackground=C["border"],
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self._enabled = True
        label = f"{icon}  {text}" if icon else text
        self.lbl = tk.Label(self, text=label, bg=self.bg, fg=self.fg, font=F_BOLD,
                            padx=14, pady=7, cursor="hand2")
        if width:
            self.lbl.configure(width=width)
        self.lbl.pack(fill="both", expand=True)
        for w in (self, self.lbl):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _on_enter(self, _=None):
        if self._enabled:
            self.configure(bg=self.hbg)
            self.lbl.configure(bg=self.hbg)

    def _on_leave(self, _=None):
        if self._enabled:
            self.configure(bg=self.bg)
            self.lbl.configure(bg=self.bg)

    def _on_click(self, _=None):
        if self._enabled and self.command:
            self.command()

    def set_enabled(self, on):
        self._enabled = bool(on)
        if on:
            self.configure(bg=self.bg)
            self.lbl.configure(bg=self.bg, fg=self.fg, cursor="hand2")
            self.configure(cursor="hand2")
        else:
            self.configure(bg=C["panel"], cursor="")
            self.lbl.configure(bg=C["panel"], fg=C["dim"], cursor="")

    def set_text(self, text, icon=""):
        self.lbl.configure(text=f"{icon}  {text}" if icon else text)


class CollisionDialog(tk.Toplevel):
    """Upozornění, že ve výstupní složce už některé soubory existují."""

    def __init__(self, master, names, on_choice):
        super().__init__(master)
        self.title(L("coll_title"))
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.transient(master)
        self.choice = None
        self.on_choice = on_choice

        root = tk.Frame(self, bg=C["bg"])
        root.pack(fill="both", expand=True, padx=16, pady=14)

        head = tk.Frame(root, bg=C["bg"])
        head.pack(fill="x")
        tk.Label(head, text="⚠", bg=C["bg"], fg=C["amber"],
                 font=(FONT, 22)).pack(side="left", padx=(0, 12))
        txt = tk.Frame(head, bg=C["bg"])
        txt.pack(side="left", fill="x", expand=True)
        tk.Label(txt, text=L("coll_head", len(names)), bg=C["bg"], fg=C["text"],
                 font=(FONT, 11, "bold"), anchor="w").pack(anchor="w")
        tk.Label(txt, text=L("coll_sub"), bg=C["bg"],
                 fg=C["muted"], font=F_BASE, anchor="w").pack(anchor="w", pady=(2, 0))

        box = Card(root)
        box.pack(fill="both", expand=True, pady=(12, 12))
        inner = tk.Frame(box, bg=C["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        lb = tk.Listbox(inner, bg=C["panel"], fg=C["text"], font=F_MONO,
                        relief="flat", highlightthickness=0, borderwidth=0,
                        selectbackground=C["accent_dk"], activestyle="none",
                        height=min(10, max(3, len(names))), width=64)
        for n in names[:500]:
            lb.insert("end", "  " + n)
        if len(names) > 500:
            lb.insert("end", L("coll_more", len(names) - 500))
        sb = ttk.Scrollbar(inner, orient="vertical", command=lb.yview,
                           style="D.Vertical.TScrollbar")
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(fill="both", expand=True)

        bar = tk.Frame(root, bg=C["bg"])
        bar.pack(fill="x")
        FlatButton(bar, L("cancel"), lambda: self._pick(None), kind="ghost").pack(side="left")
        FlatButton(bar, L("coll_overwrite"), lambda: self._pick("overwrite"),
                   kind="danger").pack(side="right", padx=(8, 0))
        FlatButton(bar, L("coll_skip"), lambda: self._pick("skip"),
                   kind="normal").pack(side="right", padx=(8, 0))
        FlatButton(bar, L("coll_rename"), lambda: self._pick("rename"),
                   kind="primary").pack(side="right")

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + max(40, (master.winfo_height() - self.winfo_height()) // 3)
        self.geometry(f"+{max(0,x)}+{max(0,y)}")
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: self._pick(None))
        self.bind("<Escape>", lambda e: self._pick(None))

    def _pick(self, choice):
        self.destroy()
        self.on_choice(choice)


class AdvancedDialog(tk.Toplevel):
    """HandBrake-like pokročilé nastavení enkodéru."""

    def __init__(self, master, adv, enc_key, on_ok):
        super().__init__(master)
        self.title(L("adv_title"))
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.transient(master)
        self.on_ok = on_ok
        self.enc_key = enc_key
        self.family = enc_family(enc_key)
        self.is_hevc = enc_key in ("hevc_nvenc", "hevc_qsv", "hevc_amf", "libx265")
        self.v = {k: (tk.BooleanVar(value=val) if isinstance(val, bool) else
                      tk.DoubleVar(value=val) if isinstance(val, float) else
                      tk.IntVar(value=val) if isinstance(val, int) else
                      tk.StringVar(value=val))
                  for k, val in adv.items()}
        self._updaters = []     # sync widgetů po přepnutí profilu
        self._picked = None     # profil zvolený ručně v tomto dialogu
        self._build()
        for k in PROFILE_ADV["balanced"]:
            self.v[k].trace_add("write", lambda *_: self._sync_profile_label())
        self._sync_profile_label()
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + max(30, (master.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{max(0,x)}+{max(0,y)}")
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

    # --- malé pomůcky ---
    def _sec(self, parent, title):
        c = Card(parent, title)
        c.pack(fill="x", pady=(0, 10))
        b = tk.Frame(c, bg=C["panel"])
        b.pack(fill="x", padx=12, pady=(6, 11))
        b.columnconfigure(1, weight=1)
        b._row = 0
        return b

    def _combo(self, box, label, key, mapping, width=30):
        r = box._row
        box._row += 1
        tk.Label(box, text=label, bg=C["panel"], fg=C["muted"], font=F_BASE,
                 anchor="w").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
        inv = {v: k for k, v in mapping.items()}
        var = tk.StringVar(value=mapping.get(self.v[key].get(), list(mapping.values())[0]))
        cb = ttk.Combobox(box, textvariable=var, state="readonly", style="D.TCombobox",
                          font=F_BASE, width=width, values=list(mapping.values()))
        cb.grid(row=r, column=1, sticky="ew", pady=3)
        var.trace_add("write", lambda *_: self.v[key].set(inv[var.get()]))
        first = list(mapping.values())[0]
        self._updaters.append(lambda: var.set(mapping.get(self.v[key].get(), first)))
        return cb

    def _list(self, box, label, key, values, width=30):
        r = box._row
        box._row += 1
        tk.Label(box, text=label, bg=C["panel"], fg=C["muted"], font=F_BASE,
                 anchor="w").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
        cb = ttk.Combobox(box, textvariable=self.v[key], state="readonly",
                          style="D.TCombobox", font=F_BASE, width=width, values=values)
        cb.grid(row=r, column=1, sticky="ew", pady=3)
        return cb

    def _slider(self, box, label, key, lo, hi, fmt="{:.0f}", step=None):
        r = box._row
        box._row += 1
        tk.Label(box, text=label, bg=C["panel"], fg=C["muted"], font=F_BASE,
                 anchor="w").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
        wrap = tk.Frame(box, bg=C["panel"])
        wrap.grid(row=r, column=1, sticky="ew", pady=3)
        val = tk.Label(wrap, text=fmt.format(self.v[key].get()), bg=C["panel_hi"],
                       fg=C["accent"], font=(FONT, 9, "bold"), width=6, pady=2)
        val.pack(side="right", padx=(8, 0))

        def on(x):
            x = float(x)
            if step:
                x = round(x / step) * step
            if isinstance(self.v[key], tk.IntVar):
                x = int(round(x))
            self.v[key].set(x)
            val.configure(text=fmt.format(x))

        s = ttk.Scale(wrap, from_=lo, to=hi, orient="horizontal",
                      style="D.Horizontal.TScale", command=on)
        s.set(self.v[key].get())
        s.pack(side="left", fill="x", expand=True)
        self._updaters.append(lambda: s.set(self.v[key].get()))
        return s

    def _hint(self, box, text):
        tk.Label(box, text=text, bg=C["panel"], fg=C["dim"], font=F_SMALL,
                 anchor="w").grid(row=box._row, column=1, sticky="w")
        box._row += 1

    def _check(self, box, label, key):
        r = box._row
        box._row += 1
        f = tk.Frame(box, bg=C["panel"])
        f.grid(row=r, column=0, columnspan=2, sticky="w", pady=3)
        App._checkbox(self, f, label, self.v[key]).pack(anchor="w")

    def _entry(self, box, label, key):
        r = box._row
        box._row += 1
        tk.Label(box, text=label, bg=C["panel"], fg=C["muted"], font=F_BASE,
                 anchor="w").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
        tk.Entry(box, textvariable=self.v[key], bg=C["panel_hi"], fg=C["text"],
                 insertbackground=C["accent"], relief="flat", font=F_MONO,
                 highlightthickness=1, highlightbackground=C["border"],
                 highlightcolor=C["accent"]).grid(row=r, column=1, sticky="ew",
                                                  pady=3, ipady=4)

    def _build(self):
        root = tk.Frame(self, bg=C["bg"])
        root.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(root, text=L("adv_encoder", ENCODERS[self.enc_key]["label"]), bg=C["bg"],
                 fg=C["text"], font=(FONT, 11, "bold")).pack(anchor="w", pady=(0, 10))

        # --- profil kvality ---
        b = self._sec(root, L("sec_profile"))
        tk.Label(b, text=L("prof_label"), bg=C["panel"], fg=C["muted"], font=F_BASE,
                 anchor="w").grid(row=0, column=0, sticky="w", pady=3, padx=(0, 10))
        labels = loc(QUALITY_PROFILES)
        self.prof_var = tk.StringVar(value=labels[detect_profile(
            {k: v.get() for k, v in self.v.items()})])
        cbp = ttk.Combobox(b, textvariable=self.prof_var, state="readonly",
                           style="D.TCombobox", font=F_BASE, width=52,
                           values=[labels[k] for k in QUALITY_PROFILES])
        cbp.grid(row=0, column=1, sticky="ew", pady=3)
        cbp.bind("<<ComboboxSelected>>", self._on_profile_pick)
        self.prof_speed = tk.Label(b, text="", bg=C["panel"], fg=C["accent"],
                                   font=F_SMALL, anchor="w")
        self.prof_speed.grid(row=1, column=1, sticky="w")
        tk.Label(b, text=L("prof_hint"), bg=C["panel"], fg=C["dim"], font=F_SMALL,
                 anchor="w").grid(row=2, column=1, sticky="w")

        cols = tk.Frame(root, bg=C["bg"])
        cols.pack(fill="both", expand=True)
        left = tk.Frame(cols, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = tk.Frame(cols, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        # --- řízení datového toku ---
        b = self._sec(left, L("sec_rc"))
        self._combo(b, L("adv_mode"), "rc_mode", loc(RC_MODES))
        self._slider(b, L("adv_cq"), "cq", 10, 40, "{:.0f}")
        self._hint(b, L("adv_cq_hint"))
        self._slider(b, L("adv_maxrate"), "maxrate_mult", 1.0, 3.0, "{:.2f}×", step=0.05)
        self._slider(b, L("adv_bufsize"), "bufsize_mult", 0.5, 6.0, "{:.1f}×", step=0.1)
        if self.family == "nvenc":
            self._combo(b, L("adv_multipass"), "multipass", loc(MULTIPASS))

        # --- struktura GOP ---
        b = self._sec(left, L("sec_gop"))
        self._slider(b, L("adv_gop"), "gop", 0, 600, "{:.0f}")
        self._hint(b, L("adv_gop_hint"))
        self._slider(b, L("adv_bframes"), "bframes", 0, 5, "{:.0f}")
        if self.family == "nvenc":
            self._combo(b, L("adv_bref"), "bref", loc(BREF_MODES))
            self._slider(b, L("adv_lookahead"), "lookahead", 0, 60, "{:.0f}")

        # --- kvalita / AQ ---
        b = self._sec(left, L("sec_aq"))
        if self.family == "nvenc":
            self._check(b, L("adv_saq"), "spatial_aq")
            self._slider(b, L("adv_aqs"), "aq_strength", 1, 15, "{:.0f}")
            self._check(b, L("adv_taq"), "temporal_aq")
            self._check(b, L("adv_wp"), "weighted_pred")
            self._combo(b, L("adv_tune"), "tune", loc(TUNE_NVENC))
        elif self.family == "x26x":
            self._combo(b, L("adv_tune"), "tune_x265", loc(TUNE_X265))
        self._list(b, L("adv_level"), "level",
                   LEVELS_HEVC if self.is_hevc else LEVELS_H264)
        if self.is_hevc:
            self._check(b, L("adv_tier"), "tier_high")

        # --- obraz ---
        b = self._sec(right, L("sec_image"))
        self._combo(b, L("adv_scale"), "scale", loc(SCALES))
        self._hint(b, L("adv_scale_hint"))
        self._slider(b, L("adv_cw"), "scale_w", 0, 3840, "{:.0f}", step=2)
        self._slider(b, L("adv_ch"), "scale_h", 0, 2160, "{:.0f}", step=2)
        self._hint(b, L("adv_custom_hint"))
        self._combo(b, L("adv_fps"), "fps", loc(FPS_OPTS))
        self._combo(b, L("adv_rotate"), "rotate", loc(ROTATE))
        self._combo(b, L("adv_denoise"), "denoise", loc(DENOISE))
        self._check(b, L("adv_deint"), "deinterlace")

        # --- výkon ---
        b = self._sec(right, L("sec_perf"))
        self._check(b, L("adv_hwaccel"), "hwaccel")
        self._slider(b, L("adv_threads"), "threads", 0, 32, "{:.0f}")

        # --- expert ---
        b = self._sec(right, L("sec_expert"))
        if self.family == "x26x":
            self._entry(b, L("adv_x265"), "x265_params")
            self._hint(b, L("adv_x265_hint"))
        self._entry(b, L("adv_extra"), "extra_args")
        self._hint(b, L("adv_extra_hint"))

        # --- tlačítka ---
        bar = tk.Frame(root, bg=C["bg"])
        bar.pack(fill="x", pady=(6, 0))
        FlatButton(bar, L("adv_reset"), self._reset, kind="ghost").pack(side="left")
        FlatButton(bar, L("adv_apply"), self._ok, kind="primary",
                   width=12).pack(side="right")
        FlatButton(bar, L("cancel"), self.destroy, kind="normal",
                   width=10).pack(side="right", padx=(0, 8))

    # --- profily ---
    def _on_profile_pick(self, _=None):
        name = rev(QUALITY_PROFILES, self.prof_var.get(), "custom")
        if name == "custom":
            self._sync_profile_label()
            return
        for k, val in PROFILE_ADV[name].items():
            self.v[k].set(val)
        for sync in self._updaters:
            sync()
        self._sync_profile_label()
        self._picked = name          # až po syncu, ten si _picked přenastavuje

    def _sync_profile_label(self):
        """Popisek profilu vždy odpovídá skutečným hodnotám ve widgetech."""
        if not hasattr(self, "prof_var"):
            return
        name = detect_profile({k: v.get() for k, v in self.v.items()})
        self.prof_var.set(loc(QUALITY_PROFILES)[name])
        if name == "custom":
            self._picked = None
            self.prof_speed.configure(text="")
        else:
            speed = PROFILE_SPEED[name][self.family]
            self.prof_speed.configure(
                text=L("prof_speed", App._preset_label(speed)))

    def _reset(self):
        for k, val in ADV_DEFAULTS.items():
            self.v[k].set(val)
        self.destroy()
        self.on_ok(dict(ADV_DEFAULTS), None)

    def _ok(self):
        out = {}
        for k, default in ADV_DEFAULTS.items():
            try:
                out[k] = type(default)(self.v[k].get())
            except (tk.TclError, ValueError):
                out[k] = default
        self.destroy()
        self.on_ok(out, self._picked)


class AudioDialog(tk.Toplevel):
    """Pokročilé nastavení zvuku — kodek, stopy, EBU R128, časování."""

    def __init__(self, master, adv_a, codec_ok, on_ok):
        super().__init__(master)
        self.title(L("aud_title"))
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.transient(master)
        self.on_ok = on_ok
        self.codec_ok = codec_ok or {}
        self.v = {k: (tk.DoubleVar(value=val) if isinstance(val, float) else
                      tk.IntVar(value=val) if isinstance(val, int) else
                      tk.StringVar(value=val))
                  for k, val in adv_a.items()}
        self._updaters = []          # využívají sdílené pomůcky _combo/_slider
        self._build()
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + max(30, (master.winfo_height() - self.winfo_height()) // 3)
        self.geometry(f"+{max(0,x)}+{max(0,y)}")
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

    # sdílené pomůcky z AdvancedDialog
    _sec = AdvancedDialog._sec
    _combo = AdvancedDialog._combo
    _slider = AdvancedDialog._slider
    _hint = AdvancedDialog._hint

    def _build(self):
        root = tk.Frame(self, bg=C["bg"])
        root.pack(fill="both", expand=True, padx=14, pady=12)

        # --- kodek ---
        b = self._sec(root, L("sec_acodec"))
        avail = {k: v for k, v in loc(AUDIO_CODECS).items()
                 if self.codec_ok.get(k, True)}
        if self.v["codec"].get() not in avail:
            self.v["codec"].set(next(iter(avail)))
        self._combo(b, L("aud_codec"), "codec", avail, width=34)
        self._hint(b, L("aud_codec_hint"))
        self._combo(b, L("aud_channels"), "channels", loc(AUDIO_CHANNELS), width=34)
        self._combo(b, L("aud_rate"), "samplerate", loc(AUDIO_RATES), width=34)

        # --- stopy ---
        b = self._sec(root, L("sec_atracks"))
        self._combo(b, L("aud_tracks"), "tracks", loc(AUDIO_TRACKS), width=34)
        self._hint(b, L("aud_tracks_hint"))

        # --- normalizace ---
        b = self._sec(root, L("sec_norm"))
        self._combo(b, L("aud_norm"), "normalize", loc(NORMALIZE), width=34)
        self._slider(b, L("aud_lufs"), "lufs", -30, -5, "{:.0f}")
        self._slider(b, L("aud_tp"), "tpeak", -9, 0, "{:.1f}", step=0.5)
        self._slider(b, L("aud_lra"), "lra", 1, 20, "{:.0f}")
        self._hint(b, L("aud_norm_hint"))

        # --- časování ---
        b = self._sec(root, L("sec_atime"))
        self._slider(b, L("aud_offset"), "offset_ms", -2000, 2000, "{:.0f}", step=10)
        self._hint(b, L("aud_offset_hint"))

        bar = tk.Frame(root, bg=C["bg"])
        bar.pack(fill="x", pady=(6, 0))
        FlatButton(bar, L("adv_reset"), self._reset, kind="ghost").pack(side="left")
        FlatButton(bar, L("adv_apply"), self._ok, kind="primary",
                   width=12).pack(side="right")
        FlatButton(bar, L("cancel"), self.destroy, kind="normal",
                   width=10).pack(side="right", padx=(0, 8))

    def _reset(self):
        self.destroy()
        self.on_ok(dict(ADV_A_DEFAULTS))

    def _ok(self):
        out = {}
        for k, default in ADV_A_DEFAULTS.items():
            try:
                out[k] = type(default)(self.v[k].get())
            except (tk.TclError, ValueError):
                out[k] = default
        self.destroy()
        self.on_ok(out)


# ================================================================ main app ==
class App(tk.Tk, *( (TkinterDnD.DnDWrapper,) if TkinterDnD else () )):

    def __init__(self):
        super().__init__()
        self.dnd_ok = False
        if TkinterDnD is not None:
            try:                                  # načte tkdnd do interpretu
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_ok = True
            except Exception:
                self.dnd_ok = False
        self.title(f"{APP_NAME} {APP_VER}")
        self.configure(bg=C["bg"])
        # okno nikdy nesmí přerůst obrazovku — spodní panel s průběhem
        # se jinak schová pod hranu a je vidět, až když se okno roztáhne
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(1180, sw - 60)
        h = min(900, sh - 90)
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        # pod ~780 px na výšku už nezbývá místo na seznam souborů
        self.minsize(min(1000, w), min(780, h))

        self.files = []             # list of dict
        self.msgq = queue.Queue()
        self.worker = None
        self.stop_flag = threading.Event()
        self.pause_flag = threading.Event()
        self.cur_proc = None
        self.encoder_ok = {}        # key -> bool | None (None = netestováno)
        self.running = False
        self.adv = dict(ADV_DEFAULTS)
        self.adv_a = dict(ADV_A_DEFAULTS)
        self.acodec_ok = {}

        self._init_style()
        self._build()
        self._load_settings()
        self.after(80, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if not FFMPEG or not FFPROBE:
            self.after(200, lambda: messagebox.showerror(APP_NAME, L("no_ffmpeg")))
        else:
            threading.Thread(target=self._probe_encoders, daemon=True).start()

    # ------------------------------------------------------------- styling --
    def _init_style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Treeview",
                     background=C["panel"], fieldbackground=C["panel"],
                     foreground=C["text"], rowheight=27, borderwidth=0,
                     font=F_BASE)
        st.configure("Treeview.Heading",
                     background=C["panel_hi"], foreground=C["muted"],
                     font=(FONT, 8, "bold"), relief="flat", borderwidth=0, padding=(6, 7))
        st.map("Treeview.Heading", background=[("active", C["border"])])
        st.map("Treeview",
               background=[("selected", C["accent_dk"])],
               foreground=[("selected", "#ffffff")])
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        st.configure("D.TCombobox", fieldbackground=C["panel_hi"], background=C["panel_hi"],
                     foreground=C["text"], arrowcolor=C["muted"], bordercolor=C["border"],
                     lightcolor=C["border"], darkcolor=C["border"], relief="flat",
                     padding=(8, 5))
        st.map("D.TCombobox",
               fieldbackground=[("readonly", C["panel_hi"])],
               background=[("readonly", C["panel_hi"])],
               foreground=[("readonly", C["text"])],
               bordercolor=[("focus", C["accent"])])
        self.option_add("*TCombobox*Listbox.background", C["panel_hi"])
        self.option_add("*TCombobox*Listbox.foreground", C["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", C["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.font", F_BASE)

        st.configure("D.Horizontal.TScale", background=C["panel"], troughcolor=C["track"],
                     bordercolor=C["panel"], lightcolor=C["accent"], darkcolor=C["accent"])
        st.configure("D.Vertical.TScrollbar", background=C["border"], troughcolor=C["panel"],
                     bordercolor=C["panel"], arrowcolor=C["muted"], relief="flat")
        st.map("D.Vertical.TScrollbar", background=[("active", C["border_hi"])])

    # ------------------------------------------------------------- jazyk ---
    def _set_language(self, code):
        """Přepne jazyk a znovu postaví celé UI (hodnoty se zachovají)."""
        global LANG
        if code == LANG or self.running:
            return
        self._save_settings()
        LANG = code
        self.root_frame.destroy()
        self._build()
        self._load_settings()
        if self.encoder_ok:
            self._apply_encoder_availability()
        rows, self.files = self.files, []      # _add_row si je vloží zpět
        for info in rows:
            self._add_row(info)
        self._update_summary()

    # -------------------------------------------------------------- layout --
    def _build(self):
        root = self.root_frame = tk.Frame(self, bg=C["bg"])
        root.pack(fill="both", expand=True, padx=14, pady=12)

        self._build_header(root)
        self._build_paths(root)
        self._build_settings(root)
        self._build_actions(root)
        # panel s průběhem se pakuje odspodu ještě před tabulkou — má tak
        # své místo jisté a při nedostatku výšky se zmenšuje jen tabulka
        self._build_progress(root)
        self._build_table(root)
        self._register_dnd(self)

    # header
    def _build_header(self, root):
        h = tk.Frame(root, bg=C["bg"])
        h.pack(fill="x", pady=(0, 12))
        left = tk.Frame(h, bg=C["bg"])
        left.pack(side="left")
        tk.Label(left, text="Video Bitrate Compressor", bg=C["bg"], fg=C["text"],
                 font=F_TITLE).pack(anchor="w")
        tk.Label(left, text=L("subtitle"),
                 bg=C["bg"], fg=C["muted"], font=F_BASE).pack(anchor="w", pady=(2, 0))

        right = tk.Frame(h, bg=C["bg"])
        right.pack(side="right")
        langbar = tk.Frame(right, bg=C["bg"])
        langbar.pack(anchor="e")
        for code in ("cs", "en"):
            active = (code == LANG)
            b = tk.Label(langbar, text=LANG_NAMES[code], font=F_SMALL,
                         bg=C["accent"] if active else C["panel_hi"],
                         fg="#ffffff" if active else C["muted"],
                         padx=10, pady=3, cursor="hand2")
            b.pack(side="left", padx=(4, 0))
            if not active:
                b.bind("<Button-1>", lambda e, c=code: self._set_language(c))
        self.hw_lbl = tk.Label(right, text=L("detecting_enc"), bg=C["bg"],
                               fg=C["muted"], font=F_SMALL)
        self.hw_lbl.pack(anchor="e", pady=(5, 0))

    # cesty
    def _build_paths(self, root):
        card = Card(root)
        card.pack(fill="x", pady=(0, 10))
        body = tk.Frame(card, bg=C["panel"])
        body.pack(fill="x", padx=12, pady=11)
        body.columnconfigure(1, weight=1)

        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.recurse_var = tk.BooleanVar(value=False)
        self.ignore_var = tk.StringVar(value="compressed")

        def row(r, text, var, cb):
            tk.Label(body, text=text, bg=C["panel"], fg=C["muted"], font=F_BOLD,
                     width=14, anchor="w").grid(row=r, column=0, sticky="w", pady=4)
            e = tk.Entry(body, textvariable=var, bg=C["panel_hi"], fg=C["text"],
                         insertbackground=C["accent"], relief="flat", font=F_BASE,
                         highlightthickness=1, highlightbackground=C["border"],
                         highlightcolor=C["accent"])
            e.grid(row=r, column=1, sticky="ew", ipady=5, padx=(0, 8))
            FlatButton(body, L("browse"), cb).grid(row=r, column=2, sticky="e")

        row(0, L("in_folder"), self.in_var, self._pick_in)
        row(1, L("out_folder"), self.out_var, self._pick_out)

        opt = tk.Frame(body, bg=C["panel"])
        opt.grid(row=2, column=1, columnspan=2, sticky="w", pady=(7, 0))
        self._checkbox(opt, L("recurse"), self.recurse_var).pack(side="left")

        tk.Label(opt, text=L("ignore_dirs"), bg=C["panel"], fg=C["muted"],
                 font=F_BASE).pack(side="left", padx=(24, 6))
        tk.Entry(opt, textvariable=self.ignore_var, bg=C["panel_hi"], fg=C["text"],
                 insertbackground=C["accent"], relief="flat", font=F_BASE, width=26,
                 highlightthickness=1, highlightbackground=C["border"],
                 highlightcolor=C["accent"]).pack(side="left", ipady=3)
        tk.Label(opt, text=L("ignore_hint"), bg=C["panel"], fg=C["dim"],
                 font=F_SMALL).pack(side="left", padx=(10, 0))

    def _checkbox(self, master, text, var, cmd=None):
        f = tk.Frame(master, bg=master["bg"], cursor="hand2")
        box = tk.Canvas(f, width=16, height=16, bg=master["bg"], highlightthickness=0, bd=0)
        box.pack(side="left")
        lab = tk.Label(f, text=text, bg=master["bg"], fg=C["text"], font=F_BASE,
                       padx=7, cursor="hand2")
        lab.pack(side="left")

        def draw(*_):
            box.delete("all")
            on = var.get()
            box.create_rectangle(1, 1, 15, 15, outline=C["accent"] if on else C["border_hi"],
                                 fill=C["accent"] if on else C["panel_hi"], width=1)
            if on:
                box.create_line(4, 8, 7, 11, 12, 5, fill="#ffffff", width=2,
                                capstyle="round", joinstyle="round")

        def toggle(_=None):
            var.set(not var.get())
            draw()
            if cmd:
                cmd()

        for w in (f, box, lab):
            w.bind("<Button-1>", toggle)
        var.trace_add("write", draw)
        draw()
        return f

    # nastavení
    def _build_settings(self, root):
        card = Card(root, L("sec_convert"))
        card.pack(fill="x", pady=(0, 10))
        body = tk.Frame(card, bg=C["panel"])
        body.pack(fill="x", padx=12, pady=(8, 12))
        for i in range(4):
            body.columnconfigure(i, weight=1, uniform="s")

        def field(col, row, text):
            f = tk.Frame(body, bg=C["panel"])
            f.grid(row=row, column=col, sticky="ew", padx=(0, 12), pady=(0, 10))
            tk.Label(f, text=text, bg=C["panel"], fg=C["muted"], font=F_SMALL
                     ).pack(anchor="w", pady=(0, 3))
            return f

        # --- režim bitrate ---
        f = field(0, 0, L("br_mode").upper())
        self.mode_var = tk.StringVar(value=loc(BR_MODES)["pct"])
        ttk.Combobox(f, textvariable=self.mode_var, state="readonly", style="D.TCombobox",
                     font=F_BASE, values=list(loc(BR_MODES).values())).pack(fill="x")
        self.mode_var.trace_add("write", lambda *_: self._on_mode_change())

        # --- hodnota bitrate (procenta NEBO fixní) ---
        self.br_field = field(1, 0, L("target_br").upper())
        self.br_caption = self.br_field.winfo_children()[0]
        self.br_holder = tk.Frame(self.br_field, bg=C["panel"])
        self.br_holder.pack(fill="x")

        # procenta
        self.pct_frame = tk.Frame(self.br_holder, bg=C["panel"])
        self.pct_var = tk.IntVar(value=70)
        self.pct_lbl = tk.Label(self.pct_frame, text="70 %", bg=C["panel_hi"], fg=C["accent"],
                                font=(FONT, 11, "bold"), width=6, pady=3)
        self.pct_lbl.pack(side="right", padx=(8, 0))
        self.pct_scale = ttk.Scale(self.pct_frame, from_=5, to=150, orient="horizontal",
                                   style="D.Horizontal.TScale", command=self._on_pct)
        self.pct_scale.set(70)
        self.pct_scale.pack(side="left", fill="x", expand=True)

        # fixní
        self.fix_frame = tk.Frame(self.br_holder, bg=C["panel"])
        self.fix_var = tk.StringVar(value="4000")
        self.fix_unit = tk.StringVar(value="kb/s")
        tk.Label(self.fix_frame, textvariable=self.fix_unit, bg=C["panel_hi"], fg=C["accent"],
                 font=(FONT, 10, "bold"), width=7, pady=4).pack(side="right", padx=(8, 0))
        fe = tk.Entry(self.fix_frame, textvariable=self.fix_var, bg=C["panel_hi"], fg=C["text"],
                      insertbackground=C["accent"], relief="flat", font=(FONT, 10, "bold"),
                      highlightthickness=1, highlightbackground=C["border"],
                      highlightcolor=C["accent"])
        fe.pack(side="left", fill="x", expand=True, ipady=4)
        self.fix_var.trace_add("write", lambda *_: self._refresh_targets())

        self.pct_frame.pack(fill="x")

        # --- enkodér ---
        f = field(2, 0, L("encoder").upper())
        self.enc_var = tk.StringVar()
        self.enc_cb = ttk.Combobox(f, textvariable=self.enc_var, state="readonly",
                                   style="D.TCombobox", font=F_BASE,
                                   values=[v["label"] for v in ENCODERS.values()])
        # CPU encoding works on every supported PC; hardware encoders remain selectable.
        self.enc_cb.set(ENCODERS["libx265"]["label"])
        self.enc_cb.pack(fill="x")
        self.enc_cb.bind("<<ComboboxSelected>>", self._on_encoder_change)

        # --- bitová hloubka ---
        f = field(3, 0, L("depth").upper())
        self.depth_var = tk.StringVar(value="8 bit")
        self.depth_cb = ttk.Combobox(f, textvariable=self.depth_var, state="readonly",
                                     style="D.TCombobox", font=F_BASE,
                                     values=["8 bit", "10 bit"])
        self.depth_cb.pack(fill="x")

        # --- preset ---
        f = field(0, 1, L("preset").upper())
        self.preset_var = tk.StringVar()
        self.preset_cb = ttk.Combobox(f, textvariable=self.preset_var, state="readonly",
                                      style="D.TCombobox", font=F_BASE)
        self.preset_cb.pack(fill="x")

        # --- kontejner ---
        f = field(1, 1, L("container").upper())
        self.cont_var = tk.StringVar(value=loc(CONTAINERS)["mp4"])
        ttk.Combobox(f, textvariable=self.cont_var, state="readonly",
                     style="D.TCombobox", font=F_BASE,
                     values=list(loc(CONTAINERS).values())).pack(fill="x")
        self.cont_var.trace_add("write", lambda *_: self._refresh_targets())

        # --- audio ---
        f = field(2, 1, L("audio").upper())
        arow = tk.Frame(f, bg=C["panel"])
        arow.pack(fill="x")
        self.audio_var = tk.StringVar(value=loc(AUDIO_MODES)["copy"])
        ttk.Combobox(arow, textvariable=self.audio_var, state="readonly",
                     style="D.TCombobox", font=F_BASE,
                     values=list(loc(AUDIO_MODES).values())).pack(
            side="left", fill="x", expand=True)
        self.acustom_var = tk.StringVar(value="128")
        self.acustom_entry = tk.Entry(arow, textvariable=self.acustom_var, width=7,
                                      bg=C["panel_hi"], fg=C["text"],
                                      insertbackground=C["accent"], relief="flat",
                                      font=F_BASE, justify="center",
                                      highlightthickness=1,
                                      highlightbackground=C["border"],
                                      highlightcolor=C["accent"])
        self.audio_var.trace_add("write", lambda *_: self._on_audio_change())
        self.acustom_var.trace_add("write", lambda *_: self._refresh_targets())

        # --- přípona ---
        f = field(3, 1, L("suffix").upper())
        self.suffix_var = tk.StringVar(value="")
        tk.Entry(f, textvariable=self.suffix_var, bg=C["panel_hi"], fg=C["text"],
                 insertbackground=C["accent"], relief="flat", font=F_BASE,
                 highlightthickness=1, highlightbackground=C["border"],
                 highlightcolor=C["accent"]).pack(fill="x", ipady=5)

        # --- co překódovat ---
        f = field(0, 2, L("proc_mode").upper())
        self.proc_var = tk.StringVar(value=loc(PROC_MODES)["both"])
        ttk.Combobox(f, textvariable=self.proc_var, state="readonly",
                     style="D.TCombobox", font=F_BASE,
                     values=list(loc(PROC_MODES).values())).pack(fill="x")
        self.proc_var.trace_add("write", lambda *_: self._on_proc_change())

        # --- zaokrouhlení bitrate ---
        f = field(1, 2, L("rounding").upper())
        self.round_var = tk.StringVar(value=loc(ROUNDING)["100"])
        ttk.Combobox(f, textvariable=self.round_var, state="readonly",
                     style="D.TCombobox", font=F_BASE,
                     values=list(loc(ROUNDING).values())).pack(fill="x")
        self.round_var.trace_add("write", lambda *_: self._refresh_targets())

        # --- volby (zalamují se, aby se při zúžení okna nepřekrývaly) ---
        f = FlowFrame(body, hgap=22, vgap=8)
        f.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(2, 0))
        self.skip_bigger_var = tk.BooleanVar(value=True)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.qname_var = tk.BooleanVar(value=True)
        self.strip_tag_var = tk.BooleanVar(value=True)
        f.add(self._checkbox(f, L("qname"), self.qname_var, cmd=self._refresh_targets))
        f.add(self._checkbox(f, L("strip_tag"), self.strip_tag_var,
                             cmd=self._refresh_targets))
        f.add(self._checkbox(f, L("skip_bigger"), self.skip_bigger_var))
        f.add(self._checkbox(f, L("overwrite"), self.overwrite_var))
        self.keep_partial_var = tk.BooleanVar(value=True)
        f.add(self._checkbox(f, L("keep_partial"), self.keep_partial_var), gap=28)

        f.add(FlatButton(f, L("advanced_btn"), self._open_advanced,
                         kind="normal", icon="⚙"), gap=8)
        f.add(FlatButton(f, L("audio_btn"), self._open_audio,
                         kind="normal", icon="♪"), gap=12)
        self.adv_hint = tk.Label(f, text="", bg=C["panel"], fg=C["accent"], font=F_SMALL)
        f.add(self.adv_hint)
        self.opt_flow = f

        self._on_encoder_change()
        self._on_mode_change()
        self._on_audio_change()
        self._update_adv_hint()

    def _open_audio(self):
        AudioDialog(self, self.adv_a, self.acodec_ok, self._apply_audio)

    def _apply_audio(self, adv_a):
        self.adv_a = adv_a
        self._refresh_targets()
        self._update_adv_hint()

    def _on_audio_change(self):
        if not self._alive("acustom_entry"):
            return
        if self._audio_key() == "custom":
            self.acustom_entry.pack(side="left", padx=(6, 0), ipady=4)
        else:
            self.acustom_entry.pack_forget()
        self._refresh_targets()

    def _open_advanced(self):
        AdvancedDialog(self, self.adv, self._enc_key(), self._apply_advanced)

    def _apply_advanced(self, adv, profile=None):
        self.adv = adv
        if profile in PROFILE_SPEED:
            # profil řídí i rychlostní preset v hlavním okně
            fam = enc_family(self._enc_key())
            want = PROFILE_SPEED[profile][fam]
            avail = ENCODERS[self._enc_key()]["presets"]
            if want in avail:
                self.preset_var.set(self._preset_label(want))
        self._update_adv_hint()

    def _update_adv_hint(self):
        if not self._alive("adv_hint"):
            return
        self.after_idle(self.opt_flow._relayout)   # změna délky textu → přeskládat
        diffs = sum(1 for k, v in ADV_DEFAULTS.items() if self.adv.get(k, v) != v)
        diffs += sum(1 for k, v in ADV_A_DEFAULTS.items() if self.adv_a.get(k, v) != v)
        bits = []
        if self._proc_key() == "audio":
            self.adv_hint.configure(text=L("audio_only_hint"))
            return
        prof = detect_profile(self.adv)
        if prof != "balanced":
            bits.append(loc(QUALITY_PROFILES)[prof].split("—")[0].strip())
        if self.adv["rc_mode"] == "cq":
            bits.append(f"CQ {self.adv['cq']:.0f}")
        if self.adv["scale"] == "custom":
            bits.append(f"{int(self.adv['scale_w'])}×{int(self.adv['scale_h'])}")
        elif self.adv["scale"] != "orig":
            bits.append(loc(SCALES)[self.adv["scale"]].split("—")[-1].strip())
        if self.adv["fps"] != "orig":
            bits.append(self.adv["fps"] + " fps")
        if self.adv["rotate"] != "none":
            bits.append(loc(ROTATE)[self.adv["rotate"]])
        if self.adv["denoise"] != "none":
            bits.append(L("denoise_short"))
        if self.adv_a["normalize"] != "off":
            bits.append(f"EBU R128 {self.adv_a['lufs']:.0f} LUFS")
        if int(self.adv_a["offset_ms"]):
            bits.append(f"{int(self.adv_a['offset_ms']):+d} ms")
        if self._audio_key() not in ("copy", "none"):
            bits.append(self.adv_a["codec"])
        txt = " · ".join(bits)
        if diffs and not txt:
            txt = L("changes_vs_default", diffs)
        self.adv_hint.configure(text=("● " + txt) if txt else "")

    # akční tlačítka
    def _build_actions(self, root):
        bar = tk.Frame(root, bg=C["bg"])
        bar.pack(fill="x", pady=(0, 8))

        self.btn_scan = FlatButton(bar, L("scan"), self._scan, kind="normal", icon="⟳")
        self.btn_scan.pack(side="left", padx=(0, 8))
        self.btn_add = FlatButton(bar, L("add_files"), self._add_files,
                                  kind="normal", icon="＋")
        self.btn_add.pack(side="left", padx=(0, 8))
        self.btn_start = FlatButton(bar, L("start"), self._start, kind="primary", icon="▶")
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_pause = FlatButton(bar, L("pause"), self._toggle_pause,
                                    kind="normal", icon="❚❚")
        self.btn_pause.pack(side="left", padx=(0, 8))
        self.btn_pause.set_enabled(False)
        self.btn_stop = FlatButton(bar, L("stop"), self._stop, kind="danger", icon="■")
        self.btn_stop.pack(side="left", padx=(0, 8))
        self.btn_stop.set_enabled(False)

        FlatButton(bar, L("open_out"), self._open_out, kind="ghost",
                   icon="📁").pack(side="right")
        FlatButton(bar, L("clear"), self._clear, kind="ghost",
                   icon="✕").pack(side="right", padx=(0, 8))

        self.summary_lbl = tk.Label(bar, text="", bg=C["bg"], fg=C["muted"], font=F_BASE)
        self.summary_lbl.pack(side="right", padx=16)

    # tabulka
    def _build_table(self, root):
        card = self.table_card = Card(root)
        card.pack(fill="both", expand=True, pady=(0, 10))
        wrap = tk.Frame(card, bg=C["panel"])
        wrap.pack(fill="both", expand=True, padx=1, pady=1)

        cols = ("name", "res", "dur", "obr", "tbr", "asrc", "aout",
                "out", "prog", "state")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 selectmode="browse", height=6)
        heads = {
            "name": (L("col_src"), 190, "w"),
            "res": (L("col_res"), 88, "center"),
            "dur": (L("col_dur"), 62, "center"),
            "obr": (L("col_obr"), 96, "e"),
            "tbr": (L("col_tbr"), 96, "e"),
            "asrc": (L("col_asrc"), 128, "w"),
            "aout": (L("col_aout"), 150, "w"),
            "out": (L("col_out"), 190, "w"),
            "prog": (L("col_prog"), 175, "w"),
            "state": (L("col_state"), 115, "w"),
        }
        for c, (t, w, a) in heads.items():
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a, stretch=(c == "name"))

        self.tree.tag_configure("odd", background=C["panel"])
        self.tree.tag_configure("even", background="#1f232b")
        self.tree.tag_configure("done", foreground=C["green"])
        self.tree.tag_configure("err", foreground=C["red"])
        self.tree.tag_configure("skip", foreground=C["dim"])
        self.tree.tag_configure("active", foreground=C["accent"])

        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview,
                           style="D.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # nápověda „přetáhni sem“ přes prázdnou tabulku
        self.drop_hint = tk.Frame(wrap, bg=C["panel"])
        tk.Label(self.drop_hint, text="⤓", bg=C["panel"], fg=C["border_hi"],
                 font=(FONT, 26)).pack()
        tk.Label(self.drop_hint, text=L("drop_hint"), bg=C["panel"], fg=C["muted"],
                 font=(FONT, 11, "bold")).pack(pady=(4, 0))
        tk.Label(self.drop_hint, text=L("drop_hint2"), bg=C["panel"], fg=C["dim"],
                 font=F_SMALL).pack(pady=(2, 0))
        self._sync_drop_hint()

    # spodní progress
    def _build_progress(self, root):
        card = Card(root)
        card.pack(side="bottom", fill="x")
        body = tk.Frame(card, bg=C["panel"])
        body.pack(fill="x", padx=14, pady=12)

        r1 = tk.Frame(body, bg=C["panel"])
        r1.pack(fill="x")
        self.cur_name = tk.Label(r1, text=L("ready"), bg=C["panel"], fg=C["text"],
                                 font=F_BOLD, anchor="w")
        self.cur_name.pack(side="left")
        self.cur_stats = tk.Label(r1, text="", bg=C["panel"], fg=C["muted"], font=F_SMALL)
        self.cur_stats.pack(side="right")

        self.bar_file = RoundBar(body, height=24, color=C["accent"])
        self.bar_file.pack(fill="x", pady=(6, 12))

        r2 = tk.Frame(body, bg=C["panel"])
        r2.pack(fill="x")
        tk.Label(r2, text=L("total_progress"), bg=C["panel"], fg=C["muted"],
                 font=F_SMALL).pack(side="left")
        self.total_stats = tk.Label(r2, text="", bg=C["panel"], fg=C["muted"], font=F_SMALL)
        self.total_stats.pack(side="right")

        self.bar_total = RoundBar(body, height=16, color=C["green"], show_text=False)
        self.bar_total.pack(fill="x", pady=(5, 0))

    # ------------------------------------------------------------ handlers --
    def _on_pct(self, val):
        v = int(round(float(val)))
        self.pct_var.set(v)
        self.pct_lbl.configure(text=f"{v} %")
        self._refresh_targets()

    @staticmethod
    def _preset_label(p):
        pair = PRESET_HINT.get(p)
        return pair[0 if LANG == "cs" else 1] if pair else p

    def _on_encoder_change(self, _=None):
        key = self._enc_key()
        info = ENCODERS[key]
        self.preset_cb.configure(values=[self._preset_label(p) for p in info["presets"]])
        self.preset_cb.set(self._preset_label(info["default_preset"]))
        if info["ten_bit"]:
            self.depth_cb.configure(state="readonly", values=["8 bit", "10 bit"])
        else:
            self.depth_var.set("8 bit")
            self.depth_cb.configure(state="disabled", values=["8 bit"])

    def _enc_key(self):
        lbl = self.enc_var.get()
        for k, v in ENCODERS.items():
            if v["label"] == lbl:
                return k
        return "hevc_nvenc"

    def _preset_value(self):
        txt = self.preset_var.get()
        return txt.split(" ")[0] if txt else ENCODERS[self._enc_key()]["default_preset"]

    def _audio_key(self):
        return rev(AUDIO_MODES, self.audio_var.get(), "copy")

    def _pick_in(self):
        d = filedialog.askdirectory(title=L("pick_in_title"),
                                    initialdir=self.in_var.get() or None)
        if d:
            self.in_var.set(os.path.normpath(d))
            if not self.out_var.get():
                self.out_var.set(os.path.join(os.path.normpath(d), "compressed"))

    def _pick_out(self):
        d = filedialog.askdirectory(title=L("pick_out_title"),
                                    initialdir=self.out_var.get() or None)
        if d:
            self.out_var.set(os.path.normpath(d))

    def _open_out(self):
        p = self.out_var.get()
        if p and os.path.isdir(p):
            os.startfile(p)
        else:
            messagebox.showinfo(APP_NAME, L("no_out_dir"))

    def _clear(self):
        if self.running:
            return
        self.files.clear()
        self.tree.delete(*self.tree.get_children())
        self.summary_lbl.configure(text="")
        self.bar_file.set(0, "")
        self.bar_total.set(0)
        self.cur_name.configure(text=L("ready"))
        self.cur_stats.configure(text="")
        self._sync_drop_hint()

    # -------------------------------------------------- probe dostupnosti ---
    def _probe_encoders(self):
        for key, info in ENCODERS.items():
            if not info["hw"]:
                self.encoder_ok[key] = True
                continue
            cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                   "-i", "testsrc=size=256x144:rate=25:duration=0.2",
                   "-c:v", info["codec"], "-f", "null", "-"]
            try:
                ok = run_hidden(cmd, timeout=25).returncode == 0
            except Exception:
                ok = False
            self.encoder_ok[key] = ok

        for key in AUDIO_CODECS:
            cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                   "-i", "anullsrc=r=48000:cl=stereo", "-t", "0.2",
                   "-c:a", key, "-f", "null", "-"]
            try:
                self.acodec_ok[key] = run_hidden(cmd, timeout=20).returncode == 0
            except Exception:
                self.acodec_ok[key] = False
        self.msgq.put(("encoders", None))

    def _apply_encoder_availability(self):
        tag = L("unavailable")
        self.enc_cb.configure(values=[
            v["label"] if self.encoder_ok.get(k, True) else v["label"] + tag
            for k, v in ENCODERS.items()])
        cur = self._enc_key()
        self.enc_cb.set(ENCODERS[cur]["label"] +
                        ("" if self.encoder_ok.get(cur, True) else tag))
        hw = sorted({ENCODERS[k]["label"].split("— ")[-1] for k in ENCODERS
                     if ENCODERS[k]["hw"] and self.encoder_ok.get(k)})
        if hw:
            self.hw_lbl.configure(text=L("hw_accel", ", ".join(hw)), fg=C["green"])
        else:
            self.hw_lbl.configure(text=L("cpu_only"), fg=C["amber"])

    def _enc_key(self):  # noqa: F811  (přepis kvůli příponě „nedostupné“)
        lbl = self.enc_var.get()
        for suffix in (S["unavailable"][0], S["unavailable"][1]):
            lbl = lbl.replace(suffix, "")
        for k, v in ENCODERS.items():
            if v["label"] == lbl:
                return k
        return "hevc_nvenc"

    # ---------------------------------------------------------- skenování ---
    def _scan(self):
        if self.running:
            return
        src = self.in_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showwarning(APP_NAME, L("pick_input"))
            return
        self._clear()
        self._n_before_add = 0
        self.stop_flag.clear()      # po zrušeném převodu by sken jinak nic nenašel
        self.btn_scan.set_enabled(False)
        self.btn_add.set_enabled(False)
        self.cur_name.configure(text=L("scanning"))
        ignore = {n.strip().lower() for n in self.ignore_var.get().split(",")
                  if n.strip()}
        # výstupní složku nikdy neskenujeme, i když leží uvnitř vstupní
        out = self.out_var.get().strip()
        threading.Thread(target=self._scan_worker,
                         args=(src, self.recurse_var.get(), ignore, out),
                         daemon=True).start()

    def _scan_worker(self, src, recurse, ignore, out):
        root = Path(src)
        out_res = None
        if out:
            try:
                out_res = Path(out).resolve()
            except OSError:
                out_res = None

        def skipped(p):
            rel_dirs = [part.lower() for part in p.relative_to(root).parts[:-1]]
            if ignore.intersection(rel_dirs):
                return True
            if out_res is not None:
                try:
                    p.parent.resolve().relative_to(out_res)
                    return True                  # leží ve výstupní složce
                except (ValueError, OSError):
                    pass
            return False

        paths = sorted(root.rglob("*") if recurse else root.glob("*"))
        vids = [p for p in paths
                if p.is_file() and p.suffix.lower() in VIDEO_EXTS and not skipped(p)]
        self._probe_list(vids, lambda p: p.relative_to(root))

    def _probe_list(self, paths, rel_fn):
        """Proběhne seznam souborů, nevidea zahodí, zbytek pošle do UI."""
        total = len(paths)
        nonvideo = 0
        for i, p in enumerate(paths, 1):
            if self.stop_flag.is_set():
                break
            try:
                info = probe(p)
                info["path"] = p
                info["rel"] = rel_fn(p)
                info["error"] = None
            except NotAVideo:
                nonvideo += 1                    # není video → do seznamu nepatří
                self.msgq.put(("scan_tick", (i, total)))
                continue
            except Exception as e:
                info = dict(path=p, rel=rel_fn(p), error=str(e),
                            width=0, height=0, duration=0,
                            size=p.stat().st_size if p.exists() else 0,
                            vbitrate=0, codec="?", bsource="", fps=0, naudio=0,
                            acodec="", pix_fmt="")
            self.msgq.put(("scanned", (info, i, total)))
        self.msgq.put(("scan_done", nonvideo))

    # ------------------------------------------------------- drag & drop ---
    def _register_dnd(self, widget):
        """Přihlásí okno i všechny jeho prvky jako cíl přetažení souborů."""
        if not self.dnd_ok:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_dnd_drop)
            widget.dnd_bind("<<DragEnter>>", self._on_dnd_enter)
            widget.dnd_bind("<<DragLeave>>", self._on_dnd_leave)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._register_dnd(child)

    def _on_dnd_enter(self, _=None):
        if getattr(self, "_dnd_off", None):
            self.after_cancel(self._dnd_off)
            self._dnd_off = None
        self._highlight_drop(True)
        return "copy"

    def _on_dnd_leave(self, _=None):
        # při přejezdu mezi prvky přijde Leave hned před dalším Enter,
        # takže se zhasíná se zpožděním — jinak by rámeček blikal
        if getattr(self, "_dnd_off", None):
            self.after_cancel(self._dnd_off)
        self._dnd_off = self.after(80, lambda: self._highlight_drop(False))
        return "copy"

    def _highlight_drop(self, on):
        self._dnd_off = None
        if not self._alive("table_card"):
            return
        self.table_card.configure(
            highlightbackground=C["accent"] if on else C["border"])
        if self._alive("drop_hint"):
            for lab, base in zip(self.drop_hint.winfo_children(),
                                 (C["border_hi"], C["muted"], C["dim"])):
                lab.configure(fg=C["accent"] if on else base)

    def _dnd_paths(self, data):
        """Rozebere seznam cest z tkdnd.

        Tcl umí na zpětných lomítkách ve windowsových cestách udělat nesmysl
        („C:\\Users“ → escape sekvence), proto se zkouší víc způsobů a bere se
        ten, jehož výsledek skutečně existuje na disku.
        """
        variants = []
        try:
            variants.append([str(x) for x in self.tk.splitlist(data)])
        except tk.TclError:
            pass
        # ruční rozbor: cesty s mezerami jsou ve složených závorkách
        manual = [a or b for a, b in re.findall(r"\{([^{}]*)\}|(\S+)", data)]
        variants.append(manual)
        variants.append([data.strip()])

        for v in variants:
            v = [x for x in v if x]
            if v and all(os.path.exists(x) for x in v):
                return v
        for v in variants:                    # nic nesedí → aspoň něco vrátit
            v = [x for x in v if x and os.path.exists(x)]
            if v:
                return v
        return []

    def _on_dnd_drop(self, event):
        self._highlight_drop(False)
        paths = self._dnd_paths(event.data)
        if paths:
            self.after(0, lambda: self._accept_dropped(paths))
        return "copy"

    def _sync_drop_hint(self):
        """Nápověda k přetažení se ukazuje jen nad prázdnou tabulkou."""
        if not self._alive("drop_hint"):
            return
        if self.files:
            self.drop_hint.place_forget()
        else:
            self.drop_hint.place(relx=0.5, rely=0.5, anchor="center")

    def _accept_dropped(self, raw):
        if self.running or not self.btn_scan._enabled:
            return
        found, relmap, first_dir = [], {}, None
        for s in raw:
            p = Path(s)
            try:
                if p.is_dir():
                    first_dir = first_dir or p
                    it = p.rglob("*") if self.recurse_var.get() else p.glob("*")
                    for q in sorted(it):
                        if q.is_file() and q.suffix.lower() in VIDEO_EXTS:
                            found.append(q)
                            relmap[q] = q.relative_to(p)
                elif p.is_file() and p.suffix.lower() in VIDEO_EXTS:
                    found.append(p)
                    relmap[p] = Path(p.name)
            except OSError:
                continue

        have = {str(Path(f["path"]).resolve()).lower() for f in self.files}
        new = []
        for p in found:
            try:
                key = str(p.resolve()).lower()
            except OSError:
                continue
            if key in have:
                continue
            have.add(key)
            new.append(p)

        if not new:
            messagebox.showinfo(APP_NAME, L("drop_none"))
            return

        base = first_dir or new[0].parent
        if not self.in_var.get().strip():
            self.in_var.set(str(base))
        if not self.out_var.get().strip():
            self.out_var.set(str(base / "compressed"))

        self._n_before_add = len(self.files)
        self.stop_flag.clear()
        self.btn_scan.set_enabled(False)
        self.btn_add.set_enabled(False)
        self.cur_name.configure(text=L("scanning"))
        threading.Thread(target=self._probe_list,
                         args=(new, lambda p: relmap.get(p, Path(p.name))),
                         daemon=True).start()

    # ------------------------------------------------ přidání jednotlivých ---
    def _add_files(self):
        if self.running:
            return
        exts = " ".join("*" + e for e in sorted(VIDEO_EXTS))
        picked = filedialog.askopenfilenames(
            title=L("pick_files_title"),
            initialdir=self.in_var.get() or None,
            filetypes=[(L("ft_video"), exts), (L("ft_all"), "*.*")])
        if not picked:
            return

        have = {str(Path(f["path"]).resolve()).lower() for f in self.files}
        new = []
        for s in picked:
            p = Path(s)
            if p.suffix.lower() not in VIDEO_EXTS:
                continue
            key = str(p.resolve()).lower()
            if key in have:
                continue
            have.add(key)
            new.append(p)

        if not new:
            messagebox.showinfo(APP_NAME, L("no_new_files"))
            return

        if not self.in_var.get().strip():
            self.in_var.set(str(new[0].parent))
        if not self.out_var.get().strip():
            self.out_var.set(str(new[0].parent / "compressed"))

        self._n_before_add = len(self.files)
        self.stop_flag.clear()      # totéž při ručním přidávání souborů
        self.btn_scan.set_enabled(False)
        self.btn_add.set_enabled(False)
        self.cur_name.configure(text=L("scanning"))
        threading.Thread(target=self._probe_list,
                         args=(new, lambda p: Path(p.name)), daemon=True).start()

    def _add_row(self, info):
        idx = len(self.files)
        self.files.append(info)
        tag = "even" if idx % 2 else "odd"
        if info["error"]:
            vals = (str(info["rel"]), "—", "—", "—", "—", "—", "—", "—",
                    "", "✕ " + info["error"])
            self.tree.insert("", "end", iid=str(idx), values=vals, tags=(tag, "err"))
        else:
            vals = (str(info["rel"]),
                    f'{info["width"]}×{info["height"]}',
                    human_time(info["duration"]),
                    kbps(info["vbitrate"]),
                    kbps(self._target_br(info)),
                    self._audio_src_text(info),
                    self._audio_out_text(info),
                    self._out_name(info),
                    self._bar_text(0),
                    L("st_wait"))
            self.tree.insert("", "end", iid=str(idx), values=vals, tags=(tag,))
        self.tree.see(str(idx))
        self._sync_drop_hint()

    def _out_name(self, info):
        """Náhled názvu výstupního souboru."""
        return (self._clean_stem(Path(info["rel"]).stem)
                + self.suffix_var.get().strip() + self._name_tag(info)
                + "." + self._resolve_container(self._container_key(), info))

    def _audio_src_text(self, info):
        sts = info.get("astreams") or []
        if not sts:
            return "—"
        s = sts[0]
        txt = s.get("codec", "?")
        if s.get("bitrate", 0) > 0:
            txt += f" {int(round(s['bitrate']/1000))} kb/s"
        if s.get("channels"):
            txt += f" {s['channels']}ch"
        if len(sts) > 1:
            txt += f" ×{len(sts)}"
        return txt

    def _audio_out_text(self, info):
        if self._audio_key() == "none":
            return "—"
        n = info.get("naudio", 0)
        if not n:
            return "—"
        if self._audio_key() == "copy" \
                and not self._audio_reencode_forced(self._audio_cfg()):
            return L("same_as_src")
        codec, kb = self._effective_audio(info)
        txt = codec.replace("lib", "")
        if kb:
            txt += f" {kb} kb/s"
        if self.adv_a["channels"] != "orig":
            txt += f" {self.adv_a['channels']}ch"
        if self.adv_a["normalize"] != "off":
            txt += f" · R128 {self.adv_a['lufs']:.0f}"
        tracks = 1 if self.adv_a["tracks"] == "first" else n
        if tracks > 1:
            txt += f" ×{tracks}"
        return txt

    def _mode_key(self):
        return rev(BR_MODES, self.mode_var.get(), "pct")

    def _fixed_bps(self):
        """Fixní bitrate v bit/s; 0 = neplatná hodnota."""
        txt = (self.fix_var.get() or "").strip().replace(",", ".")
        m = re.match(r"^(\d+(?:\.\d+)?)\s*(k|m)?", txt, re.I)
        if not m:
            return 0.0
        val = float(m.group(1))
        unit = (m.group(2) or "").lower()
        if unit == "m":
            return val * 1_000_000
        if unit == "k":
            return val * 1000
        # bez jednotky: čísla do 10 000 ber jako kb/s, větší jako bit/s
        return val * 1000 if val <= 10_000 else val

    def _round_key(self):
        return rev(ROUNDING, self.round_var.get(), "100")

    def _proc_key(self):
        return rev(PROC_MODES, self.proc_var.get(), "both")

    def _container_key(self):
        return rev(CONTAINERS, self.cont_var.get(), "mp4")

    @staticmethod
    def _resolve_container(container, info):
        """„auto“ = ponechat příponu zdroje."""
        if container != "auto":
            return container
        ext = Path(info["path"]).suffix.lstrip(".").lower()
        return ext or "mkv"

    def _on_proc_change(self):
        # u pouhé výměny zvuku je bezpečnější nechat původní kontejner
        if self._proc_key() == "audio" and self._container_key() == "mp4":
            self.cont_var.set(loc(CONTAINERS)["auto"])
        self._refresh_targets()
        self._update_adv_hint()

    def _target_br(self, info):
        if self._proc_key() == "audio":
            # video se jen kopíruje — bitrate zůstává přesně jako v originálu
            return info["vbitrate"]
        mode = self._mode_key()
        if mode == "pct":
            raw = info["vbitrate"] * self.pct_var.get() / 100.0
        else:
            fixed = self._fixed_bps()
            if fixed <= 0:
                return info["vbitrate"]
            if mode == "cap":
                raw = min(info["vbitrate"], fixed) if info["vbitrate"] else fixed
            else:
                # pevnou hodnotu zadal uživatel — tu nepřepisujeme
                return fixed
        target = round_bitrate(raw, self._round_key())
        # zaokrouhlení nahoru nesmí přelézt originál
        if info["vbitrate"] and target > info["vbitrate"]:
            target = round_bitrate(raw, "off") if raw <= info["vbitrate"] else raw
        return target

    def _audio_cfg(self):
        return dict(audio=self._audio_key(), audio_custom=self.acustom_var.get(),
                    adv_a=self.adv_a)

    def _effective_audio(self, info):
        """(kodek, kb/s) zvuku na výstupu; kb/s je None u bezztrátových."""
        cfg = self._audio_cfg()
        st = (info.get("astreams") or [{}])[0]
        codec = self._stream_codec(cfg, st)
        if codec in AUDIO_LOSSLESS:
            return codec, None
        kb = self._chosen_kbps(cfg)
        if kb is None:
            if self.adv_a["codec"] == "same" and st.get("bitrate", 0) > 0:
                kb = int(round(st["bitrate"] / 1000))
            else:
                kb = 192
        return codec, kb

    def _audio_name_tag(self, info):
        """ „ a192“ + „n“ při normalizaci; prázdné, pokud se zvuk nemění."""
        if self._audio_key() == "none":
            return " anone"
        if not info.get("naudio"):
            return ""
        if self._audio_key() == "copy" \
                and not self._audio_reencode_forced(self._audio_cfg()):
            return ""                        # zvuk se jen kopíruje → nic nepřipisuj
        codec, kb = self._effective_audio(info)
        tag = f" a{kb}" if kb else " a" + codec
        if self.adv_a["normalize"] != "off":
            tag += "n"
        return tag

    Q_IN_NAME = re.compile(r"\bq(\d+)\b", re.I)

    def _video_name_tag(self, info):
        """ „ q10000“ / „ CQ28“; v režimu pouze zvuk bitrate originálu."""
        if self._proc_key() == "audio":
            # video se nepřekódovává, takže se jeho značka nesmí měnit:
            # když už název nějaké q nese, převezmeme ho přesně tak, jak je
            m = self.Q_IN_NAME.search(Path(info["rel"]).stem)
            if m:
                return " q" + m.group(1)
            # jinak zapíšeme naměřený bitrate bez zaokrouhlování
            kb = int(round(info["vbitrate"] / 1000))
            return f" q{kb}" if kb > 0 else ""
        if self.adv.get("rc_mode") == "cq":
            return f" CQ{self.adv['cq']:.0f}"
        # počítáme vždy znovu — uložený „target“ může být z předchozího běhu
        kb = int(round(self._target_br(info) / 1000))
        return f" q{kb}" if kb > 0 else ""

    def _name_tag(self, info):
        if not self.qname_var.get():
            return ""
        return self._video_name_tag(info) + self._audio_name_tag(info)

    # značky, které aplikace sama vyrábí — aby se v názvu nehromadily
    TAG_RE = re.compile(
        r"(?:\s+(?:q\d+|CQ\d+|a(?:\d+|none|flac|alac|pcm_s\d+le)n?))+$", re.I)

    def _clean_stem(self, stem):
        return self.TAG_RE.sub("", stem).rstrip() if self.strip_tag_var.get() else stem

    def _dest_path(self, info, out_root, container, suffix, tag):
        rel = Path(info["rel"])
        d = out_root / rel.parent if str(rel.parent) != "." else out_root
        ext = self._resolve_container(container, info)
        return d / (self._clean_stem(rel.stem) + suffix + tag + "." + ext)

    @staticmethod
    def _unique_path(p):
        if not p.exists():
            return p
        for i in range(2, 1000):
            cand = p.with_name(f"{p.stem} ({i}){p.suffix}")
            if not cand.exists():
                return cand
        return p

    def _on_mode_change(self):
        mode = self._mode_key()
        self.pct_frame.pack_forget()
        self.fix_frame.pack_forget()
        if mode == "pct":
            self.br_caption.configure(text=L("target_br_pct").upper())
            self.pct_frame.pack(fill="x")
        else:
            self.br_caption.configure(
                text=(L("fixed_br") if mode == "fix" else L("max_br")).upper())
            self.fix_frame.pack(fill="x")
        self._refresh_targets()

    def _alive(self, name):
        """Existuje daný widget? (po přepnutí jazyka se UI staví znovu)"""
        w = getattr(self, name, None)
        try:
            return w is not None and w.winfo_exists()
        except tk.TclError:
            return False

    def _refresh_targets(self):
        if not self._alive("tree"):          # během sestavování / přestavby UI
            return
        for i, info in enumerate(self.files):
            if info.get("error"):
                continue
            try:
                self.tree.set(str(i), "tbr", kbps(self._target_br(info)))
                self.tree.set(str(i), "aout", self._audio_out_text(info))
                self.tree.set(str(i), "out", self._out_name(info))
            except tk.TclError:
                pass
        self._update_summary()

    def _update_summary(self):
        if not self._alive("summary_lbl"):
            return
        ok = [f for f in self.files if not f.get("error")]
        if not ok:
            self.summary_lbl.configure(text="")
            return
        tot_size = sum(f["size"] for f in ok)
        tot_dur = sum(f["duration"] for f in ok)
        est = sum((self._target_br(f) + 128000) * f["duration"] / 8 for f in ok)
        self.summary_lbl.configure(text=L("summary", len(ok), human_time(tot_dur),
                                          human_size(tot_size), human_size(est)))

    @staticmethod
    def _bar_text(frac, width=18):
        filled = int(round(frac * width))
        return "█" * filled + "░" * (width - filled) + f" {frac*100:5.1f} %"

    # ------------------------------------------------------------- převod ---
    def _start(self):
        if self.running:
            return
        if not FFMPEG:
            messagebox.showerror(APP_NAME, L("no_ffmpeg"))
            return
        todo = [f for f in self.files if not f.get("error")]
        if not todo:
            messagebox.showwarning(APP_NAME, L("scan_first"))
            return
        audio_only = self._proc_key() == "audio"
        if not audio_only and self._mode_key() != "pct" and self._fixed_bps() < 50_000:
            messagebox.showwarning(APP_NAME, L("bad_fixed"))
            return
        if audio_only and self._audio_key() == "copy" \
                and not self._audio_reencode_forced(dict(adv_a=self.adv_a)):
            messagebox.showwarning(APP_NAME, L("nothing_to_do"))
            return
        out = self.out_var.get().strip()
        if not out:
            messagebox.showwarning(APP_NAME, L("pick_output"))
            return
        if os.path.normpath(out) == os.path.normpath(self.in_var.get().strip()):
            messagebox.showwarning(APP_NAME, L("same_folder"))
            return
        key = self._enc_key()
        if not audio_only and self.encoder_ok.get(key) is False:
            if not messagebox.askyesno(
                    APP_NAME, L("enc_unavailable", ENCODERS[key]["label"])):
                return
        if (self._container_key() == "mp4" and self._audio_key() != "none"
                and self.adv_a["codec"] in AUDIO_MP4_BAD
                and (self._audio_key() != "copy"
                     or self._audio_reencode_forced(dict(adv_a=self.adv_a)))):
            if messagebox.askyesno(
                    APP_NAME, L("mp4_audio_warn", self.adv_a["codec"])):
                self.cont_var.set(loc(CONTAINERS)["mkv"])
        try:
            os.makedirs(out, exist_ok=True)
        except Exception as e:
            messagebox.showerror(APP_NAME, L("mkdir_fail", e))
            return

        # cílové bitraty a cesty zmrazíme teď — vlákno nesmí sahat na Tk proměnné
        out_root = Path(out)
        container = self._container_key()
        suffix = self.suffix_var.get().strip()
        for f in self.files:
            if f.get("error"):
                f["target"], f["dst"] = 0.0, None
                continue
            f["target"] = self._target_br(f)
            f["dst"] = self._dest_path(f, out_root, container, suffix, self._name_tag(f))

        # POJISTKA: výstup nesmí nikdy ukázat na některý ze vstupních souborů
        sources = set()
        for f in self.files:
            try:
                sources.add(str(Path(f["path"]).resolve()).lower())
            except OSError:
                pass
        clashes = []
        for f in self.files:
            if not f.get("dst"):
                continue
            try:
                if str(f["dst"].resolve()).lower() in sources:
                    clashes.append(str(f["dst"]))
            except OSError:
                pass
        if clashes:
            messagebox.showerror(APP_NAME,
                                 L("would_hit_source", "\n".join(clashes[:8])))
            return

        self._save_settings()

        existing = [f for f in self.files if f.get("dst") and f["dst"].exists()]
        if existing and not self.overwrite_var.get():
            names = [str(f["dst"].relative_to(out_root)) for f in existing]
            CollisionDialog(self, names,
                            lambda ch: self._begin(ch) if ch else None)
            return
        self._begin("overwrite")

    def _begin(self, collision):
        if collision == "rename":
            used = set()
            for f in self.files:
                if not f.get("dst"):
                    continue
                p = self._unique_path(f["dst"])
                while p in used:
                    p = self._unique_path(p.with_name(f"{p.stem} (x){p.suffix}"))
                used.add(p)
                f["dst"] = p

        self.stop_flag.clear()
        self.pause_flag.clear()
        self.running = True
        self.btn_start.set_enabled(False)
        self.btn_scan.set_enabled(False)
        self.btn_pause.set_enabled(True)
        self.btn_stop.set_enabled(True)
        self.btn_pause.set_text(L("pause"), "❚❚")

        cfg = dict(
            collision=collision, enc=self._enc_key(),
            out_root=Path(self.out_var.get().strip()).resolve(),
            preset=self._preset_value(), depth=self.depth_var.get(),
            container=self._container_key(), audio=self._audio_key(),
            audio_custom=self.acustom_var.get(), proc=self._proc_key(),
            skip_bigger=self.skip_bigger_var.get() and self._proc_key() != "audio",
            keep_partial=self.keep_partial_var.get(),
            adv=dict(self.adv), adv_a=dict(self.adv_a),
        )
        self.worker = threading.Thread(target=self._convert_worker, args=(cfg,), daemon=True)
        self.worker.start()

    @staticmethod
    def _video_filters(info, adv):
        """Sestaví -vf řetězec podle pokročilého nastavení."""
        vf = []
        if adv["deinterlace"]:
            vf.append("yadif=mode=0:parity=-1:deint=0")

        # --- rozlišení ---
        if adv["scale"] == "custom":
            w, h = int(adv["scale_w"]), int(adv["scale_h"])
            if w > 0 and h > 0:
                vf.append(f"scale={w}:{h}:flags=lanczos")
            elif w > 0:
                vf.append(f"scale={w}:-2:flags=lanczos")
            elif h > 0:
                vf.append(f"scale=-2:{h}:flags=lanczos")
        elif adv["scale"] != "orig":
            th = SCALE_H[adv["scale"]]
            # zmenšujeme jen když je zdroj větší; rozměry zaokrouhlíme na sudé
            if info.get("height", 0) > th:
                vf.append(f"scale=-2:{th}:flags=lanczos")

        # --- otočení / orientace ---
        rot = adv.get("rotate", "none")
        w0, h0 = info.get("width", 0), info.get("height", 0)
        if rot == "landscape":
            rot = "90cw" if (h0 and w0 and h0 > w0) else "none"
        elif rot == "portrait":
            rot = "90cw" if (h0 and w0 and w0 > h0) else "none"
        vf += {
            "90cw":  ["transpose=1"],
            "90ccw": ["transpose=2"],
            "180":   ["transpose=1", "transpose=1"],
            "hflip": ["hflip"],
            "vflip": ["vflip"],
        }.get(rot, [])

        if adv["denoise"] != "none":
            vf.append("hqdn3d=" + DENOISE_ARGS[adv["denoise"]])
        if adv["fps"] != "orig":
            vf.append("fps=" + adv["fps"])
        return ",".join(vf)

    # ------------------------------------------------------------- zvuk ----
    @staticmethod
    def _audio_map(cfg):
        if cfg["audio"] == "none":
            return []
        return ["-map", "0:a:0?"] if cfg["adv_a"]["tracks"] == "first" else ["-map", "0:a?"]

    @staticmethod
    def _audio_reencode_forced(cfg):
        """Vrací True, když nelze jen kopírovat (normalizace / posun / mixdown)."""
        a = cfg["adv_a"]
        return (a["normalize"] != "off" or int(a["offset_ms"]) != 0
                or a["channels"] != "orig" or a["samplerate"] != "orig")

    @staticmethod
    def _loudnorm_filter(a, measured=None):
        f = (f"loudnorm=I={a['lufs']:.1f}:TP={a['tpeak']:.1f}:LRA={a['lra']:.1f}")
        if measured:
            f += (f":measured_I={measured['input_i']}"
                  f":measured_TP={measured['input_tp']}"
                  f":measured_LRA={measured['input_lra']}"
                  f":measured_thresh={measured['input_thresh']}"
                  f":offset={measured['target_offset']}:linear=true")
        return f + ":print_format=summary"

    def _audio_filters(self, a, measured=None, src_rate=0):
        """Filtry aplikované na jednu zvukovou stopu."""
        chain = []
        off = int(a["offset_ms"])
        if off > 0:
            chain.append(f"adelay={off}:all=1")
        elif off < 0:
            chain.append(f"atrim=start={abs(off)/1000.0:.3f}")
            chain.append("asetpts=PTS-STARTPTS")
        if a["normalize"] != "off":
            chain.append(self._loudnorm_filter(a, measured))
        if a["samplerate"] != "orig":
            chain.append(f"aresample={a['samplerate']}")
        elif a["normalize"] != "off" and src_rate > 0:
            # loudnorm pracuje vnitřně na 192 kHz — vrátíme původní frekvenci
            chain.append(f"aresample={src_rate}")
        return ",".join(chain)

    def _measure_loudness(self, path, stream_idx, a):
        """První průchod loudnorm — vrátí naměřené hodnoty, nebo None."""
        cmd = [FFMPEG, "-hide_banner", "-nostdin", "-i", str(path),
               "-map", f"0:a:{stream_idx}",
               "-af", self._loudnorm_filter(a).replace("print_format=summary",
                                                       "print_format=json"),
               "-f", "null", "-"]
        try:
            r = run_hidden(cmd, timeout=900)
        except Exception:
            return None
        txt = (r.stderr or b"").decode("utf-8", "replace")
        start = txt.rfind("{")
        end = txt.rfind("}")
        if start < 0 or end < start:
            return None
        try:
            m = json.loads(txt[start:end + 1])
        except ValueError:
            return None
        need = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
        if not all(k in m for k in need):
            return None
        # ffmpeg občas vrátí "-inf" u ticha — s tím loudnorm neumí pracovat
        if any(str(m[k]).lstrip("-").lower().startswith("inf") for k in need):
            return None
        return m

    @staticmethod
    def _chosen_kbps(cfg):
        """Bitrate zvolený v hlavním okně, nebo None při „zkopírovat“."""
        mode = cfg["audio"]
        if mode == "custom":
            kb = re.sub(r"\D", "", cfg.get("audio_custom", "") or "")
            return int(kb) if kb else 128
        if mode.isdigit():
            return int(mode)
        return None

    def _stream_codec(self, cfg, stream):
        """Enkodér pro jednu stopu — buď zvolený, nebo odvozený z originálu."""
        want = cfg["adv_a"]["codec"]
        if want != "same":
            return want
        enc = SRC_TO_ENCODER.get((stream or {}).get("codec", "").lower())
        return enc or "aac"          # neznámý/nekódovatelný zdroj → bezpečné AAC

    def _audio_args(self, info, cfg):
        mode = cfg["audio"]
        if mode == "none":
            return ["-an"]

        a = cfg["adv_a"]
        streams = info.get("astreams") or []
        n_tracks = 1 if a["tracks"] == "first" else max(info.get("naudio", 0), 0)
        if n_tracks == 0:
            return []

        forced = self._audio_reencode_forced(cfg)
        if mode == "copy" and not forced:
            return ["-c:a", "copy"]

        chosen = self._chosen_kbps(cfg)
        args = []
        for i in range(n_tracks):
            st = streams[i] if i < len(streams) else {}
            codec = self._stream_codec(cfg, st)
            args += [f"-c:a:{i}", codec]

            if codec not in AUDIO_LOSSLESS:
                if chosen is not None:
                    kb = chosen
                elif a["codec"] == "same" and st.get("bitrate", 0) > 0:
                    kb = max(int(round(st["bitrate"] / 1000)), 8)   # jako originál
                else:
                    kb = 192                                        # rozumný default
                args += [f"-b:a:{i}", f"{kb}k"]

            chain = self._audio_filters(a, (info.get("loudness") or {}).get(i),
                                        st.get("rate", 0))
            if chain:
                args += [f"-filter:a:{i}", chain]

        if a["channels"] != "orig":
            args += ["-ac", a["channels"]]
        if a["samplerate"] != "orig":
            args += ["-ar", a["samplerate"]]
        return args

    def _build_audio_only_cmd(self, info, dst, cfg):
        """Video se kopíruje beze ztráty, mění se pouze zvuk."""
        # bez -nostdin: přes stdin se ffmpegu posílá „q“ = korektní ukončení
        cmd = [FFMPEG, "-hide_banner", "-y", "-i", str(info["path"]),
               "-map", "0:v:0"] + self._audio_map(cfg) + ["-map_metadata", "0"]
        container = self._resolve_container(cfg["container"], info)
        if container == "mkv":
            cmd += ["-map", "0:s?", "-c:s", "copy"]
        cmd += ["-c:v", "copy"]
        cmd += self._audio_args(info, cfg)
        if container == "mp4":
            cmd += ["-movflags", "+faststart"]
        cmd += ["-progress", "pipe:1", "-nostats", "-loglevel", "error", str(dst)]
        return cmd

    def _build_cmd(self, info, dst, cfg):
        if cfg.get("proc") == "audio":
            return self._build_audio_only_cmd(info, dst, cfg)
        key = cfg["enc"]
        adv = cfg["adv"]
        einfo = ENCODERS[key]
        family = ("nvenc" if key.endswith("_nvenc") else
                  "qsv" if key.endswith("_qsv") else
                  "amf" if key.endswith("_amf") else "x26x")
        is_hevc = key in ("hevc_nvenc", "hevc_qsv", "hevc_amf", "libx265")

        target = max(int(round(info.get("target") or 0)), 100_000)
        maxrate = int(target * max(1.0, adv["maxrate_mult"]))
        bufsize = max(int(target * adv["bufsize_mult"]), target // 2)
        cq = adv["cq"]
        rc = adv["rc_mode"]
        ten = cfg["depth"].startswith("10") and einfo["ten_bit"]

        cmd = [FFMPEG, "-hide_banner", "-y"]

        # HW dekódování vstupu (rámečky se vrací do RAM, aby fungovaly filtry)
        if adv["hwaccel"] and family == "nvenc":
            cmd += ["-hwaccel", "cuda"]
        elif adv["hwaccel"] and family == "qsv":
            cmd += ["-hwaccel", "qsv"]
        elif adv["hwaccel"] and family in ("amf", "x26x"):
            cmd += ["-hwaccel", "auto"]

        a_map = self._audio_map(cfg)
        container = self._resolve_container(cfg["container"], info)
        cmd += ["-i", str(info["path"]), "-map", "0:v:0"] + a_map + ["-map_metadata", "0"]
        if container == "mkv":
            cmd += ["-map", "0:s?", "-c:s", "copy"]

        vf = self._video_filters(info, adv)
        if vf:
            cmd += ["-vf", vf]

        cmd += ["-c:v", einfo["codec"]]

        # ---- řízení datového toku ----
        if rc == "cq":
            if family == "nvenc":
                cmd += ["-rc", "vbr", "-cq", f"{cq:.0f}", "-b:v", "0"]
            elif family == "qsv":
                cmd += ["-global_quality", f"{cq:.0f}"]
            elif family == "amf":
                cmd += ["-rc", "cqp", "-qp_i", f"{cq:.0f}", "-qp_p", f"{cq:.0f}"]
            else:
                cmd += ["-crf", f"{cq:.0f}"]
        else:
            cmd += ["-b:v", str(target), "-maxrate", str(maxrate), "-bufsize", str(bufsize)]
            if family == "nvenc":
                cmd += ["-rc", "cbr" if rc == "cbr" else "vbr"]

        # ---- specifika rodin enkodérů ----
        if family == "nvenc":
            cmd += ["-preset", cfg["preset"], "-tune", adv["tune"],
                    "-multipass", adv["multipass"],
                    "-spatial-aq", "1" if adv["spatial_aq"] else "0",
                    "-temporal-aq", "1" if adv["temporal_aq"] else "0",
                    "-rc-lookahead", str(int(adv["lookahead"]))]
            if adv["spatial_aq"]:
                cmd += ["-aq-strength", str(int(adv["aq_strength"]))]
            if adv["weighted_pred"]:
                cmd += ["-weighted_pred", "1", "-bf", "0"]   # nelze kombinovat s B-snímky
            else:
                cmd += ["-bf", str(int(adv["bframes"]))]
                if int(adv["bframes"]) > 0:
                    cmd += ["-b_ref_mode", adv["bref"]]
            if key == "hevc_nvenc":
                cmd += ["-profile:v", "main10" if ten else "main",
                        "-tier", "high" if adv["tier_high"] else "main"]
            elif key == "h264_nvenc":
                cmd += ["-profile:v", "high"]
            cmd += ["-pix_fmt", "p010le" if ten else "yuv420p"]

        elif family == "qsv":
            cmd += ["-preset", cfg["preset"],
                    "-profile:v", "main10" if ten else "main",
                    "-bf", str(int(adv["bframes"])),
                    "-pix_fmt", "p010le" if ten else "nv12"]

        elif family == "amf":
            cmd += ["-quality", cfg["preset"],
                    "-bf", str(int(adv["bframes"])),
                    "-pix_fmt", "p010le" if ten else "yuv420p"]

        else:  # libx265 / libx264
            cmd += ["-preset", cfg["preset"], "-bf", str(int(adv["bframes"])),
                    "-pix_fmt", "yuv420p10le" if ten else "yuv420p"]
            if adv["tune_x265"] != "none":
                cmd += ["-tune", adv["tune_x265"]]
            if key == "libx265":
                params = ["log-level=error"]
                if rc != "cq":
                    params += [f"vbv-maxrate={maxrate//1000}", f"vbv-bufsize={bufsize//1000}"]
                if adv["level"] != "auto":
                    params.append(f"level-idc={adv['level']}")
                if adv["tier_high"]:
                    params.append("high-tier=1")
                if adv["x265_params"].strip():
                    params.append(adv["x265_params"].strip())
                cmd += ["-x265-params", ":".join(params)]
            else:
                if rc != "cq":
                    cmd += ["-maxrate", str(maxrate), "-bufsize", str(bufsize)]
                if adv["x265_params"].strip():
                    cmd += ["-x264-params", adv["x265_params"].strip()]

        # ---- level (mimo libx265, kde jde přes x265-params) ----
        if adv["level"] != "auto" and key != "libx265":
            cmd += ["-level", adv["level"]]

        # ---- interval klíčových snímků ----
        if int(adv["gop"]) > 0:
            cmd += ["-g", str(int(adv["gop"]))]

        if int(adv["threads"]) > 0:
            cmd += ["-threads", str(int(adv["threads"]))]

        if is_hevc and container == "mp4":
            cmd += ["-tag:v", "hvc1"]

        # ---- zvuk ----
        cmd += self._audio_args(info, cfg)

        if container == "mp4":
            cmd += ["-movflags", "+faststart"]

        if adv["extra_args"].strip():
            try:
                import shlex
                cmd += shlex.split(adv["extra_args"].strip())
            except ValueError:
                pass

        cmd += ["-progress", "pipe:1", "-nostats", "-loglevel", "error", str(dst)]
        return cmd

    @staticmethod
    def _discard(tmp):
        """Smaže výhradně vlastní rozpracovaný soubor — nic jiného."""
        try:
            if ".vbc-part" in tmp.name and tmp.is_file():
                tmp.unlink()
        except OSError:
            pass

    def _keep_partial(self, tmp, dst):
        """Uloží rozdělaný soubor pod názvem s poznámkou „nedokončeno“.

        ffmpeg dostal „q“, takže stihl dokódovat rozpracované snímky a dopsat
        hlavičku — soubor je pak normálně přehratelný. Uloží se jen tehdy,
        když v něm opravdu nějaké video je.
        """
        try:
            if not tmp.is_file() or tmp.stat().st_size < 4096:
                return None
        except OSError:
            return None
        try:
            if (probe(tmp).get("duration") or 0) < 0.2:      # míň než pár snímků
                return None
        except Exception:
            return None
        target = self._unique_path(
            dst.with_name(dst.stem + L("partial_tag") + dst.suffix))
        try:
            os.replace(tmp, target)
        except OSError:
            return None
        return target

    def _convert_worker(self, cfg):
        todo = [(i, f) for i, f in enumerate(self.files) if not f.get("error")]
        total_dur = sum(f["duration"] for _, f in todo) or 1.0
        done_dur = 0.0
        t_start = time.time()
        stats = dict(ok=0, skip=0, err=0, in_bytes=0, out_bytes=0)

        for n, (idx, info) in enumerate(todo, 1):
            if self.stop_flag.is_set():
                break
            while self.pause_flag.is_set() and not self.stop_flag.is_set():
                time.sleep(0.2)
            if self.stop_flag.is_set():
                break

            rel = Path(info["rel"])
            dst = info["dst"]
            dst.parent.mkdir(parents=True, exist_ok=True)

            # poslední pojistka: zapisovat smíme jen dovnitř výstupní složky
            try:
                dst.resolve().relative_to(cfg["out_root"])
            except (ValueError, OSError):
                stats["err"] += 1
                done_dur += info["duration"]
                self.msgq.put(("row", (idx, "state", "✕ " + L("outside_out"), "err")))
                self.msgq.put(("total", (done_dur / total_dur, n, len(todo),
                                         t_start, stats)))
                continue

            if dst.exists() and cfg["collision"] == "skip":
                stats["skip"] += 1
                done_dur += info["duration"]
                self.msgq.put(("row", (idx, "state", L("st_exists"), "skip")))
                self.msgq.put(("total", (done_dur / total_dur, n, len(todo), t_start, stats)))
                continue

            if cfg["skip_bigger"] and info["vbitrate"] and info["target"] >= info["vbitrate"]:
                stats["skip"] += 1
                done_dur += info["duration"]
                self.msgq.put(("row", (idx, "state", L("st_nosmaller"), "skip")))
                self.msgq.put(("total", (done_dur / total_dur, n, len(todo), t_start, stats)))
                continue

            self.msgq.put(("cur", (str(rel), n, len(todo))))

            # dvouprůchodová EBU R128 — nejdřív změříme každou stopu
            info["loudness"] = {}
            adv_a = cfg["adv_a"]
            if (cfg["audio"] != "none" and adv_a["normalize"] == "r128_2pass"
                    and info.get("naudio", 0) > 0):
                self.msgq.put(("row", (idx, "state", L("st_measuring"), "active")))
                ntr = 1 if adv_a["tracks"] == "first" else info["naudio"]
                for si in range(ntr):
                    if self.stop_flag.is_set():
                        break
                    m = self._measure_loudness(info["path"], si, adv_a)
                    if m:
                        info["loudness"][si] = m
            if self.stop_flag.is_set():
                self.msgq.put(("row", (idx, "state", L("st_cancelled"), "skip")))
                break

            self.msgq.put(("row", (idx, "state", L("st_run"), "active")))

            # ffmpeg zapisuje do vlastního dočasného souboru; teprve hotový
            # výsledek se přesune na místo. Rozdělaný převod tak nikdy
            # nepoškodí soubor, který už ve výstupní složce je.
            tmp = dst.with_name(dst.stem + ".vbc-part" + dst.suffix)
            cmd = self._build_cmd(info, tmp, cfg)
            rc, err = self._run_ffmpeg(cmd, info, idx, done_dur, total_dur, n, len(todo),
                                       t_start, stats)

            ok = rc == 0 and tmp.exists() and tmp.stat().st_size > 0

            if self.stop_flag.is_set():
                kept = self._keep_partial(tmp, dst) if cfg["keep_partial"] else None
                if kept:
                    try:
                        psz = kept.stat().st_size
                    except OSError:
                        psz = 0
                    stats["in_bytes"] += info["size"]
                    stats["out_bytes"] += psz
                    self.msgq.put(("row", (idx, "state",
                                           L("st_partial", human_size(psz)), "done")))
                else:
                    self.msgq.put(("row", (idx, "state", L("st_cancelled"), "skip")))
                    self._discard(tmp)
                break

            if ok:
                osz = tmp.stat().st_size
                try:
                    os.replace(tmp, dst)          # atomicky, jen uvnitř výstupu
                except OSError as e:
                    ok = False
                    err = str(e)
                    self._discard(tmp)

            if ok:
                stats["ok"] += 1
                stats["in_bytes"] += info["size"]
                stats["out_bytes"] += osz
                ratio = osz / info["size"] * 100 if info["size"] else 0
                self.msgq.put(("row", (idx, "prog", self._bar_text(1.0), None)))
                self.msgq.put(("row", (idx, "state",
                                       f"✓ {human_size(osz)} ({ratio:.0f} %)", "done")))
            else:
                stats["err"] += 1
                msg = (err or "").strip().splitlines()
                msg = msg[-1][:70] if msg else f"ffmpeg exit code {rc}"
                self.msgq.put(("row", (idx, "state", "✕ " + msg, "err")))
                self.msgq.put(("log", f"[{rel}] {err}"))
                self._discard(tmp)

            done_dur += info["duration"]
            self.msgq.put(("total", (done_dur / total_dur, n, len(todo), t_start, stats)))

        self.msgq.put(("finished", stats))

    def _run_ffmpeg(self, cmd, info, idx, done_dur, total_dur, n, ntot, t_start, stats):
        try:
            # stdin je roura, aby šlo ffmpegu poslat „q“ (korektní ukončení)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 stdin=subprocess.PIPE, creationflags=CREATE_NO_WINDOW,
                                 bufsize=1, universal_newlines=True,
                                 encoding="utf-8", errors="replace")
        except Exception as e:
            return -1, str(e)

        self.cur_proc = p
        errbuf = []

        def drain_err():
            try:
                for line in p.stderr:
                    errbuf.append(line)
                    if len(errbuf) > 40:
                        del errbuf[0]
            except Exception:
                pass

        te = threading.Thread(target=drain_err, daemon=True)
        te.start()

        dur = info["duration"] or 0
        last_ui = 0.0
        t_file = time.time()
        cur = dict(speed="", fps="", size="", t=0.0, frame=0)

        stopping = False
        killer = None
        try:
            for line in p.stdout:
                if self.stop_flag.is_set() and not stopping:
                    # korektní ukončení: ffmpeg dokóduje rozpracované snímky
                    # a dopíše hlavičku, takže výsledek jde přehrát
                    stopping = True
                    self._request_quit(p)
                    self.msgq.put(("file", (0.0, L("finalizing"))))
                    killer = threading.Timer(25, lambda: self._kill(p))
                    killer.daemon = True
                    killer.start()
                if stopping:
                    continue          # rouru jen dočítáme, UI se už nemění
                line = line.strip()
                if "=" not in line:
                    continue
                k, _, v = line.partition("=")
                v = v.strip()
                if k == "out_time":
                    t = parse_ff_time(v)
                    if t is not None:
                        cur["t"] = t
                elif k == "speed":
                    cur["speed"] = v
                elif k == "fps":
                    cur["fps"] = v
                elif k == "frame":
                    try:
                        cur["frame"] = int(v)
                    except ValueError:
                        pass
                elif k == "total_size":
                    cur["size"] = v
                elif k == "progress" and v == "end":
                    cur["t"] = dur

                now = time.time()
                if now - last_ui < 0.18:
                    continue
                last_ui = now

                frac = min(cur["t"] / dur, 1.0) if dur > 0 else 0.0
                sp = 0.0
                try:
                    sp = float((cur["speed"] or "0").rstrip("x"))
                except ValueError:
                    pass
                eta_file = (dur - cur["t"]) / sp if sp > 0.01 and dur else None
                try:
                    osz = int(cur["size"] or 0)
                except ValueError:
                    osz = 0
                try:
                    fps_now = float(cur["fps"] or 0)
                except ValueError:
                    fps_now = 0.0
                wall = max(time.time() - t_file, 0.001)
                fps_avg = cur["frame"] / wall
                stat_txt = (f"{fps_now:.1f} fps ({L('avg')} {fps_avg:.1f} fps)"
                            f"   ·   {cur['speed'] or '0x'}   ·   {human_size(osz)}"
                            f"   ·   {L('remaining')} {human_time(eta_file)}")

                self.msgq.put(("file", (frac, stat_txt)))
                self.msgq.put(("row", (idx, "prog", self._bar_text(frac), None)))

                gfrac = (done_dur + cur["t"]) / total_dur
                self.msgq.put(("total", (gfrac, n, ntot, t_start, stats)))
        except Exception:
            pass

        p.wait()
        if killer:
            killer.cancel()
        te.join(timeout=1)
        try:
            if p.stdin and not p.stdin.closed:
                p.stdin.close()
        except Exception:
            pass
        self.cur_proc = None
        return p.returncode, "".join(errbuf)

    @staticmethod
    def _request_quit(p):
        """Pošle ffmpegu „q“ — ten dokončí zápis a sám se ukončí."""
        try:
            if p and p.stdin and not p.stdin.closed:
                p.stdin.write("q")
                p.stdin.flush()
        except Exception:
            pass

    @staticmethod
    def _kill(p):
        try:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        except Exception:
            pass

    def _toggle_pause(self):
        if not self.running:
            return
        if self.pause_flag.is_set():
            self.pause_flag.clear()
            if self.cur_proc:
                _proc_suspend_resume(self.cur_proc.pid, resume=True)
            self.btn_pause.set_text(L("pause"), "❚❚")
            self.cur_name.configure(fg=C["text"])
        else:
            self.pause_flag.set()
            if self.cur_proc:
                _proc_suspend_resume(self.cur_proc.pid, resume=False)
            self.btn_pause.set_text(L("resume"), "▶")
            self.cur_name.configure(fg=C["amber"])

    def _stop(self):
        if not self.running:
            return
        keep = self.keep_partial_var.get()
        if not messagebox.askyesno(APP_NAME,
                                   L("confirm_stop_keep") if keep else L("confirm_stop")):
            return
        if self.pause_flag.is_set():
            self.pause_flag.clear()
            if self.cur_proc:
                _proc_suspend_resume(self.cur_proc.pid, resume=True)
        self.stop_flag.set()
        if self.cur_proc:
            if keep:
                # ffmpeg si dopíše soubor sám; kdyby zatuhl, zabije ho hlídač
                self._request_quit(self.cur_proc)
            else:
                self._kill(self.cur_proc)

    # ------------------------------------------------------- UI event pump --
    def _pump(self):
        try:
            while True:
                kind, payload = self.msgq.get_nowait()

                if kind == "scanned":
                    info, i, total = payload
                    self._add_row(info)
                    self.cur_name.configure(text=L("scanning_n", i, total))
                    self.bar_file.set(i / total, L("scan_load", i, total))

                elif kind == "scan_tick":
                    i, total = payload
                    self.bar_file.set(i / total, L("scan_load", i, total))

                elif kind == "scan_done":
                    nonvideo = payload or 0
                    self.btn_scan.set_enabled(True)
                    self.btn_add.set_enabled(True)
                    self.bar_file.set(0, "")
                    ok = sum(1 for f in self.files if not f.get("error"))
                    bad = len(self.files) - ok
                    added = len(self.files) - getattr(self, "_n_before_add", 0)
                    if getattr(self, "_n_before_add", 0):
                        txt = L("added_n", added, len(self.files))
                    else:
                        txt = L("loaded", ok) + (L("loaded_bad", bad) if bad else "")
                    if nonvideo:
                        txt += L("skipped_nonvideo", nonvideo)
                    self._n_before_add = 0
                    self.cur_name.configure(text=txt)
                    self._update_summary()

                elif kind == "encoders":
                    self._apply_encoder_availability()

                elif kind == "row":
                    idx, col, val, tag = payload
                    iid = str(idx)
                    try:
                        self.tree.set(iid, col, val)
                        if tag:
                            base = "even" if idx % 2 else "odd"
                            self.tree.item(iid, tags=(base, tag))
                    except tk.TclError:
                        pass

                elif kind == "cur":
                    rel, n, tot = payload
                    self.cur_name.configure(text=f"[{n}/{tot}]  {rel}", fg=C["text"])
                    try:
                        self.tree.see(str(self.files.index(
                            next(f for f in self.files if str(f["rel"]) == rel))))
                    except (StopIteration, ValueError, tk.TclError):
                        pass

                elif kind == "file":
                    frac, stat_txt = payload
                    self.bar_file.set(frac)
                    self.cur_stats.configure(text=stat_txt)

                elif kind == "total":
                    frac, n, tot, t_start, stats = payload
                    frac = max(0.0, min(1.0, frac))
                    self.bar_total.set(frac)
                    elapsed = time.time() - t_start
                    eta = elapsed / frac - elapsed if frac > 0.005 else None
                    saved = ""
                    if stats["out_bytes"]:
                        saved = "   ·   " + L(
                            "saved",
                            human_size(stats["in_bytes"] - stats["out_bytes"]),
                            f"{100 - stats['out_bytes']/stats['in_bytes']*100:.0f}")
                    self.total_stats.configure(
                        text=f"{frac*100:.1f} %   ·   {L('file_n', n, tot)}   ·   "
                             f"{L('elapsed')} {human_time(elapsed)}   ·   "
                             f"{L('remaining')} {human_time(eta)}{saved}")

                elif kind == "log":
                    print(payload, file=sys.stderr)

                elif kind == "finished":
                    self._on_finished(payload)

        except queue.Empty:
            pass
        self._pump_id = self.after(80, self._pump)

    def _on_finished(self, stats):
        self.running = False
        self.btn_start.set_enabled(True)
        self.btn_scan.set_enabled(True)
        self.btn_pause.set_enabled(False)
        self.btn_stop.set_enabled(False)
        self.btn_pause.set_text(L("pause"), "❚❚")
        self.cur_name.configure(fg=C["text"])
        cancelled = self.stop_flag.is_set()
        self.cur_name.configure(text=L("stopped_by_user") if cancelled else L("done"))
        self.cur_stats.configure(text="")
        self.bar_file.set(0 if cancelled else 1.0, "")
        if not cancelled:
            self.bar_total.set(1.0)
            msg = "\n".join((L("res_converted", stats["ok"]),
                             L("res_skipped", stats["skip"]),
                             L("res_errors", stats["err"])))
            if stats["out_bytes"]:
                msg += "\n\n" + "\n".join((
                    L("res_before", human_size(stats["in_bytes"])),
                    L("res_after", human_size(stats["out_bytes"])),
                    L("res_saved",
                      human_size(stats["in_bytes"] - stats["out_bytes"]),
                      f"{100 - stats['out_bytes']/stats['in_bytes']*100:.1f}")))
            messagebox.showinfo(APP_NAME, msg)

    # ------------------------------------------------------------ settings --
    def _save_settings(self):
        try:
            CONFIG_PATH.write_text(json.dumps(dict(
                lang=LANG,
                # vstupní složka se schválně neukládá — po startu má být prázdná
                out=self.out_var.get(),
                pct=self.pct_var.get(), mode=self._mode_key(),
                fix=self.fix_var.get(), enc=self._enc_key(),
                depth=self.depth_var.get(), preset=self._preset_value(),
                container=self._container_key(), audio=self._audio_key(),
                rounding=self._round_key(), proc=self._proc_key(),
                suffix=self.suffix_var.get(), recurse=self.recurse_var.get(),
                ignore=self.ignore_var.get(),
                skip_bigger=self.skip_bigger_var.get(), qname=self.qname_var.get(),
                keep_partial=self.keep_partial_var.get(),
                strip_tag=self.strip_tag_var.get(),
                overwrite=self.overwrite_var.get(), adv=self.adv,
                adv_a=self.adv_a, audio_custom=self.acustom_var.get(),
            ), indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_settings(self):
        if not CONFIG_PATH.exists():
            return
        try:
            d = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        self.in_var.set("")                 # vstupní složka se nepamatuje
        self.out_var.set(d.get("out", ""))
        self.pct_var.set(int(d.get("pct", 70)))
        self.pct_scale.set(self.pct_var.get())
        self.pct_lbl.configure(text=f"{self.pct_var.get()} %")
        self.fix_var.set(d.get("fix", "4000"))
        if d.get("mode") in BR_MODES:
            self.mode_var.set(loc(BR_MODES)[d["mode"]])
        if d.get("enc") in ENCODERS:
            self.enc_var.set(ENCODERS[d["enc"]]["label"])
            self._on_encoder_change()
        if d.get("preset"):
            self.preset_var.set(self._preset_label(d["preset"]))
        self.depth_var.set(d.get("depth", "10 bit"))
        self.cont_var.set(loc(CONTAINERS)[d["container"]
                                          if d.get("container") in CONTAINERS else "mp4"])
        self.proc_var.set(loc(PROC_MODES)[d["proc"]
                                          if d.get("proc") in PROC_MODES else "both"])
        self.qname_var.set(bool(d.get("qname", True)))
        self.strip_tag_var.set(bool(d.get("strip_tag", True)))
        if d.get("audio") in AUDIO_MODES:
            self.audio_var.set(loc(AUDIO_MODES)[d["audio"]])
        self.round_var.set(loc(ROUNDING)[d.get("rounding")
                                         if d.get("rounding") in ROUNDING else "100"])
        self.suffix_var.set(d.get("suffix", ""))
        self.recurse_var.set(bool(d.get("recurse", False)))
        self.ignore_var.set(d.get("ignore", "compressed"))
        self.skip_bigger_var.set(bool(d.get("skip_bigger", True)))
        self.keep_partial_var.set(bool(d.get("keep_partial", True)))
        self.overwrite_var.set(bool(d.get("overwrite", False)))
        self.acustom_var.set(d.get("audio_custom", "128"))
        for store, defaults, saved in ((self.adv, ADV_DEFAULTS, d.get("adv")),
                                       (self.adv_a, ADV_A_DEFAULTS, d.get("adv_a"))):
            for k, default in defaults.items():
                if saved and k in saved:
                    try:
                        store[k] = type(default)(saved[k])
                    except (TypeError, ValueError):
                        store[k] = default
        self._on_audio_change()
        self._update_adv_hint()

    def _on_close(self):
        if self.running:
            if not messagebox.askyesno(APP_NAME, L("confirm_close")):
                return
            self.stop_flag.set()
            if self.cur_proc:
                self._kill(self.cur_proc)
        self._save_settings()
        try:                                   # ať Tk nehlásí visící „after“
            if getattr(self, "_pump_id", None):
                self.after_cancel(self._pump_id)
        except tk.TclError:
            pass
        self.destroy()


def _preload_language():
    """Jazyk musí být znám dřív, než se postaví UI."""
    global LANG
    try:
        d = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if d.get("lang") in LANG_NAMES:
            LANG = d["lang"]
    except (OSError, ValueError):
        pass


def _installation_check():
    """Return a process-friendly status without opening the GUI or touching media."""
    if not FFMPEG or not FFPROBE or TkinterDnD is None:
        return 1
    try:
        for tool in (FFMPEG, FFPROBE):
            result = run_hidden([tool, "-version"], timeout=15)
            if result.returncode != 0:
                return 1
    except (OSError, subprocess.SubprocessError):
        return 1
    return 0


if __name__ == "__main__":
    _preload_language()
    if "--check" in sys.argv:
        raise SystemExit(_installation_check())
    if "--version" in sys.argv:
        print(f"{APP_NAME} {APP_VER}")
        raise SystemExit(0)
    App().mainloop()

# Created by FajkPes with assistance from ChatGPT Codex and Claude Code.
