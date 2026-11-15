from pydantic import BaseModel, Field

class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)

class CreateOrder(BaseModel):
    showId: int = Field(gt=0)

class OrderResponse(BaseModel):
    id: int
    status: str

class PoolResponse(BaseModel):
    total: int
    ocupadas: int
    livres: int
