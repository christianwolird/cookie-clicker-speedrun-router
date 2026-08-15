from wiki_data import building_stats


class Game:

    def __init__(self):
        self.clickrate = 0.0
        self.purchase_delay = 1.0

        self.age = 0.0
        self.cookies = 0.0

        self.num_buildings = {name:0 for name in building_stats}

        self.history = []


    def copy(self):
        copy_game = Game()

        copy_game.clickrate = self.clickrate
        copy_game.age = self.age
        copy_game.cookies = self.cookies

        copy_game.num_buildings = dict(self.num_buildings)

        return copy_game


    def __str__(self):
        return f"Age: {self.age} -- Cookies baked: {self.cookies}"


    def __repr__(self):
        return str(self)


    def price_cutoff(self):
        return max(1000, self.cookies * 2)


    def cps(self):
        total = 0.0

        for name in self.num_buildings:
            num = self.num_buildings[name]
            cps = building_stats[name].base_cps

            total += num * cps

        total += self.clickrate

        return total


    def building_price(self, name):
        base_price = building_stats[name].base_price
        return base_price * 1.15**self.num_buildings[name]


    def purchase_building(self, name):
        price = self.building_price(name)

        self.age += (price + self.clickrate) / self.cps()
        self.cookies += price
        self.num_buildings[name] += 1

        self.history.append(name + f" #{self.num_buildings[name]}")
        

    def children(self):
        for name in self.num_buildings:
            if self.building_price(name) > self.price_cutoff():
                continue

            child = self.copy()
            child.purchase_building(name)

            yield child

