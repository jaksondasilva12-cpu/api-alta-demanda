"""Testes de fumaça manuais/automatizáveis contra uma API já iniciada."""
import os
import requests

BASE = os.getenv("API_URL", "http://localhost:8080")

def test_health():
    response = requests.get(f"{BASE}/health", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
