"""
Sistema de Telemetría y Control de Volumen
HMI Simulada en Python - Aproximación funcional del diagrama de clases UML
Universidad Tecnológica de Bolívar - Computación e Interfaces NRC: 1476

Autores:
  Santiago Payares Gonzalez     T00068704
  Luis Felipe Gonzalez          T00067734
  Cristian Matteo Benitez       T00078658
  Sebastián Felipe Caicedo Acosta T00070496
"""

import math
import time
import random
import sqlite3
from datetime import datetime



# Sensor ultrasonico
# Simula las lecturas del sensor HC-SR04 conectado al ESP32

class SensorUltrasonico:
    """Representa el sensor HC-SR04. En el sistema real, los datos llegan
    por puerto serial desde el ESP32."""

    def __init__(self, distancia_min_cm: float = 5.0, distancia_max_cm: float = 400.0):
        self.distancia_min = distancia_min_cm
        self.distancia_max = distancia_max_cm
        self._ultima_lectura: float = 0.0

    def leer_distancia(self) -> float:
        """Simula una lectura del sensor. En producción, esto lee del puerto serial."""
        # Simulación: nivel bajando lentamente con pequeño ruido
        self._ultima_lectura = round(random.uniform(10.0, 80.0), 2)
        return self._ultima_lectura

    @property
    def ultima_lectura(self) -> float:
        return self._ultima_lectura



# Tanque
# Modelo matemático del tanque cilíndrico

class Tanque:
    """Contiene la geometría del tanque y calcula el volumen disponible.
    Fórmula: V = π * r² * (H - d)
    Donde:
      r = radio del tanque (cm)
      H = altura total del tanque (cm)
      d = distancia medida por el sensor (cm)
    """

    def __init__(self, radio_cm: float, altura_cm: float, nombre: str = "Tanque Principal"):
        self.nombre = nombre
        self.radio = radio_cm          # cm
        self.altura = altura_cm        # cm
        self._distancia_actual = 0.0   # cm (lectura del sensor)

    def actualizar_distancia(self, distancia: float) -> None:
        """Recibe la distancia medida por el sensor y la almacena."""
        self._distancia_actual = distancia

    def calcular_volumen(self) -> float:
        """Retorna el volumen de líquido en cm³."""
        nivel_liquido = self.altura - self._distancia_actual
        if nivel_liquido < 0:
            nivel_liquido = 0.0
        return round(math.pi * (self.radio ** 2) * nivel_liquido, 2)

    def calcular_porcentaje(self) -> float:
        """Retorna el porcentaje de llenado del tanque."""
        volumen_actual = self.calcular_volumen()
        volumen_total = math.pi * (self.radio ** 2) * self.altura
        if volumen_total == 0:
            return 0.0
        return round((volumen_actual / volumen_total) * 100, 1)

    def calcular_volumen_total(self) -> float:
        return round(math.pi * (self.radio ** 2) * self.altura, 2)

    @property
    def nivel_cm(self) -> float:
        """Nivel de líquido en cm."""
        return round(max(0.0, self.altura - self._distancia_actual), 2)



# Actuador


class Actuador:
    """Representa el relé + bomba + buzzer. Activa o desactiva según el
    porcentaje de llenado del tanque."""

    def __init__(self, umbral_bajo: float = 20.0, umbral_alto: float = 90.0):
        self.umbral_bajo = umbral_bajo    # % — activa bomba
        self.umbral_alto = umbral_alto    # % — activa alarma
        self.bomba_activa = False
        self.alarma_activa = False

    def evaluar(self, porcentaje: float) -> dict:
        """Evalúa el nivel y activa/desactiva actuadores."""
        self.bomba_activa = porcentaje < self.umbral_bajo
        self.alarma_activa = porcentaje > self.umbral_alto
        return {
            "bomba": self.bomba_activa,
            "alarma": self.alarma_activa
        }

    def estado(self) -> str:
        estados = []
        if self.bomba_activa:
            estados.append("BOMBA: ON (nivel bajo)")
        else:
            estados.append("BOMBA: OFF")
        if self.alarma_activa:
            estados.append("ALARMA: ON (sobrellenado)")
        else:
            estados.append("ALARMA: OFF")
        return " | ".join(estados)



# Base de datos


class BaseDatos:
    """Gestiona la base de datos SQLite para historial de lecturas."""

    def __init__(self, ruta: str = "telemetria_tanque.db"):
        self.ruta = ruta
        self._conexion = sqlite3.connect(self.ruta)
        self._crear_tabla()

    def _crear_tabla(self) -> None:
        cursor = self._conexion.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lecturas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                distancia   REAL,
                nivel_cm    REAL,
                volumen_cm3 REAL,
                porcentaje  REAL,
                bomba       INTEGER,
                alarma      INTEGER
            )
        """)
        self._conexion.commit()

    def guardar_lectura(self, distancia: float, nivel: float, volumen: float,
                        porcentaje: float, bomba: bool, alarma: bool) -> None:
        cursor = self._conexion.cursor()
        cursor.execute("""
            INSERT INTO lecturas (timestamp, distancia, nivel_cm, volumen_cm3,
                                  porcentaje, bomba, alarma)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), distancia, nivel, volumen,
              porcentaje, int(bomba), int(alarma)))
        self._conexion.commit()

    def obtener_ultimas(self, n: int = 5) -> list:
        cursor = self._conexion.cursor()
        cursor.execute("""
            SELECT timestamp, distancia, nivel_cm, volumen_cm3, porcentaje, bomba, alarma
            FROM lecturas ORDER BY id DESC LIMIT ?
        """, (n,))
        return cursor.fetchall()

    def cerrar(self) -> None:
        self._conexion.close()



# HMI  (Human-Machine Interface)

class HMI:
    """Interfaz principal del sistema. Integra sensor, tanque, actuadores
    y base de datos. En la versión final usará tkinter o PyQt5."""

    def __init__(self):
        # Configuración del tanque (radio=25cm, altura=100cm)
        self.tanque = Tanque(radio_cm=25.0, altura_cm=100.0, nombre="Tanque A")
        self.sensor = SensorUltrasonico()
        self.actuador = Actuador(umbral_bajo=20.0, umbral_alto=85.0)
        self.db = BaseDatos()
        self.frecuencia_muestreo = 2  # segundos

    def configurar_tanque(self, radio: float, altura: float) -> None:
        """Permite al usuario configurar las dimensiones del tanque."""
        self.tanque.radio = radio
        self.tanque.altura = altura
        print(f"[CONFIG] Tanque actualizado: radio={radio}cm, altura={altura}cm")
        print(f"         Volumen total = {self.tanque.calcular_volumen_total():.2f} cm³")

    def ciclo_medicion(self) -> dict:
        """Ejecuta un ciclo completo: leer → calcular → actuar → guardar."""
        distancia = self.sensor.leer_distancia()
        self.tanque.actualizar_distancia(distancia)

        volumen = self.tanque.calcular_volumen()
        porcentaje = self.tanque.calcular_porcentaje()
        nivel = self.tanque.nivel_cm

        estado_actuadores = self.actuador.evaluar(porcentaje)
        self.db.guardar_lectura(distancia, nivel, volumen, porcentaje,
                                estado_actuadores["bomba"],
                                estado_actuadores["alarma"])
        return {
            "distancia_cm": distancia,
            "nivel_cm": nivel,
            "volumen_cm3": volumen,
            "porcentaje": porcentaje,
            "bomba": estado_actuadores["bomba"],
            "alarma": estado_actuadores["alarma"]
        }

    def mostrar_dashboard(self, datos: dict) -> None:
        """Muestra el estado actual en consola (versión simplificada de la GUI)."""
        barra = int(datos["porcentaje"] / 5)
        barra_str = "█" * barra + "░" * (20 - barra)

        print("\n" + "=" * 55)
        print(f"  🛢  {self.tanque.nombre}  — {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 55)
        print(f"  Distancia sensor : {datos['distancia_cm']:>8.2f} cm")
        print(f"  Nivel de líquido : {datos['nivel_cm']:>8.2f} cm")
        print(f"  Volumen actual   : {datos['volumen_cm3']:>8.2f} cm³")
        print(f"  Llenado          : [{barra_str}] {datos['porcentaje']}%")
        print("-" * 55)
        bomba_str = "🟢 ON " if datos["bomba"] else "⚫ OFF"
        alarma_str = "🔴 ON " if datos["alarma"] else "⚫ OFF"
        print(f"  Bomba  : {bomba_str}   |   Alarma : {alarma_str}")
        print("=" * 55)

    def mostrar_historial(self) -> None:
        """Imprime las últimas 5 lecturas de la base de datos."""
        registros = self.db.obtener_ultimas(5)
        print("\n📋 Últimas lecturas:")
        print(f"{'Timestamp':<25} {'Dist':>6} {'Nivel':>6} {'Vol':>10} {'%':>6}")
        print("-" * 60)
        for r in registros:
            ts, dist, nivel, vol, pct, bomba, alarma = r
            print(f"{ts:<25} {dist:>6.1f} {nivel:>6.1f} {vol:>10.2f} {pct:>5.1f}%")

    def ejecutar(self, ciclos: int = 6) -> None:
        """Corre la simulación por N ciclos."""
        print("\n🚀 Iniciando HMI - Sistema de Telemetría de Tanque")
        print(f"   Tanque: r={self.tanque.radio}cm, H={self.tanque.altura}cm")
        print(f"   Vol. total = {self.tanque.calcular_volumen_total():.2f} cm³")
        print(f"   Muestreo cada {self.frecuencia_muestreo}s | {ciclos} ciclos\n")

        for i in range(ciclos):
            datos = self.ciclo_medicion()
            self.mostrar_dashboard(datos)
            if i < ciclos - 1:
                time.sleep(self.frecuencia_muestreo)

        self.mostrar_historial()
        self.db.cerrar()
        print("\n✅ Simulación finalizada. Datos guardados en telemetria_tanque.db")





if __name__ == "__main__":
    hmi = HMI()

    
    hmi.configurar_tanque(radio=30.0, altura=120.0)

    
    hmi.ejecutar(ciclos=6)
