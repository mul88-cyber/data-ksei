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
    # Ambil tanggal-tanggal unik dan urutkan
    unique_dates = sorted(data['Last Trading Date'].unique())
    if len(unique_dates) < 2:
        return pd.DataFrame() # Tidak cukup data untuk perbandingan

    end_date = unique_dates[-1]
    
    # Tentukan tanggal awal berdasarkan periode, cari tanggal terdekat yang ada di data
    start_date_target = end_date - pd.DateOffset(days=period_days)
    available_past_dates = [d for d in unique_dates if d <= start_date_target]
    if not available_past_dates:
        return pd.DataFrame() # Tidak ada data historis yang cukup jauh
    start_date = available_past_dates[-1]


    end_data_df = data[data['Last Trading Date'] == end_date].set_index('Code')
    start_data_df = data[data['Last Trading Date'] == start_date].set_index('Code')

    # Gabungkan data awal dan akhir untuk perhitungan yang efisien
    merged_df = end_data_df.join(start_data_df, lsuffix='_end', rsuffix='_start')
    
    # Hitung perubahan
    merged_df['delta_inst_local'] = merged_df['Local_Institusi_end'] - merged_df['Local_Institusi_start']
    merged_df['delta_inst_foreign'] = merged_df['Foreign_Institusi_end'] - merged_df['Foreign_Institusi_start']
    merged_df['delta_retail_local'] = merged_df['Local_Retail_end'] - merged_df['Local_Retail_start']
    merged_df['price_change'] = ((merged_df['Price_end'] - merged_df['Price_start']) / merged_df['Price_start'].replace(0, np.nan)) * 100
    
    result_df = merged_df.reset_index()
    
    # --- Logika Scoring ---
    result_df['Skor_Inst_Lokal'] = (result_df['delta_inst_local'] - result_df['delta_inst_local'].mean()) / result_df['delta_inst_local'].std()
    result_df['Skor_Inst_Asing'] = (result_df['delta_inst_foreign'] - result_df['delta_inst_foreign'].mean()) / result_df['delta_inst_foreign'].std()
    result_df['Skor_Retail'] = -(result_df['delta_retail_local'] - result_df['delta_retail_local'].mean()) / result_df['delta_retail_local'].std()
    
    result_df['Skor Akumulasi'] = (
        result_df['Skor_Inst_Lokal'].fillna(0) * 0.4 +
        result_df['Skor_Inst_Asing'].fillna(0) * 0.4 +
        result_df['Skor_Retail'].fillna(0) * 0.2
    )
    result_df.loc[result_df['price_change'] > 0, 'Skor Akumulasi'] += 0.5
    
    # Finalisasi kolom untuk display
    final_df = pd.DataFrame({
        'Saham': result_df['Code'],
        'Nama Perusahaan': result_df.get('Description_end', result_df['Code']),
        'Sektor': result_df.get('Sector_end', 'N/A'),
        'Harga Akhir': result_df['Price_end'],
        'Perubahan Harga %': result_df['price_change'],
        'Akumulasi Inst. Lokal': result_df['delta_inst_local'],
        'Akumulasi Inst. Asing': result_df['delta_inst_foreign'],
        'Perubahan Ritel Lokal': result_df['delta_retail_local'],
        'Skor Akumulasi': result_df['Skor Akumulasi']
    })
    
    return final_df.sort_values(by='Skor Akumulasi', ascending=False)

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
