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

        # استخراج الأرقام
        numbers = re.findall(r'\d+', full_name)
        column_num = int(numbers[0]) if len(numbers) >= 1 else ""
        feeder_num = int(numbers[1]) if len(numbers) >= 2 else ""
        
        # التعرف على المحطة
        station_match = re.search(r'(?:محطة|Station|ST|ق)\s*([a-zA-Z\u0600-\u06FF0-9]*)', full_name, re.IGNORECASE)
        station_code = station_match.group(0).strip() if station_match else ""
        if not station_code:
            station_part = re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name)
            station_code = station_part.group(0) if station_part else ""

        desc = pm.xpath("./kml:description/text()", namespaces=ns)
        desc_text = desc[0] if desc else ""
        ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
        search_area = (desc_text + " " + ext_vals).strip()

        # استخراج اسم الشارع
        street_match = re.search(r'(?:شارع|Street)\s+([^,\n0-9]+)', search_area)
        street_name = street_match.group(1).strip() if street_match else ""

        # الملاحظة (للتلوين الأحمر)
        observation = "طبيعي"
        if "مغروز" in search_area: observation = "مغروز"
        elif "مفقود" in search_area: observation = "مفقود"

        # طول العمود
        height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
        val_height = height_match.group(1) if height_match else ""

        # الذراع (دبل/مفرد)
        lamps = ""
        if any(kw in search_area for kw in ["2/2", "دبل"]): lamps = 2
        elif any(kw in search_area for kw in ["1/1", "مفرد"]): lamps = 1

        # الإحداثيات
        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat_val, lon_val = "", ""
        if coords:
            coord_split = coords[0].strip().split(',')
            lat_val = float(coord_split[1])
            lon_val = float(coord_split[0])

        # الترتيب طبقاً للصورة: المحطة، رقم العمود، رقم الفيدر، طول العمود، الذراع، الاحداثيات x، الاحداثيات y، اسم الشارع
        data.append({
            "المحطة": station_code,
            "رقم العمود": column_num,
            "رقم الفيدر": feeder_num,
            "طول العمود": val_height,
            "الذراع": lamps,
            "الاحداثيات x": lon_val,
            "الاحداثيات y": lat_val,
            "اسم الشارع": street_name,
            "ملاحظة_داخلية": observation
        })

    df = pd.DataFrame(data)
    # فرز البيانات لضمان الترتيب التسلسلي
    df = df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    return df

if uploaded_file:
    result_df = process_kmz(uploaded_file)
    st.write("### معاينة الجدول (نفس ترتيب الصورة):")
    st.dataframe(result_df.drop(columns=['ملاحظة_داخلية']), use_container_width=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        export_df = result_df.drop(columns=['ملاحظة_داخلية'])
        export_df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        workbook  = writer.book
        worksheet = writer.sheets['Sheet1']
        worksheet.right_to_left() 

        # تعريف التنسيقات بناءً على الصورة
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        # تنسيق العمود الأول (الرمادي الغامق كما في الصورة)
        station_col_fmt = workbook.add_format({'bg_color': '#7F7F7F', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        # تنسيق الإحداثيات (5 أرقام عشرية)
        coord_fmt = workbook.add_format({'num_format': '0.00000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        # التنسيق الأحمر للحالات الخاصة
        red_fmt = workbook.add_format({'bg_color': '#FF0000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})

        # ضبط عرض الأعمدة
        worksheet.set_column('A:A', 12) # المحطة
        worksheet.set_column('B:C', 12) # أرقام الأعمدة والفيدر
        worksheet.set_column('D:E', 12) # الطول والذراع
        worksheet.set_column('F:G', 18) # الإحداثيات
        worksheet.set_column('H:H', 25) # اسم الشارع

        # كتابة العناوين بتنسيق الصورة
        for col_num, value in enumerate(export_df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)

        # كتابة البيانات وتطبيق التنسيق اللوني
        for row_idx in range(len(result_df)):
            obs_val = result_df.iloc[row_idx]['ملاحظة_داخلية']
            is_red = obs_val in ["مغروز", "مفقود"]
            
            for col_idx in range(len(export_df.columns)):
                cell_value = export_df.iloc[row_idx, col_idx]
                col_name = export_df.columns[col_idx]
                
                # اختيار التنسيق المناسب لكل خلية
                if is_red:
                    current_fmt = red_fmt
                elif col_idx == 0: # عمود المحطة
                    current_fmt = station_col_fmt
                elif "الاحداثيات" in col_name:
                    current_fmt = coord_fmt
                else:
                    current_fmt = cell_fmt
                
                worksheet.write(row_idx + 1, col_idx, cell_value, current_fmt)

    st.download_button(
        label="📥 تحميل ملف Excel بنفس تنسيق الصورة",
        data=output.getvalue(),
        file_name="Lighting_Report_Formatted.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
