st.set_page_config(page_title="مستخرج بيانات شبكة الإنارة - متعدد", layout="centered")
st.title("📂 مستخرج بيانات KMZ (متعدد الملفات)")

# تعديل هنا: إضافة accept_multiple_files=True
# تحميل الملفات
uploaded_files = st.file_uploader("اختر ملفات KMZ", type=['kmz'], accept_multiple_files=True)

def process_kmz(file):
@@ -34,7 +34,8 @@ def process_kmz(file):
        desc = pm.xpath("./kml:description/text()", namespaces=ns)
        desc_text = desc[0] if desc else ""
        ext_vals = " ".join(pm.xpath(".//kml:Data/kml:value/text()", namespaces=ns))
        search_area = (desc_text + " " + ext_vals).strip()
        # البحث في الاسم والوصف والبيانات الإضافية
        search_area = (full_name + " " + desc_text + " " + ext_vals).strip()

        # استخراج اسم الشارع
        street_match = re.search(r'(?:شارع|Street)\s+([^,\n0-9]+)', search_area)
@@ -54,12 +55,18 @@ def process_kmz(file):

        # منطق "هاي ماست"
        is_highmast = any(kw in search_area.lower() for kw in ["هاي ماست", "هايماست", "highmast", "high mast"])
        
        # --- التعديل هنا: منطق التعرف على "جداري" ---
        is_wall = any(kw in search_area.lower() for kw in ["جداري", "wall", "جدار"])

        # طول العمود
        # تحديد طول العمود
        if is_highmast:
            val_height = "هاي ماست"
        elif is_wall:
            val_height = "جداري"
        else:
            height_match = re.search(r'(12|10|9|8|6)\s*(?:m|م|(?=\s|$))', search_area)
            # البحث عن الأرقام المعروفة للأطوال
            height_match = re.search(r'\b(12|10|9|8|6)\b\s*(?:m|م|(?=\s|$))', search_area)
            val_height = height_match.group(1) if height_match else ""

        # عدد الشمعات (الذراع)
@@ -98,21 +105,17 @@ def process_kmz(file):
if uploaded_files:
    all_dataframes = []

    # معالجة كل ملف مرفوع
    for uploaded_file in uploaded_files:
        df_single = process_kmz(uploaded_file)
        all_dataframes.append(df_single)

    # دمج جميع الجداول في جدول واحد
    result_df = pd.concat(all_dataframes, ignore_index=True)
    
    # ترتيب البيانات النهائية
    result_df = result_df.sort_values(by=['المحطة', 'رقم الفيدر', 'رقم العمود'])

    st.write(f"### تم دمج {len(uploaded_files)} ملفات. معاينة البيانات:")
    st.dataframe(result_df.drop(columns=['ملاحظة_داخلية']))

    # كود التنسيق والإكسيل (نفس منطقك السابق)
    # حساب التكرارات للتمييز اللوني
    dup_coords = result_df.duplicated(subset=['الاحداثيات x', 'الاحداثيات y'], keep=False)
    dup_columns = result_df.duplicated(subset=['المحطة', 'رقم الفيدر', 'رقم العمود'], keep=False)
    is_duplicated_any = dup_coords | dup_columns
@@ -126,7 +129,7 @@ def process_kmz(file):
        worksheet = writer.sheets['Sheet1']
        worksheet.right_to_left()

        # تعريف التنسيقات
        # تنسيقات الإكسيل
        num_fmt = workbook.add_format({'num_format': '0.00000', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#A6A6A6', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
