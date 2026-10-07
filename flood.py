#!/usr/bin/env python3
"""
DDoS Load Tester / Stress Tool para pruebas de resistencia y Fail2ban.
Basado en el script educativo de laboratorio y ampliado con soporte de argumentos CLI.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


class RateLimiter:
    """Limita la tasa agregada de peticiones concurrentes por segundo."""

    def __init__(self, requests_per_second: int) -> None:
        self.interval = 1.0 / max(1, requests_per_second)
        self.next_request_at = 0.0
        self.lock = threading.Lock()

    def wait_for_turn(self, stop_event: threading.Event) -> bool:
        with self.lock:
            now = time.monotonic()
            scheduled_at = max(now, self.next_request_at)
            self.next_request_at = scheduled_at + self.interval
        return not stop_event.wait(max(0.0, scheduled_at - now))


def request_status(opener: urllib.request.OpenerDirector, url: str, timeout: float) -> str:
    """Realiza una petición GET y retorna el código HTTP o '000' en caso de fallo de red/bloqueo."""
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", "DDoS-LoadTester/2.0")
    try:
        with opener.open(request, timeout=timeout) as response:
            return str(response.status)
    except urllib.error.HTTPError as error:
        return str(error.code)
    except (urllib.error.URLError, TimeoutError, OSError):
        # 000 indica que el servidor no respondió, rechazó la conexión o fue baneado por Fail2ban
        return "000"


def worker(
    url: str,
    deadline: float,
    stop_event: threading.Event,
    rate_limiter: RateLimiter,
    counts: Counter[str],
    counts_lock: threading.Lock,
    timeout: float,
) -> None:
    """Envía peticiones continuas hasta alcanzar la duración límite o interrupción."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while not stop_event.is_set() and time.monotonic() < deadline:
        if not rate_limiter.wait_for_turn(stop_event):
            break
        if time.monotonic() >= deadline:
            break
        code = request_status(opener, url, timeout)
        with counts_lock:
            counts[code] += 1


def snapshot(counts: Counter[str], counts_lock: threading.Lock) -> Counter[str]:
    with counts_lock:
        return counts.copy()


def report(target_label: str, counts: Counter[str], final: bool = False) -> None:
    total = sum(counts.values())
    ok_count = counts.get("200", 0) + counts.get("201", 0)
    blocked_count = total - ok_count
    label = "RESULTADO FINAL" if final else f"[{datetime.now():%H:%M:%S}] Peticiones"
    print(
        f"  {label} -> Total: {total} | Exitosas (2xx): {ok_count} | Bloqueadas/Caídas (000/err): {blocked_count}",
        flush=True,
    )
    if final and total:
        pct_failed = (blocked_count * 100) // total
        print(f"  -> Tasa de respuestas fallidas / bloqueadas: {pct_failed}%\n", flush=True)


def run_flood(
    target_url: str,
    concurrency: int,
    duration: int,
    requests_per_second: int,
    timeout: float,
) -> None:
    print("\n" + "=" * 70)
    print(f"⚡ INICIANDO PRUEBA DE CARGA / DDOS:")
    print(f"   Target URL   : {target_url}")
    print(f"   Workers      : {concurrency} hilos")
    print(f"   RPS Límite   : {requests_per_second} req/s")
    print(f"   Duración     : {duration} segundos")
    print(f"   Timeout      : {timeout}s")
    print("=" * 70, flush=True)

    counts: Counter[str] = Counter()
    counts_lock = threading.Lock()
    stop_event = threading.Event()
    rate_limiter = RateLimiter(requests_per_second)
    deadline = time.monotonic() + duration

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                worker,
                target_url,
                deadline,
                stop_event,
                rate_limiter,
                counts,
                counts_lock,
                timeout,
            )
            for _ in range(concurrency)
        ]

        try:
            while time.monotonic() < deadline:
                time.sleep(min(2.0, deadline - time.monotonic()))
                report(target_url, snapshot(counts, counts_lock))
        except KeyboardInterrupt:
            stop_event.set()
            print("\n[!] Prueba detenida por el usuario (Ctrl-C)...", flush=True)
        finally:
            stop_event.set()

        for future in futures:
            future.result()

    report(target_url, snapshot(counts, counts_lock), final=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Script de ataque / prueba de estrés DDoS HTTP parametrizable."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host objetivo (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Puerto objetivo del servicio (ej. 3000, 5000, 8000)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default="/",
        help="Ruta HTTP a atacar (default: /)",
    )
    parser.add_argument(
        "--scheme",
        type=str,
        default="http",
        choices=["http", "https"],
        help="Protocolo HTTP o HTTPS (default: http)",
    )
    parser.add_argument(
        "-c",
        "--workers",
        "--concurrency",
        dest="concurrency",
        type=int,
        default=50,
        help="Número de workers / hilos concurrentes (default: 50)",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=int,
        default=20,
        help="Duración del ataque en segundos (default: 20)",
    )
    parser.add_argument(
        "-r",
        "--rps",
        "--requests-per-second",
        dest="rps",
        type=int,
        default=100,
        help="Tasa máxima de peticiones por segundo (default: 100)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=2.0,
        help="Timeout por petición en segundos (default: 2.0)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    clean_path = args.path if args.path.startswith("/") else f"/{args.path}"
    target_url = f"{args.scheme}://{args.host}:{args.port}{clean_path}"

    run_flood(
        target_url=target_url,
        concurrency=args.concurrency,
        duration=args.duration,
        requests_per_second=args.rps,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
