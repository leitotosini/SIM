import streamlit as st
import pandas as pd
import math
import random

# ==========================================
# 1. CLASES 
# ==========================================
class Paciente:
    def __init__(self, id_paciente, tiempo_llegada):
        self.id = id_paciente
        self.estado = 'En Triage'
        self.tiempo_llegada = tiempo_llegada
        self.hora_limite_espera = None
        self.slot_asignado = -1

class SimuladorSonrisas:
    def __init__(self, tiempo_x, desde_iter_i, desde_hora_j, params):
        self.tiempo_x = tiempo_x
        self.desde_iter_i = desde_iter_i
        self.desde_hora_j = desde_hora_j
        self.params = params
        
        self.reloj = 0.0
        self.iteracion = 0
        self.vector_estado = []
        
        # Métricas iniciales
        self.llegadas_totales = 0
        self.abandonos_totales = 0

    def ejecutar(self): 
        # Por ahora, generamos un par de filas de prueba
        self.vector_estado.append({
            "Reloj": 0.0, "Evento": "Inicio", "Cola Triage": 0, "Estado General": "Libre"
        })
        self.vector_estado.append({
            "Reloj": 15.2, "Evento": "Llegada Paciente", "Cola Triage": 1, "Estado General": "Libre"
        })
        
        self.llegadas_totales = 1 # Dato de prueba

# ==========================================
# 2. INTERFAZ GRÁFICA 
# ==========================================
def main():
    st.set_page_config(page_title="Simulador Guardia Odontológica", layout="wide")
    st.title("🦷 Simulador - Guardia Odontológica Sonrisas")
    
    # --- BARRA LATERAL (CONFIGURACIONES) ---
    with st.sidebar:
        st.header("⚙️ Parámetros de Simulación")
        
        st.subheader("Corte y Visualización")
        tiempo_x = st.number_input("Tiempo a simular (X min)", min_value=1.0, value=1000.0, step=10.0)
        desde_iter_i = st.number_input("Mostrar desde iteración (i)", min_value=0, value=0)
        desde_hora_j = st.number_input("Mostrar desde hora (j)", min_value=0.0, value=0.0)
        
        st.divider()
        st.subheader("Variables del Sistema")
        media_llegadas = st.number_input("Media entre llegadas (min)", min_value=0.1, value=30.0)
        tiempo_triage = st.number_input("Demora en Triage (min)", min_value=0.1, value=5.0)

    # --- PANEL CENTRAL ---
    st.info('Ajustá los parámetros en la barra lateral y presioná "Iniciar Simulación".')
    
    if st.button("🚀 Iniciar Simulación", type="primary", use_container_width=True):
        with st.spinner('Ejecutando la simulación...'):
            
            # Empaquetamos los parámetros elegidos 
            params = {
                'media_llegadas': media_llegadas,
                'tiempo_triage': tiempo_triage
            }
            
            # Instanciamos y corremos el simulador
            simulador = SimuladorSonrisas(tiempo_x, desde_iter_i, desde_hora_j, params)
            simulador.ejecutar()
            
            # --- MOSTRAR RESULTADOS ---
            st.success("¡Simulación completada con éxito!")
            
            st.header("📊 Métricas")
            col1, col2 = st.columns(2)
            col1.metric("Llegadas Totales", simulador.llegadas_totales)
            col2.metric("Abandonos", simulador.abandonos_totales)
            
            st.header("📋 Vector de Estado")
            if simulador.vector_estado:
                # Convertimos la lista de diccionarios a una tabla de Pandas
                df = pd.DataFrame(simulador.vector_estado)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("No se registraron iteraciones en el rango solicitado.")

if __name__ == "__main__":
    main()
