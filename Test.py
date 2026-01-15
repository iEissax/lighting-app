import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import pydeck as pdk  # مكتبة الخرائط المتقدمة

# إعداد الصفحة
st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة", layout="wide")
st.title("📂 مستخرج ومحلل بيانات KMZ الملون")

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
            station_code = station_part.group(0) if station_part else ""

            formatted_name = f"{column_num}/{feeder_num}"
            if extra_num: formatted_name += f"/{extra_num}"
            if station_code: formatted_name = f"{station_code} {formatted_name}"

            desc = pm.xpath("./kml:description/text()", namespaces=ns)
            desc_text = desc[0] if desc else ""
            ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
            search_area = (desc_text + " " + ext_vals).strip()

            status = "مغروز" if "مغروز" in search_area else ("مفقود" if "مفقود" in search_area else "طبيعي")
            
            # استخراج الطول وتحديد اللون
            height_match = re.search(r'\b(12|10|9|8|6)\b', search_area)
            val_height = height_match.group(1) if height_match else "غير مسجل"
            
            # قاموس الألوان (RGB) بناءً على الطول
            colors = {
                "12": [255, 0, 0],    # أحمر
                "10": [0, 255, 0],    # أخضر
                "9":  [0, 0, 255],    # أزرق
                "8":  [255, 165, 0],  # برتقالي
                "6":  [128, 0, 128],  # بنفسجي
                "غير مسجل": [150, 150, 150] # رمادي
            }
            color = colors.get(val_height, [0, 0, 0])

            lamps = 2 if "دبل" in search_area else (1 if "مفرد" in search_area else 0)

            coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
            lat, lon = 0.0, 0.0
            if coords:
                try:
                    coord_split = coords[0].strip().split(',')
                    lat = float(coord_split[1])
                    lon = float(coord_split[0])
                except: pass

            data.append({
                "Station": station_code,
                "ID (Col/Feed)": formatted_name,
                "Status": status,
                "Height (m)": val_height,
                "Lamps": lamps,
                "lat": lat, 
                "lon": lon,
                "color": color, # إضافة اللون للبيانات
                "Coordinates": f"{lat:.5f},{lon:.5f}",
                "f_num": feeder_num,
                "c_num": column_num
            })

        if not data: return None
        df = pd.DataFrame(data)
        df = df.sort_values(by=['Station', 'f_num', 'c_num'], ascending=[True, True, True])
        return df
    except Exception as e:
        st.error(f"خطأ: {e}")
        return None

if uploaded_file:
    result_df = process_kmz(uploaded_file)
    
    if result_df is not None:
        # الإحصائيات
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("إجمالي الأعمدة", len(result_df))
        c2.metric("مغروز", len(result_df[result_df['Status'] == "مغروز"]))
        c3.metric("مفقود", len(result_df[result_df['Status'] == "مفقود"]))
        c4.metric("طبيعي", len(result_df[result_df['Status'] == "طبيعي"]))

        # الخريطة الملونة باستخدام Pydeck
        st.subheader("📍 خريطة الأعمدة (ملونة حسب الطول)")
        
        # تصفية النقاط الصالحة فقط
        map_df = result_df[result_df['lat'] != 0].copy()
        
        if not map_df.empty:
            # تعريف طبقة النقاط
            layer = pdk.Layer(
                "ScatterplotLayer",
                map_df,
                get_position='[lon, lat]',
                get_color='color',
                get_radius=5,  # حجم النقطة
                pickable=True,
            )
            
            # إعدادات عرض الخريطة
            view_state = pdk.ViewState(
                latitude=map_df['lat'].mean(),
                longitude=map_df['lon'].mean(),
                zoom=14,
                pitch=0
            )

            # عرض الخريطة
            st.pydeck_chart(pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip={"text": "الاسم: {ID (Col/Feed)}\nالطول: {Height (m)}\nالحالة: {Status}"}
            ))
            
            # مفتاح الألوان
            st.write("🔴 12م | 🟢 10م | 🔵 9م | 🟠 8م | 🟣 6م | ⚪ غير مسجل")
        
        # المعاينة والتحميل (نفس الكود السابق)
        st.subheader("📄 معاينة البيانات")
        final_df = result_df.drop(columns=['f_num', 'c_num', 'lat', 'lon', 'color'])
        st.dataframe(final_df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Sheet1')
            workbook = writer.book
            worksheet = writer.sheets['Sheet1']
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
            for i, col in enumerate(final_df.columns):
                max_len = max(final_df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, max_len)
                worksheet.write(0, i, col, header_fmt)

        st.download_button("📥 تحميل ملف Excel المنسق", output.getvalue(), "Lighting_Report.xlsx")
