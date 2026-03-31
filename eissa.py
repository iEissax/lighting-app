import streamlit as st
import simplekml
import xml.etree.ElementTree as ET
import zipfile
import re
import math

st.set_page_config(page_title="مخطط شبكة إنارة نمار", layout="centered")

st.title("⚡ مخطط الشبكة الهندسية المتكامل")
st.write("هذا النظام يربط الأعمدة كشبكة مربعات منظمة لتناسب شوارع نمار.")

# سلايدر للتحكم في طول الخط (المسافة بين الأعمدة)
# إذا كانت الخطوط تقفز بين الشوارع، صغر هذه القيمة
max_dist = st.slider("مدى التوصيل (الحساسية):", 0.0001, 0.0010, 0.0004, format="%.4f")

uploaded_file = st.file_uploader("ارفع ملف KMZ أو KML", type=['kmz', 'kml'])

def get_distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

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
            new_kml = simplekml.Kml()
            
            # منع تكرار رسم الخطوط بين نفس النقطتين
            connections = set()
            
            for i in range(len(points)):
                p1 = points[i]
                # قائمة بالجيران القريبين
                potential_neighbors = []
                for j in range(len(points)):
                    if i == j: continue
                    p2 = points[j]
                    dist = get_distance(p1, p2)
                    if dist < max_dist:
                        potential_neighbors.append((dist, j))
                
                # ترتيب الجيران من الأقرب للأبعد
                potential_neighbors.sort()
                
                # توصيل العمود بأقرب جارين له فقط لضمان شكل الشبكة (طول وعرض)
                for d, neighbor_idx in potential_neighbors[:2]:
                    conn_id = tuple(sorted((i, neighbor_idx)))
                    if conn_id not in connections:
                        line = new_kml.newlinestring(name="مسار إنارة")
                        line.coords = [p1, points[neighbor_idx]]
                        line.style.linestyle.width = 5
                        line.style.linestyle.color = simplekml.Color.orange
                        connections.add(conn_id)

            # إضافة الأعمدة كعلامات في الملف الجديد
            for p in points:
                new_kml.newpoint(name="", coords=[p])

            output_kml = new_kml.kml()
            st.success(f"✅ تم رسم الشبكة الهندسية بنجاح لـ {len(points)} عمود!")
            
            st.download_button(
                label="تحميل المخطط الشبكي 📥",
                data=output_kml,
                file_name="Grid_Final_Layout.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
    except Exception as e:
        st.error(f"خطأ تقني: {e}")
