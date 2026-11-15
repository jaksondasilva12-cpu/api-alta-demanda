from sqlalchemy import String, Integer, ForeignKey, Enum, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from .database import Base

class OrderStatus(str, enum.Enum):
    NO_CARRINHO = "NO_CARRINHO"
    RESERVADO = "RESERVADO"
    CANCELADO = "CANCELADO"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    orders: Mapped[list["Order"]] = relationship(back_populates="user")

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    show_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=OrderStatus.NO_CARRINHO
    )
    user: Mapped["User"] = relationship(back_populates="orders")
    __table_args__ = (
        Index("ix_orders_status", "status"),
        Index("ix_orders_user_status", "user_id", "status"),
    )

class TicketPool(Base):
    __tablename__ = "ticket_pool"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    __table_args__ = (CheckConstraint("id = 1", name="single_pool_row"),)
