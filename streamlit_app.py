import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
import os
import time
from openai import OpenAI
import json

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="Pemberi Label Lirik Otomatis",
    page_icon="🎶"
)

st.title("🎶 Aplikasi Pemberi Label Lirik Otomatis")
st.markdown("Pilih model AI, masukkan API key, dan tempel data lirik untuk mendapatkan rekomendasi rating.")

# Pemilihan Model AI
selected_model = st.selectbox(
    "Pilih Model AI:",
    ["DeepSeek", "Gemini"]
)

# Input API Key berdasarkan pilihan model
if selected_model == "Gemini":
    api_key = st.text_input("Masukkan Gemini API Key Anda:", type="password")
    if api_key:
        genai.configure(api_key=api_key)
    client = None
else:
    api_key = st.text_input("Masukkan DeepSeek API Key Anda:", type="password")
    if api_key:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    else:
        client = None

# Optional reasoning checkbox
reasoning_enabled = st.checkbox("Sertakan Alasan (Reasoning)", value=False)

# Text area untuk menempel data
pasted_data = st.text_area(
    "Tempel data (lirik dan judul lagu) di sini:",
    height=300,
    placeholder="Contoh: (Salin dari Excel, termasuk header)\nJudul\tLirik\nJudul Lagu 1\tLirik dari lagu pertama.\nJudul Lagu 2\tLirik dari lagu kedua."
)

# Prompt Template untuk AI
PROMPT_TEMPLATE_FULL = """
Anda adalah sistem klasifikasi musik Indonesia. Berdasarkan lirik dan judul lagu berikut, rekomendasikan rating yang paling sesuai dari kategori ini: "SU (semua umur)", "13+", "17+", atau "21+".

- **SU**: Cocok untuk semua kalangan. Tidak ada kata-kata kotor, kekerasan, atau tema dewasa. Tema ramah keluarga, persahabatan, alam, dan motivasi. Tidak ada referensi seksualitas, narkoba, atau konflik serius.
- **13+**: Cocok untuk remaja. Boleh mengandung tema percintaan ringan (patah hati, kerinduan). Boleh ada sedikit kata kasar (non-eksplisit) atau ekspresi emosional. Tidak ada konten seksual, kekerasan grafis, atau bahasa vulgar.
- **17+**: Cocok untuk remaja akhir dan dewasa. Boleh ada tema dewasa (konflik hubungan, pengkhianatan, kekerasan implisit). Boleh mengandung kiasan sugestif atau bahasa agak kasar (tidak eksplisit). Tidak ada deskripsi seksual gamblang atau kekerasan ekstrem.
- **21+**: Cocok untuk dewasa. Boleh mengandung konten seksual eksplisit, kekerasan grafis, atau bahasa vulgar berat. Judul/lirik boleh bersifat provokatif atau sangat eksplisit. Contoh: Deskripsi seksual mendetail, adegan sadis, atau kata-kata makian ekstrem.

Aturan Tambahan:
Jika konten berada di batas dua kategori, gunakan rating yang lebih tinggi.
Jika ragu, tanyakan: "Apakah ini pantas untuk usia di bawah kategori ini?"

Analisis lirik dan judul di bawah ini:
Judul: {title}
Lirik: {lyric}

Berikan respons Anda dalam format JSON dengan properti 'rating' (string) dan 'reason' (string). Pastikan respons hanya berupa objek JSON. Contoh: {{"rating": "13+", "reason": "Lirik membahas tema percintaan."}}.
"""

PROMPT_TEMPLATE_RATING_ONLY = """
Anda adalah sistem klasifikasi musik Indonesia. Berdasarkan lirik dan judul lagu berikut, rekomendasikan rating yang paling sesuai dari kategori ini: "SU (semua umur)", "13+", "17+", atau "21+".

- **SU**: Cocok untuk semua kalangan. Tidak ada kata-kata kotor, kekerasan, atau tema dewasa. Tema ramah keluarga, persahabatan, alam, dan motivasi. Tidak ada referensi seksualitas, narkoba, atau konflik serius.
- **13+**: Cocok untuk remaja. Boleh mengandung tema percintaan ringan (patah hati, kerinduan). Boleh ada sedikit kata kasar (non-eksplisit) atau ekspresi emosional. Tidak ada konten seksual, kekerasan grafis, atau bahasa vulgar.
- **17+**: Cocok untuk remaja akhir dan dewasa. Boleh ada tema dewasa (konflik hubungan, pengkhianatan, kekerasan implisit). Boleh mengandung kiasan sugestif atau bahasa agak kasar (tidak eksplisit). Tidak ada deskripsi seksual gamblang atau kekerasan ekstrem.
- **21+**: Cocok untuk dewasa. Boleh mengandung konten seksual eksplisit, kekerasan grafis, atau bahasa vulgar berat. Judul/lirik boleh bersifat provokatif atau sangat eksplisit. Contoh: Deskripsi seksual mendetail, adegan sadis, atau kata-kata makian ekstrem.

Aturan Tambahan:
Jika konten berada di batas dua kategori, gunakan rating yang lebih tinggi.
Jika ragu, tanyakan: "Apakah ini pantas untuk usia di bawah kategori ini?"

Analisis lirik dan judul di bawah ini:
Judul: {title}
Lirik: {lyric}

Berikan respons Anda dalam format JSON dengan properti 'rating' (string). Pastikan respons hanya berupa objek JSON. Contoh: {{"rating": "13+"}}.
"""

def get_rating_from_model(model_name, title, lyric, reasoning_enabled):
    """
    Memanggil API AI yang dipilih untuk mendapatkan rekomendasi rating.
    """
    retries = 0
    max_retries = 5
    base_delay = 5  # Initial delay in seconds

    prompt = PROMPT_TEMPLATE_FULL if reasoning_enabled else PROMPT_TEMPLATE_RATING_ONLY

    while retries < max_retries:
        try:
            formatted_prompt = prompt.format(title=title, lyric=lyric)
            result_text = None
            
            if model_name == "Gemini":
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(formatted_prompt, generation_config={"response_mime_type": "application/json"})
                result_text = response.text
            elif model_name == "DeepSeek":
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "user", "content": formatted_prompt},
                    ],
                    stream=False
                )
                result_text = response.choices[0].message.content

            # Menangani respons yang tidak valid (misalnya, jika berisi blok kode markdown)
            if result_text and result_text.strip().startswith('```json') and result_text.strip().endswith('```'):
                result_text = result_text.strip()[7:-3].strip()

            # Mengurai respons JSON
            try:
                result = json.loads(result_text)
                rating = result.get('rating', 'Tidak Diketahui')
                reason = result.get('reason', 'Alasan tidak diminta.') if reasoning_enabled else 'Alasan tidak diminta.'
                return rating, reason
            except json.JSONDecodeError:
                st.error(f"Respons dari {model_name} tidak valid: {result_text}")
                return "Error", f"Respons tidak valid: {result_text}"

        except Exception as e:
            st.error(f"Terjadi kesalahan saat memanggil {model_name} API: {e}")
            delay = base_delay * (2 ** retries)
            st.warning(f"Menunggu {delay} detik sebelum mencoba kembali...")
            time.sleep(delay)
            retries += 1
            if retries >= max_retries:
                st.error("Gagal mendapatkan rating setelah beberapa kali percobaan.")
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
                
                # Mendapatkan rating dari model AI yang dipilih
                rating, reason = get_rating_from_model(selected_model, title, lyric, reasoning_enabled)
                
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
