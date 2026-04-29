"""
Aplikasi Form Pengumpulan Data Peserta
=====================================
Streamlit app dengan integrasi Google Sheets & Google Drive
Author: Senior Python Developer
"""

import streamlit as st
import gspread
import io
import base64
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

# ─────────────────────────────────────────────
# KONFIGURASI & KONSTANTA
# ─────────────────────────────────────────────

PAGE_TITLE = "Form Data Peserta"
PAGE_ICON = "📋"

MAX_FILE_SIZE_MB = 2
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Google API Scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Pilihan Dropdown
DROPDOWN_ALAT_BANTU = ["-- Pilih --", "Tidak Ada", "Glory", "Dynamic", "Secure", "Lainnya"]
DROPDOWN_MESIN_HITUNG = ["-- Pilih --", "Tidak Ada", "Glory", "Dynamic", "NCL", "Lainnya"]
DROPDOWN_KOMPUTER_PRINTER = ["-- Pilih --", "Tidak Ada", "PC + Printer", "Laptop + Printer", "Printer Only", "Lainnya"]

# Header kolom Google Sheets (urutan wajib sama saat append)
SHEET_HEADERS = [
    "Timestamp",
    "Email Address",
    "Regional Corpu",
    "Batch",
    "Nama Lengkap",
    "Personal Number",
    "Unit Kerja",
    "Link Tanda Tangan",
    "Alat Bantu Pendeteksi Keaslian Uang",
    "Keterangan Alat Bantu Lainnya",
    "Mesin Hitung Uang",
    "Keterangan Mesin Hitung Lainnya",
    "Komputer dan Printer",
    "Keterangan Komputer Printer Lainnya",
]


# ─────────────────────────────────────────────
# INISIALISASI GOOGLE CREDENTIALS
# ─────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_google_credentials():
    """Ambil credentials dari st.secrets dengan penanganan private_key yang robust."""
    sa = dict(st.secrets["gcp_service_account"])

    # Ambil private key dan normalisasi format apapun yang mungkin masuk
    pk = sa["private_key"]

    # Kasus 1: Windows line endings
    pk = pk.replace("\r\n", "\n")

    # Kasus 2: literal backslash-n (dari copy-paste JSON langsung ke TOML)
    if "\\n" in pk:
        pk = pk.replace("\\n", "\n")

    # Kasus 3: spasi berlebih di header/footer PEM saja (bukan di baris base64)
    lines = pk.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Hanya strip baris header/footer PEM dan baris kosong
        if stripped.startswith("-----") or stripped == "":
            cleaned.append(stripped)
        else:
            cleaned.append(line)  # baris base64: jangan diubah
    pk = "\n".join(cleaned)
    if not pk.endswith("\n"):
        pk += "\n"

    sa["private_key"] = pk
    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    return creds


def get_gspread_client(creds):
    """Buat gspread client dari credentials."""
    return gspread.authorize(creds)




# ─────────────────────────────────────────────
# UTILITAS VALIDASI FILE
# ─────────────────────────────────────────────

def validate_png_file(uploaded_file) -> tuple[bool, str]:
    """
    Validasi ketat bahwa file adalah PNG:
    1. Ekstensi harus .png
    2. MIME type harus image/png
    3. Magic bytes harus PNG
    4. Ukuran tidak boleh melebihi MAX_FILE_SIZE_BYTES

    Returns:
        (True, "") jika valid
        (False, pesan_error) jika tidak valid
    """
    if uploaded_file is None:
        return False, "File Tanda Tangan wajib diupload."

    # Cek ekstensi
    filename = uploaded_file.name.lower()
    if not filename.endswith(".png"):
        return False, f"❌ File '{uploaded_file.name}' bukan PNG. Hanya file .png yang diterima."

    # Cek MIME type yang dilaporkan browser
    if uploaded_file.type not in ("image/png", "image/x-png"):
        return False, f"❌ MIME type '{uploaded_file.type}' tidak valid. Hanya image/png yang diterima."

    # Cek ukuran file
    file_bytes = uploaded_file.getvalue()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        return False, f"❌ Ukuran file {size_mb:.2f} MB melebihi batas {MAX_FILE_SIZE_MB} MB."

    # Cek magic bytes (signature PNG: 8 byte pertama)
    png_signature = b"\x89PNG\r\n\x1a\n"
    if file_bytes[:8] != png_signature:
        return False, "❌ File bukan PNG yang valid (magic bytes tidak sesuai). Harap upload file PNG asli."

    return True, ""


# ─────────────────────────────────────────────
# UPLOAD KE CLOUDINARY
# ─────────────────────────────────────────────

def upload_to_cloudinary(file_bytes: bytes, filename: str) -> str:
    """
    Upload file PNG ke Cloudinary (production-grade image hosting).
    Free plan: 25 kredit/bulan — cukup untuk ribuan TTD.

    Returns:
        URL secure file di Cloudinary
    """
    import hashlib
    import time

    cloud_name = st.secrets["cloudinary"]["cloud_name"]
    api_key    = st.secrets["cloudinary"]["api_key"]
    api_secret = st.secrets["cloudinary"]["api_secret"]

    # Buat signature untuk authenticated upload
    timestamp  = str(int(time.time()))
    folder     = "ttd_peserta"
    public_id  = filename.replace(".png", "")

    # String yang di-sign: harus urut alphabetically
    sign_str = f"folder={folder}&public_id={public_id}&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()

    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

    response = requests.post(
        upload_url,
        data={
            "api_key":   api_key,
            "timestamp": timestamp,
            "signature": signature,
            "folder":    folder,
            "public_id": public_id,
        },
        files={"file": (filename, file_bytes, "image/png")},
        timeout=60,
    )

    if response.status_code != 200:
        raise Exception(f"Cloudinary upload gagal: {response.status_code} — {response.text}")

    result = response.json()
    if "secure_url" not in result:
        raise Exception(f"Cloudinary error: {result}")

    return result["secure_url"]


# ─────────────────────────────────────────────
# SIMPAN KE GOOGLE SHEETS
# ─────────────────────────────────────────────

def ensure_sheet_headers(worksheet):
    """
    Pastikan baris pertama sheet sudah berisi header yang benar.
    Jika sheet masih kosong, tulis header otomatis.
    """
    existing = worksheet.row_values(1)
    if existing != SHEET_HEADERS:
        worksheet.insert_row(SHEET_HEADERS, index=1)


def save_to_sheet(gc, spreadsheet_id: str, sheet_name: str, row_data: list):
    """
    Tambahkan satu baris data ke Google Sheets.
    """
    spreadsheet = gc.open_by_key(spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

    ensure_sheet_headers(worksheet)
    worksheet.append_row(row_data, value_input_option="USER_ENTERED")


# ─────────────────────────────────────────────
# VALIDASI FORM
# ─────────────────────────────────────────────

def validate_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"
    return bool(re.match(pattern, email))


def validate_form_data(data: dict, uploaded_file) -> list[str]:
    """
    Validasi semua field form.
    Returns list of error messages (kosong = valid).
    """
    errors = []

    if not data["email"] or not validate_email(data["email"]):
        errors.append("Email Address tidak valid.")

    for field_name, field_value in [
        ("Regional Corpu", data["regional_corpu"]),
        ("Batch", data["batch"]),
        ("Nama Lengkap", data["nama_lengkap"]),
        ("Personal Number", data["personal_number"]),
        ("Unit Kerja", data["unit_kerja"]),
    ]:
        if not field_value or not field_value.strip():
            errors.append(f"Field '{field_name}' wajib diisi.")

    # Validasi dropdown wajib dipilih (bukan placeholder)
    if data["alat_bantu"] == "-- Pilih --":
        errors.append("Pilih opsi untuk 'Alat Bantu Pendeteksi Keaslian Uang'.")
    if data["mesin_hitung"] == "-- Pilih --":
        errors.append("Pilih opsi untuk 'Mesin Hitung Uang'.")
    if data["komputer_printer"] == "-- Pilih --":
        errors.append("Pilih opsi untuk 'Komputer dan Printer'.")

    # Logika: jika pilih "Lainnya", field opsional wajib diisi
    if data["alat_bantu"] == "Lainnya" and not data["alat_bantu_lainnya"].strip():
        errors.append("Anda memilih 'Lainnya' untuk Alat Bantu — harap isi keterangan merek.")
    if data["mesin_hitung"] == "Lainnya" and not data["mesin_hitung_lainnya"].strip():
        errors.append("Anda memilih 'Lainnya' untuk Mesin Hitung — harap isi keterangan merek.")
    if data["komputer_printer"] == "Lainnya" and not data["komputer_printer_lainnya"].strip():
        errors.append("Anda memilih 'Lainnya' untuk Komputer dan Printer — harap isi keterangan merek.")

    # Validasi file PNG
    is_valid_png, png_error = validate_png_file(uploaded_file)
    if not is_valid_png:
        errors.append(png_error)

    return errors


# ─────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────

def setup_page():
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # Custom CSS agar lebih rapi
    st.markdown("""
    <style>
        .main { max-width: 720px; margin: auto; }
        .stAlert { border-radius: 8px; }
        .section-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #1a1a2e;
            border-left: 4px solid #4f8ef7;
            padding-left: 10px;
            margin-top: 1.5rem;
            margin-bottom: 0.5rem;
        }
        .success-box {
            background: #d4edda;
            border: 1px solid #28a745;
            border-radius: 8px;
            padding: 16px;
            color: #155724;
        }
    </style>
    """, unsafe_allow_html=True)


def render_form():
    """Render seluruh form dan kembalikan (form_data, uploaded_file, submitted)."""

    st.title(f"{PAGE_ICON} Form Data Peserta")
    st.caption("Semua field bertanda * wajib diisi. File Tanda Tangan hanya menerima format PNG (maks. 2 MB).")
    st.divider()

    with st.form(key="peserta_form", clear_on_submit=False):

        # ── SEKSI 1: Data Diri ──────────────────
        st.markdown('<p class="section-title">📌 Data Diri Peserta</p>', unsafe_allow_html=True)

        email = st.text_input("Email Address *", placeholder="nama@perusahaan.co.id")
        regional_corpu = st.text_input("Regional Corpu *", placeholder="Contoh: Regional 1 Jakarta")
        batch = st.text_input("Batch *", placeholder="Contoh: Batch 5")

        col1, col2 = st.columns(2)
        with col1:
            nama_lengkap = st.text_input("Nama Lengkap *", placeholder="Nama sesuai ID pegawai")
        with col2:
            personal_number = st.text_input("Personal Number *", placeholder="Contoh: 1234567")

        unit_kerja = st.text_input("Unit Kerja *", placeholder="Contoh: Kantor Cabang Bandung")

        # ── SEKSI 2: Tanda Tangan ───────────────
        st.markdown('<p class="section-title">✍️ Tanda Tangan Digital</p>', unsafe_allow_html=True)
        st.info("⚠️ Hanya file **PNG** yang diterima. File JPG, JPEG, PDF, atau format lain akan **ditolak**.")
        ttd_file = st.file_uploader(
            "Upload Tanda Tangan (PNG) *",
            type=None,           # Sengaja None agar kita validasi manual lebih ketat
            accept_multiple_files=False,
            help=f"Format: PNG saja | Maks: {MAX_FILE_SIZE_MB} MB",
        )

        # Realtime warning jika bukan PNG
        if ttd_file is not None and not ttd_file.name.lower().endswith(".png"):
            st.error(f"❌ File '{ttd_file.name}' bukan PNG. Ganti dengan file PNG.")

        # ── SEKSI 3: Peralatan ──────────────────
        st.markdown('<p class="section-title">🖥️ Data Peralatan</p>', unsafe_allow_html=True)

        # Alat Bantu Pendeteksi Keaslian Uang
        alat_bantu = st.selectbox("Alat Bantu Pendeteksi Keaslian Uang *", DROPDOWN_ALAT_BANTU)
        _label_ab = "Jika merek Alat Bantu tidak ada di daftar, tulis di sini *" if alat_bantu == "Lainnya" else "Jika merek Alat Bantu tidak ada di daftar, tulis di sini (opsional)"
        alat_bantu_lainnya = st.text_input(
            _label_ab,
            placeholder="Tulis merek alat bantu Anda jika tidak ada di daftar",
            key="alat_bantu_lainnya",
        )

        # Mesin Hitung Uang
        mesin_hitung = st.selectbox("Mesin Hitung Uang *", DROPDOWN_MESIN_HITUNG)
        _label_mh = "Jika merek Mesin Hitung tidak ada di daftar, tulis di sini *" if mesin_hitung == "Lainnya" else "Jika merek Mesin Hitung tidak ada di daftar, tulis di sini (opsional)"
        mesin_hitung_lainnya = st.text_input(
            _label_mh,
            placeholder="Tulis merek mesin hitung Anda jika tidak ada di daftar",
            key="mesin_hitung_lainnya",
        )

        # Komputer dan Printer
        komputer_printer = st.selectbox("Komputer dan Printer *", DROPDOWN_KOMPUTER_PRINTER)
        _label_kp = "Jika pilihan Komputer dan Printer tidak ada di daftar, tulis di sini *" if komputer_printer == "Lainnya" else "Jika pilihan Komputer dan Printer tidak ada di daftar, tulis di sini (opsional)"
        komputer_printer_lainnya = st.text_input(
            _label_kp,
            placeholder="Tulis spesifikasi Anda jika tidak ada di daftar",
            key="komputer_printer_lainnya",
        )

        st.divider()
        submitted = st.form_submit_button(
            "📤 Submit Data",
            use_container_width=True,
            type="primary",
        )

    form_data = {
        "email": email,
        "regional_corpu": regional_corpu,
        "batch": batch,
        "nama_lengkap": nama_lengkap,
        "personal_number": personal_number,
        "unit_kerja": unit_kerja,
        "alat_bantu": alat_bantu,
        "alat_bantu_lainnya": alat_bantu_lainnya,
        "mesin_hitung": mesin_hitung,
        "mesin_hitung_lainnya": mesin_hitung_lainnya,
        "komputer_printer": komputer_printer,
        "komputer_printer_lainnya": komputer_printer_lainnya,
    }

    return form_data, ttd_file, submitted


# ─────────────────────────────────────────────
# MAIN LOGIC
# ─────────────────────────────────────────────

def main():
    setup_page()

    # Inisialisasi session state untuk anti-double-submit
    if "last_submitted_pn" not in st.session_state:
        st.session_state["last_submitted_pn"] = None
    if "submit_success" not in st.session_state:
        st.session_state["submit_success"] = False

    # Tampilkan pesan sukses persisten setelah submit berhasil
    if st.session_state["submit_success"]:
        st.success("✅ Data berhasil disimpan! Terima kasih telah mengisi form.")
        st.balloons()
        if st.button("📝 Isi Form Baru"):
            st.session_state["submit_success"] = False
            st.session_state["last_submitted_pn"] = None
            st.rerun()
        return

    form_data, ttd_file, submitted = render_form()

    if not submitted:
        return

    # ── VALIDASI ────────────────────────────
    errors = validate_form_data(form_data, ttd_file)

    if errors:
        st.error("**Harap perbaiki kesalahan berikut sebelum submit:**")
        for e in errors:
            st.warning(e)
        return

    # ── ANTI DOUBLE SUBMIT ───────────────────
    current_pn = form_data["personal_number"].strip()
    if st.session_state["last_submitted_pn"] == current_pn:
        st.warning("⚠️ Data dengan Personal Number ini sudah pernah disubmit di sesi ini.")
        return

    # ── PROSES UPLOAD & SIMPAN ───────────────
    with st.spinner("Memproses data... harap tunggu ⏳"):
        try:
            creds = get_google_credentials()
            gc = get_gspread_client(creds)

            # Buat nama file TTD
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = re.sub(r"[^a-zA-Z0-9]", "_", form_data["nama_lengkap"])
            safe_pn = re.sub(r"[^a-zA-Z0-9]", "_", form_data["personal_number"])
            filename = f"TTD_{safe_pn}_{safe_name}_{timestamp_str}.png"

            # Upload ke Cloudinary
            drive_link = upload_to_cloudinary(
                ttd_file.getvalue(),
                filename,
            )

            # Simpan ke Google Sheets
            spreadsheet_id = st.secrets["google_sheets"]["spreadsheet_id"]
            sheet_name = st.secrets["google_sheets"].get("sheet_name", "Data Peserta")

            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                form_data["email"],
                form_data["regional_corpu"],
                form_data["batch"],
                form_data["nama_lengkap"],
                form_data["personal_number"],
                form_data["unit_kerja"],
                drive_link,
                form_data["alat_bantu"],
                form_data["alat_bantu_lainnya"],
                form_data["mesin_hitung"],
                form_data["mesin_hitung_lainnya"],
                form_data["komputer_printer"],
                form_data["komputer_printer_lainnya"],
            ]

            save_to_sheet(gc, spreadsheet_id, sheet_name, row)

            # Tandai sukses
            st.session_state["last_submitted_pn"] = current_pn
            st.session_state["submit_success"] = True
            st.rerun()

        except Exception as e:
            st.error(f"❌ Terjadi kesalahan saat memproses data:\n\n`{e}`")
            st.info("Coba kembali. Jika masalah berlanjut, hubungi administrator.")


if __name__ == "__main__":
    main()
