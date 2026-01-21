import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io

st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة - المطور", layout="centered")
st.title("📂 مستخرج بيانات KMZ (استخراج الطول المتسلسل)")

# دالة تحويل الأرقام لضمان التعرف على الأطوال المكتوبة بالعربي
def convert_arabic_numbers(text):
    if not text: return ""
    arabic_numbers = '٠١٢٣٤٥٦٧٨٩'
    english_numbers = '0123456789'
    translation_table = str.maketrans(arabic_numbers, english_numbers)
    return text.translate(translation_table)

uploaded_files = st.file_uploader("اختر ملفات KMZ", type=['kmz'], accept_multiple_files=True)

def process_kmz(file):
    with zipfile.ZipFile(file, 'r') as f:
        kml_filename = [name for name in f.namelist() if name.endswith('.kml')][0]
        kml_content = f.read(kml_filename)

    tree = etree.fromstring(kml_content)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    data = []

    for pm in tree.xpath("//kml:Placemark", namespaces=ns):
        # 1. استخراج الاسم الأساسي
        name_text = pm.xpath("./kml:name/text()", namespaces=ns)
        full_name = name_text[0].strip() if name_text else ""
        
        # 2. استخراج الوصف (Description) وهو المكان المتوقع للأطوال المتسلسلة
        desc = pm.xpath("./kml:description/text()", namespaces=ns)
        desc_text = desc[0].strip() if desc else ""
        
        # تحويل الأرقام في الوصف والاسم
        full_name_eng = convert_arabic_numbers(full_name)
        desc_text_eng = convert_arabic_numbers(desc_text)

        # استخراج رقم العمود (للترتيب)
        numbers = re.findall(r'\d+', full_name_eng)
        column_num = int(numbers[0]) if len(numbers) >= 1 else 0
        feeder_num = int(numbers[1]) if len(numbers) >= 2 else 0

        # --- استخراج الطول من الوصف ---
        val_height = ""
        # البحث عن الأطوال الشائعة (16, 12, 10, 9, 8, 6) في نص الوصف
        # الرمز \b يضمن استخراج الرقم المستقل (مثلاً 12 وليس 120)
        height_match = re.search(r'\b(16|12|10|9|8|6)\b', desc_text_eng)
        
        if height_match:
            val_height = height_match.group(1)
        elif "جداري" in desc_text or "wall" in desc_text.lower():
            val_height = "جداري"
        elif "هاي ماست" in desc_text or "highmast" in desc_text.lower():
            val_height = "هاي ماست"

        # --- استخراج الذراع ---
        lamps = ""
        if any(kw in desc_text_eng for kw in ["2/2", "٢/٢", "دبل", "مزدوج"]):
            lamps = 2
        elif any(kw in desc_text_eng for kw in ["1/1", "١/١", "مفرد"]):
            lamps = 1
        elif val_height == "هاي ماست":
            lamps = 6

        # الإحداثيات
        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat_val, lon_val = 0.0, 0.0
        if coords:
            coord_split = coords[0].strip().split(',')
            lat_val = float(coord_split[1])
            lon_val = float(coord_split[0])

        data.append({
            "المحطة": re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name_eng).group(0) if re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name_eng) else "",
            "رقم العمود": column_num,
            "رقم الفيدر": feeder_num,
            "طول العمود": val_height,
            "الذراع": lamps,
            "الاحداثيات x": lon_val,
            "الاحداثيات y": lat_val,
            "الوصف": desc_text # لكي تراجع ما تم استخراجه
        })

    return pd.DataFrame(data)

if uploaded_files:
    all_dfs = [process_kmz(f) for f in uploaded_files]
    result_df = pd.concat(all_dfs, ignore_index=True)
    
    # الترتيب حسب رقم العمود لضمان ظهور التسلسل بشكل صحيح
    result_df = result_df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    
    st.write(f"### معاينة البيانات المتسلسلة ({len(result_df)} عمود):")
    st.dataframe(result_df)
    
    # تصدير إكسيل
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        result_df.to_excel(writer, index=False, sheet_name='Data')
        workbook = writer.book
        worksheet = writer.sheets['Data']
        worksheet.right_to_left()
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center'})
        for col_num, value in enumerate(result_df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 15)

    st.download_button("📥 تحميل التقرير المتسلسل (Excel)", output.getvalue(), "Lighting_Sequence_Report.xlsx")
