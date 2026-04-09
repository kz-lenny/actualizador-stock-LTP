import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# =============================================================================
# CONFIGURACIÓN GENERAL
# Nombres de columnas esperadas en ambos archivos Excel.
# Si en algún momento cambian los headers, solo hay que modificar estas
# constantes y el resto del código se adapta automáticamente.
# =============================================================================
st.set_page_config(page_title="Sincronizador de Stock - LTP", layout="wide")

COL_SKU        = "SKU"
COL_STOCK      = "Stock"
COL_PRECIO     = "Precio"
COL_VISIB      = "Visibilidad (Visible o Oculto)"   # columna de visibilidad en Archivo A
VALOR_VISIBLE  = "Visible"       # valor exacto (con mayúscula) para producto visible
VALOR_OCULTO   = "Oculto"        # valor exacto (con mayúscula) para producto oculto

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

/* CHECKBOXES */
.stCheckbox label { color: white; }

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
    Usa caché de Streamlit: no vuelve a leer el archivo en cada interacción,
    solo cuando cambia el archivo subido. Mejora el rendimiento notablemente.
    """
    return pd.read_excel(archivo)


def normalizar_sku(serie: pd.Series) -> pd.Series:
    """
    Normaliza SKUs para comparación sin falsos negativos por formato.
    Convierte a minúsculas, elimina espacios internos y laterales.
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
    Convierte números en formato argentino (coma decimal) a float de Python.

    Formato esperado: coma como separador decimal, sin separador de miles.
    Ejemplos: '116100,83' → 116100.83  |  '62000' → 62000.0

    ¿Por qué NO se hace str.replace('.', '') primero?
    Porque si el número ya tiene punto decimal (formato internacional),
    borrarlo produce valores incorrectos: '1500.50' → '150050'.
    La solución correcta es solo reemplazar la coma por punto.
    """
    return pd.to_numeric(
        serie.astype(str)
             .str.strip()
             .str.replace(",", ".", regex=False),
        errors="coerce"   # valores no parseables quedan como NaN
    )


def generar_excel(df: pd.DataFrame) -> BytesIO:
    """
    Serializa un DataFrame como archivo .xlsx en memoria.
    Retorna un BytesIO listo para usar en st.download_button.
    """
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer


def validar_columnas(df: pd.DataFrame, nombre: str, columnas: list) -> bool:
    """
    Verifica que el DataFrame tenga todas las columnas requeridas.
    Si falta alguna, muestra un error descriptivo y retorna False.
    Retorna True si todo está bien.
    """
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        st.error(
            f"❌ **{nombre}** no tiene las columnas requeridas: "
            f"`{'`, `'.join(faltantes)}`\n\n"
            f"Columnas encontradas: `{'`, `'.join(df.columns.tolist())}`"
        )
        return False
    return True


def colorear_cambios(val):
    """
    Estilo para la tabla de cambios: verde si subió, rojo si bajó.
    Solo aplica a celdas con formato 'valor_antes → valor_después'.
    Las celdas de texto (ej: cambios de Visibilidad) se ignoran sin error.
    """
    try:
        if "→" in str(val):
            antes, despues = str(val).split("→")
            antes   = float(antes.strip())
            despues = float(despues.strip())
            if despues > antes:
                return "color: #05F81B; font-weight: bold;"   # verde = subió
            elif despues < antes:
                return "color: #F40A09; font-weight: bold;"   # rojo  = bajó
    except (ValueError, TypeError):
        pass   # celdas de texto como "Oculto → Visible" no se colorean
    return ""


# =============================================================================
# PANEL DE CONTROL: ACCIONES Y OPCIONES
# =============================================================================
st.subheader("⚙️ Acción a realizar")

accion = st.radio(
    "Seleccionar operación:",
    ["Actualizar Stock", "Actualizar precios", "Actualizar ambos"],
    horizontal=True
)

# Opción de visibilidad: disponible cuando se va a actualizar stock
# (necesita la columna "Visibilidad" en el Archivo A)
actualizar_visibilidad = st.checkbox(
    f"👁️ Actualizar Visibilidad según stock "
    f"(stock ≥ 1 → {VALOR_VISIBLE} | stock = 0 → {VALOR_OCULTO})",
    help=(
        f"Requiere columna '{COL_VISIB}' en el Archivo A. "
        f"Si el stock queda en 0, el producto pasa a '{VALOR_OCULTO}'. "
        f"Si el stock queda en 1 o más, pasa a '{VALOR_VISIBLE}'."
    )
)

simulacion = st.toggle("🧪 Modo simulación (ver cambios sin aplicarlos)")

if simulacion:
    st.info("Modo simulación activo: podés revisar los cambios que se aplicarían sin modificar ningún dato.")


# =============================================================================
# CARGA DE ARCHIVOS
# =============================================================================
st.subheader("📂 Cargar archivos .XLSX")

col1, col2 = st.columns(2)

with col1:
    archivo_a = st.file_uploader(
        "Archivo A — Template de Tienda Negocio (el que se va a actualizar)",
        type=["xlsx"]
    )

with col2:
    archivo_b = st.file_uploader(
        "Archivo B — Exportado de Contabilium (fuente de stock/precios actualizados)",
        type=["xlsx"]
    )


# =============================================================================
# PROCESAMIENTO PRINCIPAL
# Todo lo que sigue solo se ejecuta cuando ambos archivos están cargados.
# =============================================================================
if archivo_a and archivo_b:

    # -------------------------------------------------------------------------
    # LECTURA CON CACHÉ
    # -------------------------------------------------------------------------
    df_a = cargar_excel(archivo_a)
    df_b = cargar_excel(archivo_b)

    # -------------------------------------------------------------------------
    # VALIDACIÓN DE COLUMNAS REQUERIDAS
    # -------------------------------------------------------------------------
    columnas_base = [COL_SKU, COL_STOCK, COL_PRECIO]

    ok_a = validar_columnas(df_a, "Archivo A", columnas_base)
    ok_b = validar_columnas(df_b, "Archivo B", columnas_base)

    # Si se activó visibilidad, verificar que la columna exista en Archivo A
    if actualizar_visibilidad and COL_VISIB not in df_a.columns:
        st.warning(
            f"⚠️ Se activó 'Actualizar Visibilidad' pero el Archivo A "
            f"no tiene la columna `{COL_VISIB}`. La opción será ignorada."
        )
        actualizar_visibilidad = False

    if not ok_a or not ok_b:
        st.stop()

    # =========================================================================
    # VISTA PREVIA DE ARCHIVOS
    # Permite confirmar que los archivos se cargaron correctamente antes
    # de ejecutar cualquier operación.
    # =========================================================================
    with st.expander("👁️ Vista previa de archivos cargados"):
        prev1, prev2 = st.columns(2)

        with prev1:
            st.caption(f"Archivo A — {len(df_a)} productos, {len(df_a.columns)} columnas")
            st.dataframe(df_a.head(5), use_container_width=True)

        with prev2:
            st.caption(f"Archivo B — {len(df_b)} productos, {len(df_b.columns)} columnas")
            st.dataframe(df_b.head(5), use_container_width=True)

    # =========================================================================
    # COMPARACIÓN RÁPIDA DE SKUs
    # Muestra cuántos productos de A están en B y viceversa, antes de ejecutar.
    # Ayuda a detectar problemas de formato o archivos incorrectos.
    # =========================================================================
    skus_norm_a = set(normalizar_sku(df_a[COL_SKU]))
    skus_norm_b = set(normalizar_sku(df_b[COL_SKU]))

    coincidentes   = skus_norm_a & skus_norm_b
    solo_en_a      = skus_norm_a - skus_norm_b
    solo_en_b      = skus_norm_b - skus_norm_a

    with st.expander("🔗 Comparación rápida de SKUs"):
        cq1, cq2, cq3 = st.columns(3)
        cq1.metric("SKUs coincidentes",     len(coincidentes),
                   help="Productos que existen en ambos archivos y serán procesados")
        cq2.metric("Solo en Archivo A",     len(solo_en_a),
                   help="Productos del Archivo A que no están en Contabilium")
        cq3.metric("Solo en Archivo B",     len(solo_en_b),
                   help="Productos nuevos en Contabilium que no están en el Archivo A")

        porc = round(len(coincidentes) / max(len(skus_norm_a), 1) * 100, 1)
        st.progress(
            len(coincidentes) / max(len(skus_norm_a), 1),
            text=f"{porc}% de los productos del Archivo A serán actualizados"
        )

    # =========================================================================
    # COLUMNAS PROTEGIDAS
    # El usuario elige qué columnas NO deben ser modificadas bajo ningún
    # concepto, incluso si la lógica de actualización las tocaría.
    # Por defecto ninguna está protegida. Se excluyen las columnas de control
    # interno (sku_norm) que no son columnas reales del Excel.
    # =========================================================================
    with st.expander("🔒 Columnas protegidas (no modificar)"):
        st.caption(
            "Marcá las columnas del Archivo A que no deben ser tocadas. "
            "Útil para proteger datos sensibles o columnas que se manejan manualmente."
        )
        cols_protegibles = [c for c in df_a.columns]
        cols_protegidas  = []

        # Mostrar checkboxes en grilla de 4 columnas para no ocupar mucho espacio
        grid_cols = st.columns(4)
        for idx, col_name in enumerate(cols_protegibles):
            with grid_cols[idx % 4]:
                if st.checkbox(col_name, key=f"prot_{col_name}"):
                    cols_protegidas.append(col_name)

        if cols_protegidas:
            st.info(f"Columnas protegidas: `{'`, `'.join(cols_protegidas)}`")

    # =========================================================================
    # FILTROS
    # =========================================================================
    st.subheader("🔎 Filtros")

    if "Categoria" in df_a.columns:
        categorias    = ["Todas"] + sorted(df_a["Categoria"].dropna().unique().tolist())
        categoria_sel = st.selectbox("Filtrar por categoría", categorias)
    else:
        categoria_sel = "Todas"

    busqueda = st.text_input("Buscar producto por SKU")

    # =========================================================================
    # BOTÓN DE EJECUCIÓN
    # =========================================================================
    if st.button("🚀 Ejecutar comparación"):

        # ---------------------------------------------------------------------
        # PASO 1: NORMALIZACIÓN DE SKUs
        # Columna auxiliar 'sku_norm': no se escribe en el Excel final.
        # ---------------------------------------------------------------------
        df_a["sku_norm"] = normalizar_sku(df_a[COL_SKU])
        df_b["sku_norm"] = normalizar_sku(df_b[COL_SKU])

        # ---------------------------------------------------------------------
        # PASO 2: PARSEO DE STOCK
        # fillna(0): stock vacío = 0.
        # ---------------------------------------------------------------------
        df_a[COL_STOCK] = parsear_numero_argentino(df_a[COL_STOCK]).fillna(0)
        df_b[COL_STOCK] = parsear_numero_argentino(df_b[COL_STOCK]).fillna(0)

        # ---------------------------------------------------------------------
        # PASO 3: PARSEO DE PRECIOS
        # Solo se reemplaza coma por punto (formato argentino).
        # Los precios NaN se dejan como NaN (≠ precio cero).
        # Ver parsear_numero_argentino() para explicación del bug original.
        # ---------------------------------------------------------------------
        df_a[COL_PRECIO] = parsear_numero_argentino(df_a[COL_PRECIO])
        df_b[COL_PRECIO] = parsear_numero_argentino(df_b[COL_PRECIO])

        # ---------------------------------------------------------------------
        # PASO 4: DICCIONARIOS DE LOOKUP (SKU normalizado → valor)
        # Permiten acceso O(1) dentro del loop, mucho más rápido que filtrar
        # el DataFrame completo en cada iteración.
        # ---------------------------------------------------------------------
        stock_b  = dict(zip(df_b["sku_norm"], df_b[COL_STOCK]))
        precio_b = dict(zip(df_b["sku_norm"], df_b[COL_PRECIO]))

        # ---------------------------------------------------------------------
        # PASO 5: FILTROS DE USUARIO
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
        # Por cada producto en Archivo A (filtrado):
        #   - Si tiene par en Archivo B:
        #       · Actualiza Stock si corresponde (y no está protegido)
        #       · Actualiza Precio si corresponde (y no está protegido)
        #       · Actualiza Visibilidad si está activado (y no está protegida)
        #   - Registra en sin_stock si el stock final es <= 0
        #   - Registra en no_encontrados si el SKU no existe en Archivo B
        # ---------------------------------------------------------------------
        cambios       = []   # lista de dicts: cada fila modificada
        aumentos      = []   # SKUs donde el precio subió
        bajadas       = []   # SKUs donde el precio bajó
        sin_stock     = []   # SKUs con stock <= 0 tras la actualización
        no_encontrados = []  # SKUs del Archivo A que no están en Archivo B

        # Barra de progreso
        total_filas  = len(df_filtrado)
        barra        = st.progress(0, text="Procesando productos...")

        for contador, (i, row) in enumerate(df_filtrado.iterrows()):

            sku_norm = row["sku_norm"]
            sku_real = row[COL_SKU]

            if sku_norm in stock_b:

                stock_actual  = row[COL_STOCK]
                nuevo_stock   = stock_b[sku_norm]
                precio_actual = row[COL_PRECIO]
                nuevo_precio  = precio_b.get(sku_norm)

                cambio = {}

                # --- STOCK ---
                # Solo actualiza si la columna no está protegida.
                if accion in ["Actualizar Stock", "Actualizar ambos"]:
                    if COL_STOCK not in cols_protegidas:
                        if stock_actual != nuevo_stock:
                            cambio[COL_STOCK] = f"{stock_actual} → {nuevo_stock}"
                            if not simulacion:
                                df_a.at[i, COL_STOCK] = nuevo_stock

                # --- PRECIO ---
                # Solo se actualiza si el nuevo precio es un número válido (no NaN).
                # Esto evita sobreescribir precios existentes con celdas vacías.
                if accion in ["Actualizar precios", "Actualizar ambos"]:
                    if COL_PRECIO not in cols_protegidas:
                        if pd.notna(nuevo_precio) and precio_actual != nuevo_precio:
                            cambio[COL_PRECIO] = f"{precio_actual} → {nuevo_precio}"

                            if pd.notna(precio_actual):
                                if nuevo_precio > precio_actual:
                                    aumentos.append(sku_real)
                                elif nuevo_precio < precio_actual:
                                    bajadas.append(sku_real)

                            if not simulacion:
                                df_a.at[i, COL_PRECIO] = nuevo_precio

                # --- VISIBILIDAD ---
                # Lógica bidireccional:
                #   stock >= 1  →  Visible   (si estaba Oculto)
                #   stock <= 0  →  Oculto    (si estaba Visible)
                # Se usa el stock YA actualizado (o el original si es simulación).
                # Solo aplica si la columna no está protegida.
                if actualizar_visibilidad and COL_VISIB not in cols_protegidas:
                    stock_post = nuevo_stock if (accion in ["Actualizar Stock", "Actualizar ambos"]) else stock_actual
                    visib_actual = row.get(COL_VISIB, "")

                    if stock_post >= 1 and visib_actual != VALOR_VISIBLE:
                        cambio[COL_VISIB] = f"{visib_actual} → {VALOR_VISIBLE}"
                        if not simulacion:
                            df_a.at[i, COL_VISIB] = VALOR_VISIBLE

                    elif stock_post <= 0 and visib_actual != VALOR_OCULTO:
                        cambio[COL_VISIB] = f"{visib_actual} → {VALOR_OCULTO}"
                        if not simulacion:
                            df_a.at[i, COL_VISIB] = VALOR_OCULTO

                if cambio:
                    cambios.append({"SKU": sku_real, **cambio})

            else:
                # SKU del Archivo A que no tiene par en Archivo B
                no_encontrados.append(sku_real)

            # Stock final para clasificar sin_stock
            stock_final = df_a.at[i, COL_STOCK] if not simulacion else row[COL_STOCK]
            if stock_final <= 0:
                sin_stock.append(sku_real)

            # Actualizar barra de progreso
            barra.progress(
                (contador + 1) / total_filas,
                text=f"Procesando... {contador + 1}/{total_filas}"
            )

        barra.empty()   # ocultar la barra al terminar

        # =====================================================================
        # RESULTADOS — MÉTRICAS GENERALES
        # =====================================================================
        st.subheader("📊 Resultados")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Cambios totales",   len(cambios))
        m2.metric("Sin stock",         len(sin_stock))
        m3.metric("Precios subieron",  len(aumentos))
        m4.metric("Precios bajaron",   len(bajadas))
        m5.metric("No encontrados",    len(no_encontrados),
                  help="SKUs en Archivo A sin par en Archivo B")

        # ---------------------------------------------------------------------
        # GRÁFICO DE RESUMEN
        # ---------------------------------------------------------------------
        st.subheader("📊 Visualización")

        df_graf = pd.DataFrame({
            "Tipo":     ["Cambios", "Sin stock", "Aumentos", "Bajadas", "No encontrados"],
            "Cantidad": [len(cambios), len(sin_stock), len(aumentos), len(bajadas), len(no_encontrados)]
        })
        st.bar_chart(df_graf, x="Tipo", y="Cantidad")

        # ---------------------------------------------------------------------
        # RESUMEN POR CATEGORÍA (si la columna existe)
        # Muestra cuántos cambios hubo en cada categoría del Archivo A.
        # ---------------------------------------------------------------------
        if "Categoria" in df_a.columns and cambios:
            with st.expander("🏷️ Resumen por categoría"):
                skus_con_cambio = {c["SKU"] for c in cambios}
                df_cat = df_a[df_a[COL_SKU].isin(skus_con_cambio)].copy()
                resumen_cat = (
                    df_cat.groupby("Categoria")
                    .size()
                    .reset_index(name="Cambios")
                    .sort_values("Cambios", ascending=False)
                )
                st.dataframe(resumen_cat, use_container_width=True)

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
        # DETALLES COLAPSABLES
        # ---------------------------------------------------------------------
        colA, colB, colC, colD = st.columns(4)

        with colA:
            if aumentos:
                with st.expander(f"📈 Precios subieron ({len(aumentos)})"):
                    st.dataframe(pd.DataFrame(aumentos, columns=["SKU"]))

        with colB:
            if bajadas:
                with st.expander(f"📉 Precios bajaron ({len(bajadas)})"):
                    st.dataframe(pd.DataFrame(bajadas, columns=["SKU"]))

        with colC:
            if sin_stock:
                with st.expander(f"⚠️ Sin stock ({len(sin_stock)})"):
                    st.dataframe(pd.DataFrame(sin_stock, columns=["SKU"]))

        with colD:
            if no_encontrados:
                with st.expander(f"❓ No encontrados ({len(no_encontrados)})"):
                    st.caption("SKUs en Archivo A que no tienen par en Archivo B.")
                    st.dataframe(pd.DataFrame(no_encontrados, columns=["SKU"]))

        # =====================================================================
        # DESCARGA PRINCIPAL
        # Misma estructura que Archivo A, con los valores actualizados.
        # Se elimina la columna auxiliar 'sku_norm' antes de exportar.
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

        col_exp1, col_exp2, col_exp3, col_exp4 = st.columns(4)

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

        with col_exp4:
            if no_encontrados:
                st.download_button(
                    "❓ No encontrados",
                    data=generar_excel(pd.DataFrame(no_encontrados, columns=["SKU"])),
                    file_name="no_encontrados.xlsx"
                )

        # =====================================================================
        # HISTORIAL DE CAMBIOS (sesión actual)
        #
        # NOTA TÉCNICA: Streamlit Cloud tiene sistema de archivos efímero.
        # Guardar en disco no persiste entre reinicios del servidor.
        # Se usa st.session_state para acumular cambios durante la sesión.
        # Para persistencia real entre sesiones, integrar una DB externa
        # (ej: Google Sheets vía gspread, Supabase, o SQLite en entorno local).
        # =====================================================================
        if not simulacion and cambios:

            if "historial" not in st.session_state:
                st.session_state["historial"] = []

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
