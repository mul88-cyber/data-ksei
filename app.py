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
button[data-baseweb="tab"] { font-size: 18px; font-weight: bold; padding-top: 10px !important; padding-bottom: 10px !important; }
div[data-testid="stMetricValue"] { font-size: 22px; }
div[data-testid="stMetricLabel"] { font-size: 15px; }
</style>
""", unsafe_allow_html=True)
st.title("🚀 Dasbor Analisa Switching Kepemilikan")

# --- Load Data & Kalkulasi ---
@st.cache_data(ttl=3600)
def load_data():
    """Memuat data KSEI dari URL dan menghitung kolom agregat."""
    csv_url = "https://storage.googleapis.com/stock-csvku/hasil_gabungan_ksei.csv"
    try:
        df = pd.read_csv(csv_url)
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'Last Trading Date'}, inplace=True)
        if 'Total' in df.columns and 'Total.1' in df.columns:
            df.rename(columns={'Total': 'Total_Local', 'Total.1': 'Total_Foreign'}, inplace=True)

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
def calculate_switching_score(data, period_months):
    if data.empty: return pd.DataFrame()
    results = []

    for code, group in data.groupby('Code'):
        group = group.sort_values('Last Trading Date')
        if len(group) < period_months + 1:
            continue

        end_row = group.iloc[-1]
        start_row = group.iloc[-(period_months + 1)]

        delta_inst_local = end_row['Local_Institusi'] - start_row['Local_Institusi']
        delta_inst_foreign = end_row['Foreign_Institusi'] - start_row['Foreign_Institusi']
        delta_retail_local = end_row['Local_Retail'] - start_row['Local_Retail']
        delta_retail_foreign = end_row['Foreign_Retail'] - start_row['Foreign_Retail']

        total_inst_change = delta_inst_local + delta_inst_foreign
        total_retail_change = delta_retail_local + delta_retail_foreign
        
        switching_score = total_inst_change - total_retail_change
        
        results.append({
            'Saham': code,
            'Nama Perusahaan': end_row.get('Description', code),
            'Switching Score': switching_score,
            'Akumulasi Institusi': total_inst_change,
            'Distribusi Ritel': total_retail_change,
        })
    
    if not results: return pd.DataFrame()
    return pd.DataFrame(results).sort_values(by='Switching Score', ascending=False)

# --- Fungsi Grafik Detail ---
def create_switching_charts(data, code):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
        row_heights=[0.5, 0.5], specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
        subplot_titles=(f"Pergerakan Harga Saham {code}", "Kepemilikan Absolut (dalam Lembar Saham)")
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
        period_options = {"1 Bulan": 1, "3 Bulan": 3, "6 Bulan": 6}
        selected_period_label = st.selectbox("Pilih Periode Analisa", options=list(period_options.keys()))
        period_months = period_options[selected_period_label]

        with st.spinner(f"Menganalisa..."):
            final_results = calculate_switching_score(df, period_months)
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
        
        period_options_detail = {"3 Bulan": 3, "6 Bulan": 6, "12 Bulan (1 Tahun)": 12}
        selected_period_detail_label = st.sidebar.selectbox("Pilih Periode Grafik", options=list(period_options_detail.keys()))
        period_months_detail = period_options_detail[selected_period_detail_label]
        
        stock_data = df[df['Code'] == selected_stock].copy()
        
        if not stock_data.empty and len(stock_data) > period_months_detail:
            # Ambil data N bulan terakhir + 1 data sebelumnya untuk perbandingan
            display_data = stock_data.tail(period_months_detail + 1)
            
            start_row = display_data.iloc[0]
            end_row = display_data.iloc[-1]
            
            delta_local_retail = end_row['Local_Retail'] - start_row['Local_Retail']
            delta_local_inst = end_row['Local_Institusi'] - start_row['Local_Institusi']
            delta_foreign_retail = end_row['Foreign_Retail'] - start_row['Foreign_Retail']
            delta_foreign_inst = end_row['Foreign_Institusi'] - start_row['Foreign_Institusi']
            
            st.markdown(f"#### Ringkasan Perubahan dalam **{selected_period_detail_label}** untuk **{selected_stock}**")
            st.caption(f"Periode Analisa: **{start_row['Last Trading Date'].strftime('%d %b %Y')}** s/d **{end_row['Last Trading Date'].strftime('%d %b %Y')}**")
            
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
        st.warning("Gagal memuat data.")
