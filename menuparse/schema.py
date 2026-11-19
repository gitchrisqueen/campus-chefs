"""The shape the model must return (plan phase 12). Model output is untrusted input.

The allowed values come straight from `meals.models`, so a value the MenuItem form would reject
cannot get through here either. Anything outside the lists makes `MenuDraft` raise a
`ValidationError`, which the service reports as invalid output (AI-03).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from meals.models import ALLERGENS, DIETARY_TAGS, Course, MealType

MAX_DISHES = 20

# Literal needs the values spelled out, so the tests compare these to the model choices.
MealTypeValue = Literal["breakfast", "lunch", "dinner"]
CourseValue = Literal["main", "side"]
AllergenValue = Literal["milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanuts", "wheat", "soy", "sesame"]
DietaryTagValue = Literal["vegetarian", "vegan", "dairy_free", "gluten_free"]

assert set(MealTypeValue.__args__) == set(MealType.values)
assert set(CourseValue.__args__) == set(Course.values)
assert set(AllergenValue.__args__) == {v for v, _ in ALLERGENS}
assert set(DietaryTagValue.__args__) == {v for v, _ in DIETARY_TAGS}


class DraftDish(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80, description="Dish name, at most 80 characters")
    description: str = Field(max_length=500, description="One short sentence, at most 500 characters; empty if none")
    meal_type: MealTypeValue
    course: CourseValue
    allergens: list[AllergenValue] = Field(description="Only major allergens the text clearly says or implies")
    dietary_tags: list[DietaryTagValue] = Field(description="Only tags the text clearly supports")


class MenuDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dishes: list[DraftDish] = Field(max_length=MAX_DISHES, description=f"At most {MAX_DISHES} dishes")
