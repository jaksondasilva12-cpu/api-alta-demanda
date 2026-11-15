"""Teste de concorrência contra a API já rodando (docker compose up).
Rode com o banco zerado:  docker compose down -v && docker compose up --build -d
Depois:                    pytest -q tests
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = os.getenv("API_URL", "http://localhost:8080")


def novo_usuario():
    nome = f"u_{uuid.uuid4().hex[:12]}"
    assert requests.post(f"{BASE}/auth/registrar", json={"username": nome, "password": "senha123"}).status_code == 201
    token = requests.post(f"{BASE}/auth/login", json={"username": nome, "password": "senha123"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def novo_pedido(h):
    r = requests.post(f"{BASE}/pedidos", json={"showId": 7}, headers=h)
    assert r.status_code == 201 and r.json()["status"] == "NO_CARRINHO"
    return r.json()["id"]


def reservar(h, pid):
    return requests.post(f"{BASE}/pedidos/{pid}/reservar", headers=h)


def test_health():
    assert requests.get(f"{BASE}/health", timeout=5).json() == {"status": "ok"}


def test_cota_pessoal_e_cancelamento():
    h = novo_usuario()
    ids = [novo_pedido(h) for _ in range(3)]
    r1, r2, r3 = (reservar(h, i) for i in ids)
    assert r1.status_code == r2.status_code == 200
    assert r1.headers["X-Lote"] == "7F3A"
    assert r3.status_code == 409 and r3.json() == {"error": "COTA_PESSOAL"}
    c = requests.post(f"{BASE}/pedidos/{ids[0]}/cancelar", headers=h)
    assert c.status_code == 200 and c.json()["status"] == "CANCELADO"
    assert reservar(h, ids[2]).status_code == 200
    # limpa para não sujar o pool nos outros testes
    for i in (ids[1], ids[2]):
        requests.post(f"{BASE}/pedidos/{i}/cancelar", headers=h)


def test_pedido_de_outro_usuario_404():
    a, b = novo_usuario(), novo_usuario()
    pid = novo_pedido(a)
    assert reservar(b, pid).status_code == 404
    assert requests.post(f"{BASE}/pedidos/{pid}/cancelar", headers=b).status_code == 404


def test_150_disputando_100_vagas():
    antes = requests.get(f"{BASE}/pool").json()
    livres = antes["livres"]
    usuarios = [novo_usuario() for _ in range(150)]
    pedidos = [(h, novo_pedido(h)) for h in usuarios]
    with ThreadPoolExecutor(max_workers=150) as ex:
        resp = list(ex.map(lambda x: reservar(*x), pedidos))
    ok = [r for r in resp if r.status_code == 200]
    cheio = [r for r in resp if r.status_code == 409 and r.json() == {"error": "POOL_CHEIO"}]
    assert len(ok) == livres
    assert len(ok) + len(cheio) == 150          # nenhum 500, nenhum timeout
    assert all(r.headers["X-Lote"] == "7F3A" for r in ok)
    p = requests.get(f"{BASE}/pool").json()
    assert p["ocupadas"] == 100 and p["livres"] == 0 and p["ocupadas"] + p["livres"] == p["total"]
