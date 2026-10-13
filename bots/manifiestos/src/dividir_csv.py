import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import math

# Límite de Excel por hoja (filas totales)
EXCEL_MAX_ROWS = 1_048_576

def dividir_csv_en_partes(ruta_csv, max_filas_excel=EXCEL_MAX_ROWS, asumir_encabezado=True):
    """
    Divide un CSV en tantas partes como sea necesario para que cada archivo
    no exceda el máximo de filas permitido por Excel.

    - Si asumir_encabezado=True, cada parte incluye el encabezado (si existe),
      y el máximo de filas de datos por parte será max_filas_excel - 1.
    """
    try:
        # 1) Contar filas de datos
        total_filas_datos = 0
        with open(ruta_csv, "r", newline="", encoding="utf-8") as f:
            lector = csv.reader(f)
            encabezado = next(lector, None) if asumir_encabezado else None
            for _ in lector:
                total_filas_datos += 1

        if total_filas_datos == 0:
            raise ValueError("El archivo no tiene filas de datos (solo encabezado o está vacío).")

        # 2) Calcular capacidad por archivo (filas de datos)
        capacidad_datos = max_filas_excel - 1 if asumir_encabezado else max_filas_excel
        if capacidad_datos <= 0:
            raise ValueError("El máximo de filas de Excel debe ser mayor que 1 si hay encabezado.")

        # 3) Calcular cuántas partes se necesitan
        num_partes = math.ceil(total_filas_datos / capacidad_datos)

        carpeta, nombre = os.path.split(ruta_csv)
        base, ext = os.path.splitext(nombre)

        rutas_salida = []
        for i in range(1, num_partes + 1):
            rutas_salida.append(os.path.join(carpeta, f"{base}_parte{i}{ext}"))

        # 4) Escribir en N archivos (streaming: no carga todo en memoria)
        with open(ruta_csv, "r", newline="", encoding="utf-8") as f_in:
            lector = csv.reader(f_in)

            encabezado_real = next(lector, None) if asumir_encabezado else None

            parte_actual = 1
            filas_en_parte = 0
            f_out = open(rutas_salida[parte_actual - 1], "w", newline="", encoding="utf-8")
            escritor = csv.writer(f_out)

            if encabezado_real is not None:
                escritor.writerow(encabezado_real)

            for fila in lector:
                # Si llegamos a la capacidad, cerramos y abrimos nueva parte
                if filas_en_parte >= capacidad_datos:
                    f_out.close()
                    parte_actual += 1
                    filas_en_parte = 0

                    f_out = open(rutas_salida[parte_actual - 1], "w", newline="", encoding="utf-8")
                    escritor = csv.writer(f_out)

                    if encabezado_real is not None:
                        escritor.writerow(encabezado_real)

                escritor.writerow(fila)
                filas_en_parte += 1

            f_out.close()

        return rutas_salida, total_filas_datos, num_partes, capacidad_datos

    except Exception as e:
        raise e


def seleccionar_y_dividir():
    ruta_csv = filedialog.askopenfilename(
        title="Seleccionar archivo CSV",
        filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
    )
    if not ruta_csv:
        return

    try:
        rutas, total, partes, capacidad = dividir_csv_en_partes(ruta_csv)

        # Mensaje final (resumen)
        nombres = "\n".join([f"- {os.path.basename(r)}" for r in rutas[:8]])
        if len(rutas) > 8:
            nombres += f"\n... y {len(rutas) - 8} más."

        mensaje = (
            f"✅ Proceso completado.\n\n"
            f"Filas totales de datos: {total}\n"
            f"Máximo de filas de datos por archivo: {capacidad}\n"
            f"Partes generadas: {partes}\n\n"
            f"Archivos:\n{nombres}\n\n"
            f"Se guardaron en la misma carpeta del archivo original."
        )
        messagebox.showinfo("Éxito", mensaje)

    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un problema:\n{e}")


def crear_interfaz():
    root = tk.Tk()
    root.title("Dividir CSV para Excel")
    root.resizable(False, False)

    frame = tk.Frame(root, padx=20, pady=20)
    frame.pack()

    etiqueta = tk.Label(
        frame,
        text="Selecciona un archivo CSV. Se dividirá en tantas partes como sea necesario\n"
             "para no exceder el límite de filas de Excel por archivo.",
        wraplength=420,
        justify="center"
    )
    etiqueta.pack(pady=(0, 15))

    boton = tk.Button(
        frame,
        text="Seleccionar CSV y dividir",
        command=seleccionar_y_dividir,
        width=28,
        height=2
    )
    boton.pack()

    root.mainloop()


if __name__ == "__main__":
    crear_interfaz()
