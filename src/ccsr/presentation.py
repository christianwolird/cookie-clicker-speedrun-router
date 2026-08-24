"""Terminal formatting shared by route generation and replay."""


ITEM_WIDTH = 20
ERRAND_WIDTH = 8
TIME_WIDTH = 13
COOKIES_WIDTH = 18
CPS_WIDTH = 15


def format_time(seconds):
    tenths = round(seconds * 10)
    minutes, remaining_tenths = divmod(tenths, 600)
    return f"{minutes}:{remaining_tenths / 10:04.1f}"


def _header():
    labels = (
        ("Errand", ERRAND_WIDTH, "<"),
        ("Item", ITEM_WIDTH, "<"),
        ("Time (m:ss.s)", TIME_WIDTH, ">"),
        ("Cookies produced", COOKIES_WIDTH, ">"),
        ("Current CpS", CPS_WIDTH, ">"),
    )
    header = "  ".join(f"{label:{align}{width}}" for label, width, align in labels)
    divider = "  ".join("-" * width for _, width, _ in labels)
    return header, divider


def _item_label(item):
    return item if len(item) <= ITEM_WIDTH else f"{item[:ITEM_WIDTH - 3]}..."


def _marker(errand_number, purchase_index, purchase_count):
    if purchase_index == 0:
        return f"#{errand_number}"
    return "└─" if purchase_index == purchase_count - 1 else "│"


def _purchase_row(marker, purchase):
    return (
        f"{marker:<{ERRAND_WIDTH}}  "
        f"{_item_label(purchase.display_item):<{ITEM_WIDTH}}  "
        f"{format_time(purchase.age):>{TIME_WIDTH}}  "
        f"{purchase.lifetime_cookies:>{COOKIES_WIDTH},.1f}  "
        f"{purchase.current_cps:>{CPS_WIDTH},.3f}"
    )


def _done_row(final_gamestate, target):
    return (
        f"{'':<{ERRAND_WIDTH}}  {'Done!':<{ITEM_WIDTH}}  "
        f"{format_time(final_gamestate.age):>{TIME_WIDTH}}  "
        f"{target:>{COOKIES_WIDTH},.1f}  "
        f"{final_gamestate.cps():>{CPS_WIDTH},.3f}"
    )


def format_route(result, target, include_purchases=True):
    lines = list(_header())
    if include_purchases:
        for errand_number, errand in enumerate(result.errands, 1):
            for purchase_index, purchase in enumerate(errand):
                lines.append(
                    _purchase_row(
                        _marker(errand_number, purchase_index, len(errand)),
                        purchase,
                    )
                )
    lines.append(_done_row(result.final_gamestate, target))
    return "\n".join(lines)


class LiveRouteTable:
    def __init__(self):
        self.errand_count = 0
        self.started = False

    def _start(self):
        if not self.started:
            print(*_header(), sep="\n")
            self.started = True

    def print_errand(self, errand):
        self._start()
        self.errand_count += 1
        for purchase_index, purchase in enumerate(errand):
            print(
                _purchase_row(
                    _marker(
                        self.errand_count,
                        purchase_index,
                        len(errand),
                    ),
                    purchase,
                ),
                flush=True,
            )

    def print_done(self, final_gamestate, target):
        self._start()
        print(_done_row(final_gamestate, target))
