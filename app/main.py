from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .database import Base, engine, get_db, SessionLocal
from .models import User, Order, OrderStatus, TicketPool
from .schemas import Credentials, CreateOrder, OrderResponse, PoolResponse
from .security import hash_password, verify_password, create_access_token, current_user

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Ensure one authoritative row represents the 100-ticket pool.
    with SessionLocal() as db:
        if db.get(TicketPool, 1) is None:
            db.add(TicketPool(id=1, total=100))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
    yield

app = FastAPI(title="API sob Alta Demanda", version="1.0.0", lifespan=lifespan)

@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    # Toda recusa volta como {"error": "CODIGO"}, nunca {"detail": ...}
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"error": "REQUISICAO_INVALIDA"})

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/registrar", status_code=201)
def register(body: Credentials, db: Session = Depends(get_db)):
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="USUARIO_JA_EXISTE")
    return {"message": "USUARIO_CRIADO"}

@app.post("/auth/login")
def login(body: Credentials, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="CREDENCIAIS_INVALIDAS")
    return {"token": create_access_token(user.id)}

@app.post("/pedidos", status_code=201, response_model=OrderResponse)
def create_order(
    body: CreateOrder,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = Order(user_id=user.id, show_id=body.showId, status=OrderStatus.NO_CARRINHO)
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "status": order.status.value}

@app.post("/pedidos/{order_id}/reservar", response_model=OrderResponse)
def reserve(
    order_id: int,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # All reservation/cancellation decisions lock the same pool row. This serializes
    # the critical section across API workers and prevents overselling.
    pool = db.scalar(select(TicketPool).where(TicketPool.id == 1).with_for_update())
    if pool is None:
        raise HTTPException(status_code=500, detail="POOL_NAO_INICIALIZADO")

    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if order is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="PEDIDO_NAO_ENCONTRADO")

    if order.status != OrderStatus.NO_CARRINHO:
        db.rollback()
        raise HTTPException(status_code=409, detail="STATUS_INVALIDO")

    occupied = db.scalar(select(func.count()).select_from(Order).where(Order.status == OrderStatus.RESERVADO)) or 0
    if occupied >= pool.total:
        db.rollback()
        return JSONResponse(status_code=409, content={"error": "POOL_CHEIO"})

    personal = db.scalar(
        select(func.count()).select_from(Order).where(
            Order.user_id == user.id, Order.status == OrderStatus.RESERVADO
        )
    ) or 0
    if personal >= 2:
        db.rollback()
        return JSONResponse(status_code=409, content={"error": "COTA_PESSOAL"})

    order.status = OrderStatus.RESERVADO
    db.commit()
    response.headers["X-Lote"] = "7F3A"
    return {"id": order.id, "status": order.status.value}

@app.post("/pedidos/{order_id}/cancelar", response_model=OrderResponse)
def cancel(
    order_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.scalar(select(TicketPool).where(TicketPool.id == 1).with_for_update())
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if order is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="PEDIDO_NAO_ENCONTRADO")
    if order.status != OrderStatus.RESERVADO:
        db.rollback()
        raise HTTPException(status_code=409, detail="STATUS_INVALIDO")
    order.status = OrderStatus.CANCELADO
    db.commit()
    return {"id": order.id, "status": order.status.value}

@app.get("/pool", response_model=PoolResponse)
def get_pool(db: Session = Depends(get_db)):
    # A single SQL statement reads a consistent snapshot for this response.
    pool = db.get(TicketPool, 1)
    if pool is None:
        raise HTTPException(status_code=503, detail="POOL_NAO_INICIALIZADO")
    occupied = db.scalar(
        select(func.count()).select_from(Order).where(Order.status == OrderStatus.RESERVADO)
    ) or 0
    return {"total": pool.total, "ocupadas": occupied, "livres": pool.total - occupied}
