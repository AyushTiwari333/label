# streamlit_label_app_local_template_nohistory.py
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import os, platform, json, tempfile, io
from typing import List, Dict, Tuple, Any

st.set_page_config(page_title="Label Renderer", layout="wide")

# ---------------------------
# CONFIG: template json path
# ---------------------------
TEMPLATE_JSON_PATH = "./template_clean.json"

# ---------------------------
# BUILT-IN SAMPLE MASTER LABELS
# ---------------------------
SAMPLE_IMAGES = {
    "Master Label Johnny Walker": "Master Label Johnny Walker.png",
    "Master Label VAT": "Master Label VAT.png"
}

# ---------------------------
# Demo rules
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
# ===== RENDER ENGINE (UNCHANGED) =====
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
            "NotoSansDevanagari-Regular.ttf","Lohit-Devanagari.ttf","Mukta-Regular.ttf",
            "Devanagari Sangam MN.ttf","Mangal.ttf","Arial Unicode.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
            "/Library/Fonts/Devanagari Sangam MN.ttf",
            "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttf","DejaVuSans.ttf"
        ]
    elif script == "bengali":
        cands = [
            "NotoSansBengali-Regular.ttf","Lohit-Bengali.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf","DejaVuSans.ttf"
        ]
    else:
        cands = ["DejaVuSans.ttf","Arial.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]

    if system == "Darwin":
        cands += ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf"]
    elif system == "Windows":
        cands += ["C:/Windows/Fonts/arialuni.ttf","C:/Windows/Fonts/Mangal.ttf"]
    else:
        cands += ["/usr/share/fonts/truetype/freefont/FreeSans.ttf"]

    return list(dict.fromkeys(cands))

def try_load_font(candidate: str, size: int):
    try:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    except: pass
    try:
        return ImageFont.truetype(candidate, size)
    except: pass
    return None

def font_supports_text(font, text):
    try:
        img = Image.new("L",(10,10))
        d = ImageDraw.Draw(img)
        b = d.textbbox((0,0), text, font=font)
        return (b[2]-b[0])>0
    except:
        return False

def find_best_font_for_box(draw, text, box_w, box_h, max_size=400, min_size=6):
    if has_devanagari(text):
        candidates = candidate_fonts_for_script("devanagari")
    elif has_bengali(text):
        candidates = candidate_fonts_for_script("bengali")
    else:
        candidates = candidate_fonts_for_script("latin")

    best_font=None; best_score=-1
    for cand in candidates:
        test = try_load_font(cand,40)
        if not test or not font_supports_text(test,text): continue

        lo=min_size; hi=max_size; chosen=min_size
        while lo<=hi:
            mid=(lo+hi)//2
            f=try_load_font(cand,mid)
            if not f: hi=mid-1; continue
            b=draw.textbbox((0,0),text,font=f)
            w=b[2]-b[0]; h=b[3]-b[1]
            if w<=box_w and h<=box_h:
                chosen=mid; lo=mid+1
            else: hi=mid-1

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

def percent_to_pixels(bbox_pct, image_size):
    W,H=image_size
    x,y,w,h=bbox_pct
    return int(x/100*W),int(y/100*H),int(w/100*W),int(h/100*H)

def render_label(master_img_path, template_entry, state_name, rules, output_path, debug=True):
    img=Image.open(master_img_path).convert("RGBA")
    W,H=img.size
    draw=ImageDraw.Draw(img)

    for region in template_entry.get("regions",[]):
        label=region.get("label")
        if label not in rules[state_name]: continue
        text=rules[state_name][label]

        left,top,w,h=percent_to_pixels((region["x"],region["y"],region["width"],region["height"]),(W,H))
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
    st.subheader("Inputs")

    # SAMPLE OPTION
    sample_choice = st.selectbox(
        "Use sample master label (optional)",
        ["None"] + list(SAMPLE_IMAGES.keys())
    )

    uploaded_img = st.file_uploader("Or upload master label", type=["png","jpg","jpeg"])

    template_names=[os.path.basename(t.get("image","unnamed")) for t in templates]
    sel_name=st.selectbox("Select template", options=template_names)
    template_entry=templates[template_names.index(sel_name)]

    state_choice=st.selectbox("Select state", options=list(RULES.keys()))
    debug=st.checkbox("Show debug boxes", value=True)
    generate_btn=st.button("Generate")

with col_result:
    st.subheader("Result")

if generate_btn:

    # decide master image
    if sample_choice!="None":
        master_path = SAMPLE_IMAGES[sample_choice]
        if not os.path.exists(master_path):
            st.error("Sample image not found in app folder")
            st.stop()

    elif uploaded_img:
        tmp_master=tempfile.NamedTemporaryFile(delete=False,suffix=".png")
        tmp_master.write(uploaded_img.getvalue())
        tmp_master.close()
        master_path=tmp_master.name
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
