# API sob Alta Demanda — Python + FastAPI

Implementação do enunciado do projeto de venda concorrida de 100 ingressos.

## Stack
- Python 3.12 + FastAPI
- PostgreSQL 16
- SQLAlchemy 2
- JWT para autenticação
- Argon2 para hash de senhas
- Docker Compose

## Executar

Pré-requisito: Docker Desktop ou Docker Engine com o plugin Compose.

Na raiz do projeto:

```bash
docker compose down -v
docker compose up --build -d
docker compose logs -f api
```

A API ficará em http://localhost:8080 e a documentação interativa em
http://localhost:8080/docs.

`docker compose down -v` apaga os dados do banco; use apenas quando quiser reiniciar
o projeto do zero, conforme a instrução de avaliação.

## Fluxo de teste

1. Registre um usuário em `POST /auth/registrar`:
   ```json
   {"username":"joao","password":"senha123"}
   ```
2. Faça login em `POST /auth/login` e copie `token`.
3. Em `/docs`, clique em **Authorize** e informe `Bearer SEU_TOKEN` (ou use o
   token conforme a interface solicitar).
4. Crie pedidos em `POST /pedidos`:
   ```json
   {"showId":7}
   ```
5. Reserve em `POST /pedidos/{id}/reservar`.
6. Cancele em `POST /pedidos/{id}/cancelar`.
7. Consulte `GET /pool`.

## Contratos importantes

- O pool é inicializado com total = 100.
- `NO_CARRINHO -> RESERVADO -> CANCELADO`.
- Só pedidos do próprio usuário podem ser reservados/cancelados; pedido alheio ou
  inexistente retorna 404.
- Pool cheio: HTTP 409 e `{"error":"POOL_CHEIO"}`.
- Cota pessoal esgotada: HTTP 409 e `{"error":"COTA_PESSOAL"}`.
- Toda reserva bem-sucedida responde com `X-Lote: 7F3A`.
- O pool considera ocupados apenas pedidos `RESERVADO`.

## Estratégia de concorrência

A transação de reserva bloqueia a linha única `ticket_pool` com `SELECT ... FOR UPDATE`.
Todas as reservas e cancelamentos passam pelo mesmo bloqueio. Assim, cada operação crítica
é processada uma por vez no banco, inclusive se houver vários processos da API, e a contagem
e a alteração de estado ocorrem dentro da mesma transação. Isso impede que duas requisições
vejam simultaneamente a última vaga como livre e vendam ambas.

**Justiça:** quem pede o lock primeiro é atendido primeiro. O PostgreSQL não garante FIFO
estrito pelo instante de chegada na rede, mas ninguém fica sem resposta e não há sobre-venda.

## Respostas de erro

Todos os erros (inclusive 401/404/400) retornam `{"error":"CODIGO"}`; pool e cota, exatamente como o enunciado exige:
`{"error":"POOL_CHEIO"}` e `{"error":"COTA_PESSOAL"}`.

## Testes

Com a API no ar (`docker compose up --build -d`) e o banco zerado:

```bash
pip install -r requirements.txt
pytest -q tests
```

Cobrem: cota pessoal, cancelamento, 404 para não-dono, header `X-Lote` e 150
requisições simultâneas disputando 100 vagas (exatamente 100 sucessos, 50 `POOL_CHEIO`,
nenhum 500).

## Integrantes

- Nome 1
- Nome 2
- Nome 3
