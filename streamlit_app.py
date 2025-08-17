import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
import os
import time  # Import library time

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="Pemberi Label Lirik Otomatis",
    page_icon="🎶"
)

st.title("🎶 Aplikasi Pemberi Label Lirik Otomatis")
st.markdown("Tempel baris dari file Excel atau CSV Anda untuk mendapatkan rekomendasi rating lirik secara otomatis menggunakan Gemini API.")

# Input API Key
api_key = st.text_input("Masukkan Gemini API Key Anda:", type="password")

if api_key:
    genai.configure(api_key=api_key)

# Text area untuk menempel data
pasted_data = st.text_area(
    "Tempel data (lirik dan judul lagu) di sini:",
    height=300,
    placeholder="Contoh: (Salin dari Excel, termasuk header)\nJudul\tLirik\nJudul Lagu 1\tLirik dari lagu pertama.\nJudul Lagu 2\tLirik dari lagu kedua."
)

# Prompt Template untuk Gemini
PROMPT_TEMPLATE = """
Anda adalah sistem klasifikasi musik Indonesia. Berdasarkan lirik dan judul lagu berikut, rekomendasikan rating yang paling sesuai dari kategori ini: "SU (semua umur)", "13+", "17+", atau "21+".

- **SU (semua umur)**: Cocok untuk semua kalangan. Tidak ada kata-kata kotor, kekerasan, atau tema dewasa.
- **13+**: Cocok untuk remaja. Dapat berisi tema percintaan ringan, sedikit kata-kata kasar (non-eksplisit), atau nada sedih/emosional.
- **17+**: Cocok untuk remaja akhir dan dewasa. Dapat berisi tema dewasa yang lebih jelas, referensi seksual non-eksplisit, atau kekerasan.
- **21+**: Cocok untuk dewasa. Berisi konten seksual eksplisit, kekerasan ekstrem, atau penggunaan bahasa yang sangat vulgar.

Analisis lirik dan judul di bawah ini:
Judul: {title}
Lirik: {lyric}

Berikan respons Anda dalam format JSON dengan properti 'rating' (string) dan 'reason' (string). Contoh: {{"rating": "13+", "reason": "Lirik membahas tema percintaan."}}.
"""

def get_rating_from_gemini(title, lyric):
    """
    Memanggil Gemini API untuk mendapatkan rekomendasi rating dengan penanganan retry.
    """
    retries = 0
    max_retries = 5
    base_delay = 5  # Initial delay in seconds

    while retries < max_retries:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = PROMPT_TEMPLATE.format(title=title, lyric=lyric)
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            
            # Mengurai respons JSON dari Gemini
            import json
            result = json.loads(response.text)
            
            rating = result.get('rating', 'Tidak Diketahui')
            reason = result.get('reason', 'Tidak ada alasan yang diberikan.')
            
            return rating, reason
        except genai.types.BlockedPromptException as e:
            # Handle 429 errors specifically
            if "429 You exceeded your current quota" in str(e):
                delay = base_delay * (2 ** retries)
                st.warning(f"Batas kuota terlampaui. Menunggu {delay} detik sebelum mencoba kembali...")
                time.sleep(delay)
                retries += 1
            else:
                # Other BlockedPromptExceptions (e.g., safety issues)
                st.error(f"Terjadi kesalahan saat memanggil Gemini API: {e}")
                return "Error", f"Permintaan diblokir: {str(e)}"
        except Exception as e:
            st.error(f"Terjadi kesalahan saat memanggil Gemini API: {e}")
            return "Error", f"Gagal mendapatkan rating: {str(e)}"

    st.error("Gagal mendapatkan rating setelah beberapa kali percobaan. Silakan coba lagi nanti.")
    return "Error", "Gagal setelah percobaan berulang."


# Logika untuk memproses data yang ditempel
if pasted_data and api_key:
    st.info("Data ditempel. Memulai analisis...")
    
    try:
        # Buat objek seperti file dari string yang ditempel
        data_io = io.StringIO(pasted_data)
        # Baca data, mengasumsikan dipisahkan oleh tab
        df = pd.read_csv(data_io, sep='\t')
        
        # Validasi kolom yang dibutuhkan
        if 'Title' not in df.columns or 'Lyric' not in df.columns:
            st.error("Data Anda harus memiliki kolom 'Title' dan 'Lyric'.")
        else:
            # Kolom baru untuk hasil analisis
            df['Predicted Rating'] = None
            df['Reason'] = None
            
            progress_bar = st.progress(0)
            
            for index, row in df.iterrows():
                title = row['Title']
                lyric = row['Lyric']
                
                # Mendapatkan rating dari Gemini API
                rating, reason = get_rating_from_gemini(title, lyric)
                
                # Memperbarui DataFrame dengan data baru
                df.at[index, 'Predicted Rating'] = rating
                df.at[index, 'Reason'] = reason
                
                # Memperbarui progress bar
                progress = (index + 1) / len(df)
                progress_bar.progress(progress)
            
            st.success("Analisis selesai! Berikut hasilnya:")
            st.dataframe(df)

            # Bagian unduh
            st.header("Unduh Hasil")
            
            # Persiapan file CSV untuk diunduh
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode('utf-8')
            st.download_button(
                label="📥 Unduh sebagai CSV",
                data=csv_bytes,
                file_name="labeled_lyrics.csv",
                mime="text/csv",
            )
            
            # Persiapan file Excel untuk diunduh
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_bytes = excel_buffer.getvalue()
            st.download_button(
                label="📥 Unduh sebagai Excel",
                data=excel_bytes,
                file_name="labeled_lyrics.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses data: {e}")
