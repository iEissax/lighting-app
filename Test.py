import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import pydeck as pdk

# إعداد الصفحة
st.set_page_config(page_title="محلل بيانات شبكة الإنارة", layout="wide")
st.title("📊 نظام تحليل ومراقبة شبكة الإنارة")

uploaded_file = st.file_uploader("اختر ملف KMZ", type=['kmz'])

def process_kmz(file):
    try:
        with zipfile.ZipFile(file, 'r') as f:
            kml_files = [name for name in f.namelist() if name.endswith('.kml')]
            if not kml_files:
                st.error("لم يتم العثور على ملف KML")
                return None
            kml_content = f.read(kml_files[0])

        tree = etree.fromstring(kml_content)
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        data = []

        # قاموس الألوان - RGB
        color_lookup = {
            "12": [255, 0, 0],    # أحمر
            "10": [0, 255, 0],    # أخضر
            "9":  [0, 0, 255],    # أزرق
            "8":  [255, 165, 0],  # برتقالي
            "6":  [128, 0, 128],  # بنفسجي
            "غير مسجل": [150, 150, 150] # رمادي
        }

        for pm in tree.xpath("//kml:Placemark", namespaces=ns):
            name_text = pm.xpath("./kml:name/text()", namespaces=ns)
            full_name = name_text[0].strip() if name_text else "Unknown"

            numbers = re.findall(r'\d+', full_name)
            column_num = int(numbers[0]) if len(numbers) >= 1 else 0
            feeder_num = int(numbers[1]) if len(numbers) >= 2 else 0
            extra_num = numbers[2] if len(numbers) >= 3 else ""

            station_part = re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name)
            station_code = station_part.group(0) if station_part else "غير محدد"

            formatted_name = f"{column_num}/{feeder_num}"
            if extra_num: formatted_name += f"/{extra_num}"
            if station_code != "غير محدد": formatted_name = f"{station_code} {formatted_name}"

            desc = pm.xpath("./kml:description/text()", namespaces=ns)
            desc_text = desc[0] if desc else ""
            ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
            search_area = (desc_text + " " + ext_vals).strip()

            status = "مغروز" if "مغروز" in search_area else ("مفقود" if "مفقود" in search_area else "طبيعي")
            height_match = re.search(r'\b(12|10|9|8|6)\b', search_area)
            val_height = height_match.group(1) if height_match else "غير مسجل"
            
            # الحصول على اللون
            current_color = color_lookup.get(val_height, [0, 0, 0])

            coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
            lat, lon = 0.0, 0.0
            if coords:
                try:
                    coord_split = coords[0].strip().split(',')
                    lat, lon = float(coord_split[1]), float(coord_split[0])
                except: pass

            data.append({
                "Station": station_code,
                "ID": formatted_name,
                "Status": status,
                "Height": val_height,
                "lat": lat, 
                "lon": lon, 
                "r": current_color[0], # فصل الألوان لضمان التعرف عليها
                "g": current_color[1],
                "b": current_color[2],
                "f_num": feeder_num, 
                "c_num": column_num
            })

        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"خطأ: {e}")
        return None

if uploaded_file:
    raw_df = process_kmz(uploaded_file)
    
    if raw_df is not None:
        # --- الفلاتر في الجانب ---
        st.sidebar.header("🔍 فلاتر البحث")
        selected_status = st.sidebar.multiselect("حالة العمود", raw_df['Status'].unique(), default=raw_df['Status'].unique())
        selected_height = st.sidebar.multiselect("طول العمود (م)", raw_df['Height'].unique(), default=raw_df['Height'].unique())

        filtered_df = raw_df[(raw_df['Status'].isin(selected_status)) & (raw_df['Height'].isin(selected_height))]

        # --- الخريطة ---
        st.subheader("📍 مواقع الأعمدة")
        map_data = filtered_df[filtered_df['lat'] != 0].copy()
        
        if not map_data.empty:
            # تعريف الطبقة مع الإشارة الصريحة للأعمدة r, g, b
            layer = pdk.Layer(
                "ScatterplotLayer",
                map_data,
                get_position='[lon, lat]',
                get_color='[r, g, b, 200]', # 200 هي درجة الشفافية
                get_radius=8,
                pickable=True,
            )
            
            view_state = pdk.ViewState(latitude=map_data['lat'].mean(), longitude=map_data['lon'].mean(), zoom=14)

            st.pydeck_chart(pdk.Deck(
                layers=[layer], 
                initial_view_state=view_state, 
                tooltip={"text": "الاسم: {ID}\nالطول: {Height}\nالحالة: {Status}"}
            ))
            st.markdown("🔴 12م | 🟢 10م | 🔵 9م | 🟠 8م | 🟣 6م | ⚪ غير مسجل")

        # --- الجدول والتحميل ---
        st.subheader("📄 البيانات")
        # حذف أعمدة الألوان التقنية قبل عرض الجدول وتحميله
        display_df = filtered_df.drop(columns=['f_num', 'c_num', 'lat', 'lon', 'r', 'g', 'b'])
        st.dataframe(display_df, use_container_width=True)
        
        # كود تحميل الإكسل (نفسه السابق)
        # ... (يمكنك إضافته هنا)
