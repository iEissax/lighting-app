import streamlit as st
import pandas as pd
import io

# إعدادات الصفحة
st.set_page_config(page_title="مدير ملفات KMZ و Excel", layout="wide")

st.title("📂 نظام إدارة الخرائط والبيانات المنفصلة")
st.info("ارفع ملف KMZ وملف Excel الخاص به، وسيتم عزلهما في طبقة مستقلة.")

# 1. تهيئة مخزن البيانات في الحالة (Session State)
if 'projects_list' not in st.session_state:
    st.session_state.projects_list = []

# --- منطقة التحكم (Side Bar) ---
with st.sidebar:
    st.header("➕ إضافة مشروع جديد")
    project_name = st.text_input("اسم المشروع/الطبقة", placeholder="مثلاً: المنطقة الشمالية")
    uploaded_kmz = st.file_uploader("ارفع ملف KMZ", type=['kmz'])
    uploaded_excel = st.file_uploader("ارفع ملف Excel", type=['xlsx', 'xls'])
    
    if st.button("إضافة وتثبيت"):
        if project_name and uploaded_kmz and uploaded_excel:
            # تخزين البيانات في قاموس معزول تماماً
            new_entry = {
                "id": len(st.session_state.projects_list) + 1,
                "name": project_name,
                "kmz_filename": uploaded_kmz.name,
                "excel_data": pd.read_excel(uploaded_excel)
            }
            st.session_state.projects_list.append(new_entry)
            st.success(f"تمت إضافة {project_name} بنجاح!")
        else:
            st.error("يرجى إكمال جميع الحقول والملفات.")

# --- منطقة العرض الرئيسية ---
if not st.session_state.projects_list:
    st.warning("لا توجد مشاريع مضافة حالياً. استخدم القائمة الجانبية للبدء.")
else:
    # عرض ملخص المشاريع المضافة
    st.subheader(f"🗂️ الطبقات الحالية ({len(st.session_state.projects_list)})")
    
    for project in st.session_state.projects_list:
        with st.expander
