import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io

st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة", layout="wide") # تم تغييرها لـ wide لعرض أفضل
st.title("📂 مستخرج ومحلل بيانات KMZ")

uploaded_file = st.file_uploader("اختر ملف KMZ", type=['kmz'])

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
        height_match = re.search(r'\b(12|10|9|8|6)\b', search_area)
        val_height = height_match.group(1) if height_match else "غير مسجل"
        lamps = 2 if "دبل" in search_area else (1 if "مفرد" in search_area else 0)

        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat, lon = 0.0, 0.0
        if coords:
            coord_split = coords[0].strip().split(',')
            lat = float(coord_split[1])
            lon = float(coord_split[0])

        data.append({
            "Station": station_code,
            "ID (Col/Feed)": formatted_name,
            "Status": status,
            "Height (m)": val_height,
            "Lamps": lamps,
            "Latitude": lat,
            "Longitude": lon,
            "Coordinates": f"{lat:.5f},{lon:.5f}",
            "f_num": feeder_num,
            "c_num": column_num
        })

    df = pd.DataFrame(data)
    df = df.sort_values(by=['Station', 'f_num', 'c_num'], ascending=[True, True, True])
    return df

if uploaded_file:
    result_df = process_kmz(uploaded_file)
    
    # --- قسم الإحصائيات (Metrics) ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("إجمالي الأعمدة", len(result_df))
    col2.metric("مغروز", len(result_df[result_df['Status'] == "مغروز"]))
    col3.metric("مفقود", len(result_df[result_df['Status'] == "مفقود"]))
    col4.metric("طبيعي", len(result_df[result_df['Status'] == "طبيعي"]))

    # --- قسم الخريطة ---
    st.subheader("📍 مواقع أعمدة الإنارة على الخريطة")
    map_data = result_df[['Latitude', 'Longitude']].rename(columns={'Latitude': 'lat', 'Longitude': 'lon'})
    st.map(map_data)

    # --- قسم معاينة الجدول ---
    st.subheader("📄 معاينة البيانات")
    st.dataframe(result_df.drop(columns=['f_num', 'c_num', 'Latitude', 'Longitude']), use_container_width=True)

    # --- قسم التحميل (Excel) ---
    output = io.BytesIO()
    # (نفس كود التنسيق الخاص بك مع تعديل بسيط لحذف الأعمدة الزائدة قبل الحفظ)
    final_df_for_excel = result_df.drop(columns=['f_num', 'c_num', 'Latitude', 'Longitude'])
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        final_df_for_excel.to_excel(writer, index=False, sheet_name='Lighting Report')
        workbook  = writer.book
        worksheet = writer.sheets['Lighting Report']
        worksheet.set_right_to_left(False) 
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
        
        for i, col in enumerate(final_df_for_excel.columns):
            column_len = max(final_df_for_excel[col].astype(str).str.len().max(), len(col)) + 4
            worksheet.set_column(i, i, column_len)
            worksheet.write(0, i, col, header_format)

    st.divider()
    st.download_button("📥 تحميل ملف Excel المنسق", output.getvalue(), "Lighting_Final_Report.xlsx", mime="application/vnd.ms-excel")
