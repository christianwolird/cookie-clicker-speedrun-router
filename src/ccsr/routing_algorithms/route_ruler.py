"""Remaining-time estimates interpolated from one executed reference route."""

from bisect import bisect_right


DEFAULT_RULER_SCALE = 0.9


class RouteRuler:
    def __init__(self, route_result, scale=DEFAULT_RULER_SCALE):
        if scale < 0:
            raise ValueError("scale cannot be negative")
        initial = route_result.initial_gamestate
        points = [(initial.lifetime_cookies, initial.age)]
        for errand in route_result.errands:
            purchase = errand[-1]
            if purchase.lifetime_cookies > points[-1][0]:
                points.append((purchase.lifetime_cookies, purchase.age))
        final = route_result.final_gamestate
        if final.lifetime_cookies > points[-1][0]:
            points.append((final.lifetime_cookies, final.age))
        if len(points) < 2:
            raise ValueError("Ruler route must advance lifetime cookies")

        self.lifetimes = tuple(point[0] for point in points)
        self.ages = tuple(point[1] for point in points)
        self.final_age = final.age
        self.scale = scale
        self.route = route_result

    def remaining_time(self, lifetime_cookies):
        if lifetime_cookies >= self.lifetimes[-1]:
            return 0.0

        right = bisect_right(self.lifetimes, lifetime_cookies)
        left = max(0, right - 1)
        right = min(right, len(self.lifetimes) - 1)
        left_lifetime = self.lifetimes[left]
        right_lifetime = self.lifetimes[right]
        if right_lifetime == left_lifetime:
            interpolated_age = self.ages[left]
        else:
            fraction = (
                (lifetime_cookies - left_lifetime)
                / (right_lifetime - left_lifetime)
            )
            interpolated_age = self.ages[left] + fraction * (
                self.ages[right] - self.ages[left]
            )
        return self.scale * max(0.0, self.final_age - interpolated_age)

    def __call__(self, gamestate):
        return self.remaining_time(gamestate.lifetime_cookies)
