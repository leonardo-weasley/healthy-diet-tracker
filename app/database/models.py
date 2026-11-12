"""ORM models for the three tables: ``food``, ``meal`` and ``meal_item``.

Schema and constraints follow the shared contract in ``05`` §5.1.  The
important rules are:

* deleting a meal cascades to its items (``ON DELETE CASCADE``);
* deleting a reference food keeps history and nulls ``meal_item.food_id``
  (``ON DELETE SET NULL``);
* nutrition values on ``meal_item`` are a snapshot written once and never
  recomputed on read.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index

from ..extensions import db


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Food(db.Model):
    __tablename__ = "food"

    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.Text, nullable=False, unique=True)
    display_name = db.Column(db.Text, nullable=False)
    calories_per_100g = db.Column(db.Float, nullable=False)
    protein_per_100g = db.Column(db.Float, nullable=False)
    carbs_per_100g = db.Column(db.Float, nullable=False)
    fat_per_100g = db.Column(db.Float, nullable=False)
    source = db.Column(db.Text, nullable=False, default="local")
    aliases = db.Column(db.Text)
    is_verified = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (
        CheckConstraint(
            "calories_per_100g >= 0 AND calories_per_100g <= 900",
            name="ck_food_calories",
        ),
        CheckConstraint(
            "protein_per_100g >= 0 AND protein_per_100g <= 100",
            name="ck_food_protein",
        ),
        CheckConstraint(
            "carbs_per_100g >= 0 AND carbs_per_100g <= 100",
            name="ck_food_carbs",
        ),
        CheckConstraint(
            "fat_per_100g >= 0 AND fat_per_100g <= 100",
            name="ck_food_fat",
        ),
    )


class Meal(db.Model):
    __tablename__ = "meal"

    id = db.Column(db.Integer, primary_key=True)
    meal_type = db.Column(db.Text, nullable=False)
    meal_datetime_utc = db.Column(db.Text, nullable=False)
    meal_date = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.Text)
    created_at = db.Column(db.Text, nullable=False, default=_utcnow_iso)

    items = db.relationship(
        "MealItem",
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealItem.sort_order",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "meal_type IN ('breakfast','lunch','dinner','snack')",
            name="ck_meal_type",
        ),
        Index("idx_meal_date", "meal_date"),
    )


class MealItem(db.Model):
    __tablename__ = "meal_item"

    id = db.Column(db.Integer, primary_key=True)
    meal_id = db.Column(
        db.Integer, db.ForeignKey("meal.id", ondelete="CASCADE"), nullable=False
    )
    food_id = db.Column(
        db.Integer, db.ForeignKey("food.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot of food_name as well: the reference row may be renamed later.
    food_name = db.Column(db.Text)
    display_name = db.Column(db.Text, nullable=False)
    weight_g = db.Column(db.Float, nullable=False)
    calories_kcal = db.Column(db.Float, nullable=False)
    protein_g = db.Column(db.Float, nullable=False)
    carbs_g = db.Column(db.Float, nullable=False)
    fat_g = db.Column(db.Float, nullable=False)
    food_data_source = db.Column(db.Text, nullable=False, default="local")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    meal = db.relationship("Meal", back_populates="items")

    __table_args__ = (
        CheckConstraint("weight_g > 0 AND weight_g <= 5000", name="ck_item_weight"),
        CheckConstraint("calories_kcal >= 0", name="ck_item_calories"),
        CheckConstraint("protein_g >= 0", name="ck_item_protein"),
        CheckConstraint("carbs_g >= 0", name="ck_item_carbs"),
        CheckConstraint("fat_g >= 0", name="ck_item_fat"),
        Index("idx_meal_item_meal", "meal_id"),
    )
