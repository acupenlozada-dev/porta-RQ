import os
import shutil
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# ---------------------------------------------------------
# 1. PARCHE / FIX PARA SECRETS EN RENDER
# ---------------------------------------------------------
# Si Render guardó el Secret File en la raíz como 'secrets.toml',
# lo copiamos automáticamente a '.streamlit/secrets.toml'
if os.path.exists("secrets.toml") and not os.path.exists(".streamlit/secrets.toml"):
    os.makedirs(".streamlit", exist_ok=True)
    shutil.copy("secrets.toml", ".streamlit/secrets.toml")

# ---------------------------------------------------------
# 2. CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Porta · Seguimiento de Requisiciones",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #8B0000 0%, #C8102E 100%);
        padding: 12px 18px;
        border-radius: 8px;
        color: white;
        margin-bottom: 15px;
    }
    .main-header h3 {
        margin: 0;
        font-size: 1.3rem;
        font-weight: 800;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h3>PORTA · CONTROL DE REQUISICIONES Y REPOSICIÓN</h3></div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. CARGA Y LIMPIEZA DE DATOS (GOOGLE SHEETS)
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Intenta leer la pestaña 'DB_REQUISICIONES'; si no existe o falla, lee la primera hoja disponible
    try:
        df = conn.read(worksheet="DB_REQUISICIONES")
    except Exception:
        df = conn.read() # Lee la primera pestaña del archivo
    
    # Limpieza de columnas
    if 'RequisicionNumero' in df.columns:
        df['RequisicionNumero'] = df['RequisicionNumero'].astype(str).str.zfill(10)
    if 'Item' in df.columns:
        df['Item'] = df['Item'].astype(str).str.zfill(10)
        
    df['CantidadPedida'] = pd.to_numeric(df.get('CantidadPedida', 0), errors='coerce').fillna(0)
    df['CantidadRecibida'] = pd.to_numeric(df.get('CantidadRecibida', 0), errors='coerce').fillna(0)
    
    cols_texto = ['GuiaNumero', 'NT', 'SituacionRQ', 'NombreAlmacenDestinoRQ', 'NombreAlmacenOrigenRQ', 'Descripcion', 'EstadoDetalle']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("-").astype(str)
            
    return df

# ---------------------------------------------------------
# 4. FILTROS Y BARRA LATERAL (SIDEBAR)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Filtros de Selección")
    
    # 1. Filtro Principal: Tienda Destino
    tiendas_disponibles = sorted([t for t in df_raw['NombreAlmacenDestinoRQ'].unique() if t != "-"])
    tienda_selected = st.selectbox(
        "🏪 Seleccionar Tienda Destino:",
        options=["-- TODAS LAS TIENDAS --"] + tiendas_disponibles
    )
    
    # 2. Filtro Secundario: Estado / Situación de Requisición
    situaciones_disp = sorted(df_raw['SituacionRQ'].unique())
    situacion_selected = st.multiselect(
        "📦 Situación RQ:",
        options=situaciones_disp,
        default=situaciones_disp
    )
    
    # 3. Buscador General
    search_query = st.text_input("🔍 Buscar SKU, Descripción, RQ o Guía:", "").strip()
    
    st.divider()
    
    # Botón para refrescar la memoria caché si
