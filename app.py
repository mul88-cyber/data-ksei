import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
st.title("🚀 Dasbor Analisa Switching Kepemilikan")

# --- Load Data & Kalkulasi ---
@st.cache_data(ttl=3600)
def load_data():
    """Memuat dan membersihkan data KSEI dari URL dan menghitung kolom agregat."""
    csv_url = "https://storage.googleapis.com/stock-csvku/hasil_gabungan_ksei.csv"
    try:
        df = pd.read_csv(csv_url)
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'Last Trading Date'}, inplace=True)
        df['Last Trading Date'] = pd.to_datetime(df['Last Trading Date'], errors='coerce')
        
        owner_cols = [
            'Price', 'Local IS', 'Local CP', 'Local PF', 'Local IB', 'Local ID', 'Local MF', 'Local SC', 'Local FD', 'Local OT', 'Total_Local',
            'Foreign IS', 'Foreign CP', 'Foreign PF', 'Foreign IB', 'Foreign ID', 'Foreign MF', 'Foreign SC', 'Foreign FD', 'Foreign OT', 'Total_Foreign'
        ]
        for col in owner_cols:
             if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        local_institution_cols = ['Local IS', 'Local CP', 'Local PF', 'Local IB', 'Local MF', 'Local SC', 'Local FD', 'Local OT']
        foreign_institution_cols = ['Foreign IS', 'Foreign CP', 'Foreign PF', 'Foreign IB', 'Foreign MF', 'Foreign SC', 'Foreign FD', 'Foreign OT']
        
        df['Local_Retail'] = df.get('Local ID', 0)
        df['Local_Institusi'] = df[[c for c in local_institution_cols if c in df.columns]].sum(axis=1)
        df['Foreign_Retail'] = df.get('Foreign ID', 0)
        df['Foreign_Institusi'] = df[[c for c in foreign_institution_cols if c in df.columns]].sum(axis=1)
        df['Total_Saham_KSEI'] = df.get('Total_Local', 0) + df.get('Total_Foreign', 0)

        df.sort_values(by=['Code', 'Last Trading Date'], inplace=True)
        df.dropna(subset=['Last Trading Date', 'Code'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Gagal memuat atau memproses data dari URL: {e}")
        return pd.DataFrame()

df = load_data()

# --- Fungsi Analisa & Scoring ---
@st.cache_data(ttl=3600)
def calculate_switching_score(data, period_days):
    """Menghitung skor switching dari Ritel ke Institusi."""
    if data.empty: return pd.DataFrame()
    results = []
    unique_dates = sorted(data['Last Trading Date'].unique())
    if len(unique_dates) < 2: return pd.DataFrame()

    end_date = unique_dates[-1]
    start_date_target = end_date - pd.DateOffset(days=period_days)
    available_past_dates = [d for d in unique_dates if d <= start_date_target]
    if not available_past_dates: return pd.DataFrame()
    start_date = available_past_dates[-1]

    end_data_df = data[data['Last Trading Date'] == end_date].set_index('Code')
    start_data_df = data[data['Last Trading Date'] == start_date].set_index('Code')
    
    merged_df = end_data_df.join(start_data_df, lsuffix='_end', rsuffix='_start')
    merged_df.dropna(subset=['Local_Institusi_start', 'Foreign_Institusi_start', 'Local_Retail_start', 'Foreign_Retail_start'], inplace=True)
    
    merged_df['delta_inst_local'] = merged_df['Local_Institusi_end'] - merged_df['Local_Institusi_start']
    merged_df['delta_inst_foreign'] = merged_df['Foreign_Institusi_end'] - merged_df['Foreign_Institusi_start']
    merged_df['delta_retail_local'] = merged_df['Local_Retail_end'] - merged_df['Local_Retail_start']
    merged_df['delta_retail_foreign'] = merged_df['Foreign_Retail_end'] - merged_df['Foreign_Retail_start']

    merged_df['total_inst_change'] = merged_df['delta_inst_local'] + merged_df['delta_inst_foreign']
    merged_df['total_retail_change'] = merged_df['delta_retail_local'] + merged_df['delta_retail_foreign']
    
    merged_df['switching_score'] = merged_df['total_inst_change'] - merged_df['total_retail_change']
    
    result_df = merged_df.reset_index()
    
    final_df = pd.DataFrame({
        'Saham': result_df['Code'],
        'Nama Perusahaan': result_df.get('Description_end', result_df['Code']),
        'Switching Score': result_df['switching_score'],
        'Akumulasi Institusi': result_df['total_inst_change'],
        'Distribusi Ritel': result_df['total_retail_change'],
    })
    
    return final_df.sort_values(by='Switching Score', ascending=False), start_date, end_date

# --- Fungsi Grafik Detail ---
def create_switching_charts(data, code):
    # ... (Fungsi ini tidak berubah) ...
    pass

# --- Tampilan Utama dengan Tab ---
tab_screener, tab_detail = st.tabs(["🏆 Screener Saham Switching", "📊 Analisa Detail"])

with tab_screener:
    st.header("🏆 Screener Saham 'Switching'")
    st.markdown("Menyaring saham berdasarkan **perpindahan kepemilikan terbesar** dari **Ritel** ke **Institusi** dalam periode waktu tertentu.")

    if not df.empty:
        period_options = {"1 Bulan Terakhir": 30, "3 Bulan Terakhir": 90, "6 Bulan Terakhir": 180}
        selected_period_label = st.selectbox("Pilih Periode Analisa", options=list(period_options.keys()))
        period_days = period_options[selected_period_label]

        with st.spinner(f"Menganalisa..."):
            final_results, start_date_used, end_date_used = calculate_switching_score(df, period_days)
            
            if not final_results.empty:
                # --- PENAMBAHAN: Analisa Bulan Switching Terbesar ---
                top_results = final_results.head(50).copy()
                
                peak_months = []
                for index, row in top_results.iterrows():
                    stock_code = row['Saham']
                    stock_period_data = df[(df['Code'] == stock_code) & (df['Last Trading Date'] >= start_date_used) & (df['Last Trading Date'] <= end_date_used)]
                    
                    if len(stock_period_data) > 1:
                        delta_df = stock_period_data.set_index('Last Trading Date')[['Local_Institusi', 'Foreign_Institusi', 'Local_Retail', 'Foreign_Retail']].diff()
                        delta_df['monthly_switching_score'] = (delta_df['Local_Institusi'] + delta_df['Foreign_Institusi']) - (delta_df['Local_Retail'] + delta_df['Foreign_Retail'])
                        
                        if not delta_df['monthly_switching_score'].isna().all():
                            peak_date = delta_df['monthly_switching_score'].idxmax()
                            peak_months.append(peak_date.strftime('%b-%Y'))
                        else:
                            peak_months.append('N/A')
                    else:
                        peak_months.append('N/A')
                
                top_results['Bulan Switching Terbesar'] = peak_months
                # --- Akhir Penambahan ---

                st.success(f"Ditemukan **{len(top_results)}** saham dengan *switching score* tertinggi.")
                
                # Pindahkan kolom baru ke posisi yang lebih baik
                cols_ordered = ['Saham', 'Nama Perusahaan', 'Switching Score', 'Bulan Switching Terbesar', 'Akumulasi Institusi', 'Distribusi Ritel']
                display_df = top_results[cols_ordered].style.format({
                    'Switching Score': "{:,.0f}",
                    'Akumulasi Institusi': "{:,.0f} lbr",
                    'Distribusi Ritel': "{:,.0f} lbr"
                }).background_gradient(cmap='Greens', subset=['Switching Score'])
                
                st.dataframe(display_df, use_container_width=True, height=800)
            else:
                st.warning("Tidak cukup data untuk analisa pada periode yang dipilih.")
    else:
        st.warning("Gagal memuat data.")

with tab_detail:
    # ... (sisa kode tab_detail tidak berubah) ...
    pass
