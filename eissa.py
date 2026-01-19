import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io

st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة المطور", layout="wide")
st.title("📂 مستخرج بيانات KMZ المتعدد")

# تفعيل خاصية رفع أكثر من ملف في نفس الوقت
uploaded_files = st.file_uploader("اختر ملفات KMZ (يمكنك اختيار أكثر من ملف)", type=['kmz'], accept_multiple_files=True)

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

        is_highmast = any(kw in search_area.lower() for kw in ["هاي ماست", "هايماست", "highmast", "high mast"])

        if is_highmast:
            val_height = "هاي ماست"
            lamps = 6
        else:
            height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
            val_height = height_match.group(1) if height_match else ""
            if any(keyword in search_area for keyword in ["2/2", "دبل"]):
                lamps = 2
            elif any(keyword in search_area for keyword in ["1/1", "مفرد"]):
                lamps = 1
            else:
                lamps = ""

        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat_val, lon_val = 0.0, 0.0
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
            "التفاصيل": details,
            "ملاحظة_داخلية": observation 
        })

    df = pd.DataFrame(data)
    df = df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    return df

# معالجة كل ملف بشكل مستقل تماماً
if uploaded_files:
    st.write(f"### تم العثور على {len(uploaded_files)} ملفات:")
    
    for i, file in enumerate(uploaded_files):
        # صندوق منعزل لكل ملف (Expander) لترتيب العرض
        with st.expander(f"📄 معالجة الملف: {file.name}", expanded=True):
            result_df = process_kmz(file)
            st.dataframe(result_df.drop(columns=['ملاحظة_داخلية']), use_container_width=True)
            
            # منطق التكرار الخاص بهذا الملف فقط
            dup_coords = result_df.duplicated(subset=['الاحداثيات x', 'الاحداثيات y'], keep=False)
            dup_columns = result_df.duplicated(subset=['المحطة', 'رقم الفيدر', 'رقم العمود'], keep=False)
            is_duplicated_any = dup_coords | dup_columns
            
            # توليد ملف Excel خاص بهذا الملف تحديداً
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                export_df = result_df.drop(columns=['ملاحظة_داخلية'])
                export_df.to_excel(writer, index=False, sheet_name='Data')
                
                workbook  = writer.book
                worksheet = writer.sheets['Data']
                worksheet.right_to_left()
                
                # إعداد التنسيقات (نفس منطقك الأصلي)
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#A6A6A6', 'border': 1, 'align': 'center'})
                cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
                red_fmt = workbook.add_format({'bg_color': '#FF0000', 'border': 1, 'align': 'center'})
                blue_fmt = workbook.add_format({'bg_color': '#00B0F0', 'border': 1, 'align': 'center'})
                
                # كتابة البيانات وتطبيق التنسيق اللوني
                for row_idx in range(len(result_df)):
                    obs_val = result_df.iloc[row_idx]['ملاحظة_داخلية']
                    is_dup = is_duplicated_any.iloc[row_idx]
                    
                    for col_idx, cell_value in enumerate(export_df.iloc[row_idx]):
                        if obs_val in ["مغروز", "مفقود"]:
                            fmt = red_fmt
                        elif is_dup:
                            fmt = blue_fmt
                        else:
                            fmt = cell_fmt
                        worksheet.write(row_idx + 1, col_idx, cell_value, fmt)

            # زر تحميل مخصص لكل ملف
            st.download_button(
                label=f"📥 تحميل تقرير {file.name}",
                data=output.getvalue(),
                file_name=f"Report_{file.name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"btn_{i}" # مفتاح فريد لكل زر
            )
