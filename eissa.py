import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import folium
from streamlit_folium import st_folium

# إعدادات الصفحة
st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة", layout="wide")

st.title("💡 مستخرج بيانات KMZ (تحديث: الأعمدة الجدارية)")

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

        # استخراج الأرقام (رقم العمود، الفيدر)
        numbers = re.findall(r'\d+', full_name)
        column_num = int(numbers[0]) if len(numbers) >= 1 else 0
        feeder_num = int(numbers[1]) if len(numbers) >= 2 else 0
        
        # استخراج اسم المحطة
        station_part = re.search(r'[a-zA-Z\u0600-\u06FF]+', full_name)
        station_code = station_part.group(0) if station_part else ""

        # البحث في الوصف والبيانات الإضافية
        desc = pm.xpath("./kml:description/text()", namespaces=ns)
        desc_text = desc[0] if desc else ""
        ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
        search_area = (desc_text + " " + ext_vals).strip()

        # --- منطق تحديد طول العمود (مع تصحيح جداري) ---
        is_highmast = any(kw in search_area.lower() for kw in ["هاي ماست", "هايماست", "highmast"])
        # البحث عن كلمة "جدار" أو "جداري"
        is_wall = any(kw in search_area for kw in ["جدار", "جداري", "Wall", "wall"])

        if is_highmast:
            val_height = "هاي ماست"
        elif is_wall:
            val_height = "جداري"  # تم التوحيد إلى "جداري"
        else:
            # البحث عن الأرقام المعتادة للأطوال
            height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
            val_height = height_match.group(1) if height_match else ""

        # استخراج اسم الشارع
        street_match = re.search(r'(?:شارع|Street)\s+([^,\n0-9]+)', search_area)
        street_name = street_match.group(1).strip() if street_match else ""

        # تحديد الملاحظة (التفاصيل)
        details = ""
        if "مغروز" in search_area:
            observation, details = "مغروز", "مغروز"
        elif "مفقود" in search_area:
            observation, details = "مفقود", "مفقود"
        else:
            observation, details = "طبيعي", ""

        # عدد الأذرع/الشمعات
        if is_highmast:
            lamps = 6
        else:
            lamps = 2 if any(kw in search_area for kw in ["2/2", "دبل"]) else (1 if any(kw in search_area for kw in ["1/1", "مفرد"]) else "")

        # الإحداثيات
        coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
        lat_val, lon_val = 0.0, 0.0
        if coords:
            coord_split = coords[0].strip().split(',')
            lat_val, lon_val = float(coord_split[1]), float(coord_split[0])

        data.append({
            "المحطة": station_code, "رقم العمود": column_num, "رقم الفيدر": feeder_num,
            "طول العمود": val_height, "الذراع": lamps, "الاحداثيات x": lon_val,
            "الاحداثيات y": lat_val, "اسم الشارع": street_name, "التفاصيل": details,
            "ملاحظة_داخلية": observation 
        })

    df = pd.DataFrame(data).sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])
    return df

# --- عرض النتائج ---
if uploaded_files:
    for i, file in enumerate(uploaded_files):
        with st.expander(f"📁 ملف: {file.name}", expanded=True):
            result_df = process_kmz(file)
            
            # إحصائيات سريعة للملف الحالي
            m1, m2, m3 = st.columns(3)
            m1.metric("الإجمالي", len(result_df))
            m2.metric("جداري", len(result_df[result_df['طول العمود'] == "جداري"]))
            m3.metric("ملاحظات", len(result_df[result_df['ملاحظة_داخلية'] != "طبيعي"]))

            # الخريطة التفاعلية
            if not result_df.empty:
                map_center = [result_df['الاحداثيات y'].mean(), result_df['الاحداثيات x'].mean()]
                m = folium.Map(location=map_center, zoom_start=15)
                for _, row in result_df.iterrows():
                    color = 'red' if row['ملاحظة_داخلية'] in ["مغروز", "مفقود"] else 'blue'
                    folium.Marker(
                        [row['الاحداثيات y'], row['الاحداثيات x']],
                        popup=f"عمود: {row['رقم العمود']} - {row['طول العمود']}",
                        icon=folium.Icon(color=color)
                    ).add_to(m)
                st_folium(m, width=1100, height=400, key=f"map_{i}")

            # تصدير الإكسل (بنفس تنسيقاتك)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                export_df = result_df.drop(columns=['ملاحظة_داخلية'])
                export_df.to_excel(writer, index=False, sheet_name='Data')
                
                # تطبيق الألوان (أحمر للملاحظات، أزرق للتكرار)
                workbook = writer.book
                worksheet = writer.sheets['Data']
                worksheet.right_to_left()
                
                red_fmt = workbook.add_format({'bg_color': '#FF0000', 'border': 1, 'align': 'center'})
                cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})

                for row_idx in range(len(result_df)):
                    fmt = red_fmt if result_df.iloc[row_idx]['ملاحظة_داخلية'] != "طبيعي" else cell_fmt
                    for col_idx, cell_value in enumerate(export_df.iloc[row_idx]):
                        worksheet.write(row_idx + 1, col_idx, cell_value, fmt)

            st.download_button(label=f"📥 تحميل تقرير {file.name}", data=output.getvalue(), 
                               file_name=f"Report_{file.name}.xlsx", key=f"btn_{i}")
