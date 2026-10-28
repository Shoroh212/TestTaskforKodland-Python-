
import requests
import pgzrun
from pgzero.builtins import Actor, clock

API_URL = "http://127.0.0.1:8000/api"
POLL_INTERVAL = 0.3
REQUEST_TIMEOUT = 0.25

CELL_SIZE = 32
GRID_WIDTH = 20
GRID_HEIGHT = 15

WIDTH = CELL_SIZE * GRID_WIDTH
HEIGHT = CELL_SIZE * GRID_HEIGHT
TITLE = "Cat Game for Kodland"

BACKGROUND_COLOR = (92, 160, 92)
GRID_COLOR = (82, 146, 82)
NAME_COLOR = "white"
NAME_OUTLINE_COLOR = "black"
NAME_CHAR_WIDTH = 9 


def cell_center(cell_x, cell_y):
    return (cell_x * CELL_SIZE + CELL_SIZE // 2,
            cell_y * CELL_SIZE + CELL_SIZE // 2)


class Cat:
   

    SPEED = 40  
    FRAME_COUNT = 4
    FRAME_DURATION = 0.12  

    def __init__(self, name, cell_x, cell_y):
        self.name = name
        self.cell_x = cell_x
        self.cell_y = cell_y
        self.target_cell_x = cell_x
        self.target_cell_y = cell_y
        self.direction = "down"
        self.is_moving = False
        self.frame = 0
        self.frame_timer = 0
        self.actor = Actor(self.image_name(), center=cell_center(cell_x,
                                                                 cell_y))

    def image_name(self):
        if self.is_moving:
            return f"cat_walk_{self.direction}_{self.frame}"
        return f"cat_wait_{self.direction}"

    def set_target(self, cell_x, cell_y):
        """Запомните ячейку, в которой должен находиться кот."""
        self.target_cell_x = cell_x
        self.target_cell_y = cell_y

    def start_step_to_neighbor_cell(self):
        
        step_x = (self.target_cell_x > self.cell_x) - (
            self.target_cell_x < self.cell_x)
        step_y = (self.target_cell_y > self.cell_y) - (
            self.target_cell_y < self.cell_y)
        if step_x:
            step_y = 0
            self.direction = "right" if step_x > 0 else "left"
        elif step_y:
            self.direction = "down" if step_y > 0 else "up"
        if not step_x and not step_y:
            return
        self.cell_x += step_x
        self.cell_y += step_y
        self.is_moving = True

    def move(self, dt):

        target_x, target_y = cell_center(self.cell_x, self.cell_y)
        distance = self.SPEED * dt
        self.actor.x = self.approach(self.actor.x, target_x, distance)
        self.actor.y = self.approach(self.actor.y, target_y, distance)
        if (self.actor.x, self.actor.y) == (target_x, target_y):
            self.is_moving = False

    @staticmethod
    def approach(value, target, distance):
        if abs(target - value) <= distance:
            return target
        return value + distance if target > value else value - distance

    def animate(self, dt):
        if self.is_moving:
            self.frame_timer += dt
            if self.frame_timer >= self.FRAME_DURATION:
                self.frame_timer = 0
                self.frame = (self.frame + 1) % self.FRAME_COUNT
        else:
            self.frame = 0
            self.frame_timer = 0
        self.actor.image = self.image_name()

    def update(self, dt):
        if self.is_moving:
            self.move(dt)
        if not self.is_moving:
            self.start_step_to_neighbor_cell()
        self.animate(dt)

    def draw(self, screen):
        self.actor.draw()
        half_width = len(self.name) * NAME_CHAR_WIDTH // 2
        name_x = min(max(self.actor.x, half_width), WIDTH - half_width)
        screen.draw.text(
            self.name,
            midbottom=(name_x, self.actor.top + 2),
            fontsize=18,
            color=NAME_COLOR,
            owidth=1,
            ocolor=NAME_OUTLINE_COLOR,
        )


class Coin:
    FRAME_COUNT = 4
    FRAME_DURATION = 0.15

    def __init__(self):
        self.frame = 0
        self.frame_timer = 0
        self.is_visible = False
        self.actor = Actor("coin_0")

    def place(self, cell_x, cell_y):
        self.actor.center = cell_center(cell_x, cell_y)
        self.is_visible = True

    def update(self, dt):
        self.frame_timer += dt
        if self.frame_timer >= self.FRAME_DURATION:
            self.frame_timer = 0
            self.frame = (self.frame + 1) % self.FRAME_COUNT
            self.actor.image = f"coin_{self.frame}"

    def draw(self):
        if self.is_visible:
            self.actor.draw()


cats = {}
coin = Coin()
server_available = False


def fetch_game_state():
    """Ask the server where the cats and the coin are."""
    global server_available
    try:
        response = requests.get(API_URL, timeout=REQUEST_TIMEOUT)
        state = response.json()
    except (requests.RequestException, ValueError):
        server_available = False
        return
    server_available = True

    coin.place(state["coin"]["cell_x"], state["coin"]["cell_y"])
    for player in state["players"]:
        cat = cats.get(player["id"])
        if cat is None:
            cats[player["id"]] = Cat(player["name"], player["cell_x"],
                                     player["cell_y"])
        else:
            cat.name = player["name"]
            cat.set_target(player["cell_x"], player["cell_y"])


def draw_grid():
    for x in range(0, WIDTH, CELL_SIZE):
        screen.draw.line((x, 0), (x, HEIGHT), GRID_COLOR)
    for y in range(0, HEIGHT, CELL_SIZE):
        screen.draw.line((0, y), (WIDTH, y), GRID_COLOR)


def draw():
    screen.fill(BACKGROUND_COLOR)
    draw_grid()
    coin.draw()
    for cat in cats.values():
        cat.draw(screen)
    if not server_available:
        screen.draw.text(
            "Нет связи с сервером...",
            center=(WIDTH // 2, HEIGHT // 2),
            fontsize=32,
            color="white",
            owidth=1,
            ocolor="black",
        )


def update(dt):
    coin.update(dt)
    for cat in cats.values():
        cat.update(dt)


fetch_game_state()
clock.schedule_interval(fetch_game_state, POLL_INTERVAL)
pgzrun.go()
