import streamlit as st
import pandas as pd
import math
import random

def exp_neg(media):
    """Genera un tiempo con distribución exponencial negativa."""
    rnd = random.random()
    tiempo = -media * math.log(1 - rnd)
    return rnd, tiempo

# ==========================================
# 1. CLASES DEL MOTOR DE SIMULACIÓN
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
        
        # Métricas
        self.llegadas_totales = 0
        self.abandonos_totales = 0

        # Inicialización de objetos y colas
        self.cantidad_slots = 15
        self.slots = [None] * self.cantidad_slots
        self.pacientes_activos = {}
        self.estado_triage = 'Libre'
        self.cola_triage = []

    # --- MÉTODOS DE GESTIÓN DE SLOTS ---
    def asignar_slot(self, paciente):
        """Busca el primer slot libre (None) y se lo asigna al paciente."""
        for i in range(self.cantidad_slots):
            if self.slots[i] is None:
                self.slots[i] = paciente.id
                paciente.slot_asignado = i
                break

    # --- MOTOR PRINCIPAL ---
    def ejecutar(self):
        # 1. Programar la primera llegada
        rnd_llegada, tiempo_llegada = exp_neg(self.params['media_llegadas'])
        self.eventos = {
            'llegada_paciente': tiempo_llegada,
            'fin_triage': float('inf'),
            'fin_atencion_general': float('inf'),
            'fin_cirugia': float('inf'),
            'fin_esterilizacion': float('inf')
        }
        
        # 2. Bucle principal de simulación
        while self.reloj < self.tiempo_x and self.iteracion < 100000:
            self.iteracion += 1
            
            # Buscar el evento inminente (el de menor tiempo)
            nombre_evento, tiempo_proximo = self.obtener_proximo_evento()
            
            # Chequeo de corte abrupto
            if tiempo_proximo > self.tiempo_x:
                self.reloj = self.tiempo_x
                break
                
            # Avanzar el reloj
            self.reloj = tiempo_proximo
            
            # Ejecutar lógica según el evento
            self.procesar_evento(nombre_evento)
            
            # Guardar en el vector solo si cumple los parámetros de visualización
            if self.iteracion >= self.desde_iter_i and self.reloj >= self.desde_hora_j:
                self.guardar_estado(nombre_evento)

    def obtener_proximo_evento(self):
        evento_inminente = min(self.eventos, key=self.eventos.get)
        tiempo_inminente = self.eventos[evento_inminente]
        return evento_inminente, tiempo_inminente

    def procesar_evento(self, evento):
        if evento == 'llegada_paciente':
            self.evento_llegada_paciente()
        elif evento == 'fin_triage':
            # Temporal: Apagamos el evento para que no genere un bucle infinito
            # En el próximo paso programaremos la lógica real de derivación
            self.eventos['fin_triage'] = float('inf') 

    # --- LÓGICA DE EVENTOS ---
    def evento_llegada_paciente(self):
        self.llegadas_totales += 1
        
        # Programo al siguiente
        rnd_lleg, tiempo_llegada = exp_neg(self.params['media_llegadas'])
        self.eventos['llegada_paciente'] = self.reloj + tiempo_llegada
        
        # Creamos al paciente que acaba de llegar
        nuevo_paciente = Paciente(id_paciente=self.llegadas_totales, tiempo_llegada=self.reloj)
        self.pacientes_activos[nuevo_paciente.id] = nuevo_paciente
        self.asignar_slot(nuevo_paciente)
        
        # Evaluamos el servidor (Triage)
        if self.estado_triage == 'Libre':
            self.estado_triage = 'Ocupado'
            nuevo_paciente.estado = 'En Triage'
            self.eventos['fin_triage'] = self.reloj + self.params['tiempo_triage']
        else:
            self.cola_triage.append(nuevo_paciente)
            nuevo_paciente.estado = 'Esperando Triage'

    def guardar_estado(self, nombre_evento):
        fila = {
            "Reloj": round(self.reloj, 4), 
            "Evento": nombre_evento, 
            "Cola Triage": len(self.cola_triage),
            "Estado Triage": self.estado_triage
        }
        self.vector_estado.append(fila)

# ==========================================
# 2. INTERFAZ GRÁFICA (STREAMLIT)
# ==========================================
def main():
    st.set_page_config(page_title="Simulador Guardia Odontológica", layout="wide")
    st.title("🦷 Simulador - Guardia Odontológica Sonrisas")
    
    with st.sidebar:
        st.header("⚙️ Parámetros de Simulación")
        
        st.subheader("Corte y Visualización")
        tiempo_x = st.number_input("Tiempo a simular (X min)", min_value=1.0, value=100.0, step=10.0)
        desde_iter_i = st.number_input("Mostrar desde iteración (i)", min_value=0, value=0)
        desde_hora_j = st.number_input("Mostrar desde hora (j)", min_value=0.0, value=0.0)
        
        st.divider()
        st.subheader("Variables del Sistema")
        media_llegadas = st.number_input("Media entre llegadas (min)", min_value=0.1, value=30.0)
        tiempo_triage = st.number_input("Demora en Triage (min)", min_value=0.1, value=5.0)

    st.info('Ajustá los parámetros en la barra lateral y presioná "Iniciar Simulación".')
    
    if st.button("🚀 Iniciar Simulación", type="primary", use_container_width=True):
        with st.spinner('Ejecutando la simulación...'):
            params = {
                'media_llegadas': media_llegadas,
                'tiempo_triage': tiempo_triage
            }
            
            simulador = SimuladorSonrisas(tiempo_x, desde_iter_i, desde_hora_j, params)
            simulador.ejecutar()
            
            st.success("¡Simulación completada con éxito!")
            
            st.header("📊 Métricas")
            col1, col2 = st.columns(2)
            col1.metric("Llegadas Totales", simulador.llegadas_totales)
            col2.metric("Abandonos", simulador.abandonos_totales)
            
            st.header("📋 Vector de Estado")
            if simulador.vector_estado:
                df = pd.DataFrame(simulador.vector_estado)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("No se registraron iteraciones en el rango solicitado.")

if __name__ == "__main__":
    main()
