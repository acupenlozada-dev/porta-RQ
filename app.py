import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
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
    .badge-cargado { background-color: #2196F3; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem; }
    .badge-ruta { background-color: #FF9800; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem; }
    .badge-recibido { background-color: #4CAF50; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem; }
    .badge-anulado { background-color: #F44336; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h3>PORTA · CONTROL DE REQUISICIONES Y REPOSICIÓN</h3></div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. CARGA Y LIMPIEZA DE DATOS (GOOGLE SHEETS)
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Reemplaza 'DB_REQUISICIONES' por el nombre de la pestaña en tu Google Sheet
    df = conn.read(worksheet="RQ")
    
    # Asegurar tipos de datos adecuados
    df['RequisicionNumero'] = df['RequisicionNumero'].astype(str).str.zfill(10)
    df['Item'] = df['Item'].astype(str).str.zfill(10)
    df['CantidadPedida'] = pd.to_numeric(df['CantidadPedida'], errors='coerce').fillna(0)
    df['CantidadRecibida'] = pd.to_numeric(df['CantidadRecibida'], errors='coerce').fillna(0)
    
    # Rellenar nulos en campos de texto
    for col in ['GuiaNumero', 'NT', 'SituacionRQ', 'NombreAlmacenDestinoRQ', 'Descripcion']:
        if col in df.columns:
            df[col] = df[col].fillna("-").astype(str)
            
    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# ---------------------------------------------------------
# 3. FILTROS Y SIDEBAR
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Filtros de Selección")
    
    # 1. Filtro Principal: Nombre Almacen Destino (Tiendas)
    tiendas_disponibles = sorted([t for t in df_raw['NombreAlmacenDestinoRQ'].unique() if t != "-"])
    tienda_selected = st.selectbox(
        "🏪 Seleccionar Tienda Destino:",
        options=["-- TODAS LAS TIENDAS --"] + tiendas_disponibles
    )
    
    # 2. Filtro Secundario: Situación de Requisición
    situaciones_disp = sorted(df_raw['SituacionRQ'].unique())
    situacion_selected = st.multiselect(
        "📦 Situación RQ:",
        options=situaciones_disp,
        default=situaciones_disp
    )
    
    # 3. Buscador por Producto / Requisición / Guía
    search_query = st.text_input("🔍 Buscar SKU, Descripción, RQ o Guía:", "").strip()
    
    # Botón para refrescar caché
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------
# 4. APLICACIÓN DE FILTROS
# ---------------------------------------------------------
df_filtered = df_raw.copy()

if tienda_selected != "-- TODAS LAS TIENDAS --":
    df_filtered = df_filtered[df_filtered['NombreAlmacenDestinoRQ'] == tienda_selected]

if situacion_selected:
    df_filtered = df_filtered[df_filtered['SituacionRQ'].isin(situacion_selected)]

if search_query:
    q = search_query.lower()
    df_filtered = df_filtered[
        df_filtered['Item'].str.lower().str.contains(q) |
        df_filtered['Descripcion'].str.lower().str.contains(q) |
        df_filtered['RequisicionNumero'].str.lower().str.contains(q) |
        df_filtered['GuiaNumero'].str.lower().str.contains(q)
    ]

# ---------------------------------------------------------
# 5. RESUMEN DE KPIS
# ---------------------------------------------------------
m1, m2, m3, m4, m5 = st.columns(5)

total_rqs = df_filtered['RequisicionNumero'].nunique()
cant_pedida = df_filtered['CantidadPedida'].sum()
cant_recibida = df_filtered['CantidadRecibida'].sum()
en_ruta = df_filtered[df_filtered['SituacionRQ'] == 'En Ruta']['CantidadPedida'].sum()
cargados = df_filtered[df_filtered['SituacionRQ'] == 'Cargado']['CantidadPedida'].sum()

m1.metric("📦 Requisiciones", f"{total_rqs:,}")
m2.metric("📋 Cant. Pedida", f"{int(cant_pedida):,}")
m3.metric("🔵 Cargado", f"{int(cargados):,}")
m4.metric("🟡 En Ruta", f"{int(en_ruta):,}")
m5.metric("🟢 Recibido", f"{int(cant_recibida):,}")

st.divider()

# ---------------------------------------------------------
# 6. VISTA DETALLADA POR REQUISICIÓN (DESPLEGABLES)
# ---------------------------------------------------------
st.subheader("📋 Detalle de Cargas por Requisición")

if df_filtered.empty:
    st.info("No se encontraron requisiciones para los filtros seleccionados.")
else:
    # Agrupar por Requisición
    rq_groups = df_filtered.groupby('RequisicionNumero')
    
    # Ordenar Requisiciones de forma descendente
    sorted_rqs = sorted(rq_groups.groups.keys(), reverse=True)

    for rq in sorted_rqs:
        df_rq = rq_groups.get_group(rq)
        
        # Datos resumen de la Requisición
        situacion = df_rq['SituacionRQ'].iloc[0]
        destino = df_rq['NombreAlmacenDestinoRQ'].iloc[0]
        guia = df_rq['GuiaNumero'].iloc[0]
        f_rq = df_rq['FechaRQ'].iloc[0] if 'FechaRQ' in df_rq.columns else "-"
        tot_items = df_rq['Item'].nunique()
        tot_ped = int(df_rq['CantidadPedida'].sum())
        tot_rec = int(df_rq['CantidadRecibida'].sum())
        
        # Emoji / Estado
        status_icon = "🔵" if situacion == "Cargado" else "🟡" if situacion == "En Ruta" else "🟢" if situacion == "Recibido" else "⚪"
        
        # Título del Expander
        expander_title = f"{status_icon} RQ: {rq} | {destino} | Estado: {situacion} | Guía: {guia} | Pedido: {tot_ped} Uds | {tot_items} SKUs"
        
        with st.expander(expander_title, expanded=False):
            # Encabezado informativo de la Requisición
            c1, c2, c3, c4 = st.columns(4)
            c1.caption(f"**Fecha RQ:** {f_rq}")
            c2.caption(f"**Nº Guía:** {guia}")
            c3.caption(f"**Origen:** {df_rq['NombreAlmacenOrigenRQ'].iloc[0] if 'NombreAlmacenOrigenRQ' in df_rq.columns else '-'}")
            c4.caption(f"**NT:** {df_rq['NT'].iloc[0] if 'NT' in df_rq.columns else '-'}")
            
            # Tabla de Productos en la RQ
            cols_show = ['Secuencia', 'Item', 'Descripcion', 'CantidadPedida', 'CantidadRecibida', 'EstadoDetalle']
            cols_exist = [c for c in cols_show if c in df_rq.columns]
            
            st.dataframe(
                df_rq[cols_exist].sort_values(by='Secuencia' if 'Secuencia' in df_rq.columns else 'Item'),
                use_container_width=True,
                hide_index=True
            )
