import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import folium
from streamlit_folium import st_folium

# 1. إعدادات الصفحة والواجهة
st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; border: 1px solid #dce1e6; }
    .stExpander { border: 1px solid #007BFF; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📂 نظام معالجة ملفات KMZ وبيانات الإنارة")
st.write("ارفع ملفاتك لمعالجتها وعرضها على الخريطة بشكل منفصل.")

# 2. رفع الملفات المتعددة
uploaded_files = st.file_uploader("اختر ملفات KMZ", type=['kmz'], accept_multiple_files=True)

def process_kmz(file):
    with zipfile.ZipFile(file, 'r') as f:
        kml_filename = [name for name in f.namelist() if name.endswith('.kml')][0]
        kml_content = f.read(kml_filename)

    tree = etree.fromstring(kml_content)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    data = []

    for pm in tree.xpath("//kml:Placemark", namespaces=ns):
        name_text = pm.xpath("./kml:name/text()", namespaces=ns)
        full_name = name_text[0].strip() if name_text else ""

        numbers = re.findall(r'\d+', full_name)
        column_num = int(numbers[0]) if len(numbers) >= 1 else 0
        feeder_num = int(numbers[1]) if len(numbers) >= 2 else 0
        
        station_part = re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name)
        station_code = station_part.group(0) if station_part else ""

        desc = pm.xpath("./kml:description/text()", namespaces=ns)
        desc_text = desc[0] if desc else ""
        ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
        search_area = (desc_text + " " + ext_vals).strip()

        street_match = re.search(r'(?:شارع|Street)\s+([^,\n0-9]+)', search_area)
        street_name = street_match.group(1).strip() if street_match else ""

        details = ""
        if "مغروز" in search_area:
            observation, details = "مغروز", "مغروز"
        elif "مفقود" in search_area:
            observation, details = "مفقود", "مفقود"
        else:
            observation, details = "طبيعي", ""

        is_highmast = any(kw in search_area.lower() for kw in ["هاي ماست", "هايماست", "highmast", "high mast"])

        if is_highmast:
            val_height, lamps = "هاي ماست", 6
        else:
            height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
            val_height = height_match.group(1) if height_match else ""
            lamps = 2 if any(kw in search_area for kw in ["2/2", "دبل"]) else (1 if any(kw in search_area for kw in ["1/1", "مفرد"]) else "")

        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat_val, lon_val = 0.0, 0.0
        if coords:
            coord_split = coords[0].strip().split(',')
            lat_val, lon_val = float(coord_split[1]), float(coord_split[0])

        data.append({
            "المحطة": station_code, "رقم العمود": column_num, "رقم الفيدر": feeder_num,
            "طول العمود": val_height, "الذراع": lamps, "الاحداثيات x": lon_val,
            "الاحداثيات y": lat_val, "اسم الشارع": street_name, "التفاصيل": details,
            "ملاحظة_داخلية": observation 
        })

    df = pd.DataFrame(data).sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    return df

# 3. دورة المعالجة والعرض
if uploaded_files:
    for i, file in enumerate(uploaded_files):
        with st.expander(f"📍 معالجة الملف: {file.name}", expanded=True):
            result_df = process_kmz(file)
            
            # إحصائيات سريعة
            c1, c2, c3 = st.columns(3)
            c1.metric("إجمالي الأعمدة", len(result_df))
            c2.metric("طبيعي", len(result_df[result_df['ملاحظة_داخلية'] == "طبيعي"]))
            c3.metric("ملاحظات (أحمر)", len(result_df[result_df['ملاحظة_داخلية'] != "طبيعي"]))

            # عرض الخريطة
            if not result_df.empty:
                st.write("### معاينة الخريطة:")
                m = folium.Map(location=[result_df['الاحداثيات y'].mean(), result_df['الاحداثيات x'].mean()], zoom_start=15)
                for _, row in result_df.iterrows():
                    color = 'red' if row['ملاحظة_داخلية'] in ["مغروز", "مفقود"] else 'blue'
                    folium.Marker(
                        [row['الاحداثيات y'], row['الاحداثيات x']],
                        popup=f"محطة: {row['المحطة']} | عمود: {row['رقم العمود']}",
                        icon=folium.Icon(color=color)
                    ).add_to(m)
                st_folium(m, width=1100, height=400, key=f"map_{i}")

            # جدول المعاينة
            st.write("### بيانات الجدول:")
            st.dataframe(result_df.drop(columns=['ملاحظة_داخلية']), use_container_width=True)
            
            # تصدير الإكسل بتنسيقاتك الأصلية
            dup_coords = result_df.duplicated(subset=['الاحداثيات x', 'الاحداثيات y'], keep=False)
            dup_columns = result_df.duplicated(subset=['المحطة', 'رقم الفيدر', 'رقم العمود'], keep=False)
            is_duplicated_any = dup_coords | dup_columns
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                export_df = result_df.drop(columns=['ملاحظة_داخلية'])
                export_df.to_excel(writer, index=False, sheet_name='Sheet1')
                workbook = writer.book
                worksheet = writer.sheets['Sheet1']
                worksheet.right_to_left()
                
                # تعريف التنسيقات
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#A6A6A6', 'border': 1, 'align': 'center'})
                cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
                red_fmt = workbook.add_format({'bg_color': '#FF0000', 'border': 1, 'align': 'center'})
                blue_fmt = workbook.add_format({'bg_color': '#00B0F0', 'border': 1, 'align': 'center'})

                for row_idx in range(len(result_df)):
                    obs_val = result_df.iloc[row_idx]['ملاحظة_داخلية']
                    is_dup = is_duplicated_any.iloc[row_idx]
                    for col_idx, cell_value in enumerate(export_df.iloc[row_idx]):
                        fmt = red_fmt if obs_val in ["مغروز", "مفقود"] else (blue_fmt if is_dup else cell_fmt)
                        worksheet.write(row_idx + 1, col_idx, cell_value, fmt)

            st.download_button(
                label=f"📥 تحميل إكسل {file.name}",
                data=output.getvalue(),
                file_name=f"Report_{file.name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"btn_{i}"
            )
