import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import pydeck as pdk

st.set_page_config(page_title="مستخرج بيانات الإنارة المطور", layout="wide")
st.title("📍 نظام استخراج وتحليل بيانات الشبكة")

uploaded_file = st.file_uploader("اختر ملف KMZ", type=['kmz'])

# دالة ذكية لتفكيك الاسم والترتيب حسب (المحطة/الفيدر/العمود)
def sort_key_func(name):
    # البحث عن الأرقام في النص (مثال: 30ق/1/12)
    # المجموعات: 1=المحطة، 2=الفيدر، 3=رقم العمود
    parts = re.findall(r'\d+', name)
    # تحويل الأجزاء إلى أرقام صحيحة لضمان الترتيب الحسابي (10 تأتي بعد 2)
    return [int(p) for p in parts] if parts else [0]

def process_kmz(file):
    try:
        with zipfile.ZipFile(file, 'r') as f:
            kml_files = [name for name in f.namelist() if name.endswith('.kml')]
            if not kml_files: return None
            kml_content = f.read(kml_files[0])

        tree = etree.fromstring(kml_content)
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        data = []

        color_map = {
            "12": [255, 0, 0], "10": [0, 255, 0], "9": [0, 0, 255],
            "8": [255, 165, 0], "6": [128, 0, 128], "غير مسجل": [150, 150, 150]
        }

        for pm in tree.xpath("//kml:Placemark", namespaces=ns):
            name_node = pm.xpath("./kml:name/text()", namespaces=ns)
            full_name = name_node[0].strip() if name_node else "بدون اسم"

            desc = pm.xpath("./kml:description/text()", namespaces=ns)
            ext_data = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
            full_description = (desc[0] if desc else "") + " " + ext_data

            # 1. استخراج الطول
            height_match = re.search(r'(\d+)\s*m|(?<!/)\b(12|10|9|8|6)\b', full_description, re.IGNORECASE)
            height_val = height_match.group(1) if height_match and height_match.group(1) else (height_match.group(2) if height_match else "غير مسجل")
            
            # 2. استخراج الأذرعة
            arm_count = 1
            if any(x in full_description for x in ["دبل", "1/2", "2/1"]):
                arm_count, arm_text = 2, "دبل"
            elif any(x in full_description for x in ["مفرد", "1/1"]):
                arm_count, arm_text = 1, "مفرد"
            else:
                arm_text = "غير محدد"

            # 3. استخراج الحالة
            if "مفقود" in full_description:
                status = "مفقود"
            elif "مغروز" in full_description:
                status = "مغروز"
            else:
                status = "طبيعي"

            rgb = color_map.get(height_val, [150, 150, 150])

            # 4. الإحداثيات (00.00000)
            coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
            if coords:
                parts = coords[0].strip().split(',')
                if len(parts) >= 2:
                    lat_val = float(parts[1])
                    lon_val = float(parts[0])
                    data.append({
                        "الاسم": full_name,
                        "الطول (m)": height_val,
                        "الأذرعة": arm_text,
                        "الحالة": status,
                        "lat_num": lat_val,
                        "lon_num": lon_val,
                        "Latitude": "{:.5f}".format(lat_val),
                        "Longitude": "{:.5f}".format(lon_val),
                        "r": rgb[0], "g": rgb[1], "b": rgb[2]
                    })

        df = pd.DataFrame(data)
        
        # --- تطبيق الترتيب التسلسلي الذكي ---
        if not df.empty:
            df['sort_key'] = df['الاسم'].apply(sort_key_func)
            df = df.sort_values(by='sort_key').drop(columns=['sort_key'])
            
        return df
    except Exception as e:
        st.error(f"حدث خطأ: {e}")
        return None

if uploaded_file:
    df = process_kmz(uploaded_file)
    
    if df is not None and not df.empty:
        # إحصائيات
        st.subheader("📊 ملخص الحالات")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("إجمالي الأعمدة", len(df))
        c2.metric("مفقود ❌", len(df[df['الحالة'] == "مفقود"]))
        c3.metric("مغروز 🏗️", len(df[df['الحالة'] == "مغروز"]))
        c4.metric("طبيعي ✅", len(df[df['الحالة'] == "طبيعي"]))
        
        # خريطة
        st.subheader("📍 الخريطة")
        layer = pdk.Layer("ScatterplotLayer", df, get_position='[lon_num, lat_num]', get_color='[r, g, b, 200]', get_radius=10, pickable=True)
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=df['lat_num'].mean(), longitude=df['lon_num'].mean(), zoom=14),
                                 tooltip={"text": "الاسم: {الاسم}\nالحالة: {الحالة}\nالطول: {الطول (m)}"}))

        # جدول البيانات
        st.subheader("📄 جدول البيانات (مرتب تسلسلياً: محطة/فيدر/عمود)")
        final_df = df[['الاسم', 'الطول (m)', 'الأذرعة', 'الحالة', 'Latitude', 'Longitude']]
        st.dataframe(final_df, use_container_width=True)

        # تحميل الإكسل المظلل والمنظم
        st.divider()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Report')
            workbook = writer.book
            worksheet = writer.sheets['Report']

            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
            red_row_fmt = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1})
            normal_row_fmt = workbook.add_format({'border': 1})

            for i, col in enumerate(final_df.columns):
                worksheet.write(0, i, col, header_fmt)
                worksheet.set_column(i, i, 18)

            for row_num, row_data in enumerate(final_df.values):
                current_status = row_data[3] 
                fmt = red_row_fmt if current_status in ["مفقود", "مغروز"] else normal_row_fmt
                for col_num, cell_value in enumerate(row_data):
                    worksheet.write(row_num + 1, col_num, cell_value, fmt)

        st.download_button("📥 تحميل التقرير المرتب تسلسلياً (Excel)", output.getvalue(), "Lighting_Report_Sorted.xlsx")

