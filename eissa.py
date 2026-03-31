import streamlit as st
import simplekml
import xml.etree.ElementTree as ET
import zipfile
import re

st.set_page_config(page_title="مخطط إنارة نمار المتطور", layout="centered")

st.title("⚡ مخطط مسارات الإنارة المنظم")
st.write("اختر طريقة التوصيل لتناسب اتجاه الشوارع في الخريطة.")

# إضافة خيار للمستخدم لتحديد اتجاه التوصيل
direction = st.radio(
    "اتجاه توصيل الخطوط:",
    ('أفقي (شرق - غرب)', 'عمودي (شمال - جنوب)')
)

uploaded_file = st.file_uploader("ارفع ملف KMZ أو KML", type=['kmz', 'kml'])

if uploaded_file is not None:
    try:
        kml_text = ""
        if uploaded_file.name.endswith('.kmz'):
            with zipfile.ZipFile(uploaded_file) as z:
                kml_filename = [f for f in z.namelist() if f.endswith('.kml')][0]
                with z.open(kml_filename) as f:
                    kml_text = f.read().decode("utf-8")
        else:
            kml_text = uploaded_file.read().decode("utf-8")
        
        clean_xml = re.sub(r'\sxmlns="[^"]+"', '', kml_text)
        root = ET.fromstring(clean_xml)
        
        points = []
        for coord_tag in root.iter('coordinates'):
            coords_text = coord_tag.text.strip()
            if coords_text:
                for part in coords_text.split():
                    c = part.split(',')
                    if len(c) >= 2:
                        points.append((float(c[0]), float(c[1])))

        if len(points) > 1:
            # الترتيب حسب اختيار المستخدم
            if direction == 'أفقي (شرق - غرب)':
                # يرتب حسب خط الطول (X) أولاً ثم خط العرض (Y)
                points.sort(key=lambda p: (p[0], p[1]))
            else:
                # يرتب حسب خط العرض (Y) أولاً ثم خط الطول (X)
                points.sort(key=lambda p: (p[1], p[0]))
            
            new_kml = simplekml.Kml()
            # رسم الخط المنظم
            line = new_kml.newlinestring(name=f"مسار {direction}")
            line.coords = points
            line.style.linestyle.width = 6
            line.style.linestyle.color = simplekml.Color.orange
            
            # إضافة الأعمدة
            for i, p in enumerate(points):
                new_kml.newpoint(name=f"عمود {i+1}", coords=[p])

            output_kml = new_kml.kml()
            st.success(f"✅ تم تنظيم {len(points)} عمود بنجاح!")
            
            st.download_button(
                label="تحميل الملف المنظم 📥",
                data=output_kml,
                file_name="Organized_Lighting_Map.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
        else:
            st.warning("لا توجد نقاط كافية.")
            
    except Exception as e:
        st.error(f"خطأ: {e}")
