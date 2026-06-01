import streamlit as st
import pandas as pd
import math
import random

# ==========================================
# 1. FUNCIONES ESTADÍSTICAS
# ==========================================
def exp_neg(media):
    rnd = random.random()
    tiempo = -media * math.log(1 - rnd)
    return rnd, tiempo

def uniforme(a, b):
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
        self.tiempo_entrada_cola = None # Fundamental para las métricas
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
        
        # Métricas Globales
        self.llegadas_totales = 0
        self.abandonos_totales = 0
        self.cant_general_atendidos = 0
        self.acum_espera_general_atendidos = 0.0
        
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
        self.cirujano_atendidos = 0 # Contador para esterilización

    # --- MÉTODOS DE GESTIÓN DE SLOTS Y PACIENTES ---
    def asignar_slot(self, paciente):
        for i in range(self.cantidad_slots):
            if self.slots[i] is None:
                self.slots[i] = paciente.id
                paciente.slot_asignado = i
                break

    def eliminar_paciente(self, id_paciente):
        """Borra al paciente y libera su slot visual en la tabla."""
        if id_paciente in self.pacientes_activos:
            paciente = self.pacientes_activos[id_paciente]
            if paciente.slot_asignado != -1:
                self.slots[paciente.slot_asignado] = None
            del self.pacientes_activos[id_paciente]

    # --- MOTOR PRINCIPAL ---
    def ejecutar(self):
        rnd_llegada, tiempo_llegada = exp_neg(self.params['media_llegadas'])
        self.eventos = {
            'llegada_paciente': tiempo_llegada,
            'fin_triage': float('inf'),
            'fin_atencion_general': float('inf'),
            'fin_cirugia': float('inf'),
            'fin_esterilizacion': float('inf')
        }
        
        while self.reloj < self.tiempo_x and self.iteracion < 100000:
            self.iteracion += 1
            nombre_evento, tiempo_proximo = self.obtener_proximo_evento()
            
            if tiempo_proximo > self.tiempo_x:
                self.reloj = self.tiempo_x
                break
                
            self.reloj = tiempo_proximo
            self.procesar_evento(nombre_evento)
            
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
            # Extraemos el ID del paciente directamente del nombre del evento
            id_pac = int(evento.split('_')[2])
            self.evento_limite_espera(id_pac, evento)
        elif evento == 'fin_atencion_general':
            self.evento_fin_atencion_general()
        elif evento == 'fin_cirugia':
            self.evento_fin_cirugia()
        elif evento == 'fin_esterilizacion':
            self.evento_fin_esterilizacion()

    # --- LÓGICA DE EVENTOS ---
    def evento_llegada_paciente(self):
        self.llegadas_totales += 1
        
        rnd_lleg, tiempo_llegada = exp_neg(self.params['media_llegadas'])
        self.eventos['llegada_paciente'] = self.reloj + tiempo_llegada
        
        nuevo_paciente = Paciente(id_paciente=self.llegadas_totales, tiempo_llegada=self.reloj)
        self.pacientes_activos[nuevo_paciente.id] = nuevo_paciente
        self.asignar_slot(nuevo_paciente)
        
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
            # --- DERIVACIÓN ODONTÓLOGO GENERAL ---
            if self.estado_general == 'Libre':
                self.estado_general = 'Ocupado'
                paciente.estado = 'Atención Gral'
                self.paciente_en_general = paciente
                self.cant_general_atendidos += 1 # Contabilizamos para la métrica
                
                rnd_at, tiempo_at = exp_neg(self.params['media_gral'])
                self.eventos['fin_atencion_general'] = self.reloj + tiempo_at
            else:
                paciente.tiempo_entrada_cola = self.reloj
                self.cola_general.append(paciente)
                paciente.estado = 'Cola Gral'
                
                tiempo_limite = self.reloj + self.params['tiempo_paciencia']
                paciente.hora_limite_espera = tiempo_limite
                self.eventos[f'limite_espera_{paciente.id}'] = tiempo_limite
        else:
            # --- DERIVACIÓN CIRUJANO ---
            if self.estado_cirujano == 'Libre':
                self.estado_cirujano = 'Ocupado'
                paciente.estado = 'En Cirugía'
                self.paciente_en_cirujano = paciente
                
                rnd_at, tiempo_at = uniforme(self.params['min_cirugia'], self.params['max_cirugia'])
                self.eventos['fin_cirugia'] = self.reloj + tiempo_at
            else:
                paciente.tiempo_entrada_cola = self.reloj
                self.cola_cirujano.append(paciente)
                paciente.estado = 'Cola Cirujano'
                
                tiempo_limite = self.reloj + self.params['tiempo_paciencia']
                paciente.hora_limite_espera = tiempo_limite
                self.eventos[f'limite_espera_{paciente.id}'] = tiempo_limite

        # ¿Avanza la cola de Triage?
        if len(self.cola_triage) > 0:
            siguiente_paciente = self.cola_triage.pop(0)
            siguiente_paciente.estado = 'En Triage'
            self.paciente_en_triage = siguiente_paciente
            self.eventos['fin_triage'] = self.reloj + self.params['tiempo_triage']
        else:
            self.estado_triage = 'Libre'
            self.paciente_en_triage = None
            self.eventos['fin_triage'] = float('inf')

    def evento_limite_espera(self, id_paciente, nombre_evento):
        self.eventos[nombre_evento] = float('inf') # Apagamos el reloj del evento
        
        if id_paciente in self.pacientes_activos:
            paciente = self.pacientes_activos[id_paciente]
            if paciente.estado in ['Cola Gral', 'Cola Cirujano']:
                rnd_abandono = random.random()
                if rnd_abandono < self.params['prob_abandono']:
                    self.abandonos_totales += 1
                    # Lo sacamos de la cola
                    if paciente.estado == 'Cola Gral':
                        self.cola_general.remove(paciente)
                    elif paciente.estado == 'Cola Cirujano':
                        self.cola_cirujano.remove(paciente)
                    
                    self.eliminar_paciente(id_paciente)

    def evento_fin_atencion_general(self):
        paciente_saliente = self.paciente_en_general
        self.eliminar_paciente(paciente_saliente.id)
        
        if len(self.cola_general) > 0:
            siguiente_paciente = self.cola_general.pop(0)
            siguiente_paciente.estado = 'Atención Gral'
            self.paciente_en_general = siguiente_paciente
            
            # Anulamos su probabilidad de irse porque ya lo están atendiendo
            self.eventos[f'limite_espera_{siguiente_paciente.id}'] = float('inf')
            
            # Sumamos a las métricas el tiempo que esperó y que sí fue atendido
            espera = self.reloj - siguiente_paciente.tiempo_entrada_cola
            self.acum_espera_general_atendidos += espera
            self.cant_general_atendidos += 1
            
            rnd_at, tiempo_at = exp_neg(self.params['media_gral'])
            self.eventos['fin_atencion_general'] = self.reloj + tiempo_at
        else:
            self.estado_general = 'Libre'
            self.paciente_en_general = None
            self.eventos['fin_atencion_general'] = float('inf')

    def evento_fin_cirugia(self):
        paciente_saliente = self.paciente_en_cirujano
        self.eliminar_paciente(paciente_saliente.id)
        
        self.cirujano_atendidos += 1
        
        # Control de esterilización
        if self.cirujano_atendidos >= self.params['pacientes_est']:
            self.estado_cirujano = 'Esterilizando'
            self.paciente_en_cirujano = None
            self.eventos['fin_cirugia'] = float('inf')
            self.eventos['fin_esterilizacion'] = self.reloj + self.params['tiempo_est']
            self.cirujano_atendidos = 0 # Reiniciamos el contador
        else:
            if len(self.cola_cirujano) > 0:
                siguiente_paciente = self.cola_cirujano.pop(0)
                siguiente_paciente.estado = 'En Cirugía'
                self.paciente_en_cirujano = siguiente_paciente
                self.eventos[f'limite_espera_{siguiente_paciente.id}'] = float('inf')
                
                rnd_at, tiempo_at = uniforme(self.params['min_cirugia'], self.params['max_cirugia'])
                self.eventos['fin_cirugia'] = self.reloj + tiempo_at
            else:
                self.estado_cirujano = 'Libre'
                self.paciente_en_cirujano = None
                self.eventos['fin_cirugia'] = float('inf')

    def evento_fin_esterilizacion(self):
        self.eventos['fin_esterilizacion'] = float('inf')
        
        # Al terminar de esterilizar, revisamos si quedó alguien colgado en la cola
        if len(self.cola_cirujano) > 0:
            siguiente_paciente = self.cola_cirujano.pop(0)
            siguiente_paciente.estado = 'En Cirugía'
            self.paciente_en_cirujano = siguiente_paciente
            self.eventos[f'limite_espera_{siguiente_paciente.id}'] = float('inf')
            
            rnd_at, tiempo_at = uniforme(self.params['min_cirugia'], self.params['max_cirugia'])
            self.eventos['fin_cirugia'] = self.reloj + tiempo_at
        else:
            self.estado_cirujano = 'Libre'

    def guardar_estado(self, nombre_evento):
        fila = {
            "Reloj": round(self.reloj, 4), 
            "Evento": nombre_evento, 
            "Est Triage": self.estado_triage,
            "Cola Triage": len(self.cola_triage),
            "Est Gral": self.estado_general,
            "Cola Gral": len(self.cola_general),
            "Est Cirujano": self.estado_cirujano,
            "Cola Cirujano": len(self.cola_cirujano)
        }
        
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
        prob_abandono = st.number_input("Prob. Abandono (%)", min_value=0.0, max_value=100.0, value=40.0) / 100
        
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
                'prob_abandono': prob_abandono,
                'pacientes_est': pacientes_est,
                'tiempo_est': tiempo_est
            }
            
            simulador = SimuladorSonrisas(tiempo_x, desde_iter_i, desde_hora_j, params)
            simulador.ejecutar()
            
            # --- CÁLCULOS FINALES ---
            pct_abandonos = (simulador.abandonos_totales / simulador.llegadas_totales * 100) if simulador.llegadas_totales > 0 else 0
            prom_espera_gral = (simulador.acum_espera_general_atendidos / simulador.cant_general_atendidos) if simulador.cant_general_atendidos > 0 else 0
            
            st.success("¡Simulación completada con éxito!")
            
            st.header("📊 Métricas")
            col1, col2, col3 = st.columns(3)
            col1.metric("Llegadas Totales", simulador.llegadas_totales)
            col2.metric("% Abandonos", f"{pct_abandonos:.2f}%")
            col3.metric("Espera Prom. Gral", f"{prom_espera_gral:.2f} min")
            
            st.header("📋 Vector de Estado")
            if simulador.vector_estado:
                df = pd.DataFrame(simulador.vector_estado)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("No se registraron iteraciones en el rango solicitado.")

if __name__ == "__main__":
    main()
