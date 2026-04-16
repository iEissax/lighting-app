import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io

# دالة الترتيب الطبيعي
def natural_sort_key(s):
    if pd.isna(s) or s == "":
        return tuple()
    return tuple(int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s)))

st.set_page_config(page_title="مستخرج بيانات المحطات الاحترافي", layout="wide")
st.title("📂 معالجة KMZ: فصل الفيدر واستخراج الطول من الوصف")

uploaded_files = st.file_uploader("اختر ملفات KMZ", type=['kmz'], accept_multiple_files=True)

def process_kmz(file):
    data = []
    try:
        with zipfile.ZipFile(file, 'r') as f:
            kml_filename = [name for name in f.namelist() if name.endswith('.kml')][0]
            kml_content = f.read(kml_filename)
            tree = etree.fromstring(kml_content)
            ns = {"kml": "http://www.opengis.net/kml/2.2"}

            for pm in tree.xpath("//kml:Placemark", namespaces=ns):
                # --- 1. العنوان (Name) ---
                name_nodes = pm.xpath("./kml:name/text()", namespaces=ns)
                full_name = name_nodes[0].strip() if name_nodes else ""
                
                # استخراج كود المحطة (يدعم العربية والأرقام)
                st_match = re.search(r'(\d+[\u0600-\u06FF]+|[\u0600-\u06FF]+\d+)', full_name)
                station_code = st_match.group(1) if st_match else "غير محدد"

                # استخراج أرقام (العمود / الفيدر)
                clean_name = full_name.replace(station_code, "").strip()
                name_nums = re.findall(r'\d+', clean_name)
                column_num, feeder_num = "", ""
                
                if len(name_nums) >= 2:
                    column_num, feeder_num = name_nums[0], name_nums[1]
                elif len(name_nums) == 1:
                    column_num = name_nums[0]

                # --- 2. الوصف (Description) ---
                desc = "".join(pm.xpath("./kml:description/text()", namespaces=ns))
                ext_vals = " ".join(pm.xpath(".//kml:value/text()", namespaces=ns))
                tech_info = (desc + " " + ext_vals).strip()
                
                val_height, val_arms = "", ""
                # البحث عن نمط (طول/ذراع) مثل 12/2 أو 10-1
                pattern_match = re.search(r'(\d+)[/-](\d+)', tech_info)
                if pattern_match:
                    val_height, val_arms = pattern_match.group(1), pattern_match.group(2)
                else:
                    h_search = re.search(r'\b(12|10|8|6|5)\b', tech_info)
                    if h_search: val_height = h_search.group(1)
                    
                    tech_lower = tech_info.lower()
                    if any(word in tech_lower for word in ["هاي", "mast"]):
                        val_height, val_arms = "هاي ماست", 6
                    elif "جداري" in tech_lower:
                        val_height, val_arms = "جداري", 1

                # --- 3. الإحداثيات ---
                coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
                lat_v, lon_v = 0.0, 0.0
                if coords:
                    try:
                        c_split = coords[0].strip().split(',')
                        lat_v, lon_v = round(float(c_split[1]), 6), round(float(c_split[0]), 6)
                    except (IndexError, ValueError): pass

                all_txt = (full_name + " " + tech_info).lower()
                detail = "مفقود" if "مفقود" in all_txt else ("مغروز" if "مغروز" in all_txt else "")

                data.append({
                    "المحطة": station_code,
                    "رقم العمود": column_num,
                    "رقم الفيدر": feeder_num,
                    "طول العمود": val_height,
                    "الذراع": val_arms,
                    "الاحداثيات x": lon_v,
                    "الاحداثيات y": lat_v,
                    "التفاصيل": detail
                })
    except Exception as e:
        st.error(f"خطأ في معالجة الملف {file.name}: {e}")
    return pd.DataFrame(data)

if uploaded_files:
    all_dfs = [process_kmz(f) for f in uploaded_files]
    df = pd.concat(all_dfs, ignore_index=True)

    # تنظيف البيانات وضمان الترتيب الرقمي
    for col in ['رقم العمود', 'رقم الفيدر']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    df = df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'], 
                        key=lambda x: x.map(natural_sort_key) if x.name == 'المحطة' else x)

    # تصدير Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Lighting_Report') # تصدير أولي سريع
        workbook = writer.book
        worksheet = writer.sheets['Lighting_Report']
        worksheet.right_to_left()

        # تنسيقات مخصصة
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1, 'align': 'center'})
        station_fmt = workbook.add_format({'bg_color': '#7F7F7F', 'font_color': 'white', 'border': 1, 'align': 'center'})
        red_fmt = workbook.add_format({'bg_color': '#FF0000', 'font_color': 'white', 'border': 1, 'align': 'center'})
        coord_fmt = workbook.add_format({'num_format': '0.000000', 'border': 1, 'align': 'center'})
        normal_fmt = workbook.add_format({'border': 1, 'align': 'center'})

        # ضبط عرض الأعمدة وكتابة التنسيق
        for i, col in enumerate(df.columns):
            worksheet.write(0, i, col, header_fmt)
            worksheet.set_column(i, i, 15)

        for row_idx, row_val in enumerate(df.values, start=1):
            is_urgent = str(row_val[7]) in ["مفقود", "مغروز"] # عمود التفاصيل
            for col_idx, cell_val in enumerate(row_val):
                current_fmt = normal_fmt
                if is_urgent: current_fmt = red_fmt
                elif col_idx == 0: current_fmt = station_fmt # عمود المحطة
                elif col_idx in [5, 6]: current_fmt = coord_fmt # الإحداثيات
                
                worksheet.write(row_idx, col_idx, cell_val, current_fmt)

    st.success(f"✅ تم معالجة {len(df)} عمود إنارة بنجاح!")
    st.download_button("📥 تحميل التقرير النهائي (Excel)", output.getvalue(), "Lighting_Report_Professional.xlsx")
