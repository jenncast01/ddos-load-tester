# 🛡️ DDoS Load Tester — Violin Journey Security Lab

Script de prueba de carga/DDoS para el laboratorio de seguridad con Fail2ban. Modificado a partir del script educativo del profesor para aceptar argumentos por línea de comandos y probar la resistencia de los 3 servicios del proyecto Violin Journey.

---

## 📋 Requisitos

- Python 3.8 o superior
- Sin dependencias externas (usa únicamente la biblioteca estándar de Python)

---

## 🚀 Instalación y uso

```bash
# Clonar el repositorio
git clone https://github.com/jenncast01/ddos-load-tester.git
cd ddos-load-tester

# Ejecutar directamente (sin instalar nada)
python flood.py --host localhost --port 5000
```

---

## ⚙️ Parámetros del script

| Parámetro | Alias | Tipo | Predeterminado | Descripción |
|-----------|-------|------|---------------|-------------|
| `--host` | | `str` | `localhost` | Host o IP del servicio a atacar |
| `--port` | `-p` | `int` | `80` | Puerto del servicio |
| `--path` | | `str` | `/` | Ruta HTTP del endpoint a golpear |
| `--scheme` | | `str` | `http` | Protocolo: `http` o `https` |
| `--workers` | `--concurrency` | `int` | `100` | Número de hilos concurrentes |
| `--duration` | `-d` | `int` | `30` | Duración del ataque en segundos |
| `--rps` | | `int` | `120` | Peticiones por segundo máximas |
| `--timeout` | | `float` | `5.0` | Timeout por petición en segundos |

---

## 📌 Modificaciones realizadas respecto al script original

El script original del profesor (`flood.py`) realizaba peticiones a un host/puerto fijo codificado en el código. Las modificaciones fueron:

1. **Argparse CLI**: Se reemplazaron todas las constantes fijas (`HOST`, `PORT`, `WORKERS`, `DURATION`, `RPS`) por argumentos de línea de comandos con `argparse`.
2. **`--scheme`**: Soporte para `http` y `https`.
3. **`--path`**: Permite especificar el endpoint exacto a probar.
4. **`--timeout`**: Configurable por argumento (en el original era constante).
5. **Reporte en tiempo real**: Imprime estadísticas cada 2 segundos con los códigos de respuesta y si `000` aparece frecuentemente, significa que Fail2ban está baneando la IP.

---

## 🎯 Ejemplos de uso — Pruebas contra los 3 servicios

### Frontend (Nginx, puerto 3000)
```bash
python flood.py --host localhost --port 3000 --path / --workers 150 --duration 30 --rps 150
```

### Backend (FastAPI/Uvicorn, puerto 5000)
```bash
python flood.py --host localhost --port 5000 --path /api/practices --workers 100 --duration 30 --rps 100
```

### LDAP API (FastAPI, puerto 8000)
```bash
python flood.py --host localhost --port 8000 --path /health --workers 100 --duration 30 --rps 100
```

---

## 🔬 Metodología de calibración — Encontrar el umbral de carga

El objetivo es encontrar los **valores que no tumban el servicio** pero sí generan carga real. Se modificaron 4 parámetros de forma iterativa:

| Parámetro | Qué controla | Valor que tumba | Valor seguro |
|-----------|-------------|-----------------|--------------|
| `--workers` | Hilos concurrentes | ≥ 150 | ≤ 80 |
| `--rps` | Peticiones por segundo | ≥ 120 | ≤ 60 |
| `--duration` | Tiempo total del ataque | > 60 s con carga alta | 30 s |
| `--timeout` | Segundos de espera por respuesta | < 1 s (demasiado agresivo) | 5.0 s |

### Pasos seguidos

1. **Comenzar con parámetros altos** (150 workers, 150 rps, 60s) para confirmar que el servicio cae o que Fail2ban actúa.
2. **Observar los códigos de respuesta**: si empiezan a aparecer `000` o `403`, Fail2ban está baneando.
3. **Reducir gradualmente** `--workers` y `--rps` hasta que el servicio responda con `200` de forma estable.
4. **Documentar el punto de quiebre** (último valor donde el servicio falla) y el **umbral seguro** (primer valor donde el servicio se mantiene estable).

### Resultados obtenidos

| Servicio | Host:Puerto | Workers límite (`-c`) | RPS límite (`-r`) | Duración | Timeout |
|----------|-------------|-----------------------|-------------------|----------|---------|
| Frontend | localhost:3000 | 150 | 500 | 15s | 2.0s |
| Backend  | localhost:5000 | 150 | 500 | 15s | 2.0s |
| LDAP API | localhost:8000 | 100 | 300 | 15s | 2.0s |

> **Nota:** Los valores exactos se completan después de ejecutar las pruebas reales con los contenedores corriendo.

---

## 🛡️ Comportamiento esperado con Fail2ban activo

Cuando Fail2ban detecta el flood (más de 60 peticiones en 10 segundos), banea la IP del atacante por 10 minutos con incremento exponencial:

```
[violin-frontend] Nginx + Fail2ban corriendo exitosamente.
2026-10-06 13:00:01,234 fail2ban.actions [INFO] Ban 172.18.0.1
```

Desde el script de ataque se verán respuestas `000` (conexión rechazada):

```
[+0:00:12] 200×45  000×67  | total: 112  ok: 45  blocked: 67
```

---

## 📁 Estructura del repositorio

```
ddos-load-tester/
├── flood.py       # Script principal de prueba de carga
└── README.md      # Este archivo
```

---

## ⚠️ Aviso legal

Este script es únicamente para fines **educativos y de laboratorio**. Úsalo solo en servicios que tú controlas y en entornos de prueba. El uso no autorizado contra sistemas de terceros es ilegal.
