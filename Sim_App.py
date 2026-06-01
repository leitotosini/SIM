import streamlit as st
import pandas as pd
import math
import random

# ==========================================
# 1. FUNCIONES ESTADÍSTICAS
# ==========================================
def exp_neg(media):
    """Genera un tiempo con distribución exponencial negativa."""
    rnd = random.random()
    tiempo = -media * math.log(1 - rnd)
    return rnd, tiempo

def uniforme(a, b):
    """Genera un tiempo con distribución uniforme."""
    rnd = random.random()
    tiempo = a + (b - a) * rnd
    return rnd, tiempo

# ==========================================
# 2. CLASES DEL MOTOR DE SIMULACIÓN
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

        # Gestión Visual (Slots)
        self.cantidad_slots = 15
        self.slots = [None] * self.cantidad_slots
        self.pacientes_activos = {}
        
        # Servidor Triage
        self.estado_triage = 'Libre'
        self.cola_triage = []
        self.paciente_en_triage = None
        
        # Servidor Odontólogo General
        self.estado_general = 'Libre'
        self.cola_general = []
        self.paciente_en_general = None
        
        # Servidor Cirujano
        self.estado_cirujano = 'Libre'
        self.cola_cirujano = []
        self.paciente_en_cirujano = None

    # --- MÉTODOS DE GESTIÓN DE SLOTS ---
    def asignar_slot(self, paciente):
        """Busca el primer slot libre y se lo asigna al paciente."""
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
            self.evento_fin_triage()
        elif evento.startswith('limite_espera_'):
            # Apagamos temporalmente el evento de espera para que no genere bucle
            self.eventos[evento] = float('inf')

    # --- LÓGICA DE EVENTOS ---
    def evento_llegada_paciente(self):
        self.llegadas_totales += 1
        
        # Programo al siguiente en llegar
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
            self.paciente_en_triage = nuevo_paciente
            self.eventos['fin_triage'] = self.reloj + self.params['tiempo_triage']
        else:
            self.cola_triage.append(nuevo_paciente)
            nuevo_paciente.estado = 'Esperando Triage'

    def evento_fin_triage(self):
        paciente = self.paciente_en_triage
        rnd_derivacion = random.random()
        
        if rnd_derivacion < self.params['prob_general']:
            # --- VA AL ODONTÓLOGO GENERAL ---
            if self.estado_general == 'Libre':
                self.estado_general = 'Ocupado'
                paciente.estado = 'Atención Gral'
                self.paciente_en_general = paciente
                
                # Programar fin de atención
                rnd_at, tiempo_at = exp_neg(self.params['media_gral'])
                self.eventos['fin_atencion_general'] = self.reloj + tiempo_at
            else:
                self.cola_general.append(paciente)
                paciente.estado = 'Cola Gral'
                # Programar límite de espera
                tiempo_limite = self.reloj + self.params['tiempo_paciencia']
                paciente.hora_limite_espera = tiempo_limite
                self.eventos[f'limite_espera_{paciente.id}'] = tiempo_limite
        else:
            # --- VA AL CIRUJANO ---
            if self.estado_cirujano == 'Libre':
                self.estado_cirujano = 'Ocupado'
                paciente.estado = 'En Cirugía'
                self.paciente_en_cirujano = paciente
                
                # Programar fin de cirugía
                rnd_at, tiempo_at = uniforme(self.params['min_cirugia'], self.params['max_cirugia'])
                self.eventos['fin_cirugia'] = self.reloj + tiempo_at
            else:
                self.cola_cirujano.append(paciente)
                paciente.estado = 'Cola Cirujano'
                # Programar límite de espera
                tiempo_limite = self.reloj + self.params['tiempo_paciencia']
                paciente.hora_limite_espera = tiempo_limite
                self.eventos[f'limite_espera_{paciente.id}'] = tiempo_limite

        # Revisamos si hay alguien esperando para entrar al Triage
        if len(self.cola_triage) > 0:
            siguiente_paciente = self.cola_triage.pop(0)
            siguiente_paciente.estado = 'En Triage'
            self.paciente_en_triage = siguiente_paciente
            self.eventos['fin_triage'] = self.reloj + self.params['tiempo_triage']
        else:
            self.estado_triage = 'Libre'
            self.paciente_en_triage = None
            self.eventos['fin_triage'] = float('inf')

    def guardar_estado(self, nombre_evento):
        fila = {
            "Reloj": round(self.reloj, 4), 
            "Evento": nombre_evento, 
            "Estado Triage": self.estado_triage,
            "Cola Triage": len(self.cola_triage),
            "Estado Gral": self.estado_general,
            "Cola Gral": len(self.cola_general),
            "Estado Cirujano": self.estado_cirujano,
            "Cola Cirujano": len(self.cola_cirujano)
        }
        
        # Agregamos dinámicamente las columnas de los slots
        for i in range(self.cantidad_slots):
            id_paciente = self.slots[i]
            if id_paciente is not None and id_paciente in self.pacientes_activos:
                pac = self.pacientes_activos[id_paciente]
                fila[f"P{i+1} ID"] = pac.id
                fila[f"P{i+1} Est"] = pac.estado
            else:
                fila[f"P{i+1} ID"] = "-"
                fila[f"P{i+1} Est"] = "-"
                
        self.vector_estado.append(fila)

# ==========================================
# 3. INTERFAZ GRÁFICA (STREAMLIT)
# ==========================================
def main():
    st.set_page_config(page_title="Simulador Guardia Odontológica", layout="wide")
    st.title("🦷 Simulador - Guardia Odontológica Sonrisas")
    
    with st.sidebar:
        st.header("⚙️ Parámetros de Simulación")
        
        st.subheader("Corte y Visualización")
        tiempo_x = st.number_input("Tiempo a simular (X min)", min_value=1.0, value=500.0, step=10.0)
        desde_iter_i = st.number_input("Mostrar desde iteración (i)", min_value=0, value=0)
        desde_hora_j = st.number_input("Mostrar desde hora (j)", min_value=0.0, value=0.0)
        
        st.divider()
        st.subheader("Variables del Sistema")
        media_llegadas = st.number_input("Media llegadas (min)", min_value=0.1, value=30.0)
        tiempo_triage = st.number_input("Demora en Triage (min)", min_value=0.1, value=5.0)
        prob_general = st.number_input("Prob. Derivación Gral (%)", min_value=0.0, max_value=100.0, value=70.0) / 100
        media_gral = st.number_input("Media atención Gral (min)", min_value=0.1, value=30.0)
        
        st.divider()
        st.subheader("Cirugía y Paciencia")
        min_cirugia = st.number_input("Min Cirugía (min)", min_value=0.1, value=40.0)
        max_cirugia = st.number_input("Max Cirugía (min)", min_value=0.1, value=60.0)
        tiempo_paciencia = st.number_input("Paciencia paciente (min)", min_value=1.0, value=30.0)

        st.divider()
            st.subheader("Esterilización Cirujano")
            pacientes_est = st.number_input("Pacientes para Esterilizar", min_value=1, value=3, step=1)
            tiempo_est = st.number_input("Tiempo Esterilización (min)", min_value=1.0, value=15.0)

    st.info('Ajustá los parámetros en la barra lateral y presioná "Iniciar Simulación".')
    
    if st.button("🚀 Iniciar Simulación", type="primary", use_container_width=True):
        with st.spinner('Ejecutando la simulación...'):
            params = {
                'media_llegadas': media_llegadas,
                'tiempo_triage': tiempo_triage,
                'prob_general': prob_general,
                'media_gral': media_gral,
                'min_cirugia': min_cirugia,
                'max_cirugia': max_cirugia,
                'tiempo_paciencia': tiempo_paciencia,
                'pacientes_est': pacientes_est,
                'tiempo_est': tiempo_est
            }
            
            simulador = SimuladorSonrisas(tiempo_x, desde_iter_i, desde_hora_j, params)
            simulador.ejecutar()
            
            st.success("¡Simulación completada con éxito!")
            
            st.header("📊 Métricas")
            col1, col2 = st.columns(2)
            col1.metric("Llegadas Totales", simulador.llegadas_totales)
            col2.metric("Abandonos (En progreso)", simulador.abandonos_totales)
            
            st.header("📋 Vector de Estado")
            if simulador.vector_estado:
                df = pd.DataFrame(simulador.vector_estado)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("No se registraron iteraciones en el rango solicitado.")

if __name__ == "__main__":
    main()
