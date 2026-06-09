import streamlit as st
import pandas as pd
import math
import random
import plotly.express as px
import plotly.graph_objects as go

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
        self.historico_cirujano = 0 
        
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

    def ejecutar(self):
        rnd_llegada, tiempo_llegada = exp_neg(self.params['media_llegadas'])
        self.eventos = {
            'llegada_paciente': tiempo_llegada,
            'fin_triage': float('inf'),
            'fin_atencion_general': float('inf'),
            'fin_cirugia': float('inf'),
            'fin_esterilizacion': float('inf')
        }

        self.reset_transient()
        self.t_rnd_llegada = rnd_llegada
        self.t_tiempo_llegada = tiempo_llegada
        self.guardar_estado("Inicio")
        
        fin_por_tiempo = False
        while self.iteracion < 100000:
            self.iteracion += 1
            self.reset_transient()
            nombre_evento, tiempo_proximo = self.obtener_proximo_evento()
            
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
            
            if self.reloj >= self.desde_hora_j and len(self.vector_estado) < self.mostrar_iteraciones:
                self.guardar_estado(nombre_evento)
        
        if not fin_por_tiempo:
            if self.estado_cirujano == 'Ocupado':
                self.acum_tiempo_cirugia += (self.reloj - self.inicio_actividad_cirujano)
            elif self.estado_cirujano == 'Esterilizando':
                self.acum_tiempo_esterilizacion += (self.reloj - self.inicio_actividad_cirujano)
        
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
        self.historico_cirujano += 1 
        
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
# 3. CÁLCULO DE MÉTRICAS
# ==========================================
def calcular_metricas(simulador):
    pct_abandonos = (simulador.abandonos_totales / simulador.llegadas_totales * 100) if simulador.llegadas_totales > 0 else 0
    prom_espera_gral = (simulador.acum_espera_general_atendidos / simulador.cant_general_atendidos) if simulador.cant_general_atendidos > 0 else 0
    tiempo_final = simulador.reloj
    pct_ocupacion_cirugia = (simulador.acum_tiempo_cirugia / tiempo_final * 100) if tiempo_final > 0 else 0
    pct_ocupacion_est = (simulador.acum_tiempo_esterilizacion / tiempo_final * 100) if tiempo_final > 0 else 0
    return pct_abandonos, prom_espera_gral, pct_ocupacion_cirugia, pct_ocupacion_est

def render_multiples_simulaciones(contenedor, params, tiempo_x, min_cirugia, max_cirugia):
    with contenedor:
        cN1, cN2, cN3 = st.columns([1, 2, 1])
        with cN2:
            n_simulaciones = st.number_input("Cantidad de simulaciones (N)", min_value=2, max_value=5000, value=100, step=10)
            iniciar_multi = st.button("🔁 EJECUTAR N SIMULACIONES", type="primary", use_container_width=True)

        if iniciar_multi:
            if min_cirugia > max_cirugia:
                st.error("Error: El tiempo mínimo de cirugía no puede ser mayor al máximo.")
            else:
                n = int(n_simulaciones)
                progreso = st.progress(0, text="Ejecutando simulaciones...")
                datos = {'abandonos': [], 'espera': [], 'ocup_cirugia': [], 'ocup_est': []}
                for i in range(n):
                    sim = SimuladorSonrisas(tiempo_x, 0, tiempo_x + 1, params)
                    sim.ejecutar()
                    a, e, oc, oe = calcular_metricas(sim)
                    datos['abandonos'].append(a)
                    datos['espera'].append(e)
                    datos['ocup_cirugia'].append(oc)
                    datos['ocup_est'].append(oe)
                    progreso.progress((i + 1) / n, text=f"Simulación {i + 1} de {n}")
                progreso.empty()
                datos['n'] = n
                st.session_state['resultados_multi'] = datos

        if 'resultados_multi' in st.session_state:
            rm = st.session_state['resultados_multi']
            n = rm['n']
            st.success(f"✅ {n} simulaciones ejecutadas.")

            st.subheader("Valores Promedio")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("% Abandonos (prom)", f"{sum(rm['abandonos']) / n:.2f}%")
            m2.metric("% Ocup. Cirugía (prom)", f"{sum(rm['ocup_cirugia']) / n:.2f}%")
            m3.metric("% Ocup. Esterilización (prom)", f"{sum(rm['ocup_est']) / n:.2f}%")
            m4.metric("Espera Prom. Atención Gral (prom)", f"{sum(rm['espera']) / n:.2f} min")

            st.divider()
            st.subheader("📈 Estabilización de las Métricas")

            metricas_cfg = [
                ("% Abandonos", rm['abandonos'], "#E74C3C", "%"),
                ("% Ocupación Cirugía", rm['ocup_cirugia'], "#9B59B6", "%"),
                ("% Ocupación Esterilización", rm['ocup_est'], "#636EFA", "%"),
                ("Espera Promedio Atención General", rm['espera'], "#3498DB", " min"),
            ]

            col_izq, col_der = st.columns(2)
            columnas = [col_izq, col_der, col_izq, col_der]
            for (titulo, valores, color, sufijo), col in zip(metricas_cfg, columnas):
                with col:
                    acum = []
                    suma = 0.0
                    for idx, v in enumerate(valores):
                        suma += v
                        acum.append(suma / (idx + 1))
                    df_m = pd.DataFrame({
                        "Simulaciones": list(range(1, len(valores) + 1)),
                        "Promedio acumulado": acum
                    })
                    fig = px.line(df_m, x="Simulaciones", y="Promedio acumulado", title=titulo)
                    fig.update_traces(line_color=color)
                    fig.add_hline(y=acum[-1], line_dash="dash", line_color="#7F8C8D",
                                  annotation_text=f"Final: {acum[-1]:.2f}{sufijo}")
                    fig.update_layout(showlegend=False, yaxis_title="Promedio acumulado", height=350)
                    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 4. INTERFAZ GRÁFICA (REDESARROLLADA)
# ==========================================
def main():
    st.set_page_config(page_title="Simulador Guardia Odontológica", layout="wide", page_icon="🦷")
    
    st.markdown("<h1 style='text-align: center; color: #2E86C1;'>🦷 Simulador - Guardia Odontológica Sonrisas</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #5D6D7E;'>Grupo 9 - Trabajo Práctico 4</h4>", unsafe_allow_html=True)
    st.write("")
    
    with st.expander("⚙️ PANEL DE CONFIGURACIÓN DE PARÁMETROS", expanded=True):
        st.markdown("##### ⏱️ 1. Tiempos y Visualización")
        c1, c2, c3 = st.columns(3)
        tiempo_x = c1.number_input("Tiempo a simular (X min)", min_value=1, value=5000, step=10)
        mostrar_iteraciones = c2.number_input("Mostrar (i) iteraciones", min_value=1, value=300)
        desde_hora_j = c3.number_input("Mostrar desde hora (j)", min_value=0, value=0)
        
        st.markdown("##### 🏥 2. Recepción")
        c4, c5 = st.columns(2)
        media_llegadas = c4.number_input("Media llegadas (min)", min_value=1, value=30)
        tiempo_triage = c5.number_input("Demora en Triage (min)", min_value=1, value=5)

        st.markdown("##### 🦷 3. Odontólogo General")
        c6, c7 = st.columns(2)
        prob_general = c6.number_input("Prob. Derivación Gral (%)", min_value=0, max_value=100, value=70) / 100
        media_gral = c7.number_input("Media atención Gral (min)", min_value=1, value=30)

        st.markdown("##### 💉 4. Cirugía")
        c8, c9, c10, c11 = st.columns(4)
        min_cirugia = c8.number_input("Min Cirugía (min)", min_value=1, value=40)
        max_cirugia = c9.number_input("Max Cirugía (min)", min_value=1, value=60)
        pacientes_est = c10.number_input("Cant. cirugías p/ esterilización", min_value=1, value=3, step=1)
        tiempo_est = c11.number_input("Tiempo de esterilización (min)", min_value=1, value=15)

        st.markdown("##### ⏳ 5. Paciencia y Abandono")
        c12, c13 = st.columns(2)
        tiempo_paciencia = c12.number_input("Paciencia (min)", min_value=1, value=30)
        prob_abandono = c13.number_input("Abandono (%)", min_value=0, max_value=100, value=40) / 100

    st.write("")

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

    tab_individual, tab_multi = st.tabs(["🔬 Simulación Individual", "📈 Análisis Multi-Corrida (N Simulaciones)"])

    render_multiples_simulaciones(tab_multi, params, tiempo_x, min_cirugia, max_cirugia)

    with tab_individual:
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            iniciar = st.button("🚀 INICIAR SIMULACIÓN", type="primary", use_container_width=True)

        if iniciar:
            if min_cirugia > max_cirugia:
                st.error("Error: El tiempo mínimo de cirugía no puede ser mayor al máximo.")
            else:
                with st.spinner('Ejecutando el motor de eventos discretos...'):
                    simulador = SimuladorSonrisas(tiempo_x, mostrar_iteraciones, desde_hora_j, params)
                    simulador.ejecutar()

                    pct_abandonos, prom_espera_gral, pct_ocupacion_cirugia, pct_ocupacion_est = calcular_metricas(simulador)

                    st.session_state['resultados'] = {
                        'llegadas_totales': simulador.llegadas_totales,
                        'abandonos_totales': simulador.abandonos_totales,
                        'cant_general_atendidos': simulador.cant_general_atendidos,
                        'historico_cirujano': simulador.historico_cirujano,
                        'pct_abandonos': pct_abandonos,
                        'prom_espera_gral': prom_espera_gral,
                        'pct_ocupacion_cirugia': pct_ocupacion_cirugia,
                        'pct_ocupacion_est': pct_ocupacion_est,
                        'vector_estado': simulador.vector_estado
                    }

    if 'resultados' in st.session_state:
        res = st.session_state['resultados']

        with tab_individual:
            st.success("✅ Simulación calculada exitosamente.")
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard Analítico", "📋 Vector de Estado", "🏁 Última Fila", "🗺️ Diagrama del Modelo"])

        # ==========================================
        # PESTAÑA 1: DASHBOARD
        # ==========================================
        with tab1:
            st.header("Métricas Principales")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Llegadas Totales", res['llegadas_totales'])
            kpi2.metric("% Abandonos", f"{res['pct_abandonos']:.2f}%")
            kpi3.metric("Espera Prom. Gral", f"{res['prom_espera_gral']:.2f} min")

            st.divider()
            
            row_graf1, row_graf2 = st.columns(2)
            
            with row_graf1:
                st.subheader("Destino Final de los Pacientes")
                df_destino = pd.DataFrame({
                    'Estado': ['Atendidos Gral', 'Atendidos Cirugía', 'Abandonaron'],
                    'Cantidad': [res['cant_general_atendidos'], res['historico_cirujano'], res['abandonos_totales']]
                })
                fig_bar = px.bar(df_destino, x='Estado', y='Cantidad', text='Cantidad', color='Estado',
                                 color_discrete_map={'Atendidos Gral':'#3498DB', 'Atendidos Cirugía':'#9B59B6', 'Abandonaron':'#E74C3C'})
                fig_bar.update_traces(textposition='auto')
                st.plotly_chart(fig_bar, use_container_width=True)

            with row_graf2:
                st.subheader("Ocupación del Cirujano")
                libre = max(0, 100 - res['pct_ocupacion_cirugia'] - res['pct_ocupacion_est'])
                df_pie = pd.DataFrame({
                    'Estado': ['Atendiendo', 'Esterilizando', 'Libre'],
                    'Porcentaje': [res['pct_ocupacion_cirugia'], res['pct_ocupacion_est'], libre]
                })
                fig_pie = px.pie(df_pie, values='Porcentaje', names='Estado', hole=0.4,
                                 color='Estado',
                                 color_discrete_map={'Atendiendo':'#EF553B', 'Esterilizando':'#636EFA', 'Libre':'#00CC96'})
                st.plotly_chart(fig_pie, use_container_width=True)

            st.divider()
            
            st.subheader("Análisis de Rendimiento")
            row_graf3, row_graf4 = st.columns(2)
            
            with row_graf3:
                fig_gauge_abandono = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = res['pct_abandonos'],
                    title = {'text': "% de Abandonos"},
                    number = {'suffix': "%"},
                    gauge = {'axis': {'range': [None, 100]},
                             'bar': {'color': "#E74C3C"},
                             'steps': [
                                 {'range': [0, 20], 'color': "lightgreen"},
                                 {'range': [20, 40], 'color': "khaki"},
                                 {'range': [40, 100], 'color': "lightcoral"}]}
                ))
                st.plotly_chart(fig_gauge_abandono, use_container_width=True)
                
            with row_graf4:
                fig_gauge_espera = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = res['prom_espera_gral'],
                    title = {'text': "Espera Promedio Odont. Gral (min)"},
                    gauge = {'axis': {'range': [None, 60]},
                             'bar': {'color': "#3498DB"},
                             'steps': [
                                 {'range': [0, 30], 'color': "lightgreen"},
                                 {'range': [30, 45], 'color': "khaki"},
                                 {'range': [45, 60], 'color': "lightcoral"}]}
                ))
                st.plotly_chart(fig_gauge_espera, use_container_width=True)
                
            st.divider()
            st.subheader("📈 Evolución Histórica de las Colas (Lq)")
            st.info("Muestra el crecimiento y descongestión de las colas a lo largo del tiempo simulado.")
            
            df_plot = pd.DataFrame(res['vector_estado'])
            if len(df_plot) > 2000:
                df_plot = df_plot.sample(n=2000, random_state=1).sort_values(by="Reloj")
                
            fig_colas = px.line(
                df_plot, 
                x="Reloj", 
                y=["Cola Triage", "Cola Gral", "Cola Cirujano"],
                color_discrete_map={
                    "Cola Triage": "#F39C12", 
                    "Cola Gral": "#3498DB", 
                    "Cola Cirujano": "#9B59B6"
                }
            )
            fig_colas.update_traces(line_shape='hv')
            fig_colas.update_layout(
                xaxis_title="Reloj (Minutos)", 
                yaxis_title="Cantidad de Pacientes",
                legend_title_text="Servidores"
            )
            st.plotly_chart(fig_colas, use_container_width=True)

        # ==========================================
        # PESTAÑA 2: VECTOR DE ESTADO
        # ==========================================
        with tab2:
            st.header("📋 Vector de Estado")
            if res['vector_estado']:
                df = pd.DataFrame(res['vector_estado'])
                df_general = df.iloc[:-1]
                
                column_config = {
                    "Iteración": st.column_config.Column(pinned=True),
                    "Reloj": st.column_config.Column(pinned=True),
                    "Evento": st.column_config.Column(pinned=True),
                    "ID Paciente": st.column_config.Column(pinned=True),
                }
                st.caption("Grilla general de eventos. Seleccioná una fila para resaltarla. Las primeras columnas quedan fijas al hacer scroll horizontal.")
                st.dataframe(
                    df_general,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config=column_config,
                )
            else:
                st.warning("No se registraron iteraciones en el rango solicitado.")

        # ==========================================
        # PESTAÑA 3: ÚLTIMA FILA
        # ==========================================
        with tab3:
            st.header("🏁 Última Fila")
            st.info("Fila correspondiente al instante X exacto de corte.")
            if res['vector_estado']:
                df = pd.DataFrame(res['vector_estado'])
                df_ultima = df.iloc[[-1]]
                
                column_config_ultima = {
                    "Iteración": st.column_config.Column(pinned=True),
                    "Reloj": st.column_config.Column(pinned=True),
                    "Evento": st.column_config.Column(pinned=True)
                }
                
                st.dataframe(
                    df_ultima, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config=column_config_ultima
                )

        # ==========================================
        # PESTAÑA 4: DIAGRAMA DEL MODELO
        # ==========================================
        with tab4:
            st.header("🗺️ Mapa del Sistema (Teoría de Colas)")
            st.write("Representación lógica del flujo de pacientes, derivaciones y servidores.")
            
            st.graphviz_chart('''
                digraph G {
                    rankdir=LR;
                    node [shape=box, style=filled, fillcolor="#ECF0F1", color="#2E86C1", fontname="Helvetica"];
                    edge [color="#7F8C8D", fontname="Helvetica", fontsize=10];
                    
                    Llegada [shape=oval, fillcolor="#A9DFBF", label="Llegada Paciente\\nExp(30)"];
                    Triage [fillcolor="#F9E79F", label="Servidor Triage\\n(Demora 5 min)"];
                    Gral [label="Odontólogo General\\nExp(30)"];
                    Cirujano [label="Cirujano\\nUni(40, 60)"];
                    Salida [shape=oval, fillcolor="#F5B041", label="Fin de Atención"];
                    Abandono [shape=oval, fillcolor="#E74C3C", fontcolor=white, label="Abandono por\\nImpaciencia (30m)"];
                    Esterilizacion [shape=ellipse, fillcolor="#D7BDE2", label="Esterilización\\n(15 min)"];
                    
                    Llegada -> Triage;
                    Triage -> Gral [label=" RND < 0.70"];
                    Triage -> Cirujano [label=" RND >= 0.70"];
                    
                    Gral -> Salida;
                    Cirujano -> Salida;
                    
                    Gral -> Abandono [label=" p=0.40"];
                    Cirujano -> Abandono [label=" p=0.40"];
                    
                    Cirujano -> Esterilizacion [label=" Cada 3 pac.", dir=both];
                }
            ''')

if __name__ == "__main__":
    main()
