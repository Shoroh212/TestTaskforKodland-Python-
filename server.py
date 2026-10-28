
import random
import time

from flask import Flask, jsonify, render_template, request
from sqlalchemy import Float, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

GRID_WIDTH = 20
GRID_HEIGHT = 15
CELL_SIZE = 32

DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

app = Flask(__name__)
engine = create_engine("sqlite:///game.db")


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(64))
    cell_x: Mapped[int] = mapped_column(Integer)
    cell_y: Mapped[int] = mapped_column(Integer)
    map_x: Mapped[int] = mapped_column(Integer)
    map_y: Mapped[int] = mapped_column(Integer)
    joined_at: Mapped[float] = mapped_column(Float)
    coins: Mapped[int] = mapped_column(Integer, default=0)

    def move_to_cell(self, cell_x, cell_y):
        self.cell_x = cell_x
        self.cell_y = cell_y
        self.map_x = cell_x * CELL_SIZE
        self.map_y = cell_y * CELL_SIZE

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "cell_x": self.cell_x,
            "cell_y": self.cell_y,
            "map_x": self.map_x,
            "map_y": self.map_y,
            "joined_at": self.joined_at,
            "coins": self.coins,
        }


class Coin(Base):
    __tablename__ = "coins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cell_x: Mapped[int] = mapped_column(Integer)
    cell_y: Mapped[int] = mapped_column(Integer)

    def to_dict(self):
        return {"cell_x": self.cell_x, "cell_y": self.cell_y}


def get_occupied_cells(session):
    players = session.scalars(select(Player)).all()
    return {(player.cell_x, player.cell_y) for player in players}


def get_random_free_cell(session, extra_busy_cells=()):
    busy_cells = get_occupied_cells(session) | set(extra_busy_cells)
    free_cells = [
        (x, y)
        for x in range(GRID_WIDTH)
        for y in range(GRID_HEIGHT)
        if (x, y) not in busy_cells
    ]
    return random.choice(free_cells)


def get_coin(session):
    """Return the single coin on the field, creating it if needed."""
    coin = session.scalars(select(Coin)).first()
    if coin is None:
        cell_x, cell_y = get_random_free_cell(session)
        coin = Coin(cell_x=cell_x, cell_y=cell_y)
        session.add(coin)
        session.commit()
    return coin


def respawn_coin(session, coin):
    coin.cell_x, coin.cell_y = get_random_free_cell(session)


def join_player(session, telegram_id, name):
    player = session.scalars(
        select(Player).where(Player.telegram_id == telegram_id)
    ).first()
    if player is not None:
        player.name = name
        session.commit()
        return player

    coin = get_coin(session)
    cell_x, cell_y = get_random_free_cell(
        session, extra_busy_cells=[(coin.cell_x, coin.cell_y)]
    )
    player = Player(
        telegram_id=telegram_id,
        name=name,
        joined_at=time.time(),
        coins=0,
    )
    player.move_to_cell(cell_x, cell_y)
    session.add(player)
    session.commit()
    return player


def move_player(session, player, direction):
    step_x, step_y = DIRECTIONS[direction]
    new_x = player.cell_x + step_x
    new_y = player.cell_y + step_y

    inside_field = 0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT
    if not inside_field or (new_x, new_y) in get_occupied_cells(session):
        return

    player.move_to_cell(new_x, new_y)
    coin = get_coin(session)
    if (coin.cell_x, coin.cell_y) == (new_x, new_y):
        player.coins += 1
        session.flush()
        respawn_coin(session, coin)
    session.commit()


def get_game_state(session):
    players = session.scalars(select(Player)).all()
    return {
        "grid": {"width": GRID_WIDTH, "height": GRID_HEIGHT},
        "coin": get_coin(session).to_dict(),
        "players": [player.to_dict() for player in players],
    }


@app.route("/api", methods=["GET", "POST"])
def api():
    with Session(engine) as session:
        if request.method == "GET":
            return jsonify(get_game_state(session))

        data = request.get_json(silent=True) or {}
        action = data.get("action")
        telegram_id = data.get("telegram_id")
        if telegram_id is None:
            return jsonify({"error": "telegram_id is required"}), 400

        if action == "join":
            name = data.get("name") or f"player{telegram_id}"
            player = join_player(session, telegram_id, name)
            return jsonify({"player": player.to_dict()})

        if action == "move":
            direction = data.get("direction")
            if direction not in DIRECTIONS:
                return jsonify({"error": "unknown direction"}), 400
            player = session.scalars(
                select(Player).where(Player.telegram_id == telegram_id)
            ).first()
            if player is None:
                return jsonify({"error": "player not found"}), 404
            move_player(session, player, direction)
            return jsonify({"player": player.to_dict()})

        return jsonify({"error": "unknown action"}), 400


def format_duration(seconds):
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


@app.route("/leaders")
def leaders():
    now = time.time()
    with Session(engine) as session:
        players = session.scalars(
            select(Player).order_by(Player.coins.desc(), Player.joined_at)
        ).all()
        rows = [
            {
                "name": player.name,
                "duration": format_duration(now - player.joined_at),
                "coins": player.coins,
            }
            for player in players
        ]
    return render_template("leaders.html", rows=rows)


@app.route("/about")
def about():
    return render_template("about.html")


Base.metadata.create_all(engine)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
