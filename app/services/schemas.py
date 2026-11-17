import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..utils.errors import InvalidRequest, InvalidWeight
from ..utils.timeutil import _datetime

MEAL_TYPES = {'breakfast', 'lunch', 'dinner', 'snack'}


class MealItemInput(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    food_name: str | None
    display_name: str = Field(min_length=1, max_length=100)
    weight_g: float = Field(gt=0, le=5000, allow_inf_nan=False)

    @field_validator('weight_g', mode='before')
    @classmethod
    def numeric_weight(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('weight_g must be a JSON number')
        return value


class CreateMealRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    meal_type: Literal['breakfast', 'lunch', 'dinner', 'snack']
    meal_datetime: datetime
    image_path: str | None = None
    items: list[MealItemInput] = Field(min_length=1, max_length=20)

    @field_validator('meal_datetime', mode='before')
    @classmethod
    def iso_datetime(cls, value):
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not re.match(r'^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}', value):
            raise ValueError('Use an ISO 8601 datetime string')
        return value

    @field_validator('meal_datetime')
    @classmethod
    def not_too_far_in_future(cls, value):
        try:
            utc = _datetime(value).astimezone(timezone.utc)
        except (OverflowError, ValueError):
            raise ValueError('Datetime is outside the supported range') from None
        if utc > datetime.now(timezone.utc) + timedelta(days=1):
            raise ValueError('meal_datetime must not be more than one day in the future')
        return value


def validate_payload(body):
    try:
        return CreateMealRequest.model_validate(body).model_dump()
    except ValidationError as exc:
        errors = [dict(field='.'.join(map(str, e['loc'])), message=e['msg'])
                  for e in exc.errors(include_url=False, include_context=False, include_input=False)]
        kind = InvalidWeight if any(e['field'].endswith('.weight_g') for e in errors) else InvalidRequest
        raise kind('Invalid request body.', details={'errors': errors}) from None
