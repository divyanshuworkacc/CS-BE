"""Request and response shapes."""

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    model_validator,
)

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Username = Annotated[
    str,
    StringConstraints(
        to_lower=True, strip_whitespace=True, pattern=r"^[a-zA-Z0-9_.-]{1,80}$"
    ),
]
Password = Annotated[SecretStr, Field(min_length=8, max_length=256)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PatchModel(RequestModel):
    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError(
                "Supply at least one field; supplied values cannot be null"
            )
        return self


class TenantCreate(RequestModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    ]


class TenantResponse(ResponseModel):
    id: int
    name: str


class BrandManagerCreate(RequestModel):
    """Only a platform admin can create this account, inside a brand's URL."""

    name: Name
    username: Username
    password: Password


class BrandManagerUpdate(PatchModel):
    name: Name | None = None
    password: Password | None = None


class UserResponse(ResponseModel):
    id: int
    name: str
    username: str
    role_id: int
    tenant_id: int | None


class CurrentUserResponse(UserResponse):
    role: str
    tenant_name: str | None


class RoleResponse(ResponseModel):
    id: int
    name: str


class ProductCreate(RequestModel):
    name: Name
    category: Name
    quantity: int = Field(ge=0, strict=True)
    price: float = Field(ge=0, allow_inf_nan=False)


class ProductUpdate(PatchModel):
    name: Name | None = None
    category: Name | None = None
    quantity: int | None = Field(default=None, ge=0, strict=True)
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ProductResponse(ResponseModel):
    id: int
    name: str
    category: str
    price: float
    quantity: int
    tenant_id: int


class OrderItemCreate(RequestModel):
    product_id: int = Field(gt=0, strict=True)
    quantity: int = Field(gt=0, strict=True)


class OrderCreate(RequestModel):
    order_items: list[OrderItemCreate] = Field(min_length=1, max_length=100)


class OrderItemResponse(ResponseModel):
    id: int
    quantity: int
    product_id: int
    order_id: int


class OrderResponse(ResponseModel):
    id: int
    total_quantity: int
    amount: float
    user_id: int
    tenant_id: int
    order_items: list[OrderItemResponse]
