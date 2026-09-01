"""api — pywebview-facing слой: собирает Api() из миксинов по вкладкам."""

from api.core import ApiCoreMixin
from api.promodate import ApiPromodateMixin
from api.competitors import ApiCompetitorsMixin
from api.production import ApiProductionMixin
from api.price import ApiPriceMixin
from api.scheduler import ApiSchedulerMixin
from api.oos import ApiOosMixin
from api.parsing import ApiParsingMixin


class Api(
    ApiCoreMixin,
    ApiPromodateMixin,
    ApiCompetitorsMixin,
    ApiProductionMixin,
    ApiPriceMixin,
    ApiSchedulerMixin,
    ApiOosMixin,
    ApiParsingMixin,
):
    pass
