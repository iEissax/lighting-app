import streamlit as st
import simplekml
import xml.etree.ElementTree as ET
import io
import re

st.set_page_config(page_title="مخطط مسارات الإنارة", layout="centered")

st.title("⚡ مخطط مسارات الإنارة التلقائي")
st.write("ارفع ملف KML المصدر من Map Marker لرسم الخطوط تلقائياً.")

uploaded_file = st.file_uploader("اختر ملف KML", type=['kml'])

if uploaded_file is not None:
    try:
        # قراءة محتوى الملف كنص
        kml_bytes = uploaded_file.read()
        kml_text = kml_bytes.decode("utf-8")
        
        # تنظيف النص من الـ Namespaces لسهولة البحث عن الإحداثيات
        clean_xml = re.sub(r'\sxmlns="[^"]+"', '', kml_text)
        root = ET.fromstring(clean_xml)
        
        points = []

        # البحث عن كل وسوم الإحداثيات في الملف
        for coord_tag in root.iter('coordinates'):
            coords_text = coord_tag.text.strip()
            if coords_text:
                # تقسيم النص (قد يحتوي الملف على أكثر من نقطة في الوسم الواحد)
                for part in coords_text.split():
                    c = part.split(',')
                    if len(c) >= 2:
                        # إضافة خط الطول (Longitude) ثم خط العرض (Latitude)
                        points.append((float(c[0]), float(c[1])))

        if len(points) > 1:
            # إنشاء ملف KML جديد يحتوي على الخط الواصل
            new_kml = simplekml.Kml()
            line = new_kml.newlinestring(name="مسار الإنارة المنفذ")
            line.coords = points
            line.style.linestyle.width = 5
            line.style.linestyle.color = simplekml.Color.orange # لون برتقالي واضح
            
            output_kml = new_kml.kml()
            
            st.success(f"✅ تم العثور على {len(points)} عمود بنجاح!")
            
            # زر التحميل
            st.download_button(
                label="تحميل ملف المسارات الجديد 📥",
                data=output_kml,
                file_name="Lighting_Path_Result.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
        else:
            st.warning("الملف لا يحتوي على نقاط كافية لإنشاء مسار (تحتاج نقطتين على الأقل).")
            
    except Exception as e:
        st.error(f"حدث خطأ في معالجة الملف: {e}")
