import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Konfigurasi Halaman & CSS Kustom ---
st.set_page_config(page_title="Dashboard Analisa Switching", layout="wide")
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
    """Memuat dan membersihkan data KSEI dari URL."""
    csv_url = "https://storage.googleapis.com/stock-csvku/hasil_gabungan_ksei.csv"
    try:
        df = pd.read_csv(csv_url)
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'Last Trading Date'}, inplace=True)

        df['Last Trading Date'] = pd.to_datetime(df['Last Trading Date'], errors='coerce')
        
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
    
    # Hitung delta untuk semua grup
    merged_df['delta_inst_local'] = merged_df['Local_Institusi_end'] - merged_df['Local_Institusi_start']
    merged_df['delta_inst_foreign'] = merged_df['Foreign_Institusi_end'] - merged_df['Foreign_Institusi_start']
    merged_df['delta_retail_local'] = merged_df['Local_Retail_end'] - merged_df['Local_Retail_start']
    merged_df['delta_retail_foreign'] = merged_df['Foreign_Retail_end'] - merged_df['Foreign_Retail_start']

    # Hitung total perubahan institusi dan ritel
    merged_df['total_inst_change'] = merged_df['delta_inst_local'] + merged_df['delta_inst_foreign']
    merged_df['total_retail_change'] = merged_df['delta_retail_local'] + merged_df['delta_retail_foreign']
    
    # Hitung Switching Score
    merged_df['switching_score'] = merged_df['total_inst_change'] - merged_df['total_retail_change']
    
    result_df = merged_df.reset_index()
    
    final_df = pd.DataFrame({
        'Saham': result_df['Code'],
        'Nama Perusahaan': result_df.get('Description_end', result_df['Code']),
        'Sektor': result_df.get('Sector_end', 'N/A'),
        'Switching Score': result_df['switching_score'],
        'Akumulasi Institusi': result_df['total_inst_change'],
        'Distribusi Ritel': result_df['total_retail_change'],
    })
    
    return final_df.sort_values(by='Switching Score', ascending=False)

# --- Fungsi Grafik Detail ---
def create_switching_charts(data, code):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.5, 0.5],
        subplot_titles=(f"Pergerakan Harga Saham {code}", "Perubahan Kepemilikan (Delta dari Awal Periode)")
    )
    
    # Grafik 1: Harga
    fig.add_trace(go.Scatter(
        x=data['Last Trading Date'], y=data['Price'],
        name='Harga', mode='lines', line=dict(color='cyan', width=2)
    ), row=1, col=1)
    
    # Grafik 2: Perubahan Kepemilikan
    investor_groups = ['Local_Institusi', 'Local_Retail', 'Foreign_Institusi', 'Foreign_Retail']
    colors = {'Local_Institusi': '#1f77b4', 'Local_Retail': '#ff7f0e', 'Foreign_Institusi': '#2ca02c', 'Foreign_Retail': '#d62728'}
    
    for group in investor_groups:
        # Hitung perubahan (delta) dari hari pertama dalam data yang ditampilkan
        delta_kepemilikan = data[group] - data[group].iloc[0]
        fig.add_trace(go.Scatter(
            x=data['Last Trading Date'], y=delta_kepemilikan,
            name=group.replace('_', ' '), mode='lines',
            line=dict(width=2.5),
            fill='tozeroy' if group == investor_groups[0] else 'tonexty',
            stackgroup='one',
            marker_color=colors[group]
        ), row=2, col=1)

    fig.update_layout(height=700, template='plotly_dark', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Harga (Rp)", row=1, col=1)
    fig.update_yaxes(title_text="Perubahan (Lembar)", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)


# --- Tampilan Utama dengan Tab ---
tab_screener, tab_detail = st.tabs(["🏆 Screener Saham Switching", "📊 Analisa Detail"])

with tab_screener:
    st.header("🏆 Screener Saham 'Switching'")
    st.markdown("Menyaring saham berdasarkan **perpindahan kepemilikan terbesar** dari **Ritel** ke **Institusi** dalam periode waktu tertentu.")

    if not df.empty:
        period_options = {"1 Bulan Terakhir": 30, "3 Bulan Terakhir": 90, "6 Bulan Terakhir": 180}
        selected_period_label = st.selectbox("Pilih Periode Analisa", options=list(period_options.keys()))
        period_days = period_options[selected_period_label]

        if st.button("Jalankan Analisa Switching", use_container_width=True):
            with st.spinner(f"Menganalisa..."):
                final_results = calculate_switching_score(df, period_days)
                if not final_results.empty:
                    top_results = final_results.head(50) # Tampilkan 50 teratas
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
        
        period_options_detail = {"3 Bulan": 90, "6 Bulan": 180, "1 Tahun": 365, "Semua Data": 9999}
        selected_period_detail = st.sidebar.selectbox("Pilih Periode Grafik", options=list(period_options_detail.keys()))
        period_days_detail = period_options_detail[selected_period_detail]
        
        stock_data = df[df['Code'] == selected_stock].copy()
        
        if not stock_data.empty:
            end_date = stock_data['Last Trading Date'].max()
            start_date = end_date - pd.DateOffset(days=period_days_detail)
            display_data = stock_data[stock_data['Last Trading Date'] >= start_date].copy()

            if len(display_data) > 1:
                # --- Kalkulasi Kartu Metrik ---
                start_row = display_data.iloc[0]
                end_row = display_data.iloc[-1]
                
                delta_local_retail = end_row['Local_Retail'] - start_row['Local_Retail']
                delta_local_inst = end_row['Local_Institusi'] - start_row['Local_Institusi']
                delta_foreign_retail = end_row['Foreign_Retail'] - start_row['Foreign_Retail']
                delta_foreign_inst = end_row['Foreign_Institusi'] - start_row['Foreign_Institusi']
                
                st.markdown(f"#### Ringkasan Perubahan dalam **{selected_period_detail}** untuk **{selected_stock}**")
                
                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                kpi1.metric("Ritel Lokal", f"{delta_local_retail:,.0f}")
                kpi2.metric("Institusi Lokal", f"{delta_local_inst:,.0f}")
                kpi3.metric("Ritel Asing", f"{delta_foreign_retail:,.0f}")
                kpi4.metric("Institusi Asing", f"{delta_foreign_inst:,.0f}")
                
                st.divider()

                create_switching_charts(display_data, selected_stock)
            else:
                st.warning(f"Tidak cukup data historis untuk saham {selected_stock} pada periode yang dipilih.")
        else:
            st.warning(f"Tidak ada data untuk saham {selected_stock}.")
    else:
        st.warning("Gagal memuat data.")
