import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Dashboard Kesejahteraan Pekerja RI", 
    page_icon="🇮🇩", 
    layout="wide"
)

# --- LOAD DAN PREPROCESS DATA ---
@st.cache_data
def load_data():
    gk = pd.read_csv('garisKemiskinan.csv')
    mu = pd.read_csv('minUpah.csv')
    peng = pd.read_csv('pengeluaran.csv')
    ru = pd.read_csv('rataRataUpah.csv')

    # Pembersihan data numerik (mengubah string NA menjadi NaN)
    mu['ump'] = pd.to_numeric(mu['ump'], errors='coerce')
    ru['upah'] = pd.to_numeric(ru['upah'], errors='coerce')
    peng['peng'] = pd.to_numeric(peng['peng'], errors='coerce')
    gk['gk'] = pd.to_numeric(gk['gk'], errors='coerce')

    return gk, mu, peng, ru

gk_df, mu_df, peng_df, ru_df = load_data()

# Membuat dataset gabungan untuk komparasi (Tahun 2015-2022 karena irisan datanya lengkap)
@st.cache_data
def get_merged_data():
    df_peng = peng_df[(peng_df['jenis'] == 'TOTAL') & (peng_df['daerah'] == 'PERDESAANPERKOTAAN')]
    df_gk = gk_df[(gk_df['jenis'] == 'TOTAL') & (gk_df['daerah'] == 'PERDESAANPERKOTAAN') & (gk_df['periode'] == 'SEPTEMBER')]
    
    merged = pd.merge(mu_df, ru_df, on=['provinsi', 'tahun'], how='inner')
    merged = pd.merge(merged, df_peng[['provinsi', 'tahun', 'peng']], on=['provinsi', 'tahun'], how='inner')
    merged = pd.merge(merged, df_gk[['provinsi', 'tahun', 'gk']], on=['provinsi', 'tahun'], how='inner')
    merged.dropna(inplace=True)
    return merged

merged_df = get_merged_data()
list_provinsi = sorted([p for p in merged_df['provinsi'].unique() if p != 'INDONESIA'])

# --- SIDEBAR NAVIGASI ---
st.sidebar.title("🧭 Navigasi Dashboard")
menu = st.sidebar.radio(
    "Pilih Analisis:",
    ("Ringkasan Nasional", "Analisis per Provinsi", "Pola Pengeluaran & Kemiskinan")
)

st.sidebar.markdown("---")
st.sidebar.info(
    "**Asumsi Data:**\n"
    "*Data rata-rata upah adalah upah per jam. Upah bulanan pada dashboard ini "
    "diestimasi menggunakan parameter jam kerja per bulan.*"
)

# --- HALAMAN 1: RINGKASAN NASIONAL ---
if menu == "Ringkasan Nasional":
    st.title("🇮🇩 Ringkasan Kesejahteraan Nasional")
    st.markdown("Melihat potret kesejahteraan pekerja secara makro pada tahun tertentu.")
    
    year_selected = st.selectbox("Pilih Tahun:", sorted(merged_df['tahun'].unique(), reverse=True))
    
    # Filter Data untuk "INDONESIA" (Rata-rata Nasional)
    nasional_data = merged_df[(merged_df['provinsi'] == 'INDONESIA') & (merged_df['tahun'] == year_selected)]
    nasional_prev = merged_df[(merged_df['provinsi'] == 'INDONESIA') & (merged_df['tahun'] == year_selected - 1)]
    
    if not nasional_data.empty:
        # Metrik KPI
        col1, col2, col3, col4 = st.columns(4)
        
        def display_metric(col, title, current, previous):
            delta = float(current) - float(previous) if not previous.empty else None
            col.metric(title, f"Rp {float(current):,.0f}", f"Rp {delta:,.0f}" if delta else None)

        display_metric(col1, "Rata-rata UMP Nasional", nasional_data['ump'].values[0], nasional_prev['ump'] if not nasional_prev.empty else pd.Series())
        display_metric(col2, "Upah Per Jam Nasional", nasional_data['upah'].values[0], nasional_prev['upah'] if not nasional_prev.empty else pd.Series())
        display_metric(col3, "Pengeluaran Per Kapita", nasional_data['peng'].values[0], nasional_prev['peng'] if not nasional_prev.empty else pd.Series())
        display_metric(col4, "Garis Kemiskinan Nasional", nasional_data['gk'].values[0], nasional_prev['gk'] if not nasional_prev.empty else pd.Series())
        
        st.markdown("---")
        
        # Peringkat Provinsi
        st.subheader(f"Perbandingan Antar Provinsi ({year_selected})")
        prov_only = merged_df[(merged_df['tahun'] == year_selected) & (merged_df['provinsi'] != 'INDONESIA')]
        
        fig_bar = px.bar(
            prov_only.sort_values('ump', ascending=False), 
            x='provinsi', y='ump', 
            color='ump', color_continuous_scale='Viridis',
            title='Peringkat UMP per Provinsi',
            labels={'ump': 'Upah Minimum (Rp)', 'provinsi': 'Provinsi'}
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Scatter Plot Upah vs Pengeluaran
        fig_scatter = px.scatter(
            prov_only, x='ump', y='peng', color='provinsi', size='gk',
            hover_name='provinsi',
            title='Korelasi UMP vs Pengeluaran (Besar Bubble = Garis Kemiskinan)',
            labels={'ump': 'UMP (Rp)', 'peng': 'Pengeluaran Per Kapita (Rp)'}
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# --- HALAMAN 2: ANALISIS PER PROVINSI ---
elif menu == "Analisis per Provinsi":
    st.title("📍 Analisis Kesejahteraan Provinsi")
    st.markdown("Bandingkan laju kenaikan Upah dengan Pengeluaran dan Garis Kemiskinan dari tahun ke tahun.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        prov_selected = st.selectbox("Pilih Provinsi:", ['INDONESIA'] + list_provinsi)
        # Slider jam kerja untuk menghitung upah bulanan
        jam_kerja = st.slider("Asumsi Jam Kerja per Bulan", min_value=100, max_value=240, value=160, step=8,
                              help="Digunakan untuk mengubah Upah per Jam menjadi Estimasi Upah Bulanan.")
    
    prov_data = merged_df[merged_df['provinsi'] == prov_selected].copy()
    prov_data = prov_data.sort_values('tahun')
    prov_data['upah_bulanan'] = prov_data['upah'] * jam_kerja
    
    st.markdown(f"### Tren Indikator Ekonomi Kesejahteraan: {prov_selected}")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prov_data['tahun'], y=prov_data['ump'], mode='lines+markers', name='UMP (Upah Minimum)', line=dict(color='blue', width=3)))
    fig.add_trace(go.Scatter(x=prov_data['tahun'], y=prov_data['upah_bulanan'], mode='lines+markers', name=f'Est. Upah Bulanan ({jam_kerja} jam)', line=dict(color='green', width=3)))
    fig.add_trace(go.Scatter(x=prov_data['tahun'], y=prov_data['peng'], mode='lines+markers', name='Pengeluaran Per Kapita', line=dict(color='orange', dash='dash')))
    fig.add_trace(go.Scatter(x=prov_data['tahun'], y=prov_data['gk'], mode='lines+markers', name='Garis Kemiskinan', line=dict(color='red', dash='dot')))
    
    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Tahun",
        yaxis_title="Rupiah (Rp)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- HALAMAN 3: POLA PENGELUARAN & KEMISKINAN ---
elif menu == "Pola Pengeluaran & Kemiskinan":
    st.title("🛒 Pola Pengeluaran & Kemiskinan")
    st.markdown("Menganalisis perbandingan porsi konsumsi masyarakat dan beda garis kemiskinan antara Desa vs Kota.")
    
    prov_selected = st.selectbox("Pilih Provinsi:", ['INDONESIA'] + list_provinsi, key='prov_tab3')
    
    tab1, tab2 = st.tabs(["Proporsi Pengeluaran", "Kemiskinan Desa vs Kota"])
    
    with tab1:
        st.subheader("Makanan vs Non-Makanan")
        # Filter Pengeluaran
        peng_prov = peng_df[(peng_df['provinsi'] == prov_selected) & (peng_df['daerah'] == 'PERDESAANPERKOTAAN') & (peng_df['jenis'] != 'TOTAL')]
        if not peng_prov.empty:
            fig_peng = px.bar(
                peng_prov.sort_values('tahun'), x='tahun', y='peng', color='jenis', 
                barmode='stack', title=f"Proporsi Pengeluaran {prov_selected}",
                labels={'peng': 'Pengeluaran (Rp)', 'tahun': 'Tahun', 'jenis': 'Jenis Konsumsi'},
                color_discrete_sequence=['#FF9900', '#3366CC']
            )
            st.plotly_chart(fig_peng, use_container_width=True)
            
    with tab2:
        st.subheader("Kesenjangan Garis Kemiskinan: Desa vs Kota")
        # Filter Garis Kemiskinan (Maret vs September di-rata-rata)
        gk_prov = gk_df[(gk_df['provinsi'] == prov_selected) & (gk_df['jenis'] == 'TOTAL') & (gk_df['daerah'] != 'PERDESAANPERKOTAAN')]
        gk_agg = gk_prov.groupby(['tahun', 'daerah'])['gk'].mean().reset_index()
        
        if not gk_agg.empty:
            fig_gk = px.line(
                gk_agg, x='tahun', y='gk', color='daerah', markers=True,
                title=f"Pergerakan Garis Kemiskinan {prov_selected}",
                labels={'gk': 'Rata-rata Garis Kemiskinan (Rp)', 'tahun': 'Tahun', 'daerah': 'Wilayah'},
                color_discrete_sequence=['#109618', '#DC3912']
            )
            st.plotly_chart(fig_gk, use_container_width=True)

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>Data Source: BPS Indonesia | Dibuat menggunakan Streamlit & Plotly</p>", unsafe_allow_html=True)