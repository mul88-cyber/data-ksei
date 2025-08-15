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
st.title("🚀 Dasbor Analisa Kepemilikan KSEI")

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
def calculate_akumulasi_score(data, period_days):
    """Menghitung skor akumulasi institusi."""
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
    
    merged_df['delta_inst_local'] = merged_df['Local_Institusi_end'] - merged_df['Local_Institusi_start']
    merged_df['delta_inst_foreign'] = merged_df['Foreign_Institusi_end'] - merged_df['Foreign_Institusi_start']
    merged_df['delta_retail_local'] = merged_df['Local_Retail_end'] - merged_df['Local_Retail_start']
    merged_df['price_change'] = ((merged_df['Price_end'] - merged_df['Price_start']) / merged_df['Price_start'].replace(0, np.nan)) * 100
    
    result_df = merged_df.reset_index()
    
    result_df['Skor_Inst_Lokal'] = (result_df['delta_inst_local'] - result_df['delta_inst_local'].mean()) / result_df['delta_inst_local'].std()
    result_df['Skor_Inst_Asing'] = (result_df['delta_inst_foreign'] - result_df['delta_inst_foreign'].mean()) / result_df['delta_inst_foreign'].std()
    result_df['Skor_Retail'] = -(result_df['delta_retail_local'] - result_df['delta_retail_local'].mean()) / result_df['delta_retail_local'].std()
    
    result_df['Skor Akumulasi'] = (
        result_df['Skor_Inst_Lokal'].fillna(0) * 0.4 +
        result_df['Skor_Inst_Asing'].fillna(0) * 0.4 +
        result_df['Skor_Retail'].fillna(0) * 0.2
    )
    result_df.loc[result_df['price_change'] > 0, 'Skor Akumulasi'] += 0.5
    
    final_df = pd.DataFrame({
        'Saham': result_df['Code'], 'Nama Perusahaan': result_df.get('Description_end', result_df['Code']),
        'Sektor': result_df.get('Sector_end', 'N/A'), 'Harga Akhir': result_df['Price_end'],
        'Perubahan Harga %': result_df['price_change'], 'Akumulasi Inst. Lokal': result_df['delta_inst_local'],
        'Akumulasi Inst. Asing': result_df['delta_inst_foreign'], 'Perubahan Ritel Lokal': result_df['delta_retail_local'],
        'Skor Akumulasi': result_df['Skor Akumulasi']
    })
    
    return final_df.sort_values(by='Skor Akumulasi', ascending=False)

# --- Fungsi Grafik Detail ---
def create_detail_charts(data, code, view_mode):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
        row_heights=[0.5, 0.5], specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
        subplot_titles=(f"Pergerakan Harga Saham {code}", f"Aliran Dana Kepemilikan ({view_mode})")
    )
    
    fig.add_trace(go.Scatter(x=data['Last Trading Date'], y=data['Price'], name='Harga', mode='lines', line=dict(color='cyan', width=2)), row=1, col=1)
    
    investor_groups_inst = ['Local_Institusi', 'Foreign_Institusi']
    investor_groups_retail = ['Local_Retail', 'Foreign_Retail']
    colors = {'Local_Institusi': '#1f77b4', 'Local_Retail': '#ff7f0e', 'Foreign_Institusi': '#2ca02c', 'Foreign_Retail': '#d62728'}
    
    if view_mode == 'Nilai Absolut':
        for group in investor_groups_inst:
            fig.add_trace(go.Scatter(x=data['Last Trading Date'], y=data[group], name=group.replace('_', ' '), mode='lines', line=dict(width=2.5, color=colors[group])), secondary_y=False, row=2, col=1)
        for group in investor_groups_retail:
            fig.add_trace(go.Scatter(x=data['Last Trading Date'], y=data[group], name=group.replace('_', ' '), mode='lines', line=dict(width=2.5, dash='dash', color=colors[group])), secondary_y=True, row=2, col=1)
        fig.update_yaxes(title_text="Kepemilikan Institusi (Lbr)", secondary_y=False, row=2, col=1)
        fig.update_yaxes(title_text="Kepemilikan Ritel (Lbr)", secondary_y=True, row=2, col=1, showgrid=False)

    elif view_mode == 'Persentase':
        all_groups = investor_groups_inst + investor_groups_retail
        for group in all_groups:
            fig.add_trace(go.Scatter(
                x=data['Last Trading Date'], y=data[group], name=group.replace('_', ' '),
                mode='lines', line=dict(width=2.5),
                fill='tozeroy' if group == all_groups[0] else 'tonexty',
                stackgroup='one', groupnorm='percent', marker_color=colors[group]
            ), secondary_y=False, row=2, col=1)
        fig.update_yaxes(title_text="Persentase Kepemilikan (%)", secondary_y=False, row=2, col=1, ticksuffix='%')
        fig.update_yaxes(visible=False, secondary_y=True, row=2, col=1)

    fig.update_layout(height=800, template='plotly_dark', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Harga (Rp)", row=1, col=1)
    st.plotly_chart(fig, use_container_width=True)

# --- Tampilan Utama dengan Tab ---
tab_top27, tab_detail = st.tabs(["🏆 Top 27 Akumulasi Institusi", "📊 Analisa Detail"])

with tab_top27:
    st.header("🏆 Top 27 Saham Akumulasi Institusi")
    st.markdown("Menyaring saham berdasarkan akumulasi bersih oleh **Institusi Lokal & Asing**, serta distribusi oleh **Ritel Lokal** dalam periode waktu tertentu.")

    if not df.empty:
        period_options = {"1 Bulan Terakhir": 30, "3 Bulan Terakhir": 90, "6 Bulan Terakhir": 180}
        selected_period_label = st.selectbox("Pilih Periode Analisa", options=list(period_options.keys()))
        period_days = period_options.get(selected_period_label, 30)

        if st.button("Jalankan Analisa", use_container_width=True):
            with st.spinner(f"Menganalisa..."):
                final_results = calculate_akumulasi_score(df, period_days)
                if not final_results.empty:
                    top_27 = final_results.head(27)
                    st.success(f"Ditemukan **{len(top_27)}** saham dengan akumulasi institusi tertinggi.")
                    display_df = top_27.style.format({
                        'Harga Akhir': "Rp {:,.0f}", 'Perubahan Harga %': "{:.2f}%",
                        'Akumulasi Inst. Lokal': "{:,.0f} lbr", 'Akumulasi Inst. Asing': "{:,.0f} lbr",
                        'Perubahan Ritel Lokal': "{:,.0f} lbr", 'Skor Akumulasi': "{:.2f}"
                    }).background_gradient(cmap='Greens', subset=['Skor Akumulasi'])
                    st.dataframe(display_df, use_container_width=True, height=950)
                else:
                    st.warning("Tidak cukup data untuk analisa pada periode yang dipilih.")
    else:
        st.warning("Gagal memuat data.")

with tab_detail:
    st.header("📊 Analisa Detail Kepemilikan Saham")
    if not df.empty:
        st.sidebar.header("🔍 Filter Analisa Detail")
        
        all_stocks = sorted(df['Code'].unique())
        selected_stock = st.sidebar.selectbox("Pilih Saham", all_stocks, index=all_stocks.index("BBRI") if "BBRI" in all_stocks else 0)
        
        period_options_detail = {"3 Bulan": 90, "6 Bulan": 180, "1 Tahun": 365, "Semua Data": 9999}
        selected_period_detail = st.sidebar.selectbox("Pilih Periode Grafik", options=list(period_options_detail.keys()))
        
        # --- PERBAIKAN: Gunakan .get() untuk menghindari KeyError ---
        period_days_detail = period_options_detail.get(selected_period_detail, 90)
        
        stock_data = df[df['Code'] == selected_stock].copy()
        
        if not stock_data.empty:
            end_date = stock_data['Last Trading Date'].max()
            start_date = end_date - pd.DateOffset(days=period_days_detail)
            display_data = stock_data[stock_data['Last Trading Date'] >= start_date]

            st.markdown(f"Menampilkan analisa untuk **{selected_stock}** dalam **{selected_period_detail}**.")
            
            view_mode = st.radio(
                "Pilih Mode Tampilan Grafik Kepemilikan:",
                ('Nilai Absolut', 'Persentase'),
                horizontal=True,
                label_visibility='collapsed'
            )
            
            create_detail_charts(display_data, selected_stock, view_mode)
        else:
            st.warning(f"Tidak ada data untuk saham {selected_stock}.")
    else:
        st.warning("Gagal memuat data.")
