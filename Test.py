import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import pydeck as pdk

st.set_page_config(page_title="مستخرج بيانات الإنارة المطور", layout="wide")
st.title("📍 نظام استخراج بيانات الشبكة (الأطوال والأذرعة)")

uploaded_file = st.file_uploader("اختر ملف KMZ", type=['kmz'])

def process_kmz(file):
    try:
        with zipfile.ZipFile(file, 'r') as f:
            kml_files = [name for name in f.namelist() if name.endswith('.kml')]
            if not kml_files: return None
            kml_content = f.read(kml_files[0])

        tree = etree.fromstring(kml_content)
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        data = []

        # الألوان بناءً على الطول
        color_map = {
            "12": [255, 0, 0], "10": [0, 255, 0], "9": [0, 0, 255],
            "8": [255, 165, 0], "6": [128, 0, 128], "غير مسجل": [150, 150, 150]
        }

        for pm in tree.xpath("//kml:Placemark", namespaces=ns):
            name = pm.xpath("./kml:name/text()", namespaces=ns)
            full_name = name[0].strip() if name else "بدون اسم"

            desc = pm.xpath("./kml:description/text()", namespaces=ns)
            ext_data = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
            full_description = (desc[0] if desc else "") + " " + ext_data

            # --- 1. استخراج الطول ---
            # يبحث عن نمط 12m أو رقم مجرد من الأطوال المعروفة
            height_match = re.search(r'(\d+)\s*m|(?<!/)\b(12|10|9|8|6)\b', full_description, re.IGNORECASE)
            if height_match:
                height_val = height_match.group(1) if height_match.group(1) else height_match.group(2)
            else:
                height_val = "غير مسجل"
            
            # --- 2. استخراج الأذرعة ---
            # يبحث عن مفرد/دبل أو نمط 1/1 أو 1/2
            arm_count = 1 # الافتراضي
            if "دبل" in full_description or "1/2" in full_description or "2/1" in full_description:
                arm_count = 2
                arm_text = "دبل (2)"
            elif "مفرد" in full_description or "1/1" in full_description:
                arm_count = 1
                arm_text = "مفرد (1)"
            else:
                arm_text = "غير محدد"

            rgb = color_map.get(height_val, [150, 150, 150])

            coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
            if coords:
                parts = coords[0].strip().split(',')
                if len(parts) >= 2:
                    data.append({
                        "الاسم": full_name,
                        "الطول (m)": height_val,
                        "الأذرعة": arm_text,
                        "عدد المصابيح": arm_count,
                        "lat": float(parts[1]),
                        "lon": float(parts[0]),
                        "r": rgb[0], "g": rgb[1], "b": rgb[2]
                    })

        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"حدث خطأ: {e}")
        return None

if uploaded_file:
    df = process_kmz(uploaded_file)
    
    if df is not None and not df.empty:
        # الإحصائيات
        st.subheader("📊 ملخص الأعمدة")
        c1, c2 = st.columns(2)
        c1.metric("إجمالي الأعمدة", len(df))
        c2.metric("إجمالي المصابيح", int(df['عدد المصابيح'].sum()))
        
        # الخريطة
        st.subheader("📍 الخريطة التفاعلية")
        layer = pdk.Layer(
            "ScatterplotLayer",
            df,
            get_position='[lon, lat]',
            get_color='[r, g, b, 200]',
            get_radius=10,
            pickable=True,
        )
        st.pydeck_chart(pdk.Deck(
            layers=[layer], 
            initial_view_state=pdk.ViewState(latitude=df['lat'].mean(), longitude=df['lon'].mean(), zoom=14),
            tooltip={"text": "الاسم: {الاسم}\nالطول: {الطول (m)}m\nالأذرعة: {الأذرعة}"}
        ))

        # الجدول والتحميل
        st.subheader("📄 البيانات المستخرجة")
        final_df = df[['الاسم', 'الطول (m)', 'الأذرعة', 'lat', 'lon']]
        st.dataframe(final_df, use_container_width=True)

        st.divider()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Report')
            # تنسيق عرض الأعمدة تلقائياً
            for i, col in enumerate(final_df.columns):
                writer.sheets['Report'].set_column(i, i, 18)

        st.download_button("📥 تحميل ملف Excel المنسق", output.getvalue(), "Lighting_Analysis.xlsx")
