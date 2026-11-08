"""Backend boundary validators mirroring the explicit shapes in main route E.

These do not replace the AI/nutrition modules' own schemas or calculations.
"""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..utils.errors import DatabaseError, InvalidAiResponse, ApiError

Number = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]
Weight = Annotated[float, Field(strict=True, allow_inf_nan=False, gt=0, le=5000)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
FoodId = Annotated[str, Field(pattern=r'^[a-z0-9_]+$', max_length=60, min_length=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class DetectedFood(Contract):
    food_name: FoodId | None
    display_name: Name
    estimated_weight_g: Weight | None
    confidence: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
    notes: Annotated[str, Field(max_length=200)] | None = None


class AnalysisResult(Contract):
    schema_version: Literal['1.0']
    status: Literal['success', 'partial', 'error']
    foods: Annotated[list[DetectedFood], Field(max_length=20)]
    warnings: list[str]

    @model_validator(mode='after')
    def consistent_status(self):
        missing = any(f.food_name is None or f.estimated_weight_g is None for f in self.foods)
        if self.status == 'success' and (not self.foods or missing):
            raise ValueError('success requires identifiable foods with weights')
        if self.status == 'partial' and (not self.foods or not missing or not self.warnings):
            raise ValueError('partial requires incomplete foods and warnings')
        if self.status == 'error' and (self.foods or not self.warnings):
            raise ValueError('error requires no foods and at least one warning')
        return self


class Totals(Contract):
    calories_kcal: Number
    protein_g: Number
    carbs_g: Number
    fat_g: Number


class NutritionItem(Contract):
    food_name: FoodId
    display_name: Name
    weight_g: Weight
    calories_kcal: Number
    protein_g: Number
    carbs_g: Number
    fat_g: Number
    food_data_source: Literal['USDA', 'local', 'custom']


class NutritionResult(Contract):
    schema_version: Literal['1.0']
    items: Annotated[list[NutritionItem], Field(max_length=20)]
    totals: Totals
    warnings: list[str]


class MealRecord(Contract):
    meal_id: Annotated[int, Field(gt=0)]
    meal_type: Literal['breakfast', 'lunch', 'dinner', 'snack']
    meal_datetime: str
    meal_date: str
    image_path: str | None
    created_at: str
    items: Annotated[list[NutritionItem], Field(min_length=1, max_length=20)]
    totals: Totals
    warnings: list[str]

    @model_validator(mode='after')
    def dates_and_path(self):
        local = datetime.fromisoformat(self.meal_datetime)
        if local.utcoffset() is None or local.date().isoformat() != self.meal_date:
            raise ValueError('Invalid local meal date or timezone')
        created = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
        if not self.created_at.endswith('Z') or created.utcoffset().total_seconds() != 0:
            raise ValueError('created_at must be UTC with Z')
        if self.image_path is not None:
            parts = self.image_path.split('/')
            if parts[0] != 'uploads' or len(parts) < 2 or any(p in ('', '.', '..') for p in parts) or '\\' in self.image_path or ':' in self.image_path:
                raise ValueError('Invalid stored image path')
        return self


class DailyResult(Contract):
    date: str
    totals: Totals
    meal_count: Annotated[int, Field(ge=0)]
    by_meal_type: dict[Literal['breakfast', 'lunch', 'dinner', 'snack'], Number] | None = None

    @model_validator(mode='after')
    def valid_date_and_breakdown(self):
        from datetime import date
        if date.fromisoformat(self.date).isoformat() != self.date:
            raise ValueError('Invalid dashboard date')
        if self.by_meal_type is not None and set(self.by_meal_type) != {'breakfast', 'lunch', 'dinner', 'snack'}:
            raise ValueError('by_meal_type must contain all four types')
        return self


class MealSummary(Contract):
    meal_id: Annotated[int, Field(gt=0)]
    meal_type: Literal['breakfast', 'lunch', 'dinner', 'snack']
    meal_datetime: str
    meal_date: str
    display_summary: str
    calories_kcal: Number
    item_count: Annotated[int, Field(ge=1, le=20)]


def check_contract(model, value, boundary):
    try:
        return model.model_validate(value).model_dump(exclude_unset=True)
    except ValidationError:
        if boundary == 'ai':
            raise InvalidAiResponse('AI output does not conform to contract A.') from None
        if boundary == 'database':
            raise DatabaseError('Repository output does not conform to the shared contract.') from None
        raise ApiError('INTERNAL_ERROR', 'Nutrition output does not conform to contract C.', 500) from None
