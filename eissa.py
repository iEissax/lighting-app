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
        
        # استخراج رمز المحطة (مثل "ق")
        station_part = re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name)
        station_code = station_part.group(0) if station_part else ""

        desc = pm.xpath("./kml:description/text()", namespaces=ns)
        desc_text = desc[0] if desc else ""
        ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
        search_area = (desc_text + " " + ext_vals).strip()

        # استخراج اسم الشارع
        street_match = re.search(r'(?:شارع|Street)\s+([^,\n0-9]+)', search_area)
        street_name = street_match.group(1).strip() if street_match else ""

        # الملاحظة (للتلوين)
        observation = "طبيعي"
        if "مغروز" in search_area: observation = "مغروز"
        elif "مفقود" in search_area: observation = "مفقود"

        # طول العمود والذراع
        height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
        val_height = height_match.group(1) if height_match else ""
        
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
    df = df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    
    # منطق إضافة كلمة "محطة" في أول صف من كل مجموعة
    final_data = []
    groups = df.groupby('المحطة', sort=False)
    for name, group in groups:
        # إضافة صف "محطة" في البداية
        station_row = {col: "" for col in df.columns}
        station_row["المحطة"] = "محطة"
        station_row["رقم العمود"] = group.iloc[0]["رقم العمود"] if not group.empty else ""
        station_row["ملاحظة_داخلية"] = "header_station" # علامة للتنسيق
        final_data.append(station_row)
        
        # إضافة باقي الأعمدة التابعة للمحطة
        for _, row in group.iterrows():
            final_data.append(row.to_dict())
            
    return pd.DataFrame(final_data)

if uploaded_file:
    result_df = process_kmz(uploaded_file)
    st.write("### معاينة الجدول النهائي:")
    st.dataframe(result_df.drop(columns=['ملاحظة_داخلية']), use_container_width=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        export_df = result_df.drop(columns=['ملاحظة_داخلية'])
        export_df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        workbook  = writer.book
        worksheet = writer.sheets['Sheet1']
        worksheet.right_to_left() 

        # التنسيقات
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        station_col_fmt = workbook.add_format({'bg_color': '#7F7F7F', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        coord_fmt = workbook.add_format({'num_format': '0.00000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        red_fmt = workbook.add_format({'bg_color': '#FF0000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})

        worksheet.set_column('A:E', 12)
        worksheet.set_column('F:G', 18, coord_fmt)
        worksheet.set_column('H:H', 25)

        for col_num, value in enumerate(export_df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)

        for row_idx in range(len(result_df)):
            obs_val = result_df.iloc[row_idx]['ملاحظة_داخلية']
            
            for col_idx in range(len(export_df.columns)):
                cell_value = export_df.iloc[row_idx, col_idx]
                
                # تطبيق التنسيق
                if obs_val in ["مغروز", "مفقود"]:
                    current_fmt = red_fmt
                elif col_idx == 0:
                    current_fmt = station_col_fmt
                else:
                    current_fmt = cell_fmt
                
                # كتابة القيمة (مع معالجة القيم الفارغة في صف المحطة)
                val = cell_value if cell_value != "" else ""
                worksheet.write(row_idx + 1, col_idx, val, current_fmt)

    st.download_button(
        label="📥 تحميل التقرير بالتنسيق النهائي",
        data=output.getvalue(),
        file_name="Lighting_Network_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
