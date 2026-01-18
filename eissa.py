import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io

st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة", layout="centered")
st.title("📂 مستخرج بيانات KMZ")

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

        # استخراج الملاحظة
        if "مغروز" in search_area:
            observation = "مغروز"
        elif "مفقود" in search_area:
            observation = "مفقود"
        else:
            observation = "طبيعي"

        # استخراج طول العمود
        height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
        val_height = height_match.group(1) if height_match else "غير مسجل"

        # استخراج عدد الشمعات
        if "2/2" in search_area:
            lamps = 2
        elif "1/1" in search_area:
            lamps = 1
        else:
            lamps = 0

        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat_str, lon_str = "0.00000", "0.00000"
        if coords:
            coord_split = coords[0].strip().split(',')
            lat_str = "{:.5f}".format(float(coord_split[1]))
            lon_str = "{:.5f}".format(float(coord_split[0]))

        data.append({
            "المحطة": station_code,
            "الاسم المنسق": formatted_name,
            "نوع الملاحظة": observation,
            "طول العمود": val_height,
            "عدد الشمعات": lamps,
            "الإحداثيات (Lat, Long)": f"{lat_str},{lon_str}",
            "f_num": feeder_num, 
            "c_num": column_num   
        })

    df = pd.DataFrame(data)
    df = df.sort_values(by=['المحطة', 'f_num', 'c_num'], ascending=[True, True, True])
    return df.drop(columns=['f_num', 'c_num'])

if uploaded_file:
    result_df = process_kmz(uploaded_file)
    st.write("### معاينة البيانات:")
    st.dataframe(result_df)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        result_df.to_excel(writer, index=False, sheet_name='Report')
        
        workbook  = writer.book
        worksheet = writer.sheets['Report']
        worksheet.right_to_left()
        
        # --- تعريف التنسيقات ---
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
        # تنسيق اللون الأحمر للصفوف المستهدفة
        red_fmt = workbook.add_format({'bg_color': '#FF0000', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center'})

        # ضبط العرض وتنسيق العناوين
        for i, col in enumerate(result_df.columns):
            max_len = max(result_df[col].astype(str).map(len).max(), len(col)) + 5
            worksheet.set_column(i, i, max_len, cell_fmt)
            worksheet.write(0, i, col, header_fmt)

        # --- إضافة التنسيق الشرطي للصف الكامل ---
        # نحدد النطاق من الصف الثاني (1) حتى نهاية البيانات
        # ونفحص العمود الثالث (C) الذي يحتوي على "نوع الملاحظة"
        num_rows = len(result_df)
        num_cols = len(result_df.columns)
        
        worksheet.conditional_format(1, 0, num_rows, num_cols - 1, {
            'type':     'formula',
            'criteria': 'OR($C2="مغروز", $C2="مفقود")',
            'format':   red_fmt
        })

    st.success("تم تطبيق التنسيق الأحمر للملاحظات بنجاح!")
    st.download_button(
        label="📥 تحميل التقرير النهائي الملون",
        data=output.getvalue(),
        file_name="Lighting_Report_Formatted.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
