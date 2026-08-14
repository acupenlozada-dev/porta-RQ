import os
import shutil
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# ---------------------------------------------------------
# 1. PARCHE / FIX PARA SECRETS EN RENDER
# ---------------------------------------------------------
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
# 3. CARGA Y OPTIMIZACIÓN VECTORIAL DE DATOS
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        df = conn.read(worksheet="DB_REQUISICIONES")
    except Exception:
        df = conn.read()
    
    # Formateo ultra-rápido vectorizado
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

    # Columna unificada para búsquedas ultrarrápidas
    df['_search_text'] = (
        df.get('Item', '') + " " + 
        df.get('Descripcion', '') + " " + 
        df.get('RequisicionNumero', '') + " " + 
        df.get('GuiaNumero', '')
    ).str.lower()
            
    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.info("Asegúrate de haber guardado el archivo 'secrets.toml' en Render y compartido la hoja con la Service Account.")
    st.stop()

# ---------------------------------------------------------
# 4. FILTROS Y BARRA LATERAL (SIDEBAR)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Filtros de Selección")
    
    tiendas_disponibles = sorted([t for t in df_raw['NombreAlmacenDestinoRQ'].unique() if t != "-"])
    tienda_selected = st.selectbox(
        "🏪 Seleccionar Tienda Destino:",
        options=["-- TODAS LAS TIENDAS --"] + tiendas_disponibles
    )
    
    situaciones_disp = sorted(df_raw['SituacionRQ'].unique())
    situacion_selected = st.multiselect(
        "📦 Situación RQ:",
        options=situaciones_disp,
        default=situaciones_disp
    )
    
    search_query = st.text_input("🔍 Buscar SKU, Descripción, RQ o Guía:", "").strip().lower()
    
    st.divider()
    
    # Límite de paginación para mantener velocidad
    items_per_page = st.selectbox("⚡ Requisiciones a mostrar por página:", [10, 20, 50, 100], index=1)
    
    st.divider()
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------
# 5. APLICACIÓN DE FILTROS A LA DATA
# ---------------------------------------------------------
df_filtered = df_raw.copy()

if tienda_selected != "-- TODAS LAS TIENDAS --":
    df_filtered = df_filtered[df_filtered['NombreAlmacenDestinoRQ'] == tienda_selected]

if situacion_selected:
    df_filtered = df_filtered[df_filtered['SituacionRQ'].isin(situacion_selected)]

if search_query:
    df_filtered = df_filtered[df_filtered['_search_text'].str.contains(search_query, na=False)]

# ---------------------------------------------------------
# 6. RESUMEN DE METRICAS (KPIS)
# ---------------------------------------------------------
m1, m2, m3, m4, m5 = st.columns(5)

total_rqs = df_filtered['RequisicionNumero'].nunique()
cant_pedida = df_filtered['CantidadPedida'].sum()
cant_recibida = df_filtered['CantidadRecibida'].sum()

# Filtrado rápido de métricas
en_ruta = df_filtered[df_filtered['SituacionRQ'] == 'En Ruta']['CantidadPedida'].sum()
cargados = df_filtered[df_filtered['SituacionRQ'] == 'Cargado']['CantidadPedida'].sum()

m1.metric("📦 Requisiciones", f"{total_rqs:,}")
m2.metric("📋 Cant. Pedida", f"{int(cant_pedida):,}")
m3.metric("🔵 Cargado", f"{int(cargados):,}")
m4.metric("🟡 En Ruta", f"{int(en_ruta):,}")
m5.metric("🟢 Recibido", f"{int(cant_recibida):,}")

st.divider()

# ---------------------------------------------------------
# 7. VISTA DETALLADA POR REQUISICIÓN (PAGINADA PARA MÁXIMA VELOCIDAD)
# ---------------------------------------------------------
st.subheader("📋 Detalle de Cargas por Requisición")

if df_filtered.empty:
    st.warning("No se encontraron requisiciones que coincidan con los filtros seleccionados.")
else:
    # Agrupar por RQ y ordenar
    sorted_rqs = sorted(df_filtered['RequisicionNumero'].unique(), reverse=True)
    total_pages = (len(sorted_rqs) - 1) // items_per_page + 1

    # Controles de Paginación si hay más de 1 página
    if total_pages > 1:
        col_p1, col_p2 = st.columns([1, 4])
        page = col_p1.number_input(f"Página (1 de {total_pages})", min_value=1, max_value=total_pages, value=1, step=1)
    else:
        page = 1

    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    visible_rqs = sorted_rqs[start_idx:end_idx]

    # Filtrar solo la data necesaria para las RQ visibles
    df_visible = df_filtered[df_filtered['RequisicionNumero'].isin(visible_rqs)]
    rq_groups = df_visible.groupby('RequisicionNumero')

    for rq in visible_rqs:
        if rq not in rq_groups.groups:
            continue
            
        df_rq = rq_groups.get_group(rq)
        
        situacion = df_rq['SituacionRQ'].iloc[0]
        destino = df_rq['NombreAlmacenDestinoRQ'].iloc[0]
        guia = df_rq['GuiaNumero'].iloc[0]
        f_rq = df_rq['FechaRQ'].iloc[0] if 'FechaRQ' in df_rq.columns else "-"
        tot_items = df_rq['Item'].nunique()
        tot_ped = int(df_rq['CantidadPedida'].sum())
        
        status_icon = "🔵" if situacion == "Cargado" else "🟡" if situacion == "En Ruta" else "🟢" if situacion == "Recibido" else "⚪"
        expander_title = f"{status_icon} RQ: {rq} | {destino} | Estado: {situacion} | Guía: {guia} | Pedido: {tot_ped} Uds | SKUs: {tot_items}"
        
        with st.expander(expander_title, expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.caption(f"**Fecha RQ:** {f_rq}")
            c2.caption(f"**Nº Guía:** {guia}")
            c3.caption(f"**Origen:** {df_rq['NombreAlmacenOrigenRQ'].iloc[0] if 'NombreAlmacenOrigenRQ' in df_rq.columns else '-'}")
            c4.caption(f"**NT:** {df_rq['NT'].iloc[0] if 'NT' in df_rq.columns else '-'}")
            
            cols_show = ['Secuencia', 'Item', 'Descripcion', 'CantidadPedida', 'CantidadRecibida', 'EstadoDetalle']
            cols_exist = [c for c in cols_show if c in df_rq.columns]
            
            st.dataframe(
                df_rq[cols_exist].sort_values(by='Secuencia' if 'Secuencia' in df_rq.columns else 'Item'),
                use_container_width=True,
                hide_index=True
            )
