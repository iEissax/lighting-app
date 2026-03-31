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

        # دالة للبحث عن الإحداثيات بطريقة آمنة
        def get_points(feature_list):
            for feature in feature_list:
                # التحقق من وجود هندسة (نقطة)
                if hasattr(feature, 'geometry') and feature.geometry is not None:
                    if feature.geometry.geom_type == 'Point':
                        points.append((feature.geometry.x, feature.geometry.y))
                
                # البحث في العناصر الفرعية (مجلدات أو وثائق)
                if hasattr(feature, 'features'):
                    # هنا حل المشكلة: التأكد هل هي دالة أم قائمة
                    sub_features = feature.features
                    if callable(sub_features):
                        get_points(list(sub_features()))
                    else:
                        get_points(list(sub_features))

        # بدء البحث عن النقاط من جذر الملف
        get_points(list(k_obj.features()))

        if len(points) > 1:
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
            st.warning("الملف لا يحتوي على نقاط كافية لإنشاء مسار.")
            
    except Exception as e:
        st.error(f"حدث خطأ أثناء قراءة الملف: {e}")
