import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

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
            'Foreign IS', 'Foreign CP', 'Foreign PF', 'Foreign IB', 'Foreign ID', 'Foreign MF', 'Foreign SC', 'Foreign FD', 'Foreign OT', 'Total_Foreign'
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

# --- Tampilan Utama dengan Tab ---
tab_screener, tab_detail = st.tabs(["🏆 Screener Saham Switching", "📊 Analisa Detail"])

with tab_screener:
    st.header("🏆 Screener Saham 'Switching' Detail")
    st.markdown("Menyaring saham berdasarkan total perpindahan kepemilikan terbesar di antara 18 tipe investor.")

    if not df.empty:
        period_options = {"1 Bulan": 1, "3 Bulan": 3, "6 Bulan": 6}
        selected_period_label = st.selectbox("Pilih Periode Analisa", options=list(period_options.keys()))
        period_months = period_options[selected_period_label]

        if st.button("Jalankan Analisa Switching", use_container_width=True):
            with st.spinner(f"Menganalisa perpindahan kepemilikan dalam {selected_period_label}..."):
                # Logic to find start and end dates
                unique_dates = sorted(df['Last Trading Date'].unique())
                end_date = unique_dates[-1]
                start_date_index = max(0, len(unique_dates) - 1 - period_months)
                start_date = unique_dates[start_date_index]
                
                end_df = df[df['Last Trading Date'] == end_date].set_index('Code')
                start_df = df[df['Last Trading Date'] == start_date].set_index('Code')
                
                comparison_df = end_df.join(start_df, lsuffix='_End', rsuffix='_Start')
                delta_cols = []
                for col in owner_cols_detail:
                    start_col, end_col = f'{col}_Start', f'{col}_End'
                    delta_col_name = f'Delta_{col}'
                    if start_col in comparison_df.columns and end_col in comparison_df.columns:
                        comparison_df[delta_col_name] = comparison_df[end_col] - comparison_df[start_col]
                        delta_cols.append(delta_col_name)
                
                comparison_df['Total Switching Value'] = comparison_df[delta_cols].abs().sum(axis=1)
                final_results = comparison_df.reset_index().sort_values(by='Total Switching Value', ascending=False)
                
                if not final_results.empty:
                    top_results = final_results.head(50)
                    st.success(f"Ditemukan **{len(top_results)}** saham dengan *switching value* tertinggi.")
                    display_cols = ['Code', 'Total Switching Value'] + [f'Delta_{col}' for col in owner_cols_detail]
                    df_to_display = top_results[display_cols]
                    rename_cols = {'Code': 'Saham'}
                    format_dict = {'Total Switching Value': "{:,.0f}"}
                    for col in display_cols:
                        if 'Delta' in col:
                            rename_cols[col] = col.replace('Delta_', '').replace('Local ', 'L ').replace('Foreign ', 'F ')
                            format_dict[rename_cols[col]] = "{:,.0f}"
                    display_df = df_to_display.rename(columns=rename_cols)
                    st.dataframe(display_df.style.format(format_dict).background_gradient(cmap='Greens', subset=['Total Switching Value']), use_container_width=True, height=800)
                else:
                    st.warning("Tidak cukup data untuk analisa.")
    else:
        st.warning("Gagal memuat data.")

with tab_detail:
    st.header("📊 Analisa Detail Kepemilikan Saham")
    if not df.empty:
        st.sidebar.header("🔍 Filter Analisa Detail")
        
        all_stocks = sorted(df['Code'].unique())
        selected_stock = st.sidebar.selectbox("Pilih Saham", all_stocks, index=all_stocks.index("BBRI") if "BBRI" in all_stocks else 0)
        
        period_options_detail = {"3 Bulan": 3, "6 Bulan": 6, "12 Bulan (1 Tahun)": 12}
        selected_period_detail = st.sidebar.selectbox("Pilih Periode Analisa", options=list(period_options_detail.keys()), key="detail_period")
        period_months_detail = period_options_detail[selected_period_detail]
        
        stock_data = df[df['Code'] == selected_stock].copy()
        
        if not stock_data.empty and len(stock_data) > period_months_detail:
            # Filter data berdasarkan jumlah bulan, bukan hari
            display_data = stock_data.tail(period_months_detail + 1)
            
            start_row = display_data.iloc[0]
            end_row = display_data.iloc[-1]
            start_date = start_row['Last Trading Date']
            end_date = end_row['Last Trading Date']
            
            # --- Tampilan Grafik Harga ---
            st.markdown(f"#### Pergerakan Harga **{selected_stock}** ({selected_period_detail})")
            fig_price = go.Figure()
            fig_price.add_trace(go.Scatter(
                x=display_data['Last Trading Date'], y=display_data['Price'],
                name='Harga', mode='lines', line=dict(color='cyan', width=2)
            ))
            fig_price.update_layout(height=300, template='plotly_dark', margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_price, use_container_width=True)

            # --- Tabel Analisa Detail Kepemilikan ---
            st.markdown(f"#### Detail Perubahan Kepemilikan")
            st.caption(f"Periode: **{start_date.strftime('%d %b %Y')}** s/d **{end_date.strftime('%d %b %Y')}**")
            
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
                }).background_gradient(cmap='RdYlGn', subset=['Perubahan (Lembar)']),
                use_container_width=True, height=660
            )
        else:
            st.warning(f"Tidak cukup data historis untuk saham {selected_stock} pada periode yang dipilih.")
    else:
        st.warning("Gagal memuat data.")
