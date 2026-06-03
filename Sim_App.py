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
                
                tiempo_limite = self.reloj + self.params['tiempo_p
