from game import Game


def get_score(child, parent):
    cost = child.cookies - parent.cookies
    cps_buff = child.cps() - parent.cps()
    return cps_buff / cost / child.cps()


def top_child(parent):
    scored_children = []
    for child in parent.children():
        score = get_score(child, parent)
        scored_children.append((score, child))
    return max(scored_children)[1]


g = Game()
g.clickrate = 8.0

print(g)


for _ in range(100):
    g = top_child(g)
    print(g.history[-1], g.age, g.cookies, g.cps())

