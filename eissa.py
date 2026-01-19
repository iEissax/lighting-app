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
        
        station_part = re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name)
        station_code = station_part.group(0) if station_part else ""

        desc = pm.xpath("./kml:description/text()", namespaces=ns)
        desc_text = desc[0] if desc else ""
        ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
        search_area = (desc_text + " " + ext_vals).strip()

        # استخراج اسم الشارع
        street_match = re.search(r'(?:شارع|Street)\s+([^,\n0-9]+)', search_area)
        street_name = street_match.group(1).strip() if street_match else ""

        # الملاحظة (التفاصيل)
        details = ""
        if "مغروز" in search_area:
            observation = "مغروز"
            details = "مغروز"
        elif "مفقود" in search_area:
            observation = "مفقود"
            details = "مفقود"
        else:
            observation = "طبيعي"
            details = ""

        # منطق "هاي ماست"
        is_highmast = any(kw in search_area.lower() for kw in ["هاي ماست", "هايماست", "highmast", "high mast"])

        # طول العمود
        if is_highmast:
            val_height = "هاي ماست"
        else:
            height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
            val_height = height_match.group(1) if height_match else ""

        # عدد الشمعات (الذراع)
        if is_highmast:
            lamps = 6
        elif any(keyword in search_area for keyword in ["2/2", "دبل"]):
            lamps = 2
        elif any(keyword in search_area for keyword in ["1/1", "مفرد"]):
            lamps = 1
        else:
            lamps = ""

        # الإحداثيات
        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat_val, lon_val = 0.0, 0.0
        if coords:
            coord_split = coords[0].strip().split(',')
            lat_val = float(coord_split[1])
            lon_val = float(coord_split[0])

        # ترتيب الأعمدة مع إضافة عمود "التفاصيل" في النهاية
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
            "ملاحظة_داخلية": observation # للحفاظ على منطق التلوين
        })

    df = pd.DataFrame(data)
    df = df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    return df

if uploaded_file:
    result_df = process_kmz(uploaded_file)
    st.write("### معاينة البيانات:")
    st.dataframe(result_df.drop(columns=['ملاحظة_داخلية']))
    
    # تحديد التكرارات
    dup_coords = result_df.duplicated(subset=['الاحداثيات x', 'الاحداثيات y'], keep=False)
    dup_columns = result_df.duplicated(subset=['المحطة', 'رقم الفيدر', 'رقم العمود'], keep=False)
    is_duplicated_any = dup_coords | dup_columns
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        export_df = result_df.drop(columns=['ملاحظة_داخلية'])
        export_df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        workbook  = writer.book
        worksheet = writer.sheets['Sheet1']
        worksheet.right_to_left()
        
        # التنسيقات
        num_fmt = workbook.add_format({'num_format': '0.00000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#A6A6A6', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        station_col_fmt = workbook.add_format({'bg_color': '#808080', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        red_row_fmt = workbook.add_format({'bg_color': '#FF0000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        red_num_fmt = workbook.add_format({'bg_color': '#FF0000', 'num_format': '0.00000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        blue_row_fmt = workbook.add_format({'bg_color': '#00B0F0', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        blue_num_fmt = workbook.add_format({'bg_color': '#00B0F0', 'num_format': '0.00000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})

        for col_num, value in enumerate(export_df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            if "الاحداثيات" in value:
                worksheet.set_column(col_num, col_num, 15, num_fmt)
            else:
                worksheet.set_column(col_num, col_num, 18, cell_fmt)

        for row_idx in range(len(result_df)):
            obs_val = result_df.iloc[row_idx]['ملاحظة_داخلية']
            is_dup = is_duplicated_any.iloc[row_idx]
            is_red = obs_val in ["مغروز", "مفقود"]
            row_data = export_df.iloc[row_idx].values
            
            for col_idx, cell_value in enumerate(row_data):
                col_name = export_df.columns[col_idx]
                
                if is_red:
                    target_fmt = red_num_fmt if "الاحداثيات" in col_name else red_row_fmt
                elif is_dup:
                    target_fmt = blue_num_fmt if "الاحداثيات" in col_name else blue_row_fmt
                elif col_idx == 0: 
                    target_fmt = station_col_fmt
                elif "الاحداثيات" in col_name:
                    target_fmt = num_fmt
                else:
                    target_fmt = cell_fmt
                
                worksheet.write(row_idx + 1, col_idx, cell_value, target_fmt)

    st.success("تم إضافة عمود 'التفاصيل' وتحديث المنطق بنجاح!")
    st.download_button(
        label="📥 تحميل التقرير النهائي",
        data=output.getvalue(),
        file_name="Lighting_Network_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

