# streamlit_label_app_local_template_nohistory.py
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import os, platform, json, tempfile, io
from typing import List, Dict, Tuple, Any

st.set_page_config(page_title="Label Renderer", layout="wide")

# ---------------------------
# CONFIG: update this path to your local cleaned template JSON (no UI input)
# ---------------------------
TEMPLATE_JSON_PATH = "./template_clean.json"   # <-- put your cleaned JSON here (local)

# ---------------------------
# Optional: built-in sample master images (place next to script)
# ---------------------------
SAMPLE_MAP = {
    "Master Label Sample": "Master Label Sample.png",
    "Master Label VAT": "Master Label VAT.png"
}

# ---------------------------
# Demo rules (your mapping)
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
# Utility engine code (same robust renderer)
# ---------------------------
def has_devanagari(text: str) -> bool:
    return any('\u0900' <= ch <= '\u097F' for ch in text)

def has_bengali(text: str) -> bool:
    return any('\u0980' <= ch <= '\u09FF' for ch in text)

def candidate_fonts_for_script(script: str) -> List[str]:
    system = platform.system()
    cands = []
    if script == "devanagari":
        cands = [
            "NotoSansDevanagari-Regular.ttf","NotoSansDevanagari-Regular","Lohit-Devanagari.ttf",
            "Mukta-Regular.ttf","Devanagari Sangam MN.ttf","Mangal.ttf","Arial Unicode.ttf",
            "Arial Unicode MS.ttf","/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
            "/usr/share/fonts/truetype/lohit/lohit-devanagari.ttf","/usr/share/fonts/truetype/mukta/Mukta-Regular.ttf",
            "/Library/Fonts/Mukta-Regular.ttf","/Library/Fonts/Devanagari Sangam MN.ttf",
            "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttf","DejaVuSans.ttf"
        ]
    elif script == "bengali":
        cands = [
            "NotoSansBengali-Regular.ttf","NotoSansBengali-Regular","Lohit-Bengali.ttf","Bangla.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf","DejaVuSans.ttf"
        ]
    else:
        cands = ["DejaVuSans.ttf","Arial.ttf","LiberationSans-Regular.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]

    if system == "Darwin":
        cands += ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf","/Library/Fonts/Arial Unicode.ttf"]
    elif system == "Windows":
        cands += ["C:/Windows/Fonts/arialuni.ttf","C:/Windows/Fonts/arial.ttf","C:/Windows/Fonts/segoeui.ttf","C:/Windows/Fonts/Mangal.ttf"]
    else:
        cands += ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/freefont/FreeSans.ttf"]

    seen = set(); out=[]
    for f in cands:
        if f not in seen:
            seen.add(f); out.append(f)
    return out

def try_load_font(candidate: str, size: int):
    try:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    except Exception:
        pass
    try:
        return ImageFont.truetype(candidate, size)
    except Exception:
        pass
    return None

def font_supports_text(font: ImageFont.FreeTypeFont, text: str) -> bool:
    try:
        dummy = Image.new("L", (10,10))
        d = ImageDraw.Draw(dummy)
        bbox = d.textbbox((0,0), text, font=font)
        w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
        return (w>0 and h>0)
    except Exception:
        return False

def find_best_font_for_box(draw: ImageDraw.ImageDraw, text: str, box_w: int, box_h: int,
                           max_size: int = 400, min_size: int = 6) -> ImageFont.FreeTypeFont:
    if has_devanagari(text):
        candidates = candidate_fonts_for_script("devanagari")
    elif has_bengali(text):
        candidates = candidate_fonts_for_script("bengali")
    else:
        candidates = candidate_fonts_for_script("latin")

    best_font = None; best_score = -1.0
    for cand in candidates:
        test_font = try_load_font(cand, 40)
        if test_font is None: continue
        if not font_supports_text(test_font, text): continue

        lo=min_size; hi=max_size; chosen_size=min_size
        while lo <= hi:
            mid = (lo+hi)//2
            f_mid = try_load_font(cand, mid)
            if f_mid is None:
                hi = mid-1; continue
            bbox = draw.textbbox((0,0), text, font=f_mid)
            w = bbox[2]-bbox[0]; h = bbox[3]-bbox[1]
            if w <= box_w and h <= box_h:
                chosen_size = mid; lo = mid + 1
            else:
                hi = mid - 1

        f_final = try_load_font(cand, chosen_size)
        if f_final is None: continue
        bboxf = draw.textbbox((0,0), text, font=f_final)
        w_f = bboxf[2]-bboxf[0]; h_f = bboxf[3]-bboxf[1]
        width_ratio = w_f / box_w if box_w>0 else 0
        height_ratio = h_f / box_h if box_h>0 else 0
        score = min(width_ratio, height_ratio)
        if score > best_score:
            best_score = score; best_font = f_final
        if best_score >= 0.98:
            break

    if best_font is None:
        for s in (40,20,12):
            try:
                f = ImageFont.truetype("DejaVuSans.ttf", s)
                if font_supports_text(f, text): return f
            except:
                pass
        return ImageFont.load_default()
    return best_font

def percent_to_pixels(bbox_pct: Tuple[float,float,float,float], image_size: Tuple[int,int]) -> Tuple[int,int,int,int]:
    W,H = image_size
    x_pct,y_pct,w_pct,h_pct = bbox_pct
    left = int((x_pct/100.0) * W); top = int((y_pct/100.0) * H)
    return left, top, int((w_pct/100.0)*W), int((h_pct/100.0)*H)

def render_label(master_img_path: str,
                 template_entry: Dict[str,Any],
                 state_name: str,
                 rules: Dict[str,Dict[str,str]],
                 output_path: str,
                 debug: bool = True) -> str:
    if not os.path.isfile(master_img_path):
        raise FileNotFoundError(f"Master image not found: {master_img_path}")
    img = Image.open(master_img_path).convert("RGBA")
    W,H = img.size
    draw = ImageDraw.Draw(img)
    regions = template_entry.get("regions", [])
    state_rules = rules.get(state_name)
    if state_rules is None:
        raise ValueError(f"No rules for state: {state_name}")

    for region in regions:
        label = region.get("label")
        if label is None: continue
        if label not in state_rules:
            # skip unknown keys quietly
            continue

        text = state_rules[label]
        left, top, w_px, h_px = percent_to_pixels((region.get("x",0), region.get("y",0), region.get("width",0), region.get("height",0)), (W,H))
        w_px = max(1,w_px); h_px = max(1,h_px)

        best_font = find_best_font_for_box(draw, text, w_px, h_px)
        tb = draw.textbbox((0,0), text, font=best_font)
        text_w = tb[2]-tb[0]; text_h = tb[3]-tb[1]

        padding_x = max(3, int(0.03*w_px))
        x_text = left + padding_x
        y_text = top + (h_px - text_h)/2 - tb[1]
        if y_text < top: y_text = top
        if y_text + text_h > top + h_px: y_text = top + h_px - text_h

        draw.text((x_text, y_text), text, fill=(0,0,0,255), font=best_font)

        if debug:
            draw.rectangle([left, top, left + w_px, top + h_px], outline=(255,0,0,200), width=1)

    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    img.convert("RGB").save(output_path, format="PNG")
    return output_path

# ---------------------------
# UI
# ---------------------------
st.title("Label Renderer")
st.write("Input Master Label and Select State to generate final label with appropriate text based on template regions and rules.")

if not os.path.exists(TEMPLATE_JSON_PATH):
    st.error(f"Template JSON not found at: {TEMPLATE_JSON_PATH}\nPlease update TEMPLATE_JSON_PATH at the top of this script.")
    st.stop()

with open(TEMPLATE_JSON_PATH, "r", encoding="utf-8") as f:
    try:
        templates = json.load(f)
    except Exception as e:
        st.error(f"Failed to parse template JSON: {e}")
        st.stop()

if not isinstance(templates, list) or len(templates) == 0:
    st.error("Template JSON must be a list with at least one template entry.")
    st.stop()

col_inputs, col_result = st.columns([1,1])

with col_inputs:
    st.subheader("Inputs")
    # sample selection added (optional)
    st.markdown("**Choose master label** — either upload or pick a sample")
    sample_options = ["(none)"] + list(SAMPLE_MAP.keys())
    sample_choice = st.selectbox("Pick a built-in sample (optional)", options=sample_options, index=0)

    uploaded_img = st.file_uploader("Upload master label image (PNG/JPG)", type=["png","jpg","jpeg"])
    template_names = [os.path.basename(t.get("image","unnamed")) for t in templates]
    sel_name = st.selectbox("Select template entry (image basename)", options=template_names)
    sel_idx = template_names.index(sel_name)
    template_entry = templates[sel_idx]
    state_choice = st.selectbox("Select state", options=list(RULES.keys()))
    debug = st.checkbox("Show debug boxes (red)", value=True)
    generate_btn = st.button("Generate final label")

with col_result:
    st.subheader("Result preview")
    placeholder = st.empty()  # will be replaced with before/after after generation

if generate_btn:
    # determine master source: sample preferred, else uploaded
    selected_sample_path = None
    if sample_choice != "(none)":
        sample_path = SAMPLE_MAP.get(sample_choice)
        if sample_path and os.path.exists(sample_path):
            selected_sample_path = sample_path
        else:
            st.warning(f"Sample '{sample_choice}' not found at '{sample_path}'. Please place it next to the script or upload an image.")
            selected_sample_path = None

    if selected_sample_path:
        master_path = selected_sample_path
    else:
        if uploaded_img is None:
            st.error("Please upload a master image or choose a built-in sample first.")
            st.stop()
        tmp_master = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_img.name)[1])
        tmp_master.write(uploaded_img.getvalue())
        tmp_master.flush(); tmp_master.close()
        master_path = tmp_master.name

    try:
        tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp_out.close()
        out_path = tmp_out.name

        render_label(master_path, template_entry, state_choice, RULES, out_path, debug=debug)

        with open(master_path, "rb") as fm:
            master_bytes = fm.read()
        with open(out_path, "rb") as fo:
            final_bytes = fo.read()

        # show side-by-side before/after and download (use width param)
        c1, c2 = col_result.columns(2)
        with c1:
            st.image(Image.open(io.BytesIO(master_bytes)), caption="Master (before)", width=350)
        with c2:
            st.image(Image.open(io.BytesIO(final_bytes)), caption="Final (after)", width=350)
            st.download_button("Download final PNG", data=final_bytes, file_name="final_label.png", mime="image/png")

        st.success("Rendered successfully.")
    except Exception as e:
        st.exception(e)
