> **Current application: Video Bitrate Compressor 1.4**, published 2026-10-23. Download the portable Windows ZIP from Releases, unpack it completely and run `VideoBitrateCompressor.exe`. Full FFmpeg/FFprobe 8.1.2 are in `tools/`; all three programs must remain together. Personal settings, job/project state, benchmark videos and old backups are excluded.

# Video Bitrate Compressor 1.4

Spouštěj `VideoBitrateCompressor.exe` nebo `Kompresor videa.bat`. Aplikace obsahuje vlastní běhové prostředí a při tomto způsobu spuštění nepotřebuje systémový Python.

## Windows: řízený přístup ke složkám

V Zabezpečení Windows → Ochrana před viry a hrozbami → Spravovat ochranu před ransomwarem → Povolit aplikaci prostřednictvím řízeného přístupu ke složkám povol konkrétní soubory:

- `VideoBitrateCompressor.exe` z této složky (nastavení a projekty).
- `tools/ffmpeg.exe` z této složky (zápis komprimovaného videa).

Povolení systémového `pythonw.exe` není pro samostatnou aplikaci potřeba. Windows rozlišuje cestu aplikace, takže složku s programem a nástroji po povolení ponech na stejném místě. `ffprobe.exe` slouží ke čtení a kontrole videí.

## Ovládání

- Rozlišení a FPS jsou na hlavní stránce; výchozí je **Jako zdroj**. Rozlišení SD/HD/Full HD/2K (QHD, 1440p)/4K slouží jako horní limit a menší zdroje se automaticky nezvětšují.
- **Použít na zbývající videa** přenese aktuální nastavení na čekající videa. Rozpracované a dokončené video zachová své nastavení. Při této změně se použijí nové volné názvy, aby nedošlo k nechtěnému přepsání.
- **Skrýt nastavení** uvolní většinu okna pro seznam. Nastavení má vlastní posuvník. Tabulka má vlastní vodorovné i svislé posouvání.
- Malé tlačítko vedle přepínání jazyka mění rozložení mezi nastavením nahoře a nastavením vlevo. Videa i ovládání zůstávají spolu. V režimu vedle sebe jde měnit dělení tažením čáry. Rozložení, poloha dělení a vlastní rozměry každého režimu se pamatují mezi spuštěními. Výchozí rozměry jsou 1180×1120 px pro svislé a 1880×900 px pro boční rozložení, vždy omezené obrazovkou.
- Při tažení dělicí čáry se pohybuje náhled; ovládací prvky se přeskládají jednou po puštění myši. Nedochází k úplnému překreslování obou panelů při každém posunu o pixel.
- Kliknutí na záhlaví seřadí tabulku; opakování obrátí směr. Jde o pořadí zobrazení. Odebírání funguje pravým klikem nebo klávesou Delete a nesmaže soubory z disku. Během převodu/načítání je odebrání vypnuté.
- **Web Optimized** zapisuje hlavičku MP4/MOV na začátek souboru. **Passthru Common Metadata** přebírá metadata a kapitoly ze zdroje.
- Automatický kontejner zachovává MP4, MOV, M4V nebo MKV; u ostatních zdrojových kontejnerů použije MKV.

## Spolehlivost výstupu

Automatický GOP nastavuje interval podle výstupních FPS a vynucuje klíčový snímek po 2 sekundách. U NVENC se vynucují IDR snímky. Ruční GOP je počet snímků.

Před označením dokončeného překódovaného videa aplikace kontroluje délku, počet zvukových stop, klíčové snímky na začátku delšího videa a skutečné přeskočení doprostřed s dekódováním snímku. Tato kontrola není úplné dekódování celého souboru. Nevyhovující výstup nenahradí existující finální soubor.

Video prochází pamětí; aplikace nevytváří mezilehlé rozbalené snímky ani nekomprimovaná videa. Komprimovaný výstup se nejdříve zapisuje pod unikátním dočasným názvem ve výstupní složce, zkontroluje a atomicky přejmenuje. Přejmenování nevyžaduje druhou kopii videa. Malý JSON projekt ukládá nastavení a stav pro obnovení dávky; neobsahuje obrazová data. Správa stránkovací paměti zůstává systému Windows.

## GPU a profily

NVENC enkóduje na NVIDIA GPU. Bez obrazových filtrů podporovaný vstup zůstává při CUDA dekódování ve VRAM. Filtry, které vyžadují CPU, potřebují přenos snímků do RAM. Zvuk a normalizace se zpracovávají na CPU.

Doostření má výchozí sílu 0 (vypnuto). Po zvýšení síly se ve výchozím nastavení použije `unsharp` na CPU, který byl při měření rychlejší. Volitelné GPU doostření používá `unsharp_opencl`, pokud funkční GPU a FFmpeg tento filtr podporují. Plná sestava FFmpeg v `tools` byla ověřena s RTX 3070 včetně 10bit výstupu. Posuvník ovládá skutečnou sílu doostření. Pokud OpenCL není dostupné, použije se CPU. GPU doostření může snížit práci CPU a přitom být celkově pomalejší kvůli přenosům a inicializaci. Dříve uložený projekt zachová svou výslovně uloženou volbu.

Profily mění pokročilé parametry i rychlostní preset. **Ultra rychlý** používá NVENC p1 nebo CPU ultrafast. **Rychlý** používá p4. **Vyvážený** p5 a **Ultra kvalita** p7. Profil s interním klíčem `handbrake` se nyní jmenuje Rychlý; nepředstírá shodu s aktuálními presety jiné aplikace. Změny profilu zachovávají zvolený režim bitrate, rozlišení a FPS.

## Ověření a měření

- `python -m unittest test_regressions -v` provádí skutečné převody, kontroly NVENC/OpenCL (pokud jsou dostupné), I-snímků, přeskakování, zvuku, projektů, velikostí a UI.
- `python benchmark_profiles.py` měří čtyři profily na stejném syntetickém 8s videu 1280×720/60 FPS při cíli 4 Mb/s.
- `python benchmark_gpu_options.py` porovnává při stejném p5 prostorové/časové AQ a doostření; uvádí medián ze tří převodů, čas CPU procesu FFmpeg a časy klíčových snímků.
- Výsledky jsou v `benchmark-results/results.json` a `benchmark-results/gpu-options.json`. Krátký syntetický test neurčuje kvalitu ani rychlost každého skutečného videa.

## Přibalené nástroje

Plná sestava FFmpeg 8.1.2 pochází z https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z a byla ověřena SHA-256 `0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059`. Licence je v `tools/LICENSE`. Zdrojový kód FFmpeg: https://github.com/FFmpeg/FFmpeg (větev release/8.1). Původní essentials nástroje v kořenové složce zůstaly zachované jako záloha; aplikace upřednostňuje `tools`.
