import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# =============================================================================
# CONFIGURACIÓN GENERAL
# Nombres de columnas esperadas en ambos archivos Excel.
# Si en algún momento cambian los headers, solo hay que modificar estas tres
# constantes y el resto del código se adapta automáticamente.
# =============================================================================
st.set_page_config(page_title="Sincronizador de Stock - LTP", layout="wide")

COL_SKU    = "SKU"
COL_STOCK  = "Stock"
COL_PRECIO = "Precio"

# =============================================================================
# ESTILOS
# Tema oscuro azul/rojo corporativo de La Tienda Pinturas.
# Nota: las clases .css-* son internas de Streamlit y pueden cambiar entre
# versiones. Si los estilos de cards se rompen al actualizar, revisar esas
# clases con el inspector del navegador y actualizar acá.
# =============================================================================
st.markdown("""
<style>

/* FONDO GENERAL */
.stApp {
    background: linear-gradient(135deg, #0A1543, #020617);
    font-family: 'Segoe UI', sans-serif;
}

/* CONTENEDOR PRINCIPAL */
.block-container {
    padding: 2rem;
    padding-top: 1rem;
}

/* TÍTULOS */
h1 { color: #F5E409; font-weight: 700; }
h2, h3 { color: white; }

/* TEXTO GENERAL CON CONTORNO (mejora legibilidad sobre fondo oscuro) */
p, label, span {
    color: white;
    -webkit-text-stroke: 0.3px black;
    text-shadow:
        -1px -1px 0 rgba(0,0,0,0.5),
         1px -1px 0 rgba(0,0,0,0.5),
        -1px  1px 0 rgba(0,0,0,0.5),
         1px  1px 0 rgba(0,0,0,0.5);
}

/* BOTÓN PRINCIPAL */
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

/* BOTÓN DE DESCARGA */
.stDownloadButton>button {
    background: linear-gradient(45deg, #05F81B, #00c914);
    color: black;
    border-radius: 10px;
    font-weight: bold;
}

/* INPUTS DE TEXTO */
input, .stTextInput input {
    background: white;
    color: black;
    border-radius: 8px;
}

/* SELECTBOX */
.stSelectbox div {
    background: white;
    color: black;
    border-radius: 8px;
}

/* RADIO BUTTONS */
.stRadio label { color: white; }

/* MÉTRICAS (números grandes del resumen) */
[data-testid="stMetricValue"] {
    color: #05F81B;
    font-weight: bold;
}

/* TABLAS */
[data-testid="stDataFrame"] {
    background-color: rgba(255,255,255,0.05);
    border-radius: 10px;
    padding: 10px;
}

/* SCROLLBAR PERSONALIZADA */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-thumb {
    background: #F40A09;
    border-radius: 10px;
}

/* OCULTAR HEADER Y FOOTER DE STREAMLIT */
header { visibility: hidden; }
footer { visibility: hidden; }

</style>
""", unsafe_allow_html=True)


# =============================================================================
# ENCABEZADO
# =============================================================================
st.title("Sincronizador de Stock y Precios — Contabilium → LTP")
st.caption("La Tienda Pinturas")


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

@st.cache_data
def cargar_excel(archivo):
    """
    Lee un archivo Excel y lo devuelve como DataFrame.
    Usa caché de Streamlit para no releer el archivo en cada
    interacción del usuario (mejora rendimiento notablemente).
    """
    return pd.read_excel(archivo)


def normalizar_sku(serie: pd.Series) -> pd.Series:
    """
    Normaliza una columna de SKUs para comparación sin falsos negativos.
    Convierte a minúsculas, elimina espacios y strips de espacios laterales.
    Ejemplo: '  ABC 123 ' → 'abc123'
    """
    return (
        serie.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "", regex=False)
    )


def parsear_numero_argentino(serie: pd.Series) -> pd.Series:
    """
    Convierte una columna de números en formato argentino a float.

    Formato esperado: coma como separador decimal, sin separador de miles.
    Ejemplos válidos: '116100,83' → 116100.83 | '62000' → 62000.0

    Por qué NO se usa str.replace('.', '') antes del str.replace(',', '.'):
    - Si el número tiene un punto decimal (formato internacional), borrarlo
      produce valores incorrectos: '1500.50' → '150050' (¡bug crítico!).
    - La estrategia segura es reemplazar directamente la coma por punto,
      que es lo único que hace falta para el formato de Contabilium.
    """
    return pd.to_numeric(
        serie.astype(str)
             .str.strip()
             .str.replace(",", ".", regex=False),  # '116100,83' → '116100.83'
        errors="coerce"  # cualquier valor no parseable queda como NaN
    )


def generar_excel(df: pd.DataFrame) -> BytesIO:
    """
    Convierte un DataFrame a un archivo Excel en memoria (BytesIO).
    Usado para todos los botones de descarga.
    """
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer


def validar_columnas(df: pd.DataFrame, nombre_archivo: str, columnas: list) -> bool:
    """
    Verifica que el DataFrame contenga todas las columnas requeridas.
    Muestra un error claro al usuario si falta alguna y retorna False.
    Retorna True si todas las columnas están presentes.
    """
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        st.error(
            f"❌ **{nombre_archivo}** no tiene las columnas requeridas: "
            f"`{'`, `'.join(faltantes)}`\n\n"
            f"Columnas encontradas: `{'`, `'.join(df.columns.tolist())}`"
        )
        return False
    return True


def colorear_cambios(val):
    """
    Función de estilo para la tabla de cambios.
    Colorea en verde si el nuevo valor es mayor, en rojo si es menor.
    Formato esperado en la celda: 'antes → después'
    """
    try:
        if "→" in str(val):
            antes, despues = val.split("→")
            antes   = float(antes.strip())
            despues = float(despues.strip())
            if despues > antes:
                return "color: #05F81B; font-weight: bold;"   # verde = subió
            elif despues < antes:
                return "color: #F40A09; font-weight: bold;"   # rojo  = bajó
    except Exception:
        pass
    return ""


# =============================================================================
# PANEL DE CONTROL: ACCIÓN Y MODO
# =============================================================================
st.subheader("⚙️ Acción a realizar")

accion = st.radio(
    "Seleccionar operación:",
    ["Actualizar Stock", "Actualizar precios", "Actualizar ambos"],
    horizontal=True
)

simulacion = st.toggle("🧪 Modo simulación (no aplicar cambios reales)")

if simulacion:
    st.info("Modo simulación activo: podés ver los cambios que se aplicarían sin modificar ningún dato.")


# =============================================================================
# CARGA DE ARCHIVOS
# =============================================================================
st.subheader("📂 Cargar archivos .XLSX")

col1, col2 = st.columns(2)

with col1:
    archivo_a = st.file_uploader(
        "Archivo A — Template de Tienda Negocio (el que se va a actualizar. RENOMBRAR A 'archivo_a')",
        type=["xlsx"]
    )

with col2:
    archivo_b = st.file_uploader(
        "Archivo B — Exportado de Contabilium (fuente de stock/precios actualizados. RENOMBRAR A 'archivo_b)",
        type=["xlsx"]
    )


# =============================================================================
# PROCESAMIENTO PRINCIPAL
# Todo lo que sigue solo se ejecuta cuando ambos archivos están cargados.
# =============================================================================
if archivo_a and archivo_b:

    # -------------------------------------------------------------------------
    # LECTURA CON CACHÉ
    # Al usar @st.cache_data, Streamlit no vuelve a leer el Excel cada vez
    # que el usuario toca un widget. Solo lo vuelve a leer si cambia el archivo.
    # -------------------------------------------------------------------------
    df_a = cargar_excel(archivo_a)
    df_b = cargar_excel(archivo_b)

    # -------------------------------------------------------------------------
    # VALIDACIÓN DE COLUMNAS
    # Antes de hacer cualquier cosa, verificamos que los archivos tengan
    # las columnas esperadas. Así el error es claro y no un crash de pandas.
    # -------------------------------------------------------------------------
    columnas_requeridas = [COL_SKU, COL_STOCK, COL_PRECIO]

    ok_a = validar_columnas(df_a, "Archivo A", columnas_requeridas)
    ok_b = validar_columnas(df_b, "Archivo B", columnas_requeridas)

    if not ok_a or not ok_b:
        st.stop()  # detiene la ejecución hasta que el usuario suba archivos correctos

    # -------------------------------------------------------------------------
    # FILTROS
    # -------------------------------------------------------------------------
    st.subheader("🔎 Filtros")

    if "Categoria" in df_a.columns:
        categorias     = ["Todas"] + sorted(df_a["Categoria"].dropna().unique().tolist())
        categoria_sel  = st.selectbox("Filtrar por categoría", categorias)
    else:
        categoria_sel = "Todas"

    busqueda = st.text_input("Buscar producto por SKU")

    # -------------------------------------------------------------------------
    # BOTÓN DE EJECUCIÓN
    # -------------------------------------------------------------------------
    if st.button("🚀 Ejecutar comparación"):

        # ---------------------------------------------------------------------
        # PASO 1: NORMALIZACIÓN DE SKUs
        # Se crea una columna auxiliar 'sku_norm' en ambos DataFrames para
        # comparar sin importar mayúsculas, espacios o variaciones de formato.
        # Esta columna NO se escribe en el archivo de salida.
        # ---------------------------------------------------------------------
        df_a["sku_norm"] = normalizar_sku(df_a[COL_SKU])
        df_b["sku_norm"] = normalizar_sku(df_b[COL_SKU])

        # ---------------------------------------------------------------------
        # PASO 2: PARSEO DE STOCK
        # Los stocks vienen como números enteros (ej: 5, 120, 0).
        # Se usa el mismo parser seguro para consistencia.
        # fillna(0): si el stock está vacío, se interpreta como 0.
        # ---------------------------------------------------------------------
        df_a[COL_STOCK] = parsear_numero_argentino(df_a[COL_STOCK]).fillna(0)
        df_b[COL_STOCK] = parsear_numero_argentino(df_b[COL_STOCK]).fillna(0)

        # ---------------------------------------------------------------------
        # PASO 3: PARSEO DE PRECIOS
        # Formato Contabilium: coma decimal, sin separador de miles.
        # Ejemplos: '116100,83' | '62000' | '251208,26'
        #
        # FIX del bug original: la versión anterior hacía primero
        # str.replace('.', '') para "eliminar miles", lo cual destruía
        # cualquier precio con punto decimal. La función parsear_numero_argentino
        # solo reemplaza la coma por punto, que es todo lo que se necesita
        # para este formato.
        #
        # Los precios NaN se dejan como NaN (no como 0) para distinguir
        # "precio no informado" de "precio cero".
        # ---------------------------------------------------------------------
        df_a[COL_PRECIO] = parsear_numero_argentino(df_a[COL_PRECIO])
        df_b[COL_PRECIO] = parsear_numero_argentino(df_b[COL_PRECIO])

        # ---------------------------------------------------------------------
        # PASO 4: DICCIONARIOS DE BÚSQUEDA (SKU normalizado → valor)
        # Permiten lookup O(1) en el loop principal.
        # ---------------------------------------------------------------------
        stock_b  = dict(zip(df_b["sku_norm"], df_b[COL_STOCK]))
        precio_b = dict(zip(df_b["sku_norm"], df_b[COL_PRECIO]))

        # ---------------------------------------------------------------------
        # PASO 5: APLICAR FILTROS DE USUARIO
        # ---------------------------------------------------------------------
        df_filtrado = df_a.copy()

        if categoria_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Categoria"] == categoria_sel]

        if busqueda:
            df_filtrado = df_filtrado[
                df_filtrado[COL_SKU].astype(str).str.contains(busqueda, case=False, na=False)
            ]

        # ---------------------------------------------------------------------
        # PASO 6: LOOP DE COMPARACIÓN Y ACTUALIZACIÓN
        #
        # Para cada producto del Archivo A (filtrado):
        #   - Si existe en Archivo B (por SKU normalizado):
        #       · Compara stock y/o precio según la acción seleccionada
        #       · Si hay diferencia, registra el cambio
        #       · Si no es simulación, actualiza df_a directamente
        #   - Independientemente: registra productos sin stock (stock <= 0)
        # ---------------------------------------------------------------------
        cambios   = []   # lista de dicts con cada cambio registrado
        aumentos  = []   # SKUs donde el precio subió
        bajadas   = []   # SKUs donde el precio bajó
        sin_stock = []   # SKUs con stock <= 0 en Archivo A (después de actualizar)

        for i, row in df_filtrado.iterrows():

            sku_norm = row["sku_norm"]
            sku_real = row[COL_SKU]

            if sku_norm in stock_b:

                stock_actual  = row[COL_STOCK]
                nuevo_stock   = stock_b[sku_norm]

                precio_actual = row[COL_PRECIO]
                nuevo_precio  = precio_b.get(sku_norm)  # puede ser NaN si no está en B

                cambio = {}

                # --- ACTUALIZACIÓN DE STOCK ---
                if accion in ["Actualizar Stock", "Actualizar ambos"]:
                    if stock_actual != nuevo_stock:
                        cambio[COL_STOCK] = f"{stock_actual} → {nuevo_stock}"
                        if not simulacion:
                            df_a.at[i, COL_STOCK] = nuevo_stock

                # --- ACTUALIZACIÓN DE PRECIO ---
                # Solo se actualiza si el nuevo precio es un número válido (no NaN).
                # Esto evita sobreescribir precios existentes con valores vacíos.
                if accion in ["Actualizar precios", "Actualizar ambos"]:
                    if pd.notna(nuevo_precio) and precio_actual != nuevo_precio:
                        cambio[COL_PRECIO] = f"{precio_actual} → {nuevo_precio}"

                        # Clasificar si el precio subió o bajó
                        if pd.notna(precio_actual):
                            if nuevo_precio > precio_actual:
                                aumentos.append(sku_real)
                            elif nuevo_precio < precio_actual:
                                bajadas.append(sku_real)

                        if not simulacion:
                            df_a.at[i, COL_PRECIO] = nuevo_precio

                if cambio:
                    cambios.append({"SKU": sku_real, **cambio})

            # Registrar sin stock DESPUÉS de la actualización (usa el valor actualizado)
            stock_final = df_a.at[i, COL_STOCK] if not simulacion else row[COL_STOCK]
            if stock_final <= 0:
                sin_stock.append(sku_real)


        # =====================================================================
        # RESULTADOS
        # =====================================================================
        st.subheader("📊 Resultados")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cambios totales", len(cambios))
        m2.metric("Sin stock",       len(sin_stock))
        m3.metric("Precios subieron", len(aumentos))
        m4.metric("Precios bajaron",  len(bajadas))

        # ---------------------------------------------------------------------
        # GRÁFICO DE RESUMEN
        # ---------------------------------------------------------------------
        st.subheader("📊 Visualización")

        df_graf = pd.DataFrame({
            "Tipo":     ["Cambios", "Sin stock", "Aumentos", "Bajadas"],
            "Cantidad": [len(cambios), len(sin_stock), len(aumentos), len(bajadas)]
        })

        st.bar_chart(df_graf, x="Tipo", y="Cantidad")

        # ---------------------------------------------------------------------
        # TABLA DE CAMBIOS DETALLADA
        # ---------------------------------------------------------------------
        if cambios:
            with st.expander("📋 Ver detalle de cambios", expanded=True):
                df_cambios = pd.DataFrame(cambios)
                df_style   = df_cambios.style.map(colorear_cambios)
                st.dataframe(df_style, use_container_width=True, height=400)
        else:
            st.success("No se detectaron cambios 🎉")

        # ---------------------------------------------------------------------
        # DETALLES COLAPSABLES: AUMENTOS / BAJADAS / SIN STOCK
        # ---------------------------------------------------------------------
        colA, colB, colC = st.columns(3)

        with colA:
            if aumentos:
                with st.expander(f"📈 Precios aumentaron ({len(aumentos)})"):
                    st.dataframe(pd.DataFrame(aumentos, columns=["SKU"]))

        with colB:
            if bajadas:
                with st.expander(f"📉 Precios bajaron ({len(bajadas)})"):
                    st.dataframe(pd.DataFrame(bajadas, columns=["SKU"]))

        with colC:
            if sin_stock:
                with st.expander(f"⚠️ Sin stock ({len(sin_stock)})"):
                    st.dataframe(pd.DataFrame(sin_stock, columns=["SKU"]))

        # =====================================================================
        # DESCARGA PRINCIPAL
        # El archivo descargado tiene la misma estructura que el Archivo A,
        # pero con Stock (y Precio si corresponde) actualizados.
        # La columna auxiliar 'sku_norm' se elimina antes de exportar.
        # =====================================================================
        df_exportar = df_a.drop(columns=["sku_norm"], errors="ignore")

        st.download_button(
            "⬇️ Descargar archivo actualizado",
            data=generar_excel(df_exportar),
            file_name=f"productos_actualizados_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        )

        # =====================================================================
        # EXPORTES ADICIONALES
        # =====================================================================
        st.divider()
        st.subheader("📦 Exportes adicionales")

        col_exp1, col_exp2, col_exp3 = st.columns(3)

        with col_exp1:
            if cambios:
                st.download_button(
                    "📄 Detalle de cambios",
                    data=generar_excel(pd.DataFrame(cambios)),
                    file_name="cambios.xlsx"
                )

        with col_exp2:
            if sin_stock:
                st.download_button(
                    "⚠️ Productos sin stock",
                    data=generar_excel(pd.DataFrame(sin_stock, columns=["SKU"])),
                    file_name="sin_stock.xlsx"
                )

        with col_exp3:
            if aumentos or bajadas:
                df_precios_export = pd.DataFrame({
                    "Aumentos": pd.Series(aumentos),
                    "Bajadas":  pd.Series(bajadas)
                })
                st.download_button(
                    "💲 Cambios de precios",
                    data=generar_excel(df_precios_export),
                    file_name="cambios_precios.xlsx"
                )

        # =====================================================================
        # HISTORIAL DE CAMBIOS (solo en sesión actual)
        #
        # NOTA: Streamlit Cloud tiene sistema de archivos efímero.
        # Guardar en disco (como hacía la versión anterior con .csv) no
        # persiste entre reinicios del servidor.
        # El historial se acumula en st.session_state durante la sesión activa
        # y se puede descargar como Excel. Para persistencia real entre sesiones,
        # considerar integrar una base de datos externa (ej: Google Sheets,
        # Supabase, SQLite en entorno local).
        # =====================================================================
        if not simulacion and cambios:

            # Inicializar historial en session_state si no existe
            if "historial" not in st.session_state:
                st.session_state["historial"] = []

            # Agregar cambios actuales con timestamp
            for c in cambios:
                st.session_state["historial"].append({
                    **c,
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

            st.divider()
            st.subheader("🗂️ Historial de esta sesión")

            df_historial = pd.DataFrame(st.session_state["historial"])
            st.dataframe(df_historial, use_container_width=True)

            st.download_button(
                "📥 Descargar historial completo",
                data=generar_excel(df_historial),
                file_name=f"historial_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
