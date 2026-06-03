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
# 2. CLASES 
# ==========================================
class Paciente:
    def __init__(self, id_paciente, tiempo_llegada):
        self.id = id_paciente
        self.estado = 'En Triage'
        self.tiempo_llegada = tiempo_llegada
        self.hora_limite_espera = None
        self.tiempo_entrada_cola = None
        self.slot_asignado = -1

class SimuladorSonrisas:
    def __init__(self, tiempo_x, mostrar_iteraciones, desde_hora_j, params):
        self.tiempo_x = tiempo_x
        self.mostrar_iteraciones = mostrar_iteraciones
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
        
        # Métricas Cirujano
        self.acum_tiempo_cirugia = 0.0
        self.acum_tiempo_esterilizacion = 0.0
        self.inicio_actividad_cirujano = 0.0
        
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
        self.cirujano_atendidos = 0

        # Valores transitorios (solo se muestran en la fila del evento que los genera)
        self.reset_transient()

    def reset_transient(self):
        self.t_id_paciente = None
        self.t_rnd_llegada = None
        self.t_tiempo_llegada = None
        self.t_rnd_derivacion = None
        self.t_derivado_a = None
        self.t_rnd_gral = None
        self.t_tiempo_gral = None
        self.t_rnd_cirujano = None
        self.t_tiempo_cirujano = None
        self.t_hora_limite = None
        self.t_rnd_espera = None
        self.t_sigue_esperando = None
        self.t_hora_fin_est = None

    def _fmt(self, val):
        if val is None or val == float('inf'):
            return ""
        return round(val, 4)

    # METODOS DE GESTIÓN DE SLOTS Y PACIENTES
    def asignar_slot(self, paciente):
        for i in range(self.cantidad_slots):
            if self.slots[i] is None:
                self.slots[i] = paciente.id
                paciente.slot_asignado = i
                break

    def eliminar_paciente(self, id_paciente):
        if id_paciente in self.pacientes_activos:
            paciente = self.pacientes_activos[id_paciente]
            if paciente.slot_asignado != -1:
                self.slots[paciente.slot_asignado] = None
            del self.pacientes_activos[id_paciente]

    # PRINCIPAL
    def ejecutar(self):
        rnd_llegada, tiempo_llegada = exp_neg(self.params['media_llegadas'])
        self.eventos = {
            'llegada_paciente': tiempo_llegada,
            'fin_triage': float('inf'),
            'fin_atencion_general': float('inf'),
            'fin_cirugia': float('inf'),
            'fin_esterilizacion': float('inf')
        }

        # Evento "Inicio": se genera el primer RND/tiempo de llegada en reloj 0
        self.reset_transient()
        self.t_rnd_llegada = rnd_llegada
        self.t_tiempo_llegada = tiempo_llegada
        self.guardar_estado("Inicio")
        
        fin_por_tiempo = False
        # Simula hasta el tiempo X o como máximo 100.000 iteraciones, lo que ocurra primero
        while self.iteracion < 100000:
            self.iteracion += 1
            self.reset_transient()
            nombre_evento, tiempo_proximo = self.obtener_proximo_evento()
            
            # CORTE por tiempo X
            if tiempo_proximo > self.tiempo_x:
                if self.estado_cirujano == 'Ocupado':
                    self.acum_tiempo_cirugia += (self.tiempo_x - self.inicio_actividad_cirujano)
                elif self.estado_cirujano == 'Esterilizando':
                    self.acum_tiempo_esterilizacion += (self.tiempo_x - self.inicio_actividad_cirujano)
                
                self.reloj = self.tiempo_x
                fin_por_tiempo = True
                break
                
            self.reloj = tiempo_proximo
            self.procesar_evento(nombre_evento)
            
            # Solo se materializan (i) filas a mostrar, a partir de la hora j
            if self.reloj >= self.desde_hora_j and len(self.vector_estado) < self.mostrar_iteraciones:
                self.guardar_estado(nombre_evento)
        
        # Si la simulación terminó por límite de iteraciones N (no por tiempo X),
        # cerramos la actividad en curso del cirujano hasta el reloj final
        if not fin_por_tiempo:
            if self.estado_cirujano == 'Ocupado':
                self.acum_tiempo_cirugia += (self.reloj - self.inicio_actividad_cirujano)
            elif self.estado_cirujano == 'Esterilizando':
                self.acum_tiempo_esterilizacion += (self.reloj - self.inicio_actividad_cirujano)
        
        # La última fila siempre es FIN_SIMULACIÓN (sin objetos pacientes)
        self.guardar_estado("FIN_SIMULACIÓN", con_pacientes=False)

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
            id_pac = int(evento.split('_')[2])
            self.evento_limite_espera(id_pac, evento)
        elif evento == 'fin_atencion_general':
            self.evento_fin_atencion_general()
        elif evento == 'fin_cirugia':
            self.evento_fin_cirugia()
        elif evento == 'fin_esterilizacion':
            self.evento_fin_esterilizacion()

    # LOGICA DE EVENTOS
    def evento_llegada_paciente(self):
        self.llegadas_totales += 1
        
        rnd_lleg, tiempo_llegada = exp_neg(self.params['media_llegadas'])
        self.eventos['llegada_paciente'] = self.reloj + tiempo_llegada
        self.t_rnd_llegada = rnd_lleg
        self.t_tiempo_llegada = tiempo_llegada
        
        nuevo_paciente = Paciente(id_paciente=self.llegadas_totales, tiempo_llegada=self.reloj)
        self.t_id_paciente = nuevo_paciente.id
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
        self.t_id_paciente = paciente.id
        rnd_derivacion = random.random()
        self.t_rnd_derivacion = rnd_derivacion
        
        if rnd_derivacion < self.params['prob_general']:
            self.t_derivado_a = "Atención General"
            if self.estado_general == 'Libre':
                self.estado_general = 'Ocupado'
                paciente.estado = 'Atención Gral'
                self.paciente_en_general = paciente
                self.cant_general_atendidos += 1
                
                rnd_at, tiempo_at = exp_neg(self.params['media_gral'])
                self.eventos['fin_atencion_general'] = self.reloj + tiempo_at
                self.t_rnd_gral = rnd_at
                self.t_tiempo_gral = tiempo_at
            else:
                paciente.tiempo_entrada_cola = self.reloj
                self.cola_general.append(paciente)
                paciente.estado = 'Cola Gral'
                
                tiempo_limite = self.reloj + self.params['tiempo_paciencia']
                paciente.hora_limite_espera = tiempo_limite
                self.eventos[f'limite_espera_{paciente.id}'] = tiempo_limite
        else:
            self.t_derivado_a = "Cirugía"
            if self.estado_cirujano == 'Libre':
                self.estado_cirujano = 'Ocupado'
                self.inicio_actividad_cirujano = self.reloj
                paciente.estado = 'En Cirugía'
                self.paciente_en_cirujano = paciente
                
                rnd_at, tiempo_at = uniforme(self.params['min_cirugia'], self.params['max_cirugia'])
                self.eventos['fin_cirugia'] = self.reloj + tiempo_at
                self.t_rnd_cirujano = rnd_at
                self.t_tiempo_cirujano = tiempo_at
            else:
                paciente.tiempo_entrada_cola = self.reloj
                self.cola_cirujano.append(paciente)
                paciente.estado = 'Cola Cirujano'
                
                tiempo_limite = self.reloj + self.params['tiempo_paciencia']
                paciente.hora_limite_espera = tiempo_limite
                self.eventos[f'limite_espera_{paciente.id}'] = tiempo_limite

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
        self.eventos.pop(nombre_evento, None)
        self.t_id_paciente = id_paciente
        
        if id_paciente in self.pacientes_activos:
            paciente = self.pacientes_activos[id_paciente]
            if paciente.estado in ['Cola Gral', 'Cola Cirujano']:
                rnd_abandono = random.random()
                self.t_hora_limite = paciente.hora_limite_espera
                self.t_rnd_espera = rnd_abandono
                if rnd_abandono < self.params['prob_abandono']:
                    self.t_sigue_esperando = "No"
                    self.abandonos_totales += 1
                    if paciente.estado == 'Cola Gral':
                        self.cola_general.remove(paciente)
                    elif paciente.estado == 'Cola Cirujano':
                        self.cola_cirujano.remove(paciente)
                    
                    self.eliminar_paciente(id_paciente)
                else:
                    self.t_sigue_esperando = "Sí"

    def evento_fin_atencion_general(self):
        paciente_saliente = self.paciente_en_general
        self.t_id_paciente = paciente_saliente.id
        self.eliminar_paciente(paciente_saliente.id)
        
        if len(self.cola_general) > 0:
            siguiente_paciente = self.cola_general.pop(0)
            siguiente_paciente.estado = 'Atención Gral'
            self.paciente_en_general = siguiente_paciente
            
            self.eventos.pop(f'limite_espera_{siguiente_paciente.id}', None)
            
            espera = self.reloj - siguiente_paciente.tiempo_entrada_cola
            self.acum_espera_general_atendidos += espera
            self.cant_general_atendidos += 1
            
            rnd_at, tiempo_at = exp_neg(self.params['media_gral'])
            self.eventos['fin_atencion_general'] = self.reloj + tiempo_at
            self.t_rnd_gral = rnd_at
            self.t_tiempo_gral = tiempo_at
        else:
            self.estado_general = 'Libre'
            self.paciente_en_general = None
            self.eventos['fin_atencion_general'] = float('inf')

    def evento_fin_cirugia(self):
        paciente_saliente = self.paciente_en_cirujano
        self.t_id_paciente = paciente_saliente.id
        self.eliminar_paciente(paciente_saliente.id)
        
        self.acum_tiempo_cirugia += (self.reloj - self.inicio_actividad_cirujano)
        self.cirujano_atendidos += 1
        
        if self.cirujano_atendidos >= self.params['pacientes_est']:
            self.estado_cirujano = 'Esterilizando'
            self.inicio_actividad_cirujano = self.reloj
            self.paciente_en_cirujano = None
            self.eventos['fin_cirugia'] = float('inf')
            self.eventos['fin_esterilizacion'] = self.reloj + self.params['tiempo_est']
            self.t_hora_fin_est = self.eventos['fin_esterilizacion']
            self.cirujano_atendidos = 0
        else:
            if len(self.cola_cirujano) > 0:
                siguiente_paciente = self.cola_cirujano.pop(0)
                siguiente_paciente.estado = 'En Cirugía'
                self.paciente_en_cirujano = siguiente_paciente
                self.eventos.pop(f'limite_espera_{siguiente_paciente.id}', None)
                
                self.inicio_actividad_cirujano = self.reloj
                rnd_at, tiempo_at = uniforme(self.params['min_cirugia'], self.params['max_cirugia'])
                self.eventos['fin_cirugia'] = self.reloj + tiempo_at
                self.t_rnd_cirujano = rnd_at
                self.t_tiempo_cirujano = tiempo_at
            else:
                self.estado_cirujano = 'Libre'
                self.paciente_en_cirujano = None
                self.eventos['fin_cirugia'] = float('inf')

    def evento_fin_esterilizacion(self):
        self.eventos['fin_esterilizacion'] = float('inf')
        
        self.acum_tiempo_esterilizacion += (self.reloj - self.inicio_actividad_cirujano)
        
        if len(self.cola_cirujano) > 0:
            siguiente_paciente = self.cola_cirujano.pop(0)
            siguiente_paciente.estado = 'En Cirugía'
            self.paciente_en_cirujano = siguiente_paciente
            self.eventos.pop(f'limite_espera_{siguiente_paciente.id}', None)
            
            self.inicio_actividad_cirujano = self.reloj
            rnd_at, tiempo_at = uniforme(self.params['min_cirugia'], self.params['max_cirugia'])
            self.eventos['fin_cirugia'] = self.reloj + tiempo_at
            self.t_rnd_cirujano = rnd_at
            self.t_tiempo_cirujano = tiempo_at
        else:
            self.estado_cirujano = 'Libre'

    def guardar_estado(self, nombre_evento, con_pacientes=True):
        fila = {
            "Iteración": self.iteracion,
            "Reloj": round(self.reloj, 4),
            "Evento": nombre_evento,
            "ID Paciente": str(self.t_id_paciente) if self.t_id_paciente is not None else "",
            "RND llegada pacientes": self._fmt(self.t_rnd_llegada),
            "tiempo llegada paciente": self._fmt(self.t_tiempo_llegada),
            "hora llegada paciente": self._fmt(self.eventos['llegada_paciente']),
            "hora fin triage": self._fmt(self.eventos['fin_triage']),
            "RND derivación": self._fmt(self.t_rnd_derivacion),
            "derivado a": self.t_derivado_a if self.t_derivado_a is not None else "",
            "RND atención general": self._fmt(self.t_rnd_gral),
            "tiempo atención general": self._fmt(self.t_tiempo_gral),
            "hora fin atención general": self._fmt(self.eventos['fin_atencion_general']),
            "RND cirujano": self._fmt(self.t_rnd_cirujano),
            "tiempo cirujano": self._fmt(self.t_tiempo_cirujano),
            "hora fin cirujano": self._fmt(self.eventos['fin_cirugia']),
            "hora límite espera": self._fmt(self.t_hora_limite),
            "RND sigue esperando": self._fmt(self.t_rnd_espera),
            "Sigue esperando?": self.t_sigue_esperando if self.t_sigue_esperando is not None else "",
            "hora fin esterilización": self._fmt(self.t_hora_fin_est),
            "Est Triage": self.estado_triage,
            "Cola Triage": len(self.cola_triage),
            "Est Gral": self.estado_general,
            "Cola Gral": len(self.cola_general),
            "Est Cirujano": self.estado_cirujano,
            "Cola Cirujano": len(self.cola_cirujano),
            "Cant. cirugías p/ esterilización": self.cirujano_atendidos,
            "Acumulador tiempo en cirugía": round(self.acum_tiempo_cirugia, 4),
            "Acumulador tiempo en esterilización": round(self.acum_tiempo_esterilizacion, 4),
            "Contador de pacientes": self.llegadas_totales,
            "Contador pacientes sin atención": self.abandonos_totales,
            "Acumulador tiempo espera de atención general": round(self.acum_espera_general_atendidos, 4),
            "Contador de pacientes generales atendidos": self.cant_general_atendidos
        }
        
        for i in range(self.cantidad_slots):
            id_paciente = self.slots[i]
            if con_pacientes and id_paciente is not None and id_paciente in self.pacientes_activos:
                pac = self.pacientes_activos[id_paciente]
                fila[f"P{i+1} ID"] = pac.id
                fila[f"P{i+1} Est"] = pac.estado
                fila[f"P{i+1} Hora llegada a cola"] = self._fmt(pac.tiempo_entrada_cola)
                fila[f"P{i+1} Hora límite espera"] = self._fmt(pac.hora_limite_espera)
            else:
                fila[f"P{i+1} ID"] = "-"
                fila[f"P{i+1} Est"] = "-"
                fila[f"P{i+1} Hora llegada a cola"] = "-"
                fila[f"P{i+1} Hora límite espera"] = "-"
                
        self.vector_estado.append(fila)

# ==========================================
# 3. INTERFAZ GRÁFICA
# ==========================================
def main():
    st.set_page_config(page_title="Simulador Guardia Odontológica", layout="wide")
    st.title("🦷 Simulador - Guardia Odontológica Sonrisas - Grupo 9")
    
    with st.sidebar:
        st.header("⚙️ Parámetros de Simulación")
        
        st.subheader("Corte y Visualización")
        tiempo_x = st.number_input("Tiempo a simular (X min)", min_value=1, value=5000, step=10)
        mostrar_iteraciones = st.number_input("Mostrar (i) iteraciones", min_value=1, value=300)
        desde_hora_j = st.number_input("Mostrar desde hora (j)", min_value=0, value=0)
        
        st.divider()
        st.subheader("Variables del Sistema")
        media_llegadas = st.number_input("Media llegadas (min)", min_value=1, value=30)
        tiempo_triage = st.number_input("Demora en Triage (min)", min_value=1, value=5)
        prob_general = st.number_input("Prob. Derivación Gral (%)", min_value=0, max_value=100, value=70) / 100
        media_gral = st.number_input("Media atención Gral (min)", min_value=1, value=30)
        
        st.divider()
        st.subheader("Cirugía y Paciencia")
        min_cirugia = st.number_input("Min Cirugía (min)", min_value=1, value=40)
        max_cirugia = st.number_input("Max Cirugía (min)", min_value=1, value=60)
        tiempo_paciencia = st.number_input("Paciencia paciente (min)", min_value=1, value=30)
        prob_abandono = st.number_input("Prob. Abandono (%)", min_value=0, max_value=100, value=40) / 100
        
        st.divider()
        st.subheader("Esterilización Cirujano")
        pacientes_est = st.number_input("Pacientes para Esterilizar", min_value=1, value=3, step=1)
        tiempo_est = st.number_input("Tiempo Esterilización (min)", min_value=1, value=15)

    st.info('Ajustá los parámetros en la barra lateral y presioná "Iniciar Simulación".')
    
    if st.button("🚀 Iniciar Simulación", type="primary", use_container_width=True):
        if min_cirugia > max_cirugia:
            st.error("Error: El tiempo mínimo de cirugía no puede ser mayor al máximo.")
            return

        with st.spinner('Ejecutando la simulación y calculando métricas...'):
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
            
            simulador = SimuladorSonrisas(tiempo_x, mostrar_iteraciones, desde_hora_j, params)
            simulador.ejecutar()
            
            # CÁLCULOS
            pct_abandonos = (simulador.abandonos_totales / simulador.llegadas_totales * 100) if simulador.llegadas_totales > 0 else 0
            prom_espera_gral = (simulador.acum_espera_general_atendidos / simulador.cant_general_atendidos) if simulador.cant_general_atendidos > 0 else 0
            
            tiempo_final = simulador.reloj
            pct_ocupacion_cirugia = (simulador.acum_tiempo_cirugia / tiempo_final * 100) if tiempo_final > 0 else 0
            pct_ocupacion_est = (simulador.acum_tiempo_esterilizacion / tiempo_final * 100) if tiempo_final > 0 else 0

            # Guardamos los resultados en sesión para que persistan ante reruns
            # (la selección de filas de la tabla provoca un rerun)
            st.session_state['resultados'] = {
                'llegadas_totales': simulador.llegadas_totales,
                'pct_abandonos': pct_abandonos,
                'prom_espera_gral': prom_espera_gral,
                'pct_ocupacion_cirugia': pct_ocupacion_cirugia,
                'pct_ocupacion_est': pct_ocupacion_est,
                'vector_estado': simulador.vector_estado
            }

    # Renderizado de resultados (fuera del bloque del botón para que sobrevivan a los reruns)
    if 'resultados' in st.session_state:
        res = st.session_state['resultados']

        st.success("Simulación completada con éxito!!!")

        st.header("📊 Métricas")
        col1, col2, col3 = st.columns(3)
        col1.metric("Llegadas Totales", res['llegadas_totales'])
        col2.metric("% Abandonos", f"{res['pct_abandonos']:.2f}%")
        col3.metric("Espera Prom. Gral", f"{res['prom_espera_gral']:.2f} min")

        st.subheader("Ocupación del Cirujano")
        col4, col5, col6 = st.columns(3)
        col4.metric("% Atendiendo", f"{res['pct_ocupacion_cirugia']:.2f}%")
        col5.metric("% Esterilizando", f"{res['pct_ocupacion_est']:.2f}%")
        col6.metric("% Libre", f"{max(0, 100 - res['pct_ocupacion_cirugia'] - res['pct_ocupacion_est']):.2f}%")

        st.header("📋 Vector de Estado")
        if res['vector_estado']:
            df = pd.DataFrame(res['vector_estado'])
            column_config = {
                "Iteración": st.column_config.Column(pinned=True),
                "Reloj": st.column_config.Column(pinned=True),
                "Evento": st.column_config.Column(pinned=True),
                "ID Paciente": st.column_config.Column(pinned=True),
            }
            st.caption("Hacé click en una fila para resaltarla por completo. Las columnas Iteración, Reloj, Evento e ID Paciente quedan fijas a la izquierda.")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config=column_config,
            )
        else:
            st.warning("No se registraron iteraciones en el rango solicitado.")

if __name__ == "__main__":
    main()
