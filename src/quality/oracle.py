"""RoutingOracle — the interface L10 monitors, not a router Anvil builds.

Anvil does not score routes; it watches whether a route-scoring model's
own confidence still matches reality. There is no public Vulcan API — see
anvil-build-plan.md §6. `VulcanOracle` is a documented stub implementing
this protocol, and nothing more; swapping the simulated oracle for a
production routing model is one adapter class, and nothing above L1
changes.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class RouteScore(BaseModel):
    psp: str
    confidence: float


class PaymentRouteContext(BaseModel):
    method: str
    x_psp: str
    x_issuer: str


@runtime_checkable
class RoutingOracle(Protocol):
    def score_routes(self, ctx: PaymentRouteContext) -> list[RouteScore]: ...


class SimulatedOracle:
    """Ships with the repo. The frozen generator (src/generator/engine.py)
    already embeds a simulated oracle's confidence score on every emitted
    attempt (`x_route_confidence`) — this class exists to make that
    relationship explicit and Protocol-typed, not to recompute anything;
    src.quality.calibration reads `x_route_confidence` directly from the
    events view, which is what a real deployment would do against a real
    oracle's own scores too.
    """

    def score_routes(self, ctx: PaymentRouteContext) -> list[RouteScore]:
        raise NotImplementedError(
            "SimulatedOracle documents the relationship to the generator's "
            "x_route_confidence field; it is not called at runtime. See "
            "src.quality.calibration, which reads that field from events "
            "directly instead of re-deriving it here."
        )


class VulcanOracle:
    """Documented stub only. There is no public Vulcan API to call — see
    anvil-build-plan.md §6. This class exists to prove the RoutingOracle
    interface is the actual integration seam: replacing SimulatedOracle
    with a real VulcanOracle implementation, once such an API exists,
    would require no change to src/quality/calibration.py or anything
    above L1.
    """

    def score_routes(self, ctx: PaymentRouteContext) -> list[RouteScore]:
        raise NotImplementedError(
            "VulcanOracle is a stub. There is no public Vulcan API to call."
        )
