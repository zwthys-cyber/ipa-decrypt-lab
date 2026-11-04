"""Bounded IPA display metadata and optional JPEG document thumbnail."""
import io
import plistlib
import re
import unicodedata
import urllib.parse
import urllib.request
import zipfile

MAX_ICON = 4 * 1024 * 1024

def component(value, fallback, budget=120):
    if not isinstance(value, str):
        value = fallback
    value = unicodedata.normalize("NFC", value)
    value = "".join("_" if c in '/\\:*?"<>|' else c for c in value
                    if not unicodedata.category(c).startswith("C"))
    value = re.sub(r"\s+", " ", value).strip(" .")
    value = value.encode("utf-8")[:budget].decode("utf-8", "ignore").strip(" .")
    return value or fallback

def filename(info, app_id):
    name = component(info.get("display_name"), app_id)
    version = component(info.get("version"), "unknown", 48)
    return name + "_" + version + ".ipa"

def jpeg(raw):
    from PIL import Image
    if not raw or len(raw) > MAX_ICON:
        return None
    with Image.open(io.BytesIO(raw)) as source:
        if source.format not in ("PNG", "JPEG", "WEBP") or not (0 < source.width <= 2048 and 0 < source.height <= 2048):
            return None
        source.thumbnail((320, 320))
        rgba = source.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, "white")
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        output = io.BytesIO()
        canvas.save(output, format="JPEG", quality=85)
        data = output.getvalue()
        return data if len(data) < 200000 else None

def archive_thumbnail(path):
    with zipfile.ZipFile(path) as archive:
        roots = [e for e in archive.infolist() if e.filename.startswith("Payload/")
                 and e.filename.count("/") == 2 and e.filename.endswith(".app/Info.plist")]
        if len(roots) != 1 or roots[0].file_size > 1024*1024:
            return None
        info = plistlib.loads(archive.read(roots[0]))
        if not isinstance(info, dict):
            return None
        folder = roots[0].filename.rsplit("/", 1)[0] + "/"
        declared = []
        for key in ("CFBundleIcons", "CFBundleIcons~ipad"):
            icons = info.get(key, {})
            primary = icons.get("CFBundlePrimaryIcon", {}) if isinstance(icons, dict) else {}
            files = primary.get("CFBundleIconFiles", []) if isinstance(primary, dict) else []
            if isinstance(files, list):
                declared.extend(f for f in files if isinstance(f, str))
        files = info.get("CFBundleIconFiles", [])
        if isinstance(files, list):
            declared.extend(f for f in files if isinstance(f, str))
        if isinstance(info.get("CFBundleIconFile"), str):
            declared.append(info["CFBundleIconFile"])
        stems = [f.removesuffix(".png") for f in declared
                 if "/" not in f and "\\" not in f and len(f) <= 200]
        candidates = []
        for entry in archive.infolist():
            if not entry.filename.startswith(folder):
                continue
            basename = entry.filename[len(folder):]
            if "/" in basename or not basename.lower().endswith(".png") or not 0 < entry.file_size <= MAX_ICON:
                continue
            if any(basename == s+".png" or basename.startswith(s+"@") or basename.startswith(s+"~") for s in stems):
                candidates.append(entry)
            elif not stems and basename.lower().startswith(("appicon", "icon")):
                candidates.append(entry)
        for entry in sorted(candidates, key=lambda e:e.file_size, reverse=True)[:6]:
            try:
                result = jpeg(archive.read(entry))
                if result:
                    return result
            except Exception:
                continue
    return None

def store_thumbnail(app_id):
    # Public metadata only; never follow arbitrary URLs or forward credentials.
    from app_preflight import check_app, NoRedirect
    info = check_app(app_id, historical=True)
    url = info.get("artworkUrl512") or info.get("artworkUrl100") or ""
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".mzstatic.com")
            or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.fragment):
        return None
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(url, timeout=8) as response:
        return jpeg(response.read(MAX_ICON+1))

def thumbnail(path, app_id):
    # Presentation is optional and must never cause retransmission or reject a valid IPA.
    for read in (lambda: archive_thumbnail(path), lambda: store_thumbnail(app_id)):
        try:
            result = read()
            if result:
                return result
        except Exception:
            pass
    return None
