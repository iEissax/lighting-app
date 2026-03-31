import streamlit as st
import simplekml
from fastkml import kml
import io

st.set_page_config(page_title="مخطط مسارات الإنارة", layout="centered")

st.title("⚡ مخطط مسارات الإنارة التلقائي")
st.write("ارفع ملف KML المصدر من Map Marker لرسم الخطوط تلقائياً.")

uploaded_file = st.file_uploader("اختر ملف KML", type=['kml'])

if uploaded_file is not None:
    try:
        # قراءة محتوى الملف
        kml_content = uploaded_file.read()
        k_obj = kml.KML()
        k_obj.from_string(kml_content)
        
        points = []

        # دالة للبحث عن الإحداثيات داخل أي بنية للملف (Recursive Search)
        def get_points(features):
            for feature in features:
                if hasattr(feature, 'geometry') and feature.geometry is not None:
                    if feature.geometry.geom_type == 'Point':
                        points.append((feature.geometry.x, feature.geometry.y))
                if hasattr(feature, 'features'):  # إذا كان مجلد أو وثيقة، ابحث داخلها
                    get_points(feature.features())

        # بدء البحث عن النقاط
        get_points(list(k_obj.features()))

        if len(points) > 1:
            # إنشاء KML جديد للخطوط
            new_kml = simplekml.Kml()
            line = new_kml.newlinestring(name="مسار الإنارة المنفذ")
            line.coords = points
            line.style.linestyle.width = 5
            line.style.linestyle.color = simplekml.Color.orange
            
            output_kml = new_kml.kml()
            
            st.success(f"✅ تم العثور على {len(points)} عمود وتوصيلهم بنجاح!")
            
            st.download_button(
                label="تحميل ملف المسارات الجديد 📥",
                data=output_kml,
                file_name="Lighting_Path_Result.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
        else:
            st.warning("الملف لا يحتوي على نقاط كافية (تحتاج نقطتين على الأقل لرسم خط).")
            
    except Exception as e:
        st.error(f"حدث خطأ أثناء قراءة الملف: {e}")
