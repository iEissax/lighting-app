import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import pydeck as pdk

st.set_page_config(page_title="محلل بيانات الإنارة", layout="wide")
st.title("📍 خريطة الأعمدة الملونة (تحليل الوصف)")

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

        # قاموس الألوان الثابتة [R, G, B]
        color_lookup = {
            "12": [255, 0, 0],    # أحمر
            "10": [0, 255, 0],    # أخضر
            "9":  [0, 0, 255],    # أزرق
            "8":  [255, 165, 0],  # برتقالي
            "6":  [128, 0, 128],  # بنفسجي
            "غير مسجل": [150, 150, 150] # رمادي
        }

        for pm in tree.xpath("//kml:Placemark", namespaces=ns):
            name = pm.xpath("./kml:name/text()", namespaces=ns)
            full_name = name[0].strip() if name else "بدون اسم"

            # استخراج الوصف بالكامل (نبحث فيه عن الطول)
            desc = pm.xpath("./kml:description/text()", namespaces=ns)
            ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
            full_desc = (desc[0] if desc else "") + " " + ext_vals

            # البحث عن الطول: نبحث عن رقم محاط بحدود كلمات \b لضمان عدم أخذ جزء من رقم آخر
            # الأرقام المدعومة هي 12, 10, 9, 8, 6
            height_match = re.search(r'\b(12|10|9|8|6)\b', full_desc)
            height_val = height_match.group(1) if height_match else "غير مسجل"
            
            # جلب اللون المخصص
            rgb = color_lookup.get(height_val, [150, 150, 150])

            coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
            if coords:
                parts = coords[0].strip().split(',')
                if len(parts) >= 2:
                    data.append({
                        "name": full_name,
                        "height": height_val,
                        "lat": float(parts[1]),
                        "lon": float(parts[0]),
                        "r": rgb[0],
                        "g": rgb[1],
                        "b": rgb[2],
                        "full_description": full_desc[:50] + "..." # للمعاينة فقط
                    })

        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"خطأ أثناء معالجة الملف: {e}")
        return None

if uploaded_file:
    df = process_kmz(uploaded_file)
    
    if df is not None and not df.empty:
        # --- قسم الفلاتر (شريط جانبي) ---
        st.sidebar.header("🔍 تصفية الخريطة")
        available_heights = sorted(df['height'].unique().tolist())
        selected_heights = st.sidebar.multiselect(
            "اختر الأطوال المراد عرضها:", 
            available_heights, 
            default=available_heights
        )

        # فلترة البيانات بناءً على اختيار المستخدم
        filtered_df = df[df['height'].isin(selected_heights)]

        # --- الإحصائيات ---
        st.subheader("📊 ملخص البيانات المفلترة")
        cols = st.columns(len(selected_heights) if len(selected_heights) > 0 else 1)
        for i, h in enumerate(selected_heights):
            count = len(filtered_df[filtered_df['height'] == h])
            cols[i % len(cols)].metric(f"طول {h}م", f"{count}")

        # --- الخريطة الاحترافية (Pydeck) ---
        st.subheader("📍 خريطة توزيع الأعمدة")
        
        if not filtered_df.empty:
            layer = pdk.Layer(
                "ScatterplotLayer",
                filtered_df,
                get_position='[lon, lat]',
                get_color='[r, g, b, 180]', # تلوين النقاط r,g,b من الجدول
                get_radius=12,
                pickable=True,
            )

            view_state = pdk.ViewState(
                latitude=filtered_df['lat'].mean(),
                longitude=filtered_df['lon'].mean(),
                zoom=14
            )

            st.pydeck_chart(pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip={"text": "الاسم: {name}\nالطول المكتشف: {height}م"}
            ))
            
            st.markdown("🔴 12م | 🟢 10م | 🔵 9م | 🟠 8م | 🟣 6م | ⚪ غير مسجل")
        else:
            st.warning("الرجاء اختيار طول واحد على الأقل من القائمة الجانبية.")

        # --- عرض الجدول ---
        st.subheader("📄 معاينة البيانات المستخرجة")
        st.dataframe(filtered_df[['name', 'height', 'lat', 'lon']], use_container_width=True)
