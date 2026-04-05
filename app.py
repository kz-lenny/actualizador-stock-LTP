import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os

# -----------------------------
# CONFIGURACIÓN GENERAL
# -----------------------------
st.set_page_config(page_title="Sincronizador de Stock - LTP", layout="wide")

st.title("Sincronizador de Stock y precios Contabilium --> LTP")
st.caption("La Tienda Pinturas")

col_producto = "SKU"
col_stock = "Stock"
col_precio = "Precio"

# -----------------------------
# ESTILOS
# -----------------------------
st.markdown("""
<style>

/* ------------------ FONDO GENERAL ------------------ */
.stApp {
    background: linear-gradient(135deg, #0A1543, #020617);
    font-family: 'Segoe UI', sans-serif;
}

/* ------------------ CONTENEDOR PRINCIPAL ------------------ */
.block-container {
    padding: 2rem;
}

/* ------------------ TÍTULOS ------------------ */
h1 {
    color: #F5E409;
    font-weight: 700;
}

h2, h3 {
    color: white;
}

/* ------------------ TEXTO CON CONTORNO ------------------ */
p, label, span {
    color: white;
    -webkit-text-stroke: 0.3px black;
    text-shadow:
        -1px -1px 0 rgba(0,0,0,0.5),
         1px -1px 0 rgba(0,0,0,0.5),
        -1px  1px 0 rgba(0,0,0,0.5),
         1px  1px 0 rgba(0,0,0,0.5);
}

/* ------------------ CARDS (contenedores) ------------------ */
.css-1r6slb0, .css-12w0qpk {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    padding: 15px;
    border: 1px solid rgba(255,255,255,0.1);
}

/* ------------------ BOTONES ------------------ */
.stButton>button {
    background: linear-gradient(45deg, #F40A09, #ff3c2f);
    color: white;
    border-radius: 10px;
    border: none;
    padding: 10px 15px;
    font-weight: bold;
    transition: 0.2s;
}

.stButton>button:hover {
    transform: scale(1.05);
    background: linear-gradient(45deg, #ff3c2f, #F40A09);
}

/* ------------------ BOTÓN DESCARGA ------------------ */
.stDownloadButton>button {
    background: linear-gradient(45deg, #05F81B, #00c914);
    color: black;
    border-radius: 10px;
    font-weight: bold;
}

/* ------------------ INPUTS ------------------ */
input, .stTextInput input {
    background: white;
    color: black;
    border-radius: 8px;
}

/* ------------------ SELECT ------------------ */
.stSelectbox div {
    background: white;
    color: black;
    border-radius: 8px;
}

/* ------------------ RADIO ------------------ */
.stRadio label {
    color: white;
}

/* ------------------ MÉTRICAS (números grandes) ------------------ */
[data-testid="stMetricValue"] {
    color: #05F81B;
    font-weight: bold;
}

/* ------------------ TABLAS ------------------ */
[data-testid="stDataFrame"] {
    background-color: rgba(255,255,255,0.05);
    border-radius: 10px;
    padding: 10px;
}

/* ------------------ SCROLLBAR PRO ------------------ */
::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-thumb {
    background: #F40A09;
    border-radius: 10px;
}
            
/* Ocultar barra superior de Streamlit */
header {
    visibility: hidden;
}

/* Opcional: también oculta el footer */
footer {
    visibility: hidden;
}

/* Quitar espacio que deja la barra */
.block-container {
    padding-top: 1rem;
}


</style>
""", unsafe_allow_html=True)

# -----------------------------
# ACCIONES
# -----------------------------
st.subheader("⚙️ Acción a realizar")

accion = st.radio(
    "Seleccionar operación:",
    ["Actualizar Stock", "Actualizar precios", "Actualizar ambos"],
    horizontal=True
)

simulacion = st.toggle("🧪 Modo simulación (no aplicar cambios)")

# -----------------------------
# ARCHIVOS
# -----------------------------
st.subheader("📂 Cargar archivos .XLSX")

col1, col2 = st.columns(2)

with col1:
    archivo_a = st.file_uploader("Archivo A (template bajado de Tienda Negocio, renombrar a 'archivo_a.xlsx')", type=["xlsx"])

with col2:
    archivo_b = st.file_uploader("Archivo B (bajado de Contabilium con stock actualizado, renombrar a 'archivo_b.xlsx')", type=["xlsx"])

# -----------------------------
# PROCESAMIENTO
# -----------------------------
if archivo_a and archivo_b:

    # Leer archivos (para filtros)
    df_a = pd.read_excel(archivo_a)
    df_b = pd.read_excel(archivo_b)

    # -----------------------------
    # FILTROS
    # -----------------------------
    st.subheader("🔎 Filtros")

    if "Categoria" in df_a.columns:
        categorias = ["Todas"] + sorted(df_a["Categoria"].dropna().unique().tolist())
        categoria_sel = st.selectbox("Filtrar por categoría", categorias)
    else:
        categoria_sel = "Todas"

    busqueda = st.text_input("Buscar producto por SKU")

    # -----------------------------
    # BOTÓN EJECUTAR
    # -----------------------------
    if st.button("🚀 Ejecutar comparación"):

        # NORMALIZACIÓN
        df_a["sku_norm"] = (
            df_a[col_producto]
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(" ", "", regex=False)
        )

        df_b["sku_norm"] = (
            df_b[col_producto]
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(" ", "", regex=False)
        )


        df_a[col_stock] = (
            df_a[col_stock]
            .astype(str)
            .str.replace(".", "", regex=False)   # elimina separador de miles
            .str.replace(",", ".", regex=False)  # convierte decimal
        .str.strip()
        )

        df_b[col_stock] = (
            df_b[col_stock]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )

        df_a[col_stock] = pd.to_numeric(df_a[col_stock], errors='coerce')
        df_b[col_stock] = pd.to_numeric(df_b[col_stock], errors='coerce')

        df_a[col_stock] = df_a[col_stock].fillna(0)
        df_b[col_stock] = df_b[col_stock].fillna(0)

        df_a[col_precio] = (
            df_a[col_precio]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )

        df_b[col_precio] = (
            df_b[col_precio]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )

        df_a[col_precio] = pd.to_numeric(df_a[col_precio], errors='coerce')
        df_b[col_precio] = pd.to_numeric(df_b[col_precio], errors='coerce')

        stock_b = dict(zip(df_b["sku_norm"], df_b[col_stock]))
        precio_b = dict(zip(df_b["sku_norm"], df_b[col_precio]))

        # VARIABLES
        cambios = []
        aumentos = []
        bajadas = []
        sin_stock = []

        # FILTROS APLICADOS
        df_filtrado = df_a.copy()

        if categoria_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Categoria"] == categoria_sel]

        if busqueda:
            df_filtrado = df_filtrado[
                df_filtrado[col_producto].str.contains(busqueda, case=False, na=False)
            ]
        
        # -DEBUG-
        st.write("Cantidad productos archivo A (Tienda Negocios):", len(df_a))
        st.write("Cantidad productos arcvhivo B (Contabilium):", len(df_b))
        # -DEBUG-

        # -----------------------------
        # PROCESAMIENTO
        # -----------------------------
        for i, row in df_filtrado.iterrows():

            prod_norm = row["sku_norm"]
            prod_real = row[col_producto]

            if prod_norm in stock_b:

                stock_a = row[col_stock]
                nuevo_stock = stock_b[prod_norm]

                precio_a = row[col_precio]
                nuevo_precio = precio_b.get(prod_norm)

                cambio = {}

                # STOCK
                if accion in ["Actualizar Stock", "Actualizar ambos"]:
                    if stock_a != nuevo_stock:
                        cambio["Stock"] = f"{stock_a} → {nuevo_stock}"
                        if not simulacion:
                            df_a.at[i, col_stock] = nuevo_stock

                # PRECIO
                if accion in ["Actualizar precios", "Actualizar ambos"]:
                    if precio_a != nuevo_precio:
                        cambio["Precio"] = f"{precio_a} → {nuevo_precio}"

                        if pd.notna(precio_a) and pd.notna(nuevo_precio):
                            if nuevo_precio > precio_a:
                                aumentos.append(prod_real)
                            elif nuevo_precio < precio_a:
                                bajadas.append(prod_real)

                        if not simulacion:
                            df_a.at[i, col_precio] = nuevo_precio

                if cambio:
                    cambios.append({"SKU": prod_real, **cambio})

            if row[col_stock] <= 0:
                sin_stock.append(prod_real)
            # -DEBUG-
            #if prod_norm in stock_b:
            #    st.write("Comparando:", prod_real, stock_a, "vs", nuevo_stock)
            # -DEBUG-

        # -----------------------------
        # RESULTADOS
        # -----------------------------
        st.subheader("📊 Resultados")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cambios", len(cambios))
        m2.metric("Sin stock", len(sin_stock))
        m3.metric("Aumentos", len(aumentos))
        m4.metric("Bajadas", len(bajadas))

        # -----------------------------
        #GRÁFICO DE CAMBIOS
        # -----------------------------
        st.subheader("📊 Visualización")

        df_graf = pd.DataFrame({   
            "Tipo": ["Cambios", "Sin stock", "Aumentos", "Bajadas"],
            "Cantidad": [len(cambios), len(sin_stock), len(aumentos), len(bajadas)]
        })

        st.bar_chart(df_graf, x="Tipo", y="Cantidad")


        # -----------------------------
        # TABLA
        # -----------------------------
        if cambios:
            with st.expander("📋 Ver cambios", expanded=True):

                df_cambios = pd.DataFrame(cambios)

                # -----------------------------
                # COLORES EN CAMBIOS
                # -----------------------------
                def colorear_cambios(val):
                    try:
                        if "→" in str(val):
                            antes, despues = val.split("→")
                            antes = float(antes.strip())
                            despues = float(despues.strip())

                            if despues > antes:
                                 return "color: #05F81B; font-weight: bold;"  # verde
                            elif despues < antes:
                                 return "color: #F40A09; font-weight: bold;"  # rojo
                    except:
                         pass
                    return ""


                df_style = df_cambios.style.map(colorear_cambios)

                st.dataframe(df_style, use_container_width=True, height=400)
        else:
            st.success("No se detectaron cambios 🎉")

        # -----------------------------
        # DETALLES
        # -----------------------------
        colA, colB, colC = st.columns(3)

        with colA:
            if aumentos:
                with st.expander("📈 Aumentos"):
                    st.dataframe(pd.DataFrame(aumentos, columns=["SKU"]))

        with colB:
            if bajadas:
                with st.expander("📉 Bajadas"):
                    st.dataframe(pd.DataFrame(bajadas, columns=["SKU"]))

        with colC:
            if sin_stock:
                with st.expander("⚠️ Sin stock"):
                    st.dataframe(pd.DataFrame(sin_stock, columns=["SKU"]))

        # -----------------------------
        # DESCARGA PRINCIPAL
        # -----------------------------
        output = BytesIO()
        df_a.to_excel(output, index=False)
        output.seek(0)

        st.download_button(
            "⬇️ Descargar archivo actualizado",
            data=output,
            file_name="productos_actualizados.xlsx"
        )

        # -----------------------------
        # EXPORTES
        # -----------------------------
        st.divider()
        st.subheader("📦 Exportes")

        def generar_excel(df):
            output = BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            return output

        col_exp1, col_exp2, col_exp3 = st.columns(3)

        with col_exp1:
            if cambios:
                st.download_button(
                    "📄 Cambios",
                    data=generar_excel(pd.DataFrame(cambios)),
                    file_name="cambios.xlsx"
                )

        with col_exp2:
            if sin_stock:
                st.download_button(
                    "⚠️ Sin stock",
                    data=generar_excel(pd.DataFrame(sin_stock, columns=["SKU"])),
                    file_name="sin_stock.xlsx"
                )

        with col_exp3:
            if aumentos or bajadas:
                df_precios = pd.DataFrame({
                    "Aumentos": pd.Series(aumentos),
                    "Bajadas": pd.Series(bajadas)
                })

                st.download_button(
                    "💲 Cambios de precios",
                    data=generar_excel(df_precios),
                    file_name="cambios_precios.xlsx"
                )

        # -----------------------------
        # HISTORIAL
        # -----------------------------
        if not simulacion:
            df_hist = pd.DataFrame(cambios)
            df_hist["fecha"] = datetime.now()

            if os.path.exists("historial_cambios.csv"):
                df_hist.to_csv("historial_cambios.csv", mode='a', header=False, index=False)
            else:
                df_hist.to_csv("historial_cambios.csv", index=False)
