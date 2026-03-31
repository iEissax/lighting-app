import streamlit as st
import simplekml
from fastkml import kml
from shapely.geometry import Point
import io

st.set_page_config(page_title="مخطط مسارات الإنارة", layout="centered")

st.title("⚡ مخطط مسارات الإنارة التلقائي")
st.write("ارفع ملف الـ KML الخاص بالأعمدة ليتم رسم الخطوط بينها فوراً.")

# رفع الملف
uploaded_file = st.file_uploader("اختر ملف KML المصدر من Map Marker", type=['kml'])

if uploaded_file is not None:
    # قراءة الملف المرفوع
    kml_content = uploaded_file.read()
    k = kml.KML()
    k.from_string(kml_content)
    
    points = []
    
    # استخراج الإحداثيات من الماركرز (Markers)
    for feature in list(k.features()):
        if hasattr(feature, 'features'):
            for sub_feature in list(feature.features()):
                if hasattr(sub_feature, 'geometry') and isinstance(sub_feature.geometry, Point):
                    # حفظ الإحداثيات (خط الطول، خط العرض)
                    points.append((sub_feature.geometry.x, sub_feature.geometry.y))

    if len(points) > 1:
        # إنشاء ملف KML جديد يحتوي على الخطوط
        new_kml = simplekml.Kml()
        line = new_kml.newlinestring(name="مسار الشارع المنفذ")
        line.coords = points
        line.style.linestyle.width = 5
        line.style.linestyle.color = simplekml.Color.orange # لون برتقالي واضح
        
        # تحويل الملف الجديد إلى "Bytes" للتحميل
        output_kml = new_kml.kml()
        
        st.success(f"✅ تم معالجة {len(points)} عمود بنجاح!")
        
        # زر التحميل
        st.download_button(
            label="تحميل ملف المسارات الجديد 📥",
            data=output_kml,
            file_name="Lighting_Path_Result.kml",
            mime="application/vnd.google-earth.kml+xml"
        )
    else:
        st.error("الملف لا يحتوي على نقاط كافية لإنشاء مسار.")
