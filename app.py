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
</style>
""", unsafe_allow_html=True)
st.title("🚀 Dasbor Analisa Kepemilikan KSEI")

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
            'Foreign IS', 'Foreign CP', 'Foreign PF', 'Foreign IB', 'Foreign ID', 'Foreign MF', 'Foreign SC', 'Foreign FD', 'Foreign OT', 'Total_Foreign',
            'Total_Saham_KSEI'
        ]
        for col in owner_cols:
             if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df.sort_values(by=['Code', 'Last Trading Date'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Gagal memuat atau memproses data dari URL: {e}")
        return pd.DataFrame()

df = load_data()
owner_cols_detail = [
    'Local IS', 'Local CP', 'Local PF', 'Local IB', 'Local ID', 'Local MF', 'Local SC', 'Local FD', 'Local OT',
    'Foreign IS', 'Foreign CP', 'Foreign PF', 'Foreign IB', 'Foreign ID', 'Foreign MF', 'Foreign SC', 'Foreign FD', 'Foreign OT'
]

# --- Fungsi Analisa & Scoring (Untuk Tab Screener) ---
@st.cache_data(ttl=3600)
def calculate_switching_score(data, period_days):
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
    
    # Hitung delta
    merged_df['delta_inst_local'] = (merged_df['Local_Institusi_end'] - merged_df['Local_Institusi_start']) if 'Local_Institusi_end' in merged_df.columns else 0
    merged_df['delta_inst_foreign'] = (merged_df['Foreign_Institusi_end'] - merged_df['Foreign_Institusi_start']) if 'Foreign_Institusi_end' in merged_df.columns else 0
    merged_df['delta_retail_local'] = (merged_df['Local_Retail_end'] - merged_df['Local_Retail_start']) if 'Local_Retail_end' in merged_df.columns else 0
    merged_df['delta_retail_foreign'] = (merged_df['Foreign_Retail_end'] - merged_df['Foreign_Retail_start']) if 'Foreign_Retail_end' in merged_df.columns else 0

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
    
    return final_df.sort_values(by='Switching Score', ascending=False)

# --- Tampilan Utama dengan Tab ---
tab_screener, tab_detail = st.tabs(["🏆 Screener Saham Switching", "📊 Analisa Detail"])

with tab_screener:
    st.header("🏆 Screener Saham 'Switching'")
    st.markdown("Menyaring saham berdasarkan **perpindahan kepemilikan terbesar** dari **Ritel** ke **Institusi** dalam periode waktu tertentu.")

    if not df.empty:
        # Menghitung kolom agregat jika belum ada
        if 'Local_Institusi' not in df.columns:
            local_institution_cols = [c for c in owner_cols_detail if 'Local' in c and c != 'Local ID']
            foreign_institution_cols = [c for c in owner_cols_detail if 'Foreign' in c and c != 'Foreign ID']
            df['Local_Institusi'] = df[local_institution_cols].sum(axis=1)
            df['Foreign_Institusi'] = df[foreign_institution_cols].sum(axis=1)
            df['Local_Retail'] = df.get('Local ID', 0)
            df['Foreign_Retail'] = df.get('Foreign ID', 0)

        period_options = {"1 Bulan Terakhir": 30, "3 Bulan Terakhir": 90, "6 Bulan Terakhir": 180}
        selected_period_label = st.selectbox("Pilih Periode Analisa", options=list(period_options.keys()))
        period_days = period_options[selected_period_label]

        if st.button("Jalankan Analisa Switching", use_container_width=True):
            with st.spinner(f"Menganalisa..."):
                final_results = calculate_switching_score(df, period_days)
                if not final_results.empty:
                    top_results = final_results.head(50)
                    st.success(f"Ditemukan **{len(top_results)}** saham dengan *switching score* tertinggi.")
                    display_df = top_results.style.format({
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
    st.header("📊 Analisa Detail Switching Kepemilikan")
    if not df.empty:
        st.sidebar.header("🔍 Filter Analisa Detail")
        
        all_stocks = sorted(df['Code'].unique())
        selected_stock = st.sidebar.selectbox("Pilih Saham", all_stocks, index=all_stocks.index("BBRI") if "BBRI" in all_stocks else 0)
        
        period_options_detail = {"1 Bulan": 30, "3 Bulan": 90, "6 Bulan": 180, "1 Tahun": 365}
        selected_period_detail = st.sidebar.selectbox("Pilih Periode Analisa", options=list(period_options_detail.keys()), key="detail_period")
        period_days_detail = period_options_detail[selected_period_detail]
        
        stock_data = df[df['Code'] == selected_stock].copy()
        
        if not stock_data.empty:
            end_date = stock_data['Last Trading Date'].max()
            start_date_target = end_date - pd.DateOffset(days=period_days_detail)
            available_past_dates = stock_data[stock_data['Last Trading Date'] <= start_date_target]

            if not available_past_dates.empty:
                start_date = available_past_dates['Last Trading Date'].max()
                
                # --- PERBAIKAN: Tampilan Tabel Detail ---
                st.markdown(f"#### Detail Perubahan Kepemilikan untuk **{selected_stock}**")
                st.caption(f"Periode: **{start_date.strftime('%d %b %Y')}** s/d **{end_date.strftime('%d %b %Y')}**")

                start_row = stock_data[stock_data['Last Trading Date'] == start_date].iloc[0]
                end_row = stock_data[stock_data['Last Trading Date'] == end_date].iloc[0]
                
                analysis_data = []
                for col in owner_cols_detail:
                    start_qty = start_row.get(col, 0)
                    end_qty = end_row.get(col, 0)
                    change_qty = end_qty - start_qty
                    change_pct = (change_qty / start_qty) * 100 if start_qty > 0 else np.inf
                    pct_of_total = (end_qty / end_row['Total_Saham_KSEI']) * 100 if end_row.get('Total_Saham_KSEI', 0) > 0 else 0
                    
                    analysis_data.append({
                        "Tipe Investor": col.replace('_', ' '),
                        "Lembar Saham (Awal)": start_qty,
                        "Lembar Saham (Akhir)": end_qty,
                        "Perubahan (Lembar)": change_qty,
                        "Perubahan (%)": change_pct,
                        "% Thd Total Saham KSEI": pct_of_total
                    })
                
                result_df = pd.DataFrame(analysis_data)
                result_df = result_df.iloc[result_df['Perubahan (Lembar)'].abs().argsort()[::-1]].reset_index(drop=True)

                st.dataframe(
                    result_df.style.format({
                        "Lembar Saham (Awal)": "{:,.0f}", "Lembar Saham (Akhir)": "{:,.0f}",
                        "Perubahan (Lembar)": "{:,.0f}", "Perubahan (%)": "{:,.2f}%",
                        "% Thd Total Saham KSEI": "{:.2f}%"
                    }).background_gradient(
                        cmap='RdYlGn', subset=['Perubahan (Lembar)'],
                        vmin=result_df['Perubahan (Lembar)'].min(), vmax=result_df['Perubahan (Lembar)'].max()
                    ),
                    use_container_width=True, height=660
                )
            else:
                st.warning(f"Tidak cukup data historis untuk saham {selected_stock} pada periode yang dipilih.")
        else:
            st.warning(f"Tidak ada data untuk saham {selected_stock}.")
    else:
        st.warning("Gagal memuat data.")
