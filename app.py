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
    
    return final_df.sort_values(by='Switching Score', ascending=False)

# --- Fungsi Grafik Detail ---
def create_switching_charts(data, code, view_mode):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
        row_heights=[0.5, 0.5], specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
        subplot_titles=(f"Pergerakan Harga Saham {code}", f"Kepemilikan Absolut (dalam Lembar Saham)")
    )
    fig.add_trace(go.Scatter(x=data['Last Trading Date'], y=data['Price'], name='Harga', mode='lines', line=dict(color='cyan', width=2)), row=1, col=1)
    
    investor_groups_inst = ['Local_Institusi', 'Foreign_Institusi']
    investor_groups_retail = ['Local_Retail', 'Foreign_Retail']
    colors = {'Local_Institusi': '#1f77b4', 'Local_Retail': '#ff7f0e', 'Foreign_Institusi': '#2ca02c', 'Foreign_Retail': '#d62728'}
    
    for group in investor_groups_inst:
        fig.add_trace(go.Scatter(x=data['Last Trading Date'], y=data[group], name=group.replace('_', ' '), mode='lines', line=dict(width=2.5, color=colors[group])), secondary_y=False, row=2, col=1)

    for group in investor_groups_retail:
        fig.add_trace(go.Scatter(x=data['Last Trading Date'], y=data[group], name=group.replace('_', ' '), mode='lines', line=dict(width=2.5, dash='dash', color=colors[group])), secondary_y=True, row=2, col=1)
        
    fig.update_layout(height=800, template='plotly_dark', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Harga (Rp)", row=1, col=1)
    fig.update_yaxes(title_text="Kepemilikan Institusi (Lbr)", secondary_y=False, row=2, col=1)
    fig.update_yaxes(title_text="Kepemilikan Ritel (Lbr)", secondary_y=True, row=2, col=1, showgrid=False)
    
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

        # --- PERBAIKAN: Analisa berjalan otomatis ---
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
        
        period_options_detail = {"3 Bulan": 90, "6 Bulan": 180, "1 Tahun": 365, "Semua Data": 9999}
        selected_period_detail_label = st.sidebar.selectbox("Pilih Periode Grafik", options=list(period_options_detail.keys()))
        period_days_detail = period_options_detail[selected_period_detail]
        
        stock_data = df[df['Code'] == selected_stock].copy()
        
        if not stock_data.empty:
            end_date = stock_data['Last Trading Date'].max()
            start_date_target = end_date - pd.DateOffset(days=period_days_detail)
            display_data = stock_data[stock_data['Last Trading Date'] >= start_date_target].copy()

            if len(display_data) > 1:
                start_row = display_data.iloc[0]
                end_row = display_data.iloc[-1]
                
                # --- PERBAIKAN: Menambahkan rentang tanggal ---
                start_date_display = start_row['Last Trading Date']
                end_date_display = end_row['Last Trading Date']
                
                delta_local_retail = end_row['Local_Retail'] - start_row['Local_Retail']
                delta_local_inst = end_row['Local_Institusi'] - start_row['Local_Institusi']
                delta_foreign_retail = end_row['Foreign_Retail'] - start_row['Foreign_Retail']
                delta_foreign_inst = end_row['Foreign_Institusi'] - start_row['Foreign_Institusi']
                
                st.markdown(f"#### Ringkasan Perubahan untuk **{selected_stock}**")
                st.caption(f"Periode Analisa: **{start_date_display.strftime('%d %b %Y')}** s/d **{end_date_display.strftime('%d %b %Y')}**")
                
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
