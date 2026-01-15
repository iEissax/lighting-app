import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import pydeck as pdk

st.set_page_config(page_title="مستخرج بيانات الإنارة", layout="wide")
st.title("📍 خريطة أعمدة الإنارة الملونة")

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

        # قاموس الألوان: [الأحمر, الأخضر, الأزرق]
        color_map = {
            "12": [255, 0, 0],    # أحمر
            "10": [0, 255, 0],    # أخضر
            "9":  [0, 0, 255],    # أزرق
            "8":  [255, 165, 0],  # برتقالي
            "6":  [128, 0, 128],  # بنفسجي
            "غير مسجل": [150, 150, 150] # رمادي
        }

        for pm in tree.xpath("//kml:Placemark", namespaces=ns):
            # 1. استخراج الاسم
            name = pm.xpath("./kml:name/text()", namespaces=ns)
            full_name = name[0].strip() if name else "بدون اسم"

            # 2. استخراج الوصف (حيث يوجد الطول)
            desc = pm.xpath("./kml:description/text()", namespaces=ns)
            ext_data = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
            full_description = (desc[0] if desc else "") + " " + ext_data

            # 3. استخراج الطول من الوصف باستخدام Regex
            # نبحث عن الأرقام المشهورة لأطوال الأعمدة
            height_search = re.search(r'\b(12|10|9|8|6)\b', full_description)
            height_val = height_search.group(1) if height_search else "غير مسجل"
            
            # 4. تحديد اللون بناءً على الطول المستخرج
            rgb = color_map.get(height_val, [0, 0, 0])

            # 5. استخراج الإحداثيات
            coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
            if coords:
                lon, lat, _ = (coords[0].strip().split(',') + [0])[:3]
                data.append({
                    "name": full_name,
                    "height": height_val,
                    "lat": float(lat),
                    "lon": float(lon),
                    "r": rgb[0],
                    "g": rgb[1],
                    "b": rgb[2]
                })

        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"حدث خطأ: {e}")
        return None

if uploaded_file:
    df = process_kmz(uploaded_file)
    
    if df is not None and not df.empty:
        # عرض الخريطة باستخدام pydeck بدلاً من st.map
        st.subheader(f"تم العثور على {len(df)} عمود")
        
        # إعداد طبقة النقاط الملونة
        layer = pdk.Layer(
            "ScatterplotLayer",
            df,
            get_position='[lon, lat]',
            get_color='[r, g, b, 200]', # شفافية 200 من 255
            get_radius=10,             # حجم الدائرة على الخريطة
            pickable=True,
        )

        # إعداد الرؤية الافتراضية للخريطة
        view_state = pdk.ViewState(
            latitude=df['lat'].mean(),
            longitude=df['lon'].mean(),
            zoom=15
        )

        # رسم الخريطة مع "تلميحات" تظهر عند الوقوف بالماوس
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "العمود: {name}\nالطول: {height}م"}
        ))

        # مفتاح الألوان للتوضيح
        st.markdown("""
        **مفتاح الألوان حسب الطول:** 🔴 12م | 🟢 10م | 🔵 9م | 🟠 8م | 🟣 6م | ⚪ غير مسجل
        """)
        
        st.dataframe(df[['name', 'height', 'lat', 'lon']])
