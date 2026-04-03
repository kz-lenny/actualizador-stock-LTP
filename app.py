import streamlit as st
import pandas as pd

st.title("Actualizador de Stock V0.1.10 - La Tienda Pinturas")

st.write("Subí los archivos Excel para comparar y actualizar stock")

# Subida de archivos
archivo_a = st.file_uploader("Subir archivo A, este debe ser el excel con el Stock desactualizado. (IMPORTANTE: RENOMBRAR ARCHIVO A: arcivo_a.xlsx)", type=["xlsx"])
archivo_b = st.file_uploader("Subir archivo B, este debe ser el archivo bajado desde Contabilium con el stock actualizado. (RENOMBRAR A archivo_b.xlsx)", type=["xlsx"])

if archivo_a and archivo_b:

    df_a = pd.read_excel(archivo_a)
    df_b = pd.read_excel(archivo_b)

    # Columnas (ajustar si es necesario)
    col_producto = "SKU"
    col_stock = "Stock"

    # Normalizar stock (coma a punto)
    df_a[col_stock] = pd.to_numeric(
        df_a[col_stock].astype(str).str.replace(",", "."),
        errors='coerce'
    )

    df_b[col_stock] = pd.to_numeric(
        df_b[col_stock].astype(str).str.replace(",", "."),
        errors='coerce'
    )

    # Diccionario de stock proveedor
    stock_b = dict(zip(df_b[col_producto], df_b[col_stock]))

    cambios = 0
    nuevos = 0
    no_encontrados = []

    # Actualizar stock
    for i, row in df_a.iterrows():
        producto = row[col_producto]

        if producto in stock_b:
            stock_a = row[col_stock]
            nuevo_stock = stock_b[producto]

            if stock_a != nuevo_stock:
                df_a.at[i, col_stock] = nuevo_stock
                cambios += 1
        else:
            no_encontrados.append(producto)

    # Detectar productos nuevos (que están en B pero no en A)
    productos_a = set(df_a[col_producto])
    productos_b = set(df_b[col_producto])

    productos_nuevos = productos_b - productos_a

    nuevos = len(productos_nuevos)

    # Mostrar resultados
    st.success(f"Stocks actualizados: {cambios}")
    st.info(f"Productos nuevos detectados: {nuevos}")
    st.warning(f"No encontrados en proveedor: {len(no_encontrados)}")

    # Mostrar algunos ejemplos
    if nuevos > 0:
        st.write("Ejemplo productos nuevos:")
        st.write(list(productos_nuevos)[:10])

    if len(no_encontrados) > 0:
        st.write("Ejemplo no encontrados:")
        st.write(no_encontrados[:10])

    # Descargar archivo
    from io import BytesIO

    output = BytesIO()
    df_a.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    st.download_button(
    label="Descargar Excel actualizado",
    data=output,
    file_name="archivo_actualizado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

