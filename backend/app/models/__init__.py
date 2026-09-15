# Import every model so Base.metadata is fully populated for Alembic
# autogenerate and for app.db.Base.metadata.create_all in tests.
from app.models.ingredient import Ingredient
from app.models.ingredient_alias import IngredientAlias
from app.models.ingredient_source_mention import IngredientSourceMention
from app.models.interaction import Interaction
from app.models.product import Product
from app.models.product_ingredient import ProductIngredient
from app.models.source import Source
from app.models.source_coverage import SourceCoverage
from app.models.timing_rule import TimingRule

__all__ = [
    "Ingredient",
    "IngredientAlias",
    "IngredientSourceMention",
    "Interaction",
    "Product",
    "ProductIngredient",
    "Source",
    "SourceCoverage",
    "TimingRule",
]
