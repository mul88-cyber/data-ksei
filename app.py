import streamlit as st
import pandas as pd
import numpy as np

# --- Konfigurasi Halaman & CSS Kustom ---
st.set_page_config(page_title="Dashboard Analisa KSEI", layout="wide")
st.markdown("""
<style>
/* CSS Kustom */
button[data-baseweb="tab"] {
    font-size: 18px; font-weight: bold; padding-top: 10px !important; padding-bottom: 10px !important;
}
div[data-testid="stMetricValue"] { font-size: 22px; }
div[data-testid="stMetricLabel"] { font-size: 15px; }
</style>
""", unsafe_allow_html=True)
st.title("🚀 Dasbor Analisa Kepemilikan KSEI")

# --- Load Data & Kalkulasi ---
@st.cache_data(ttl=3600)
def load_data():
    """Memuat dan membersihkan data KSEI dari URL."""
    csv_url = "https://storage.googleapis.com/stock-csvku/hasil_gabungan_ksei.csv"
    try:
        df = pd.read_csv(csv_url)
        # Ganti nama kolom 'Date' jika ada, agar konsisten
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'Last Trading Date'}, inplace=True)

        df['Last Trading Date'] = pd.to_datetime(df['Last Trading Date'], errors='coerce')
        
        # Kolom numerik yang relevan dari data KSEI
        numeric_cols = [
            'Price', 'Total_Local', 'Total_Foreign', 'Total_Saham_KSEI', 'Market_Cap',
            'KSEI_Local_%', 'KSEI_Foreign_%', 'Local_Retail', 'Local_Institusi',
            'Foreign_Retail', 'Foreign_Institusi', 'KSEI_Float_%'
        ]
        for col in numeric_cols:
             if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df.sort_values(by=['Code', 'Last Trading Date'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Gagal memuat data dari URL: {e}")
        return pd.DataFrame()

df = load_data()

# --- Fungsi Analisa & Scoring ---
@st.cache_data(ttl=3600)
def calculate_akumulasi_score(data, period_days):
    """Menghitung skor akumulasi institusi berdasarkan perubahan kepemilikan."""
    if data.empty:
        return pd.DataFrame()

    results = []
    end_date = data['Last Trading Date'].max()
    start_date = end_date - pd.DateOffset(days=period_days)

    for code, group in data.groupby('Code'):
        # Ambil data di akhir dan awal periode
        end_data = group[group['Last Trading Date'] == end_date]
        start_data_candidates = group[group['Last Trading Date'] <= start_date]
        
        if end_data.empty or start_data_candidates.empty:
            continue

        end_row = end_data.iloc[0]
        start_row = start_data_candidates.iloc[-1] # Ambil data terdekat dari awal periode

        # Hitung perubahan kepemilikan (delta) dalam lembar saham
        delta_inst_local = end_row['Local_Institusi'] - start_row['Local_Institusi']
        delta_inst_foreign = end_row['Foreign_Institusi'] - start_row['Foreign_Institusi']
        delta_retail_local = end_row['Local_Retail'] - start_row['Local_Retail']
        
        # Hitung perubahan harga
        price_change = ((end_row['Price'] - start_row['Price']) / start_row['Price']) * 100 if start_row['Price'] > 0 else 0

        results.append({
            'Saham': code,
            'Nama Perusahaan': end_row.get('Description', code),
            'Sektor': end_row.get('Sector', 'N/A'),
            'Harga Akhir': end_row['Price'],
            'Perubahan Harga %': price_change,
            'Akumulasi Inst. Lokal': delta_inst_local,
            'Akumulasi Inst. Asing': delta_inst_foreign,
            'Perubahan Ritel Lokal': delta_retail_local
        })

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # --- Logika Scoring ---
    # Normalisasi perubahan kepemilikan agar bisa dijumlahkan
    result_df['Skor_Inst_Lokal'] = (result_df['Akumulasi Inst. Lokal'] - result_df['Akumulasi Inst. Lokal'].mean()) / result_df['Akumulasi Inst. Lokal'].std()
    result_df['Skor_Inst_Asing'] = (result_df['Akumulasi Inst. Asing'] - result_df['Akumulasi Inst. Asing'].mean()) / result_df['Akumulasi Inst. Asing'].std()
    # Skor untuk distribusi ritel (semakin negatif perubahannya, semakin tinggi skornya)
    result_df['Skor_Retail'] = -(result_df['Perubahan Ritel Lokal'] - result_df['Perubahan Ritel Lokal'].mean()) / result_df['Perubahan Ritel Lokal'].std()
    
    # Skor akhir adalah gabungan dari ketiganya, dengan bobot
    result_df['Skor Akumulasi'] = (
        result_df['Skor_Inst_Lokal'].fillna(0) * 0.4 +
        result_df['Skor_Inst_Asing'].fillna(0) * 0.4 +
        result_df['Skor_Retail'].fillna(0) * 0.2
    )
    
    # Beri bonus jika harga juga naik
    result_df.loc[result_df['Perubahan Harga %'] > 0, 'Skor Akumulasi'] += 0.5
    
    return result_df.sort_values(by='Skor Akumulasi', ascending=False)

# --- Tampilan Utama ---
st.header("🏆 Top 27 Saham Akumulasi Institusi")
st.markdown("Menyaring saham berdasarkan akumulasi bersih oleh **Institusi Lokal & Asing**, serta distribusi oleh **Ritel Lokal** dalam periode waktu tertentu.")

if not df.empty:
    # Filter di Sidebar
    st.sidebar.header("🔍 Filter Analisa")
    period_options = {
        "1 Bulan Terakhir": 30,
        "3 Bulan Terakhir": 90,
        "6 Bulan Terakhir": 180
    }
    selected_period_label = st.sidebar.selectbox("Pilih Periode Analisa", options=list(period_options.keys()))
    period_days = period_options[selected_period_label]

    if st.sidebar.button("Jalankan Analisa", use_container_width=True):
        with st.spinner(f"Menganalisa perubahan kepemilikan dalam {selected_period_label}..."):
            final_results = calculate_akumulasi_score(df, period_days)
            
            if not final_results.empty:
                top_27 = final_results.head(27)

                st.success(f"Ditemukan **{len(top_27)}** saham dengan akumulasi institusi tertinggi.")
                
                # Format tampilan angka agar mudah dibaca
                display_df = top_27.style.format({
                    'Harga Akhir': "Rp {:,.0f}",
                    'Perubahan Harga %': "{:.2f}%",
                    'Akumulasi Inst. Lokal': "{:,.0f} lbr",
                    'Akumulasi Inst. Asing': "{:,.0f} lbr",
                    'Perubahan Ritel Lokal': "{:,.0f} lbr",
                    'Skor Akumulasi': "{:.2f}"
                }).background_gradient(cmap='Greens', subset=['Skor Akumulasi'])

                st.dataframe(display_df, use_container_width=True, height=950)
            else:
                st.warning("Tidak cukup data untuk melakukan analisa pada periode yang dipilih.")
    else:
        st.info("Pilih periode analisa di sidebar dan klik 'Jalankan Analisa' untuk memulai.")
else:
    st.warning("Gagal memuat data. Tidak bisa melanjutkan analisa.")
