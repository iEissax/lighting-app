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
            
            # تحديد لون RGB لكل طول
            colors = {
                "12": [255, 0, 0], "10": [0, 255, 0], "9": [0, 0, 255],
                "8": [255, 165, 0], "6": [128, 0, 128], "غير مسجل": [150, 150, 150]
            }
            color = colors.get(val_height, [0, 0, 0])

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
                "lat": lat, "lon": lon, "color": color,
                "f_num": feeder_num, "c_num": column_num
            })

        df = pd.DataFrame(data)
        return df.sort_values(by=['Station', 'f_num', 'c_num'])
    except Exception as e:
        st.error(f"خطأ: {e}")
        return None

if uploaded_file:
    raw_df = process_kmz(uploaded_file)
    
    if raw_df is not None:
        # --- الشريط الجانبي للفلاتر ---
        st.sidebar.header("🔍 فلاتر البحث")
        
        all_stations = ["الكل"] + sorted(raw_df['Station'].unique().tolist())
        selected_station = st.sidebar.selectbox("اختر المحطة", all_stations)
        
        selected_status = st.sidebar.multiselect("حالة العمود", raw_df['Status'].unique(), default=raw_df['Status'].unique())
        
        selected_height = st.sidebar.multiselect("طول العمود (م)", raw_df['Height'].unique(), default=raw_df['Height'].unique())

        # تطبيق الفلاتر على البيانات
        filtered_df = raw_df[
            (raw_df['Status'].isin(selected_status)) & 
            (raw_df['Height'].isin(selected_height))
        ]
        if selected_station != "الكل":
            filtered_df = filtered_df[filtered_df['Station'] == selected_station]

        # --- عرض الإحصائيات المحدثة بناءً على الفلتر ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("الأعمدة المختارة", len(filtered_df))
        c2.metric("مغروز", len(filtered_df[filtered_df['Status'] == "مغروز"]))
        c3.metric("مفقود", len(filtered_df[filtered_df['Status'] == "مفقود"]))
        c4.metric("طبيعي", len(filtered_df[filtered_df['Status'] == "طبيعي"]))

        # --- الخريطة التفاعلية ---
        st.subheader("📍 مواقع الأعمدة حسب الفلتر")
        map_data = filtered_df[filtered_df['lat'] != 0]
        if not map_data.empty:
            view_state = pdk.ViewState(latitude=map_data['lat'].mean(), longitude=map_data['lon'].mean(), zoom=14)
            layer = pdk.Layer("ScatterplotLayer", map_data, get_position='[lon, lat]', get_color='color', get_radius=6, pickable=True)
            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, 
                                     tooltip={"text": "الاسم: {ID}\nالطول: {Height}\nالحالة: {Status}"}))
            st.caption("🔴 12م | 🟢 10م | 🔵 9م | 🟠 8م | 🟣 6م | ⚪ غير مسجل")
        else:
            st.warning("لا توجد بيانات مطابقة للفلاتر المختارة لعرضها على الخريطة.")

        # --- الجدول والتحميل ---
        st.subheader("📄 البيانات التفصيلية")
        display_df = filtered_df.drop(columns=['f_num', 'c_num', 'lat', 'lon', 'color'])
        st.dataframe(display_df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            display_df.to_excel(writer, index=False, sheet_name='Filtered_Report')
            workbook, worksheet = writer.book, writer.sheets['Filtered_Report']
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
            for i, col in enumerate(display_df.columns):
                worksheet.set_column(i, i, max(display_df[col].astype(str).map(len).max(), len(col)) + 2)
                worksheet.write(0, i, col, header_fmt)

        st.download_button("📥 تحميل النتائج المفلترة (Excel)", output.getvalue(), "Filtered_Lighting_Report.xlsx")
