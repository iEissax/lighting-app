import streamlit as st
import zipfile
import pandas as pd
from lxml import etree
import re
import io
import pydeck as pdk

st.set_page_config(page_title="مستخرج بيانات الإنارة", layout="wide")
st.title("📍 خريطة أعمدة الإنارة الملونة")

uploaded_file = st.file_uploader("اختر ملف KMZ", type=['kmz'])

def process_kmz(file):
    try:
        with zipfile.ZipFile(file, 'r') as f:
            kml_files = [name for name in f.namelist() if name.endswith('.kml')]
            if not kml_files: return None
            kml_content = f.read(kml_files[0])

        tree = etree.fromstring(kml_content)
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        data = []

        # قاموس الألوان: [الأحمر, الأخضر, الأزرق]
        color_map = {
            "12": [255, 0, 0],    # أحمر
            "10": [0, 255, 0],    # أخضر
            "9":  [0, 0, 255],    # أزرق
            "8":  [255, 165, 0],  # برتقالي
            "6":  [128, 0, 128],  # بنفسجي
            "غير مسجل": [150, 150, 150] # رمادي
        }

        for pm in tree.xpath("//kml:Placemark", namespaces=ns):
            name = pm.xpath("./kml:name/text()", namespaces=ns)
            full_name = name[0].strip() if name else "بدون اسم"

            desc = pm.xpath("./kml:description/text()", namespaces=ns)
            ext_data = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
            full_description = (desc[0] if desc else "") + " " + ext_data

            # استخراج الطول من الوصف
            height_search = re.search(r'\b(12|10|9|8|6)\b', full_description)
            height_val = height_search.group(1) if height_search else "غير مسجل"
            
            rgb = color_map.get(height_val, [150, 150, 150])

            coords = pm.xpath(".//kml:coordinates/text()", namespaces=ns)
            if coords:
                parts = coords[0].strip().split(',')
                if len(parts) >= 2:
                    data.append({
                        "الاسم": full_name,
                        "الطول": height_val,
                        "lat": float(parts[1]),
                        "lon": float(parts[0]),
                        "r": rgb[0],
                        "g": rgb[1],
                        "b": rgb[2]
                    })

        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"حدث خطأ: {e}")
        return None

if uploaded_file:
    df = process_kmz(uploaded_file)
    
    if df is not None and not df.empty:
        # 1. عرض الإحصائيات
        st.subheader("📊 ملخص البيانات")
        st.write(f"إجمالي عدد الأعمدة المكتشفة: **{len(df)}**")
        
        # 2. الخريطة
        st.subheader("📍 خريطة توزيع الأعمدة")
        layer = pdk.Layer(
            "ScatterplotLayer",
            df,
            get_position='[lon, lat]',
            get_color='[r, g, b, 200]',
            get_radius=12,
            pickable=True,
        )
        view_state = pdk.ViewState(latitude=df['lat'].mean(), longitude=df['lon'].mean(), zoom=14)
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, 
                                 tooltip={"text": "الاسم: {الاسم}\nالطول: {الطول}م"}))
        st.markdown("🔴 12م | 🟢 10م | 🔵 9م | 🟠 8م | 🟣 6م | ⚪ غير مسجل")

        # 3. جدول البيانات
        st.subheader("📄 معاينة البيانات")
        st.dataframe(df[['الاسم', 'الطول', 'lat', 'lon']], use_container_width=True)

        # 4. خانة تحميل الملف (Excel)
        st.divider()
        st.subheader("📥 تحميل النتائج")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df[['الاسم', 'الطول', 'lat', 'lon']].to_excel(writer, index=False, sheet_name='Lighting_Report')
            workbook = writer.book
            worksheet = writer.sheets['Lighting_Report']
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
            
            for i, col in enumerate(['الاسم', 'الطول', 'lat', 'lon']):
                worksheet.set_column(i, i, 20)
                worksheet.write(0, i, col, header_fmt)

        st.download_button(
            label="📥 اضغط هنا لتحميل ملف Excel",
            data=output.getvalue(),
            file_name="Lighting_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
