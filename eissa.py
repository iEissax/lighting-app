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

        # الملاحظة
        if "مغروز" in search_area:
            observation = "مغروز"
        elif "مفقود" in search_area:
            observation = "مفقود"
        else:
            observation = "طبيعي"

        # طول العمود
        height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
        val_height = height_match.group(1) if height_match else ""

        # عدد الشمعات (الذراع)
        if "2/2" in search_area:
            lamps = 2
        elif "1/1" in search_area:
            lamps = 1
        else:
            lamps = ""

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
            "ملاحظة_داخلية": observation # للحكم على اللون فقط
        })

    df = pd.DataFrame(data)
    df = df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    return df

if uploaded_file:
    result_df = process_kmz(uploaded_file)
    st.write("### معاينة البيانات:")
    st.dataframe(result_df.drop(columns=['ملاحظة_داخلية']))
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # استثناء العمود الداخلي من الطباعة
        export_df = result_df.drop(columns=['ملاحظة_داخلية'])
        export_df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        workbook  = writer.book
        worksheet = writer.sheets['Sheet1']
        worksheet.right_to_left()
        
        # --- التنسيقات ---
        # تنسيق الرأس (رمادي داكن كما في الصورة)
        header_fmt = workbook.add_format({
            'bold': True, 
            'bg_color': '#A6A6A6', 
            'border': 1, 
            'align': 'center', 
            'valign': 'vcenter'
        })
        
        # تنسيق الخلايا العادية
        cell_fmt = workbook.add_format({
            'border': 1, 
            'align': 'center', 
            'valign': 'vcenter'
        })
        
        # تنسيق عمود المحطة (رمادي جانبي)
        station_col_fmt = workbook.add_format({
            'bg_color': '#808080', 
            'font_color': 'black', 
            'border': 1, 
            'align': 'center'
        })

        # تنسيق الصف الأحمر (للمفقود والمغروز)
        red_row_fmt = workbook.add_format({
            'bg_color': '#FF0000', 
            'font_color': 'black', 
            'border': 1, 
            'align': 'center'
        })

        # تطبيق تنسيق العناوين وعرض الأعمدة
        for col_num, value in enumerate(export_df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 15, cell_fmt)

        # تطبيق التنسيق الشرطي (تلوين الصف بناءً على القيمة المخفية في ملاحظة_داخلية)
        for row_idx in range(len(result_df)):
            obs_val = result_df.iloc[row_idx]['ملاحظة_داخلية']
            row_data = export_df.iloc[row_idx].values
            
            # تحديد التنسيق المناسب
            current_fmt = red_row_fmt if obs_val in ["مغروز", "مفقود"] else cell_fmt
            
            # كتابة الصف
            for col_idx, cell_value in enumerate(row_data):
                # إذا كان أول عمود (المحطة)، نعطيه لوناً مختلفاً إلا إذا كان الصف أحمر
                if col_idx == 0 and obs_val not in ["مغروز", "مفقود"]:
                    worksheet.write(row_idx + 1, col_idx, cell_value, station_col_fmt)
                else:
                    worksheet.write(row_idx + 1, col_idx, cell_value, current_fmt)

    st.success("تم محاكاة التنسيق المطلوب بنجاح!")
    st.download_button(
        label="📥 تحميل التقرير النهائي (نفس تنسيق الصورة)",
        data=output.getvalue(),
        file_name="Street_Lighting_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
