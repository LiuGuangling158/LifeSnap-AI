from typing import ClassVar

from pydantic import BaseModel, ValidationInfo, field_validator


class PatchModel(BaseModel):
    # Omitted fields are unchanged; explicit null only clears nullable fields.
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @field_validator("*", mode="before")
    @classmethod
    def reject_required_null(cls, value: object, info: ValidationInfo) -> object:
        if value is None and info.field_name in cls.non_nullable_fields:
            raise ValueError(f"{info.field_name} cannot be null")
        return value
