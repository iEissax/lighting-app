import streamlit as st
import simplekml
import xml.etree.ElementTree as ET
import io
import re
import zipfile

st.set_page_config(page_title="مخطط مسارات الإنارة - KMZ", layout="centered")

st.title("⚡ مخطط مسارات الإنارة (يدعم KMZ و KML)")
st.write("ارفع ملف KMZ أو KML المصدر من Map Marker لرسم الخطوط.")

uploaded_file = st.file_uploader("اختر ملف الخريطة", type=['kmz', 'kml'])

if uploaded_file is not None:
    try:
        kml_text = ""
        
        # إذا كان الملف KMZ (ملف مضغوط)
        if uploaded_file.name.endswith('.kmz'):
            with zipfile.ZipFile(uploaded_file) as z:
                # البحث عن ملف doc.kml داخل الملف المضغوط
                kml_filename = [f for f in z.namelist() if f.endswith('.kml')][0]
                with z.open(kml_filename) as f:
                    kml_text = f.read().decode("utf-8")
        else:
            # إذا كان ملف KML عادي
            kml_text = uploaded_file.read().decode("utf-8")
        
        # تنظيف النص من الـ Namespaces
        clean_xml = re.sub(r'\sxmlns="[^"]+"', '', kml_text)
        root = ET.fromstring(clean_xml)
        
        points = []

        # البحث عن الإحداثيات
        for coord_tag in root.iter('coordinates'):
            coords_text = coord_tag.text.strip()
            if coords_text:
                for part in coords_text.split():
                    c = part.split(',')
                    if len(c) >= 2:
                        # الترتيب الصحيح لـ Map Marker (Longitude, Latitude)
                        points.append((float(c[0]), float(c[1])))

        if len(points) > 1:
            new_kml = simplekml.Kml()
            # إضافة الخط
            line = new_kml.newlinestring(name="مسار الإنارة المخطط")
            line.coords = points
            line.style.linestyle.width = 6
            line.style.linestyle.color = simplekml.Color.orange
            
            # إضافة النقاط الأصلية (الأعمدة) للملف الجديد لضمان ظهورها مع الخط
            for p in points:
                new_kml.newpoint(name="عمود إنارة", coords=[p])

            output_kml = new_kml.kml()
            
            st.success(f"✅ تم استخراج {len(points)} عمود من ملف KMZ وتوصيلهم!")
            
            st.download_button(
                label="تحميل ملف المسارات المحدث 📥",
                data=output_kml,
                file_name="Lighting_Final_Map.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
        else:
            st.warning("لم يتم العثور على نقاط كافية داخل ملف KMZ.")
            
    except Exception as e:
        st.error(f"حدث خطأ في معالجة ملف KMZ: {e}")
