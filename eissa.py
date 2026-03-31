import streamlit as st
import simplekml
import xml.etree.ElementTree as ET
import zipfile
import re
import math

st.set_page_config(page_title="مخطط إنارة نمار المتكامل", layout="centered")

st.title("⚡ مخطط الشبكة الكاملة (كل الاتجاهات)")
st.write("هذا النظام يوصل الأعمدة القريبة من بعضها فقط لمنع تداخل الشوارع.")

# التحكم في "حساسية" التوصيل
max_dist = st.slider("دقة المسافة بين الأعمدة:", 0.0001, 0.0010, 0.0004, format="%.4f")
st.info("نصيحة: إذا رأيت خطوطاً تقفز بين شارعين متوازيين، صغر هذه القيمة قليلاً.")

uploaded_file = st.file_uploader("ارفع ملف KMZ أو KML", type=['kmz', 'kml'])

def get_distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

if uploaded_file is not None:
    try:
        # 1. قراءة الملف
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
        
        all_points = []
        for coord_tag in root.iter('coordinates'):
            coords_text = coord_tag.text.strip()
            if coords_text:
                for part in coords_text.split():
                    c = part.split(',')
                    if len(c) >= 2:
                        all_points.append((float(c[0]), float(c[1])))

        if len(all_points) > 1:
            new_kml = simplekml.Kml()
            
            # 2. خوارزمية التوصيل الذكي (Nearest Neighbor Groups)
            unvisited = all_points.copy()
            while unvisited:
                current_p = unvisited.pop(0)
                segment = [current_p]
                
                found_next = True
                while found_next:
                    found_next = False
                    # البحث عن أقرب نقطة للنقطة الأخيرة في الجزء الحالي
                    best_dist = max_dist
                    best_idx = -1
                    
                    for i, p in enumerate(unvisited):
                        d = get_distance(segment[-1], p)
                        if d < best_dist:
                            best_dist = d
                            best_idx = i
                    
                    if best_idx != -1:
                        segment.append(unvisited.pop(best_idx))
                        found_next = True
                
                # 3. رسم الجزء إذا كان يحتوي على أكثر من عمود
                if len(segment) > 1:
                    line = new_kml.newlinestring(name="شارع منفذ")
                    line.coords = segment
                    line.style.linestyle.width = 5
                    line.style.linestyle.color = simplekml.Color.orange
            
            # إضافة الأعمدة كعلامات
            for i, p in enumerate(all_points):
                new_kml.newpoint(name=f"عمود", coords=[p])

            output_kml = new_kml.kml()
            st.success(f"✅ تم رسم الشبكة بالكامل وتوصيل الشوارع المترابطة!")
            
            st.download_button(
                label="تحميل المخطط الشبكي الكامل 📥",
                data=output_kml,
                file_name="Full_Grid_Lighting.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
    except Exception as e:
        st.error(f"خطأ: {e}")
