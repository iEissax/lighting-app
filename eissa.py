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

        # تحليل النمط: الرقم الأول عمود / الرقم الثاني فيدر
        numbers = re.findall(r'\d+', full_name)
        column_num = int(numbers[0]) if len(numbers) >= 1 else 0
        feeder_num = int(numbers[1]) if len(numbers) >= 2 else 0
        extra_num = numbers[2] if len(numbers) >= 3 else ""

        station_part = re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name)
        station_code = station_part.group(0) if station_part else ""

        formatted_name = f"{column_num}/{feeder_num}"
        if extra_num: formatted_name += f"/{extra_num}"
        if station_code: formatted_name = f"{station_code} {formatted_name}"

        # الوصف والبيانات
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

        height_match = re.search(r'\b(12|10|9|8|6)\b', search_area)
        val_height = height_match.group(1) if height_match else "غير مسجل"
        lamps = 2 if "دبل" in search_area else (1 if "مفرد" in search_area else 0)

        # الإحداثيات
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
        
        # تم إزالة السطر المسبب للخطأ (set_right_to_left) 
        # الوضع الافتراضي للإكسل هو LTR فلا داعي للقلق
        
        # تعريف التنسيقات
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})

        # ضبط العرض وكتابة العناوين
        for i, col in enumerate(result_df.columns):
            max_len = max(result_df[col].astype(str).map(len).max(), len(col)) + 5
            worksheet.set_column(i, i, max_len, cell_fmt)
            worksheet.write(0, i, col, header_fmt)

    st.success("تم تجهيز التقرير بنجاح!")
    st.download_button(
        label="📥 تحميل التقرير النهائي",
        data=output.getvalue(),
        file_name="Lighting_Report_Final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
