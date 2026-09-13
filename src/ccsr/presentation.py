"""Terminal formatting shared by route generation and replay."""

from dataclasses import replace

ITEM_WIDTH = 20
ERRAND_WIDTH = 14
TIME_WIDTH = 13
COOKIES_WIDTH = 18


def format_time(seconds):
    tenths = round(seconds * 10)
    minutes, remaining_tenths = divmod(tenths, 600)
    return f"{minutes}:{remaining_tenths / 10:04.1f}"


def _header():
    labels = (
        ("Errand cookies", ERRAND_WIDTH, ">"),
        ("Item", ITEM_WIDTH, "<"),
        ("Time (m:ss.s)", TIME_WIDTH, ">"),
        ("Cookies produced", COOKIES_WIDTH, ">"),
    )
    header = "  ".join(f"{label:{align}{width}}" for label, width, align in labels)
    divider = "  ".join("-" * width for _, width, _ in labels)
    return header, divider


def _item_label(item):
    return item if len(item) <= ITEM_WIDTH else f"{item[:ITEM_WIDTH - 3]}..."


def _purchase_row(required_cookies, purchase):
    show_stats = required_cookies is not None
    required = f"{required_cookies:,.0f}" if show_stats else ""
    age = format_time(purchase.age) if show_stats else ""
    produced = f"{purchase.lifetime_cookies:,.0f}" if show_stats else ""
    return (
        f"{required:>{ERRAND_WIDTH}}  "
        f"{_item_label(purchase.display_item):<{ITEM_WIDTH}}  "
        f"{age:>{TIME_WIDTH}}  "
        f"{produced:>{COOKIES_WIDTH}}"
    )


def _errand_rows(errand, previous_cookies):
    if errand and errand[0].required_cookies is not None and any(
        purchase.operation == "sell" for purchase in errand
    ):
        sales = [purchase for purchase in errand if purchase.operation == "sell"]
        purchases = [purchase for purchase in errand if purchase.operation != "sell"]
        errand = (
            replace(errand[0], label="Switch to sell"),
            *sales,
            replace(errand[0], label="Switch to buy"),
            *purchases,
        )
    for purchase_index, purchase in enumerate(errand):
        required = (
            (purchase.required_cookies if purchase.required_cookies is not None
             else purchase.lifetime_cookies - previous_cookies)
            if purchase_index == 0
            else None
        )
        yield _purchase_row(required, purchase)


def _done_row(final_gamestate, target):
    return (
        f"{'':<{ERRAND_WIDTH}}  {'Done!':<{ITEM_WIDTH}}  "
        f"{format_time(final_gamestate.age):>{TIME_WIDTH}}  "
        f"{target:>{COOKIES_WIDTH},.0f}"
    )


def format_route(result, target, include_purchases=True):
    lines = list(_header())
    if include_purchases:
        previous_cookies = result.initial_gamestate.lifetime_cookies
        for errand in result.errands:
            if not errand:
                continue
            if len(lines) > 2:
                lines.append("")
            lines.extend(_errand_rows(errand, previous_cookies))
            previous_cookies = errand[-1].lifetime_cookies
    lines.append(_done_row(result.final_gamestate, target))
    return "\n".join(lines)


class LiveRouteTable:
    def __init__(self, initial_cookies=0.0):
        self.previous_cookies = initial_cookies
        self.started = False
        self.has_errands = False

    def _start(self):
        if not self.started:
            print(*_header(), sep="\n")
            self.started = True

    def print_errand(self, errand):
        self._start()
        if not errand:
            return
        if self.has_errands:
            print()
        for row in _errand_rows(errand, self.previous_cookies):
            print(row, flush=True)
        self.previous_cookies = errand[-1].lifetime_cookies
        self.has_errands = True

    def print_done(self, final_gamestate, target):
        self._start()
        print(_done_row(final_gamestate, target))
