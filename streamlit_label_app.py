# streamlit_label_app_local_template_nohistory.py
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import os, platform, json, tempfile, io, shutil, subprocess
from typing import List, Dict, Tuple, Any

st.set_page_config(page_title="Label Generator", layout="wide")

# ---- BUNDLED FONTS ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

BUNDLED_FONTS = {
    "NotoSansDevanagari-Regular.ttf": os.path.join(FONTS_DIR, "NotoSansDevanagari-Regular.ttf"),
    "Mukta-Regular.ttf": os.path.join(FONTS_DIR, "Mukta-Regular.ttf"),
    "NotoSansBengali-Regular.ttf": os.path.join(FONTS_DIR, "NotoSansBengali-Regular.ttf"),
    "DejaVuSans.ttf": os.path.join(FONTS_DIR, "DejaVuSans.ttf"),
}

# ---------------------------
# CONFIG
# ---------------------------
TEMPLATE_JSON_PATH = "./template_clean.json"

# ---------------------------
# SAMPLE MASTER LABELS
# ---------------------------
SAMPLE_IMAGES = {
    "Master Label Johnny Walker": "Master Label Johnny Walker.png",
    "Master Label VAT": "Master Label VAT.png"
}

# ---------------------------
# RULES
# ---------------------------
RULES: Dict[str, Dict[str, str]] = {
    "Uttar Pradesh": {
        "V_STATE_RESTRICTION_EN": "FOR SALE IN UTTAR PRADESH ONLY",
        "V_STATE_RESTRICTION_REG": "उप में केवल बिक्री के लिए",
        "V_AGE_RESTR_EN": "Not for sale to persons below 25 years of age.",
        "NOT_SOLD_IN": "Not for sale in Bihar",
        "V_HEALTH_WARN_EN": "CONSUMPTION OF ALCOHOL IS INJURIOUS TO HEALTH,\n BE SAFE-DON'T DRINK AND DRIVE.",
        "V_HEALTH_WARN_REG": "शराब स्वास्थ्य के लिए हानिकारक है.",
        "IMPORT_LISC": "1001245678",
        "Lisc_no": "1234567890",
        "V_StateLicense": "UP. EXCISE REGD. NO. E AC-45/110W-106046"
    },
    "Rajasthan": {
        "V_STATE_RESTRICTION_EN": "FOR SALE IN RAJASTHAN ONLY",
        "V_STATE_RESTRICTION_REG": "उप में केवल बिक्री के लिए",
        "V_AGE_RESTR_EN": "Not for sale to persons below 21 years of age.",
        "NOT_SOLD_IN": "Not for sale in Madhya Pradesh",
        "V_HEALTH_WARN_EN": "CONSUMPTION OF ALCOHOL IS INJURIOUS TO HEALTH,\n BE SAFE-DON'T DRINK AND DRIVE.",
        "V_HEALTH_WARN_REG": "शराब स्वास्थ्य के लिए हानिकारक है.",
        "IMPORT_LISC": "1001234567",
        "Lisc_no": "1234567890",
        "V_StateLicense": "RA. EXCISE REGD. NO. E AC-45/110W-10000"
    }
}

# ---------------------------
# FONT DETECT
# ---------------------------
def has_devanagari(text: str) -> bool:
    return any('\u0900' <= ch <= '\u097F' for ch in text)

def has_bengali(text: str) -> bool:
    return any('\u0980' <= ch <= '\u09FF' for ch in text)

# ---------------------------
# FONT CANDIDATES
# ---------------------------
def candidate_fonts_for_script(script: str) -> List[str]:
    if script == "devanagari":
        return [
            BUNDLED_FONTS.get("NotoSansDevanagari-Regular.ttf"),
            BUNDLED_FONTS.get("Mukta-Regular.ttf"),
            "NotoSansDevanagari-Regular.ttf",
            "Mukta-Regular.ttf",
            "Mangal.ttf",
            "DejaVuSans.ttf"
        ]
    elif script == "bengali":
        return [
            BUNDLED_FONTS.get("NotoSansBengali-Regular.ttf"),
            "NotoSansBengali-Regular.ttf",
            "DejaVuSans.ttf"
        ]
    else:
        return [
            BUNDLED_FONTS.get("DejaVuSans.ttf"),
            "DejaVuSans.ttf",
            "Arial.ttf"
        ]

# ---------------------------
# FONT LOADER (FIXED)
# ---------------------------
def try_load_font(candidate: str, size: int):
    # try path directly
    try:
        if candidate and os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    except Exception:
        pass

    # try bundled shortcut name
    try:
        if candidate:
            fname = os.path.basename(candidate)
            if fname in BUNDLED_FONTS:
                path = BUNDLED_FONTS[fname]
                if os.path.exists(path):
                    return ImageFont.truetype(path, size)
    except Exception:
        pass

    # try by name (system)
    try:
        return ImageFont.truetype(candidate, size)
    except Exception:
        pass

    return None

def font_supports_text(font, text):
    try:
        img = Image.new("L",(10,10))
        d = ImageDraw.Draw(img)
        b = d.textbbox((0,0), text, font=font)
        return (b[2]-b[0])>0
    except Exception:
        return False

# ---------------------------
# BEST FONT FIT
# ---------------------------
def find_best_font_for_box(draw, text, box_w, box_h, max_size=400, min_size=6):
    if has_devanagari(text):
        candidates = candidate_fonts_for_script("devanagari")
    elif has_bengali(text):
        candidates = candidate_fonts_for_script("bengali")
    else:
        candidates = candidate_fonts_for_script("latin")

    best_font=None; best_score=-1
    for cand in candidates:
        if not cand:
            continue
        test = try_load_font(cand,40)
        if not test or not font_supports_text(test,text):
            continue

        lo=min_size; hi=max_size; chosen=min_size
        while lo<=hi:
            mid=(lo+hi)//2
            f=try_load_font(cand,mid)
            if not f:
                hi=mid-1; continue
            b=draw.textbbox((0,0),text,font=f)
            w=b[2]-b[0]; h=b[3]-b[1]
            if w<=box_w and h<=box_h:
                chosen=mid; lo=mid+1
            else:
                hi=mid-1

        f=try_load_font(cand,chosen)
        if not f: continue
        b=draw.textbbox((0,0),text,font=f)
        score=min((b[2]-b[0])/box_w,(b[3]-b[1])/box_h)
        if score>best_score:
            best_score=score; best_font=f
        if best_score>0.98: break

    if not best_font:
        return ImageFont.load_default()
    return best_font

# ---------------------------
# UTIL
# ---------------------------
def percent_to_pixels(bbox_pct, image_size):
    W,H=image_size
    x,y,w,h=bbox_pct
    return int(x/100*W),int(y/100*H),int(w/100*W),int(h/100*H)

# ---------------------------
# VECTOR/AI => PNG conversion helper
# ---------------------------
def convert_to_png(input_path: str) -> str:
    """
    Try several methods to rasterize a vector-like file (ai/pdf/eps/svg) into a PNG.
    Returns path to PNG on success or raises RuntimeError with guidance on failure.
    """
    out_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name

    # 1) Try Pillow directly (works if AI saved with PDF-compat)
    try:
        im = Image.open(input_path)
        im.load()
        im = im.convert("RGBA")
        im.save(out_png)
        return out_png
    except Exception:
        pass

    # 2) Try pdf2image (poppler). Requires poppler installed and pdf2image pip package.
    try:
        from pdf2image import convert_from_path
        # convert first page
        pages = convert_from_path(input_path, dpi=300, first_page=1, last_page=1)
        pages[0].save(out_png, "PNG")
        return out_png
    except Exception:
        pass

    # 3) Try wand (ImageMagick). Requires wand pip package and ImageMagick installed.
    try:
        from wand.image import Image as WandImage
        with WandImage(filename=input_path, resolution=300) as wimg:
            wimg.format = 'png'
            wimg.save(filename=out_png)
        return out_png
    except Exception:
        pass

    # 4) Try ImageMagick CLI (magick or convert) via subprocess
    for cmd in ("magick", "convert"):
        if shutil.which(cmd):
            # try first page explicit index if supported
            try_cmds = [
                [cmd, input_path + "[0]", "-density", "300", out_png],
                [cmd, input_path, "-density", "300", out_png]
            ]
            for cl in try_cmds:
                try:
                    subprocess.run(cl, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if os.path.exists(out_png) and os.path.getsize(out_png) > 0:
                        return out_png
                except Exception:
                    continue

    # If all failed, raise with actionable message
    msg = (
        "Failed to convert vector/AI file to PNG. Possible fixes:\n"
        " - Export/save the .ai file from Illustrator as 'PDF compatible' or export as PNG/JPG and upload that.\n"
        " - Install system dependencies on the host: ImageMagick (magick/convert) and/or poppler utils (for pdf2image).\n"
        " - Ensure Python packages 'wand' and/or 'pdf2image' are installed in your environment.\n\n"
        "Local install examples (mac):\n"
        "  brew install imagemagick poppler\n"
        "  pip install wand pdf2image\n\n"
        "If you cannot install system packages on the deploy target, please export to PNG locally and upload the PNG."
    )
    raise RuntimeError(msg)

# ---------------------------
# RENDER (UNCHANGED)
# ---------------------------
def render_label(master_img_path, template_entry, state_name, rules, output_path, debug=True):
    img=Image.open(master_img_path).convert("RGBA")
    W,H=img.size
    draw=ImageDraw.Draw(img)

    for region in template_entry.get("regions",[]):
        label=region.get("label")
        if label not in rules[state_name]: continue
        text=rules[state_name][label]

        left,top,w,h=percent_to_pixels(
            (region["x"],region["y"],region["width"],region["height"]),
            (W,H)
        )
        w=max(1,w); h=max(1,h)

        font=find_best_font_for_box(draw,text,w,h)
        tb=draw.textbbox((0,0),text,font=font)
        tw=tb[2]-tb[0]; th=tb[3]-tb[1]

        x=left+4
        y=top+(h-th)/2-tb[1]
        if y<top: y=top

        draw.text((x,y),text,fill=(0,0,0,255),font=font)

        if debug:
            draw.rectangle([left,top,left+w,top+h],outline="red",width=1)

    img.convert("RGB").save(output_path)
    return output_path

# ---------------------------
# UI
# ---------------------------
st.title("Label Generator")

if not os.path.exists(TEMPLATE_JSON_PATH):
    st.error("Template JSON missing")
    st.stop()

templates=json.load(open(TEMPLATE_JSON_PATH,"r",encoding="utf-8"))

col_inputs, col_result = st.columns([1,1])

with col_inputs:
    st.markdown("<h2 style='text-align: center'>Inputs</h2>", unsafe_allow_html=True)

    sample_choice = st.selectbox(
        "Use sample master label (optional)",
        ["None"] + list(SAMPLE_IMAGES.keys())
    )

    # allow vector types + raster types
    uploaded_img = st.file_uploader(
        "Or upload master label (PNG/JPG/AI/PDF/EPS/SVG)",
        type=["png","jpg","jpeg","ai","pdf","eps","svg"]
    )

    template_names=[os.path.basename(t.get("image","unnamed")) for t in templates]
    sel_name=st.selectbox("Select template", options=template_names)
    template_entry=templates[template_names.index(sel_name)]

    state_choice=st.selectbox("Select state", options=list(RULES.keys()))
    debug=st.checkbox("Show debug boxes", value=True)
    generate_btn=st.button("Generate")

with col_result:
    st.markdown("<h2 style='text-align: center'>Results</h2>", unsafe_allow_html=True)

if generate_btn:
    # decide master image
    try:
        if sample_choice!="None":
            master_path = SAMPLE_IMAGES[sample_choice]
            if not os.path.exists(master_path):
                st.error("Sample image not found")
                st.stop()

        elif uploaded_img:
            # save uploaded to temp file with original suffix
            ext = os.path.splitext(uploaded_img.name)[1].lower()
            tmp_master = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            tmp_master.write(uploaded_img.getvalue())
            tmp_master.close()
            original_path = tmp_master.name

            # If vector-like, try conversion
            if ext in [".ai", ".pdf", ".eps", ".svg"]:
                try:
                    master_path = convert_to_png(original_path)
                except Exception as e:
                    st.error(f"Conversion error: {e}")
                    st.stop()
            else:
                # already raster
                master_path = original_path
        else:
            st.error("Upload image or select sample")
            st.stop()

        tmp_out=tempfile.NamedTemporaryFile(delete=False,suffix=".png")
        tmp_out.close()
        out_path=tmp_out.name

        render_label(master_path, template_entry, state_choice, RULES, out_path, debug)

        master_bytes=open(master_path,"rb").read()
        final_bytes=open(out_path,"rb").read()

        c1,c2=col_result.columns(2)
        with c1:
            st.image(master_bytes,caption="Master",width=350)
        with c2:
            st.image(final_bytes,caption="Final",width=350)
            st.download_button("Download final",data=final_bytes,file_name="final_label.png")

        st.success("Done")
    except Exception as e:
        st.exception(e)
