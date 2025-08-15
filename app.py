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
        
        # Kolom kepemilikan detail
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

# --- Fungsi Analisa & Scoring ---
@st.cache_data(ttl=3600)
def calculate_switching_score(data, period_days):
    # ... (Fungsi ini tidak berubah, digunakan untuk Tab 1)
    pass

# --- Tampilan Utama dengan Tab ---
tab_screener, tab_detail = st.tabs(["🏆 Screener Saham Switching", "📊 Analisa Detail"])

with tab_screener:
    # ... (Kode untuk tab screener tidak berubah)
    pass

with tab_detail:
    st.header("📊 Analisa Detail Kepemilikan Saham")
    if not df.empty:
        st.sidebar.header("🔍 Filter Analisa Detail")
        
        all_stocks = sorted(df['Code'].unique())
        selected_stock = st.sidebar.selectbox("Pilih Saham", all_stocks, index=all_stocks.index("BBRI") if "BBRI" in all_stocks else 0)
        
        period_options_detail = {"1 Bulan": 30, "3 Bulan": 90, "6 Bulan": 180, "1 Tahun": 365}
        selected_period_detail = st.sidebar.selectbox("Pilih Periode Analisa", options=list(period_options_detail.keys()))
        period_days_detail = period_options_detail[selected_period_detail]
        
        stock_data = df[df['Code'] == selected_stock].copy()
        
        if not stock_data.empty:
            # Tentukan tanggal awal dan akhir untuk analisa
            end_date = stock_data['Last Trading Date'].max()
            start_date_target = end_date - pd.DateOffset(days=period_days_detail)
            available_past_dates = stock_data[stock_data['Last Trading Date'] <= start_date_target]

            if not available_past_dates.empty:
                start_date = available_past_dates['Last Trading Date'].max()
                display_data = stock_data[stock_data['Last Trading Date'] >= start_date]

                # --- Tampilan Grafik Harga ---
                st.markdown(f"#### Pergerakan Harga **{selected_stock}** ({selected_period_detail})")
                fig_price = go.Figure()
                fig_price.add_trace(go.Scatter(
                    x=display_data['Last Trading Date'], y=display_data['Price'],
                    name='Harga', mode='lines', line=dict(color='cyan', width=2)
                ))
                fig_price.update_layout(height=300, template='plotly_dark', margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_price, use_container_width=True)

                # --- PERBAIKAN: Tabel Analisa Detail Kepemilikan ---
                st.markdown(f"#### Detail Perubahan Kepemilikan ({selected_period_detail})")

                start_row = display_data[display_data['Last Trading Date'] == start_date].iloc[0]
                end_row = display_data[display_data['Last Trading Date'] == end_date].iloc[0]
                
                owner_cols_detail = [
                    'Local IS', 'Local CP', 'Local PF', 'Local IB', 'Local ID', 'Local MF', 'Local SC', 'Local FD', 'Local OT',
                    'Foreign IS', 'Foreign CP', 'Foreign PF', 'Foreign IB', 'Foreign ID', 'Foreign MF', 'Foreign SC', 'Foreign FD', 'Foreign OT'
                ]
                
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
                        "Lembar Saham (Awal)": "{:,.0f}",
                        "Lembar Saham (Akhir)": "{:,.0f}",
                        "Perubahan (Lembar)": "{:,.0f}",
                        "Perubahan (%)": "{:.2f}%",
                        "% Thd Total Saham KSEI": "{:.2f}%"
                    }).background_gradient(
                        cmap='RdYlGn', # Merah-Kuning-Hijau
                        subset=['Perubahan (Lembar)'],
                        vmin=result_df['Perubahan (Lembar)'].min(),
                        vmax=result_df['Perubahan (Lembar)'].max()
                    ),
                    use_container_width=True,
                    height=660
                )
            else:
                st.warning(f"Tidak cukup data historis untuk saham {selected_stock} pada periode yang dipilih.")
        else:
            st.warning(f"Tidak ada data untuk saham {selected_stock}.")
    else:
        st.warning("Gagal memuat data.")
