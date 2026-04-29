import re
import time
import tempfile
from datetime import datetime
from typing import Any, Callable, Tuple

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


# =========================================================
# KONFIGURASI DASAR
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

EXPECTED_HEADERS = [
    "Timestamp",
    "Email Address",
    "Regional Corpu",
    "Batch",
    "Nama Lengkap",
    "Personal Number",
    "Unit Kerja",
    "Link Tanda Tangan",
    "File ID Tanda Tangan",
    "Nama File TTD",
    "PNG Transparan",
    "Alat Bantu Pendeteksi Keaslian Uang",
    "Alat Bantu Pendeteksi Keaslian Uang - Lainnya",
    "Mesin Hitung Uang",
    "Mesin Hitung Uang - Lainnya",
    "Komputer dan Printer",
    "Komputer dan Printer - Lainnya",
    "Status Submit",
]

REGIONAL_CORPU_OPTIONS = [
    "Pilih Regional Corpu",
    "RC Medan",
    "RC Padang",
    "RC Palembang",
    "RC Jakarta 1",
    "RC Jakarta 2",
    "RC Bandung",
    "RC Semarang",
    "RC Yogyakarta",
    "RC Surabaya",
    "RC Malang",
    "RC Denpasar",
    "RC Makassar",
    "RC Manado",
    "RC Banjarmasin",
]

BATCH_OPTIONS = [
    "Pilih Batch",
    "Batch 1",
    "Batch 2",
    "Batch 3",
    "Batch 4",
    "Batch 5",
]

ALAT_PENDETEKSI_OPTIONS = [
    "Pilih Merek",
    "Glory",
    "Dynamic",
    "Secure",
    "Krisbow",
    "Lainnya",
]

MESIN_HITUNG_OPTIONS = [
    "Pilih Merek",
    "Glory",
    "NCL",
    "Dynamic",
    "Krisbow",
    "Lainnya",
]

KOMPUTER_PRINTER_OPTIONS = [
    "Pilih Merek",
    "HP",
    "Epson",
    "Canon",
    "Lenovo",
    "Acer",
    "Asus",
    "Lainnya",
]


# =========================================================
# HELPER
# =========================================================

def get_secret_value(key: str, default: Any = None) -> Any:
    try:
        return st.secrets[key]
    except Exception:
        return default


def sanitize_text(text: str, max_len: int = 100) -> str:
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:max_len]


def sanitize_filename(text: str, max_len: int = 80) -> str:
    text = str(text or "").strip().lower()
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_len] or "unknown"


def validate_email(email: str) -> bool:
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    return bool(re.match(pattern, email or ""))


def retry_api_call(func: Callable, max_attempts: int = 5, base_delay: float = 1.0):
    last_error = None

    for attempt in range(max_attempts):
        try:
            return func()
        except HttpError as e:
            last_error = e
            status = getattr(e.resp, "status", None)

            if status in [403, 429, 500, 502, 503, 504]:
                time.sleep(base_delay * (2 ** attempt))
                continue

            raise
        except Exception as e:
            last_error = e
            time.sleep(base_delay * (2 ** attempt))

    raise last_error


@st.cache_resource(show_spinner=False)
def connect_google_services():
    required = [
        "SPREADSHEET_ID",
        "WORKSHEET_NAME",
        "DRIVE_FOLDER_ID",
        "gcp_service_account",
    ]

    missing = [key for key in required if key not in st.secrets]

    if missing:
        raise RuntimeError(f"Secrets belum lengkap: {', '.join(missing)}")

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )

    gc = gspread.authorize(creds)

    spreadsheet = gc.open_by_key(st.secrets["SPREADSHEET_ID"])
    worksheet = spreadsheet.worksheet(st.secrets["WORKSHEET_NAME"])

    drive_service = build(
        "drive",
        "v3",
        credentials=creds,
        cache_discovery=False,
    )

    return worksheet, drive_service


def setup_headers_if_empty(worksheet) -> None:
    values = worksheet.get_all_values()

    if not values:
        worksheet.append_row(EXPECTED_HEADERS)
        return

    first_row = values[0]

    if first_row[: len(EXPECTED_HEADERS)] != EXPECTED_HEADERS:
        st.warning(
            "Header Google Sheets berbeda dari template. "
            "Pastikan urutan kolom sudah sesuai."
        )


def personal_number_exists(worksheet, personal_number: str) -> bool:
    records = worksheet.get_all_records()
    pn_target = str(personal_number).strip().lower()

    for row in records:
        if str(row.get("Personal Number", "")).strip().lower() == pn_target:
            return True

    return False


def validate_png(uploaded_file, max_file_mb: int) -> Tuple[bool, str]:
    if uploaded_file is None:
        return False, "Tanda tangan wajib diupload."

    file_name = uploaded_file.name.lower()

    if not file_name.endswith(".png"):
        return False, "File ditolak. Tanda tangan wajib menggunakan format PNG."

    if uploaded_file.type not in ["image/png", "application/octet-stream"]:
        return False, "File ditolak. Sistem tidak mendeteksi file sebagai PNG valid."

    file_bytes = uploaded_file.getvalue()

    size_mb = len(file_bytes) / (1024 * 1024)

    if size_mb > max_file_mb:
        return False, f"File terlalu besar. Maksimal {max_file_mb} MB."

    png_signature = b"\x89PNG\r\n\x1a\n"

    if not file_bytes.startswith(png_signature):
        return False, "File ditolak. File bukan PNG asli atau hanya diganti ekstensinya."

    return True, "File PNG valid."


def upload_file_to_drive(drive_service, uploaded_file, file_name: str) -> Tuple[str, str]:
    folder_id = st.secrets["DRIVE_FOLDER_ID"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    file_metadata = {
        "name": file_name,
        "parents": [folder_id],
        "mimeType": "image/png",
    }

    media = MediaFileUpload(
        tmp_path,
        mimetype="image/png",
        resumable=True,
    )

    created = retry_api_call(
        lambda: drive_service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    file_id = created["id"]

    retry_api_call(
        lambda: drive_service.permissions()
        .create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        )
        .execute()
    )

    file_info = retry_api_call(
        lambda: drive_service.files()
        .get(
            fileId=file_id,
            fields="id, webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    return file_info["id"], file_info["webViewLink"]


def validate_required_fields(**fields):
    for label, value in fields.items():
        if not str(value or "").strip():
            st.error(f"{label} wajib diisi.")
            st.stop()


def validate_dropdown(label: str, value: str):
    if value.startswith("Pilih"):
        st.error(f"{label} wajib dipilih.")
        st.stop()


def validate_lainnya(label: str, pilihan: str, value_lainnya: str):
    if pilihan == "Lainnya" and not str(value_lainnya or "").strip():
        st.error(f"Kolom lainnya untuk {label} wajib diisi karena memilih 'Lainnya'.")
        st.stop()


# =========================================================
# UI
# =========================================================

st.set_page_config(
    page_title="Form Pengumpulan Data Peserta",
    page_icon="📝",
    layout="centered",
)

st.title("Form Pengumpulan Data Peserta")
st.caption("Tanda tangan wajib menggunakan format PNG. File selain PNG akan ditolak otomatis.")

with st.expander("Ketentuan Upload Tanda Tangan", expanded=True):
    st.markdown(
        """
        - File tanda tangan wajib berformat **PNG**.
        - Ukuran file maksimal mengikuti konfigurasi admin.
        - File JPG/JPEG/PDF/HEIC atau file yang hanya diganti ekstensi menjadi `.png` akan ditolak.
        - Disarankan menggunakan PNG dengan background transparan.
        """
    )

max_file_mb = int(get_secret_value("MAX_FILE_MB", 5))

with st.form("form_peserta", clear_on_submit=False):
    email = st.text_input("Email Address *")

    regional_corpu = st.selectbox(
        "Regional Corpu *",
        REGIONAL_CORPU_OPTIONS,
    )

    batch = st.selectbox(
        "Batch *",
        BATCH_OPTIONS,
    )

    nama_lengkap = st.text_input("Nama Lengkap *")
    personal_number = st.text_input("Personal Number *")
    unit_kerja = st.text_input("Unit Kerja *")

    tanda_tangan = st.file_uploader(
        "Tanda Tangan *",
        type=["png"],
        accept_multiple_files=False,
        help=f"Upload hanya file PNG. Maksimal {max_file_mb} MB.",
    )

    alat_pendeteksi = st.selectbox(
        "Alat Bantu Pendeteksi Keaslian Uang *",
        ALAT_PENDETEKSI_OPTIONS,
    )

    alat_pendeteksi_lainnya = ""

    if alat_pendeteksi == "Lainnya":
        alat_pendeteksi_lainnya = st.text_input(
            "Jika merek Alat Bantu Pendeteksi Keaslian Uang tidak ada, tulis di sini *"
        )

    mesin_hitung = st.selectbox(
        "Mesin Hitung Uang *",
        MESIN_HITUNG_OPTIONS,
    )

    mesin_hitung_lainnya = ""

    if mesin_hitung == "Lainnya":
        mesin_hitung_lainnya = st.text_input(
            "Jika merek Mesin Hitung Uang tidak ada, tulis di sini *"
        )

    komputer_printer = st.selectbox(
        "Komputer dan Printer *",
        KOMPUTER_PRINTER_OPTIONS,
    )

    komputer_printer_lainnya = ""

    if komputer_printer == "Lainnya":
        komputer_printer_lainnya = st.text_input(
            "Jika merek Komputer dan Printer tidak ada, tulis di sini *"
        )

    submitted = st.form_submit_button("Submit Data")


if tanda_tangan is not None:
    valid_png, png_message = validate_png(
        tanda_tangan,
        max_file_mb=max_file_mb,
    )

    if valid_png:
        st.success(png_message)
        st.info("File berhasil divalidasi sebagai PNG.")
    else:
        st.error(png_message)


if submitted:
    email = sanitize_text(email, 150)
    regional_corpu = sanitize_text(regional_corpu)
    batch = sanitize_text(batch)
    nama_lengkap = sanitize_text(nama_lengkap, 150)
    personal_number = sanitize_text(personal_number, 50)
    unit_kerja = sanitize_text(unit_kerja, 200)

    alat_pendeteksi_lainnya = sanitize_text(alat_pendeteksi_lainnya, 150)
    mesin_hitung_lainnya = sanitize_text(mesin_hitung_lainnya, 150)
    komputer_printer_lainnya = sanitize_text(komputer_printer_lainnya, 150)

    validate_required_fields(
        **{
            "Email Address": email,
            "Nama Lengkap": nama_lengkap,
            "Personal Number": personal_number,
            "Unit Kerja": unit_kerja,
        }
    )

    if not validate_email(email):
        st.error("Format Email Address tidak valid.")
        st.stop()

    validate_dropdown("Regional Corpu", regional_corpu)
    validate_dropdown("Batch", batch)
    validate_dropdown("Alat Bantu Pendeteksi Keaslian Uang", alat_pendeteksi)
    validate_dropdown("Mesin Hitung Uang", mesin_hitung)
    validate_dropdown("Komputer dan Printer", komputer_printer)

    validate_lainnya(
        "Alat Bantu Pendeteksi Keaslian Uang",
        alat_pendeteksi,
        alat_pendeteksi_lainnya,
    )

    validate_lainnya(
        "Mesin Hitung Uang",
        mesin_hitung,
        mesin_hitung_lainnya,
    )

    validate_lainnya(
        "Komputer dan Printer",
        komputer_printer,
        komputer_printer_lainnya,
    )

    valid_png, png_message = validate_png(
        tanda_tangan,
        max_file_mb=max_file_mb,
    )

    if not valid_png:
        st.error(png_message)
        st.stop()

    with st.spinner("Menyimpan data..."):
        try:
            worksheet, drive_service = connect_google_services()
            setup_headers_if_empty(worksheet)

            if retry_api_call(lambda: personal_number_exists(worksheet, personal_number)):
                st.error(
                    "Personal Number sudah pernah submit. "
                    "Silakan hubungi admin jika perlu perbaikan data."
                )
                st.stop()

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            safe_pn = sanitize_filename(personal_number)
            safe_name = sanitize_filename(nama_lengkap)

            file_name = (
                f"TTD_{safe_pn}_{safe_name}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )

            file_id, drive_link = upload_file_to_drive(
                drive_service,
                tanda_tangan,
                file_name,
            )

            png_transparan = "Tidak dicek"

            row_data = [
                timestamp,
                email,
                regional_corpu,
                batch,
                nama_lengkap,
                personal_number,
                unit_kerja,
                drive_link,
                file_id,
                file_name,
                png_transparan,
                alat_pendeteksi,
                alat_pendeteksi_lainnya,
                mesin_hitung,
                mesin_hitung_lainnya,
                komputer_printer,
                komputer_printer_lainnya,
                "Berhasil",
            ]

            retry_api_call(
                lambda: worksheet.append_row(
                    row_data,
                    value_input_option="USER_ENTERED",
                )
            )

            st.success("Data berhasil dikirim.")
            st.write("Link Tanda Tangan:", drive_link)

        except Exception as e:
            st.error(
                "Terjadi kendala saat menyimpan data. "
                "Silakan coba kembali atau hubungi admin."
            )
            st.code(str(e))


# =========================================================
# ADMIN PREVIEW OPSIONAL
# =========================================================

with st.expander("Admin: Cek koneksi dan preview data", expanded=False):
    admin_password = st.text_input("Password Admin", type="password")
    configured_password = get_secret_value("ADMIN_PASSWORD", "")

    if st.button("Tampilkan Preview"):
        if configured_password and admin_password != configured_password:
            st.error("Password admin salah.")
        else:
            try:
                worksheet, _ = connect_google_services()
                values = worksheet.get_all_values()

                if len(values) <= 1:
                    st.info("Belum ada data submit.")
                else:
                    df = pd.DataFrame(values[1:], columns=values[0])
                    st.dataframe(df.tail(20), use_container_width=True)
                    st.caption(f"Total data: {len(df)}")

            except Exception as e:
                st.error("Gagal membaca Google Sheets.")
                st.code(str(e))
