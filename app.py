import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Konfigurasi Halaman & CSS Kustom ---
st.set_page_config(page_title="Dashboard Analisa Switching KSEI", layout="wide")
st.markdown("""
<style>
/* CSS Kustom */
button[data-baseweb="tab"] {
    font-size: 18px; font-weight: bold; padding-top: 10px !important; padding-bottom: 10px !important;
}
div[data-testid="stMetricValue"] { font-size: 18px; }
div[data-testid="stMetricLabel"] { font-size: 14px; color: #a0a0a0; }
</style>
""", unsafe_allow_html=True)
st.title("🚀 Dasbor Analisa Switching Kepemilikan Detail")

# --- Load Data & Kalkulasi ---
@st.cache_data(ttl=3600)
def load_data():
    """Memuat dan membersihkan data KSEI dari URL."""
    csv_url = "https://storage.googleapis.com/stock-csvku/hasil_gabungan_ksei.csv"
    try:
        df = pd.read_csv(csv_url)
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'Last Trading Date'}, inplace=True)
        df['Last Trading Date'] = pd.to_datetime(df['Last Trading Date'], errors='coerce')
        df.sort_values(by=['Code', 'Last Trading Date'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Gagal memuat data dari URL: {e}")
        return pd.DataFrame()

df = load_data()
# Definisikan kolom kepemilikan detail
owner_cols_detail = [
    'Local IS', 'Local CP', 'Local PF', 'Local IB', 'Local ID', 'Local MF', 'Local SC', 'Local FD', 'Local OT',
    'Foreign IS', 'Foreign CP', 'Foreign PF', 'Foreign IB', 'Foreign ID', 'Foreign MF', 'Foreign SC', 'Foreign FD', 'Foreign OT'
]
# Konversi kolom ke numerik sekali saja di awal
for col in owner_cols_detail + ['Price']:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)


# --- Fungsi Analisa & Scoring ---
@st.cache_data(ttl=3600)
def calculate_detailed_switching(data, period_days):
    """Menghitung switching score detail berdasarkan 18 tipe investor."""
    if data.empty: return pd.DataFrame()
    
    unique_dates = sorted(data['Last Trading Date'].unique())
    if len(unique_dates) < 2: return pd.DataFrame()

    end_date = unique_dates[-1]
    start_date_target = end_date - pd.DateOffset(days=period_days)
    available_past_dates = [d for d in unique_dates if d <= start_date_target]
    if not available_past_dates: return pd.DataFrame()
    start_date = available_past_dates[-1]

    end_df = data[data['Last Trading Date'] == end_date].set_index('Code')
    start_df = data[data['Last Trading Date'] == start_date].set_index('Code')
    
    comparison_df = end_df.join(start_df, lsuffix='_End', rsuffix='_Start')
    
    delta_cols = []
    for col in owner_cols_detail:
        start_col, end_col = f'{col}_Start', f'{col}_End'
        delta_col_name = f'Delta_{col}'
        if start_col in comparison_df.columns and end_col in comparison_df.columns:
            comparison_df[delta_col_name] = comparison_df[end_col] - comparison_df[start_col]
            delta_cols.append(delta_col_name)
            
    comparison_df['Total Switching Value'] = comparison_df[delta_cols].abs().sum(axis=1)
    result_df = comparison_df.reset_index()
    
    return result_df.sort_values(by='Total Switching Value', ascending=False)

# --- Fungsi Grafik Detail ---
def create_detail_charts_v2(data, code):
    # ... (Fungsi ini bisa dikembangkan lebih lanjut jika diperlukan)
    st.info("Fitur grafik detail untuk analisa switching bisa dikembangkan di sini.")

# --- Tampilan Utama dengan Tab ---
tab_screener, tab_detail = st.tabs(["🏆 Screener Switching Detail", "📊 Analisa Detail"])

with tab_screener:
    st.header("🏆 Screener Switching Kepemilikan Detail")
    st.markdown("Menyaring saham berdasarkan **total perpindahan kepemilikan (gejolak)** terbesar di antara 18 tipe investor dalam periode waktu tertentu.")

    if not df.empty:
        period_options = {"1 Bulan Terakhir": 30, "3 Bulan Terakhir": 90, "6 Bulan Terakhir": 180}
        selected_period_label = st.selectbox("Pilih Periode Analisa", options=list(period_options.keys()))
        period_days = period_options[selected_period_label]

        if st.button("Jalankan Analisa Switching Detail", use_container_width=True):
            with st.spinner(f"Menganalisa..."):
                final_results = calculate_detailed_switching(df, period_days)
                if not final_results.empty:
                    top_results = final_results.head(50)
                    st.success(f"Ditemukan **{len(top_results)}** saham dengan *switching value* tertinggi.")
                    
                    # Siapkan kolom untuk ditampilkan
                    display_cols = ['Code', 'Total Switching Value'] + [f'Delta_{col}' for col in owner_cols_detail]
                    df_to_display = top_results[display_cols]
                    
                    # Format angka dan header
                    rename_cols = {'Code': 'Saham'}
                    format_dict = {'Total Switching Value': "{:,.0f}"}
                    for col in display_cols:
                        if 'Delta' in col:
                            rename_cols[col] = col.replace('Delta_', '')
                            format_dict[rename_cols[col]] = "{:,.0f}"

                    display_df = df_to_display.rename(columns=rename_cols)
                    
                    st.dataframe(display_df.style.format(format_dict).background_gradient(cmap='Greens', subset=['Total Switching Value']), use_container_width=True, height=800)
                else:
                    st.warning("Tidak cukup data untuk analisa pada periode yang dipilih.")
    else:
        st.warning("Gagal memuat data.")

with tab_detail:
    st.header("📊 Analisa Detail Switching Kepemilikan")
    if not df.empty:
        st.sidebar.header("🔍 Filter Analisa Detail")
        
        all_stocks = sorted(df['Code'].unique())
        selected_stock = st.sidebar.selectbox("Pilih Saham", all_stocks, index=all_stocks.index("BBRI") if "BBRI" in all_stocks else 0)
        
        period_options_detail = {"1 Bulan": 30, "3 Bulan": 90, "6 Bulan": 180}
        selected_period_detail_label = st.sidebar.selectbox("Pilih Periode Analisa Detail", options=list(period_options_detail.keys()))
        period_days_detail = period_options_detail[selected_period_detail_label]
        
        stock_data = df[df['Code'] == selected_stock].copy()
        
        if not stock_data.empty and len(stock_data) > 1:
            end_date = stock_data['Last Trading Date'].max()
            start_date_target = end_date - pd.DateOffset(days=period_days_detail)
            
            # Cari tanggal terdekat yang ada di data
            available_past_dates = stock_data[stock_data['Last Trading Date'] <= start_date_target]
            if not available_past_dates.empty:
                start_date = available_past_dates['Last Trading Date'].max()
                
                start_row = stock_data[stock_data['Last Trading Date'] == start_date].iloc[0]
                end_row = stock_data[stock_data['Last Trading Date'] == end_date].iloc[0]

                st.markdown(f"#### Ringkasan Perubahan dalam **{selected_period_detail_label}** untuk **{selected_stock}**")
                st.caption(f"Periode: {start_date.strftime('%d %b %Y')} hingga {end_date.strftime('%d %b %Y')}")

                deltas = {}
                for col in owner_cols_detail:
                    deltas[col] = end_row[col] - start_row[col]
                
                # Urutkan berdasarkan nilai absolut perubahan
                sorted_deltas = sorted(deltas.items(), key=lambda item: abs(item[1]), reverse=True)
                
                # Pisahkan akumulator dan distributor
                accumulators = {k: v for k, v in sorted_deltas if v > 0}
                distributors = {k: v for k, v in sorted_deltas if v < 0}

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Top Akumulator (Pembeli)")
                    for i, (investor, change) in enumerate(list(accumulators.items())[:3]):
                        st.metric(label=investor.replace('_', ' '), value=f"+{change:,.0f} lbr")
                
                with col2:
                    st.subheader("Top Distributor (Penjual)")
                    for i, (investor, change) in enumerate(list(distributors.items())[:3]):
                        st.metric(label=investor.replace('_', ' '), value=f"{change:,.0f} lbr")
                
                st.divider()
                st.markdown("Grafik detail bisa dikembangkan di sini untuk menampilkan tren dari top akumulator/distributor.")

            else:
                st.warning(f"Tidak cukup data historis untuk saham {selected_stock} pada periode yang dipilih.")
        else:
            st.warning(f"Tidak ada data untuk saham {selected_stock}.")
    else:
        st.warning("Gagal memuat data.")
