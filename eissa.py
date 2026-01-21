import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io

st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة - مطور", layout="centered")
st.title("📂 مستخرج بيانات KMZ (دعم 16م والجداري والأرقام المختلطة)")

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

        # استخراج الأرقام الأساسية (رقم العمود والفيدر) - تدعم الهندي والعربي
        numbers = re.findall(r'\d+', full_name)
        column_num = int(numbers[0]) if len(numbers) >= 1 else 0
        feeder_num = int(numbers[1]) if len(numbers) >= 2 else 0
        
        station_part = re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name)
        station_code = station_part.group(0) if station_part else ""

        desc = pm.xpath("./kml:description/text()", namespaces=ns)
        desc_text = desc[0] if desc else ""
        ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
        search_area = (full_name + " " + desc_text + " " + ext_vals).strip()

        # تجهيز المتغيرات
        val_height = ""
        lamps = ""

        # 1. التعرف على نمط (الطول/الذراع/..) مثل 12/2/2 أو 16/1/1
        # يدعم أرقام إنجليزية وعربية
        complex_match = re.search(r'(\d{1,2})[/-](\d)[/-](\d)', search_area)

        # 2. الكلمات الدلالية
        is_highmast = any(kw in search_area.lower() for kw in ["هاي ماست", "هايماست", "highmast"])
        is_wall = any(kw in search_area.lower() for kw in ["جداري", "wall", "جدار"])

        if complex_match:
            val_height = complex_match.group(1) # الرقم الأول هو الطول
            lamps = int(complex_match.group(2)) # الرقم الثاني هو الذراع
        elif is_highmast:
            val_height = "هاي ماست"
            lamps = 6
        elif is_wall:
            val_height = "جداري"
            if any(kw in search_area for kw in ["2/2", "دبل", "مزدوج"]): lamps = 2
            else: lamps = 1
        else:
            # البحث عن الأطوال المحددة بما فيها 16 الجديد
            # \b تضمن استخراج الرقم بدقة حتى لو لم يتبعه حرف
            height_match = re.search(r'\b(16|12|10|9|8|6)\b(?:\s*(?:m|م|متر))?', search_area, re.IGNORECASE)
            if height_match:
                val_height = height_match.group(1)
            
            # تحديد الذراع من الكلمات
            if any(kw in search_area for kw in ["2/2", "دبل", "مزدوج"]): lamps = 2
            elif any(kw in search_area for kw in ["1/1", "مفرد"]): lamps = 1

        # استخراج اسم الشارع
        street_match = re.search(r'(?:شارع|Street)\s+([^,\n0-9]+)', search_area)
        street_name = street_match.group(1).strip() if street_match else ""

        # الحالة الفنية
        observation = "طبيعي"
        details = ""
        if "مغروز" in search_area:
            observation = "مغروز"
            details = "مغروز"
        elif "مفقود" in search_area:
            observation = "مفقود"
            details = "مفقود"

        # الإحداثيات
        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat_val, lon_val = 0.0, 0.0
        if coords:
            coord_split = coords[0].strip().split(',')
            if len(coord_split) >= 2:
                lat_val = float(coord_split[1])
                lon_val = float(coord_split[0])

        data.append({
            "المحطة": station_code,
            "رقم العمود": column_num,
            "رقم الفيدر": feeder_num,
            "طول العمود": val_height,
            "الذراع": lamps,
            "الاحداثيات x": lon_val,
            "الاحداثيات y": lat_val,
            "اسم الشارع": street_name,
            "التفاصيل": details,
            "ملاحظة_داخلية": observation 
        })

    return pd.DataFrame(data)

if uploaded_files:
    all_dfs = []
    for f in uploaded_files:
        all_dfs.append(process_kmz(f))
    
    result_df = pd.concat(all_dfs, ignore_index=True)
    result_df = result_df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    
    st.write(f"### معاينة البيانات (إجمالي النقاط: {len(result_df)}):")
    st.dataframe(result_df.drop(columns=['ملاحظة_داخلية']))
    
    # تصدير إكسيل منسق
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        export_df = result_df.drop(columns=['ملاحظة_داخلية'])
        export_df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        worksheet.right_to_left()
        
        # تنسيق الألوان للحالات الخاصة (مفقود/مغروز)
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#A6A6A6', 'border': 1, 'align': 'center'})
        red_fmt = workbook.add_format({'bg_color': '#FF0000', 'border': 1, 'align': 'center'})
        normal_fmt = workbook.add_format({'border': 1, 'align': 'center'})

        for col_num, value in enumerate(export_df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 15)

        for row_idx in range(len(result_df)):
            is_urgent = result_df.iloc[row_idx]['ملاحظة_داخلية'] in ["مغروز", "مفقود"]
            fmt = red_fmt if is_urgent else normal_fmt
            for col_idx in range(len(export_df.columns)):
                worksheet.write(row_idx + 1, col_idx, export_df.iloc[row_idx, col_idx], fmt)

    st.download_button(
        label="📥 تحميل التقرير المدمج (Excel)",
        data=output.getvalue(),
        file_name="Lighting_Network_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
