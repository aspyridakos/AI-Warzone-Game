from __future__ import annotations
import argparse
import copy
from collections import defaultdict
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from time import sleep
from typing import Tuple, Iterable, ClassVar
import random
import requests

# maximum and minimum values for our heuristic scores (usually represents an end of game condition)
MAX_HEURISTIC_SCORE = 2000000000
MIN_HEURISTIC_SCORE = -2000000000
OUTPUT_FILE = ''


def append_to_file(result):
    """Appends game actions to existing log file"""
    # Function appends to the existing file by opening and writing to it as it did initially.
    global OUTPUT_FILE
    with open(OUTPUT_FILE, 'a') as f:
        f.write("{r}\n".format(r=result))


class UnitType(Enum):
    """Every unit type."""
    AI = 0
    Tech = 1
    Virus = 2
    Program = 3
    Firewall = 4


class Player(Enum):
    """The 2 players."""
    Attacker = 0
    Defender = 1

    def next(self) -> Player:
        """The next (other) player."""
        if self is Player.Attacker:
            return Player.Defender
        else:
            return Player.Attacker


class GameType(Enum):
    AttackerVsDefender = 0
    AttackerVsComp = 1
    CompVsDefender = 2
    CompVsComp = 3


##############################################################################################################

@dataclass(slots=True)
class Unit:
    player: Player = Player.Attacker
    type: UnitType = UnitType.Program
    health: int = 9
    # class variable: damage table for units (based on the unit type constants in order)
    damage_table: ClassVar[list[list[int]]] = [
        [3, 3, 3, 3, 1],  # AI
        [1, 1, 6, 1, 1],  # Tech
        [9, 6, 1, 6, 1],  # Virus
        [3, 3, 3, 3, 1],  # Program
        [1, 1, 1, 1, 1],  # Firewall
    ]
    # class variable: repair table for units (based on the unit type constants in order)
    repair_table: ClassVar[list[list[int]]] = [
        [0, 1, 1, 0, 0],  # AI
        [3, 0, 0, 3, 3],  # Tech
        [0, 0, 0, 0, 0],  # Virus
        [0, 0, 0, 0, 0],  # Program
        [0, 0, 0, 0, 0],  # Firewall
    ]

    def is_alive(self) -> bool:
        """Are we alive ?"""
        return self.health > 0

    def mod_health(self, health_delta: int):
        """Modify this unit's health by delta amount."""
        self.health += health_delta
        if self.health < 0:
            self.health = 0
        elif self.health > 9:
            self.health = 9

    def to_string(self) -> str:
        """Text representation of this unit."""
        p = self.player.name.lower()[0]
        t = self.type.name.upper()[0]
        return f"{p}{t}{self.health}"

    def __str__(self) -> str:
        """Text representation of this unit."""
        return self.to_string()

    def damage_amount(self, target: Unit) -> int:
        """How much can this unit damage another unit."""
        amount = self.damage_table[self.type.value][target.type.value]
        if target.health - amount < 0:
            return target.health
        return amount

    def repair_amount(self, target: Unit) -> int:
        """How much can this unit repair another unit."""
        amount = self.repair_table[self.type.value][target.type.value]
        if target.health + amount > 9:
            return 9 - target.health
        return amount


##############################################################################################################

@dataclass(slots=True)
class Coord:
    """Representation of a game cell coordinate (row, col)."""
    row: int = 0
    col: int = 0

    def col_string(self) -> str:
        """Text representation of this Coord's column."""
        coord_char = '?'
        if self.col < 16:
            coord_char = "0123456789abcdef"[self.col]
        return str(coord_char)

    def row_string(self) -> str:
        """Text representation of this Coord's row."""
        coord_char = '?'
        if self.row < 26:
            coord_char = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[self.row]
        return str(coord_char)

    def to_string(self) -> str:
        """Text representation of this Coord."""
        return self.row_string() + self.col_string()

    def __str__(self) -> str:
        """Text representation of this Coord."""
        return self.to_string()

    def clone(self) -> Coord:
        """Clone a Coord."""
        return copy.copy(self)

    def iter_range(self, dist: int) -> Iterable[Coord]:
        """Iterates over Coords inside a rectangle centered on our Coord."""
        for row in range(self.row - dist, self.row + 1 + dist):
            for col in range(self.col - dist, self.col + 1 + dist):
                yield Coord(row, col)

    def iter_adjacent(self) -> Iterable[Coord]:
        """Iterates over adjacent Coords."""
        yield Coord(self.row - 1, self.col)  # returns top-adjacent coord
        yield Coord(self.row, self.col - 1)  # returns left-adjacent coord
        yield Coord(self.row + 1, self.col)  # returns bottom-adjacent coord
        yield Coord(self.row, self.col + 1)  # returns right-adjacent coord

    @classmethod
    def from_string(cls, s: str) -> Coord | None:
        """Create a Coord from a string. ex: D2."""
        s = s.strip()
        for sep in " ,.:;-_":
            s = s.replace(sep, "")
        if len(s) == 2:
            coord = Coord()
            coord.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[0:1].upper())
            coord.col = "0123456789abcdef".find(s[1:2].lower())
            return coord
        else:
            return None


##############################################################################################################

@dataclass(slots=True)
class CoordPair:
    """Representation of a game move or a rectangular area via 2 Coords."""
    src: Coord = field(default_factory=Coord)
    dst: Coord = field(default_factory=Coord)

    def to_string(self) -> str:
        """Text representation of a CoordPair."""
        return self.src.to_string() + " " + self.dst.to_string()

    def __str__(self) -> str:
        """Text representation of a CoordPair."""
        return self.to_string()

    def clone(self) -> CoordPair:
        """Clones a CoordPair."""
        return copy.copy(self)

    def iter_rectangle(self) -> Iterable[Coord]:
        """Iterates over cells of a rectangular area."""
        for row in range(self.src.row, self.dst.row + 1):
            for col in range(self.src.col, self.dst.col + 1):
                yield Coord(row, col)

    @classmethod
    def from_quad(cls, row0: int, col0: int, row1: int, col1: int) -> CoordPair:
        """Create a CoordPair from 4 integers."""
        return CoordPair(Coord(row0, col0), Coord(row1, col1))

    @classmethod
    def from_dim(cls, dim: int) -> CoordPair:
        """Create a CoordPair based on a dim-sized rectangle."""
        return CoordPair(Coord(0, 0), Coord(dim - 1, dim - 1))

    @classmethod
    def from_string(cls, s: str) -> CoordPair | None:
        """Create a CoordPair from a string. ex: A3 B2"""
        s = s.strip()
        for sep in " ,.:;-_":
            s = s.replace(sep, "")
        if len(s) == 4:
            coords = CoordPair()
            coords.src.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[0:1].upper())
            coords.src.col = "0123456789abcdef".find(s[1:2].lower())
            coords.dst.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[2:3].upper())
            coords.dst.col = "0123456789abcdef".find(s[3:4].lower())
            return coords
        else:
            return None


##############################################################################################################

@dataclass(slots=True)
class Options:
    """Representation of the game options."""
    dim: int = 5
    max_depth: int | None = 4
    min_depth: int | None = 2
    max_time: float | None = 5.0
    game_type: GameType = GameType.AttackerVsDefender
    alpha_beta: bool = True
    max_turns: int | None = 100
    randomize_moves: bool = True
    broker: str | None = None


##############################################################################################################

@dataclass(slots=True)
class Stats:
    """Representation of the global game statistics."""
    evaluations_per_depth: dict[int, int] = field(default_factory=dict)
    total_seconds: float = 0.0


##############################################################################################################

@dataclass(slots=True)
class Game:
    """Representation of the game state."""
    board: list[list[Unit | None]] = field(default_factory=list)
    next_player: Player = Player.Attacker
    turns_played: int = 0
    options: Options = field(default_factory=Options)
    stats: Stats = field(default_factory=Stats)
    _attacker_has_ai: bool = True
    _defender_has_ai: bool = True
    move_id: int = 0

    def __post_init__(self):
        """Automatically called after class init to set up the default board state."""
        dim = self.options.dim
        self.board = [[None for _ in range(dim)] for _ in range(dim)]
        md = dim - 1
        self.set(Coord(0, 0), Unit(player=Player.Defender, type=UnitType.AI))
        self.set(Coord(1, 0), Unit(player=Player.Defender, type=UnitType.Tech))
        self.set(Coord(0, 1), Unit(player=Player.Defender, type=UnitType.Tech))
        self.set(Coord(2, 0), Unit(player=Player.Defender, type=UnitType.Firewall))
        self.set(Coord(0, 2), Unit(player=Player.Defender, type=UnitType.Firewall))
        self.set(Coord(1, 1), Unit(player=Player.Defender, type=UnitType.Program))
        self.set(Coord(md, md), Unit(player=Player.Attacker, type=UnitType.AI))
        self.set(Coord(md - 1, md), Unit(player=Player.Attacker, type=UnitType.Virus))
        self.set(Coord(md, md - 1), Unit(player=Player.Attacker, type=UnitType.Virus))
        self.set(Coord(md - 2, md), Unit(player=Player.Attacker, type=UnitType.Program))
        self.set(Coord(md, md - 2), Unit(player=Player.Attacker, type=UnitType.Program))
        self.set(Coord(md - 1, md - 1), Unit(player=Player.Attacker, type=UnitType.Firewall))

    def clone(self) -> Game:
        """Make a new copy of a game for minimax recursion.

        Shallow copy of everything except the board (options and stats are shared).
        """
        new = copy.copy(self)
        new.board = copy.deepcopy(self.board)
        return new

    def is_empty(self, coord: Coord) -> bool:
        """Check if contents of a board cell of the game at Coord is empty (must be valid coord)."""
        return self.board[coord.row][coord.col] is None

    def get(self, coord: Coord) -> Unit | None:
        """Get contents of a board cell of the game at Coord."""
        if self.is_valid_coord(coord):
            return self.board[coord.row][coord.col]
        else:
            return None

    def set(self, coord: Coord, unit: Unit | None):
        """Set contents of a board cell of the game at Coord."""
        if self.is_valid_coord(coord):
            self.board[coord.row][coord.col] = unit

    def remove_dead(self, coord: Coord):
        """Remove unit at Coord if dead."""
        unit = self.get(coord)
        if unit is not None and not unit.is_alive():
            self.set(coord, None)
            if unit.type == UnitType.AI:
                if unit.player == Player.Attacker:
                    self._attacker_has_ai = False
                else:
                    self._defender_has_ai = False

    def mod_health(self, coord: Coord, health_delta: int):
        """Modify health of unit at Coord (positive or negative delta)."""
        target = self.get(coord)
        if target is not None:
            target.mod_health(health_delta)
            self.remove_dead(coord)

    def is_valid_move(self, coords: CoordPair) -> bool:
        """Validate a move expressed as a CoordPair."""
        # Checks if source and target coordinates are within board limits
        if not self.is_valid_coord(coords.src) or not self.is_valid_coord(coords.dst):
            return False
        unit = self.get(coords.src)
        # Checks if trying to move from an empty coord OR if trying to move opponents piece
        if unit is None or unit.player != self.next_player:
            return False
        unit = self.get(coords.dst)
        is_adjacent_coord = coords.dst in coords.src.iter_adjacent()

        # Checks if destination coordinate is adjacent
        if is_adjacent_coord:
            # Checks if attempting to move piece (destination coord is empty)
            if unit is None:
                # Gets the unit type of the source piece
                unit_type = self.get(coords.src).type.value

                # Check if Virus or Tech
                # Can move freely in attack or defense, and in combat
                # After check, returns statement that move is valid
                if unit_type in [1, 2]:
                    print("valid move for Virus and Tech units")
                    self.move_id = 0
                    return True

                # Check if engaged in combat and AI, Program or Firewall
                # Cannot move in this case
                if self.engaged_in_combat(coords.src):
                    print("invalid move for AI, Program or Firewall units engaged in combat")
                    return False

                # Get player type
                player_type = self.get(coords.src).player.value

                # List out adjacent coordinates
                top_adjacent_coord = Coord(coords.src.row - 1, coords.src.col).to_string()
                left_adjacent_coord = Coord(coords.src.row, coords.src.col - 1).to_string()
                bottom_adjacent_coord = Coord(coords.src.row + 1, coords.src.col).to_string()
                right_adjacent_coord = Coord(coords.src.row, coords.src.col + 1).to_string()

                # Player is an attacker and unit is an AI, Program or Firewall
                # Can only move up or left
                if (player_type is Player.Attacker.value
                        and coords.dst.to_string() in [top_adjacent_coord, left_adjacent_coord]):
                    print("valid move for AI, Program or Firewall defender units (up or left)")
                    self.move_id = 0
                    return True

                # Player is a defender and unit is an AI, Program or Firewall
                # Can only move down or right
                elif (player_type is Player.Defender.value
                      and coords.dst.to_string() in [bottom_adjacent_coord, right_adjacent_coord]):
                    print("valid move for AI, Program or Firewall defender units (down or right)")
                    self.move_id = 0
                    return True
                else:
                    print("invalid more for AI, Program or Firewall while not engaged in combat")
                    return False

            # Checks if attacking or repairing piece
            else:
                # If units belong to same player (attempting repair)
                if unit.player is self.get(coords.src).player:
                    health_delta = self.get(coords.src).repair_amount(unit)
                    # Checks if valid repair
                    if health_delta == 0:
                        print("invalid repair")
                        return False
                    else:
                        self.move_id = 1
                        print("valid repair")
                        return True
                # If opposing units (attempting attack)
                else:
                    self.move_id = 2
                    print("valid attack")
                    return True
        # Checks if src and dst coords are the same (initiating self-destruct)
        elif coords.src == coords.dst:
            self.move_id = 3
            print("valid self-destruction")
            return True
        # Checks if trying to move to non-adjacent space and not self-destructing
        else:
            print("invalid move, non-adjacent space selected")
            return False

    def engaged_in_combat(self, coord: Coord) -> bool:
        """Check if unit is engaged in combat."""
        # Function determines if player is engaged in combat with piece
        ajd = Coord.iter_adjacent(coord)
        for adjacent_coord in ajd:
            enemy = self.get(adjacent_coord)
            # Return True if enemy player in one of adjacent coordinates
            if enemy is not None and enemy.player != self.get(coord).player:
                return True
        return False

    def perform_move(self, coords: CoordPair) -> Tuple[bool, str]:
        """Validate and perform a move expressed as a CoordPair."""
        if self.is_valid_move(coords):
            match self.move_id:
                # Available actions to play
                # Movement type case
                case 0:
                    self.set(coords.dst, self.get(coords.src))
                    self.set(coords.src, None)
                    return True, "-> Moved from {src} to {dst}".format(dst=coords.dst, src=coords.src)
                # Repair type case
                case 1:
                    health_delta = self.get(coords.src).repair_amount(self.get(coords.dst))
                    health_before = self.get(coords.dst).health
                    # modify health of unit at destination
                    self.mod_health(coords.dst, health_delta)
                    return True, "-> Repair outcome: health before = {hb} and health after = {ha}" \
                        .format(hb=health_before, ha=self.get(coords.dst).health)
                # Attack type case
                case 2:
                    damage_to_opponent = self.get(coords.src).damage_amount(self.get(coords.dst))
                    damage_from_opponent = self.get(coords.dst).damage_amount(self.get(coords.src))
                    # modify health of source unit
                    self.mod_health(coords.src, -damage_from_opponent)
                    # modify health of destination unit
                    self.mod_health(coords.dst, -damage_to_opponent)
                    # check if either unit is dead and remove if it is
                    self.remove_dead(coords.src)
                    self.remove_dead(coords.dst)
                    return True, "-> Combat damage: to source = {df}, to target {dt}".format(df=damage_from_opponent,
                                                                                             dt=damage_to_opponent)
                # Self-destruct type case
                case 3:
                    total_damage = 0
                    surrounding_units = coords.src.iter_range(1)
                    for coord in surrounding_units:
                        # unit to self-destruct
                        if str(coord) == str(coords.src):
                            unit_health = self.get(coord).health
                            self.mod_health(coord, -unit_health)
                        # surrounding units to damage
                        elif self.is_valid_coord(coord) and self.get(coord) is not None:
                            self.mod_health(coord, -2)
                            total_damage += 2
                        # check if unit is dead and remove if it is
                        self.remove_dead(coord)
                    return True, "-> Self-destructed for {td} total damage".format(td=total_damage)
        return False, "invalid move"

    def next_turn(self):
        """Transitions game to the next turn."""
        self.next_player = self.next_player.next()
        self.turns_played += 1

    def to_string(self) -> str:
        """Pretty text representation of the game."""
        dim = self.options.dim
        output = ""
        output += f"Next player: {self.next_player.name}\n"
        output += f"Turns played: {self.turns_played}\n"
        coord = Coord()
        output += "\n   "
        for col in range(dim):
            coord.col = col
            label = coord.col_string()
            output += f"{label:^3} "
        output += "\n"
        for row in range(dim):
            coord.row = row
            label = coord.row_string()
            output += f"{label}: "
            for col in range(dim):
                coord.col = col
                unit = self.get(coord)
                if unit is None:
                    output += " .  "
                else:
                    output += f"{str(unit):^3} "
            output += "\n"
        return output

    def board_only_to_string(self) -> str:
        """Pretty text representation of the board configuration only."""
        dim = self.options.dim
        output = ""
        coord = Coord()
        output += "\n   "
        for col in range(dim):
            coord.col = col
            label = coord.col_string()
            output += f"{label:^3} "
        output += "\n"
        for row in range(dim):
            coord.row = row
            label = coord.row_string()
            output += f"{label}: "
            for col in range(dim):
                coord.col = col
                unit = self.get(coord)
                if unit is None:
                    output += " .  "
                else:
                    output += f"{str(unit):^3} "
            output += "\n"
        return output

    def __str__(self) -> str:
        """Default string representation of a game."""
        return self.to_string()

    def is_valid_coord(self, coord: Coord) -> bool:
        """Check if a Coord is valid within our board dimensions."""
        dim = self.options.dim
        if coord.row < 0 or coord.row >= dim or coord.col < 0 or coord.col >= dim:
            return False
        return True

    def read_move(self) -> CoordPair:
        """Read a move from keyboard and return as a CoordPair."""
        while True:
            s = input(F'Player {self.next_player.name}, enter your move: ')
            coords = CoordPair.from_string(s)
            if coords is not None and self.is_valid_coord(coords.src) and self.is_valid_coord(coords.dst):
                return coords
            else:
                print('Invalid coordinates! Try again.')

    def human_turn(self):
        """Human player plays a move (or get via broker)."""
        if self.options.broker is not None:
            print("Getting next move with auto-retry from game broker...")
            while True:
                mv = self.get_move_from_broker()
                if mv is not None:
                    (success, result) = self.perform_move(mv)
                    print(f"Broker {self.next_player.name}: ", end='')
                    print(result)
                    append_to_file(result)
                    if success:
                        self.next_turn()
                        break
                sleep(0.1)
        else:
            while True:
                mv = self.read_move()
                (success, result) = self.perform_move(mv)
                if success:
                    print(f"Player {self.next_player.name}: ", end='')
                    print(result)
                    append_to_file(result)
                    self.next_turn()
                    break
                else:
                    print("The move is not valid! Try again.")

    def computer_turn(self) -> CoordPair | None:
        """Computer plays a move."""
        mv = self.suggest_move()
        if mv is not None:
            (success, result) = self.perform_move(mv)
            if success:
                print(f"Computer {self.next_player.name}: ", end='')
                print(result)
                self.next_turn()
        return mv

    def player_units(self, player: Player) -> Iterable[Tuple[Coord, Unit]]:
        """Iterates over all units belonging to a player."""
        for coord in CoordPair.from_dim(self.options.dim).iter_rectangle():
            unit = self.get(coord)
            if unit is not None and unit.player == player:
                yield coord, unit

    def is_finished(self) -> bool:
        """Check if the game is over."""
        return self.has_winner() is not None

    def has_winner(self) -> Player | None:
        """Check if the game is over and returns winner"""
        if self.options.max_turns is not None and self.turns_played >= self.options.max_turns:
            return Player.Defender
        if self._attacker_has_ai:
            if self._defender_has_ai:
                return None
            else:
                return Player.Attacker
        return Player.Defender

    def move_candidates(self) -> Iterable[CoordPair]:
        """Generate valid move candidates for the next player."""
        move = CoordPair()
        for (src, _) in self.player_units(self.next_player):
            move.src = src
            for dst in src.iter_adjacent():
                move.dst = dst
                if self.is_valid_move(move):
                    yield move.clone()
            move.dst = src
            yield move.clone()

    def random_move(self) -> Tuple[int, CoordPair | None, float]:
        """Returns a random move."""
        move_candidates = list(self.move_candidates())
        random.shuffle(move_candidates)
        if len(move_candidates) > 0:
            return 0, move_candidates[0], 1
        else:
            return 0, None, 0

    def minimax(self, depth: int, maximizing_player: bool) -> Tuple[int, CoordPair | None]:
        """Minimax algorithm implementation"""
        moves = self.move_candidates()

        if depth == 0 or self.is_finished():
            return self.get_heuristic_e0(), None

        if maximizing_player:
            best_move = MIN_HEURISTIC_SCORE
            for move in moves:
                self.set(move.dst, self.get(move.src))
                current_move = self.minimax(depth - 1, False)
                best_move = max(best_move, current_move)
            return best_move
        else:
            best_move = MAX_HEURISTIC_SCORE
            for move in moves:
                self.set(move.dst, self.get(move.src))
                current_move = self.minimax(depth - 1, True)
                best_move = min(best_move, current_move)

    def suggest_move(self) -> CoordPair | None:
        """Suggest the next move using minimax alpha beta. TODO: REPLACE RANDOM_MOVE WITH PROPER GAME LOGIC!!!"""
        start_time = datetime.now()

        # Clone the board to test minimax options
        board_copy = self.clone()

        # TODO: set other heuristics here (e1 => aggressive play, e2 => defensive play???)
        initial_heuristic = self.get_heuristic_e0()
        # initial_heuristic = self.get_heuristic_e1()
        # initial_heuristic = self.get_heuristic_e2()

        # Optimizing for MAX player
        if initial_heuristic > 0:
            suggested_move = board_copy.minimax(self.options.max_depth, True)
        # Optimizing for MIN player
        elif initial_heuristic < 0:
            suggested_move = board_copy.minimax(self.options.min_depth, True)
        # Optimizing for AVERAGE player
        else:
            # TODO: Optimize depth later
            avg_depth = int((self.options.max_depth + self.options.min_depth) / 2)
            suggested_move = board_copy.minimax(avg_depth, True)

        # FIXME: Not sure where avg_depth comes from...
        # (score, move, avg_depth) = suggested_move, 4
        (score, move, avg_depth) = self.random_move()

        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        self.stats.total_seconds += elapsed_seconds
        print(f"Heuristic score: {score}")
        print(f"Average recursive depth: {avg_depth:0.1f}")
        print(f"Evals per depth: ", end='')
        for k in sorted(self.stats.evaluations_per_depth.keys()):
            print(f"{k}:{self.stats.evaluations_per_depth[k]} ", end='')
        print()
        total_evals = sum(self.stats.evaluations_per_depth.values())
        if self.stats.total_seconds > 0:
            print(f"Eval perf.: {total_evals / self.stats.total_seconds / 1000:0.1f}k/s")
        print(f"Elapsed time: {elapsed_seconds:0.1f}s")
        return move

    def get_heuristic_e0(self) -> int:
        """Calculate e0 heuristic"""
        player_unit_counts = {player: defaultdict(int) for player in Player}

        for player in Player:
            for coord, unit in self.player_units(player):
                player_unit_counts[player][unit.type] += 1

        attacker_counts = player_unit_counts[Player.Attacker]
        defender_counts = player_unit_counts[Player.Defender]

        e0: int
        if self._attacker_has_ai:
            e0 = ((3 * attacker_counts[UnitType.Virus] + 3 * attacker_counts[UnitType.Tech] +
                   3 * attacker_counts[UnitType.Firewall] + 3 * attacker_counts[UnitType.Program] +
                   9999 * attacker_counts[UnitType.AI]) -
                  (3 * defender_counts[UnitType.Virus] + 3 * defender_counts[UnitType.Tech] +
                   3 * defender_counts[UnitType.Firewall] + 3 * defender_counts[UnitType.Program] +
                   9999 * defender_counts[UnitType.AI]))
        else:
            e0 = (((3 * defender_counts[UnitType.Virus] + 3 * defender_counts[UnitType.Tech] +
                    3 * defender_counts[UnitType.Firewall] + 3 * defender_counts[UnitType.Program] +
                    9999 * defender_counts[UnitType.AI]))
                  - (3 * attacker_counts[UnitType.Virus] + 3 * attacker_counts[UnitType.Tech] +
                     3 * attacker_counts[UnitType.Firewall] + 3 * attacker_counts[UnitType.Program] +
                     9999 * attacker_counts[UnitType.AI]))
        return e0

    def get_heuristic_e1(self) -> int:
        """Calculate e1 heuristic (more offensive)"""
        player_unit_counts = {player: defaultdict(int) for player in Player}

        for player in Player:
            for coord, unit in self.player_units(player):
                player_unit_counts[player][unit.type] += 1

        attacker_counts = player_unit_counts[Player.Attacker]
        defender_counts = player_unit_counts[Player.Defender]

        e1: int
        if self._attacker_has_ai:
            e1 = (
                # Prioritize killing pieces that can move/attack when engaged in combat (Tech and Virus)
                    (6 * (attacker_counts[UnitType.Tech] + 6 * attacker_counts[UnitType.Virus])) +
                # Prioritize keeping your own pieces alive that are more powerful on attack (Firewall and Program)
                    (3 * (attacker_counts[UnitType.Firewall] + 3 * attacker_counts[UnitType.Program])) -
                # Always prioritize the AI since it's the game decider
                    (9999 * attacker_counts[UnitType.AI])
            )
        else:
            e1 = (
                # Prioritize killing pieces that can move/attack when engaged in combat (Tech and Virus)
                    (6 * (defender_counts[UnitType.Tech] + 6 * defender_counts[UnitType.Virus])) +
                # Prioritize keeping your own pieces alive that are more powerful on attack (Firewall and Program)
                    (3 * (defender_counts[UnitType.Firewall] + 3 * defender_counts[UnitType.Program])) -
                # Always prioritize the AI since it's the game decider
                    (9999 * defender_counts[UnitType.AI])
            )
        return e1


    # def get_heuristics_e2(self) -> int:
    #     """Calculate e2 heuristic (more defensive)"""
    #     player_unit_counts = {player: defaultdict(int) for player in Player}
    # 
    #     for player in Player:
    #         for coord, unit in self.player_units(player):
    #
    #     attacker_counts = player_unit_counts[Player.Attacker]
    #     defender_counts = player_unit_counts[Player.Defender]
    #
    #
    #     e2:int

    def post_move_to_broker(self, move: CoordPair):
        """Send a move to the game broker."""
        if self.options.broker is None:
            return
        data = {
            "from": {"row": move.src.row, "col": move.src.col},
            "to": {"row": move.dst.row, "col": move.dst.col},
            "turn": self.turns_played
        }
        try:
            r = requests.post(self.options.broker, json=data)
            if r.status_code == 200 and r.json()['success'] and r.json()['data'] == data:
                # print(f"Sent move to broker: {move}")
                pass
            else:
                print(f"Broker error: status code: {r.status_code}, response: {r.json()}")
        except Exception as error:
            print(f"Broker error: {error}")

    def get_move_from_broker(self) -> CoordPair | None:
        """Get a move from the game broker."""
        if self.options.broker is None:
            return None
        headers = {'Accept': 'application/json'}
        try:
            r = requests.get(self.options.broker, headers=headers)
            if r.status_code == 200 and r.json()['success']:
                data = r.json()['data']
                if data is not None:
                    if data['turn'] == self.turns_played + 1:
                        move = CoordPair(
                            Coord(data['from']['row'], data['from']['col']),
                            Coord(data['to']['row'], data['to']['col'])
                        )
                        print(f"Got move from broker: {move}")
                        return move
                    else:
                        # print("Got broker data for wrong turn.")
                        # print(f"Wanted {self.turns_played+1}, got {data['turn']}")
                        pass
                else:
                    # print("Got no data from broker")
                    pass
            else:
                print(f"Broker error: status code: {r.status_code}, response: {r.json()}")
        except Exception as error:
            print(f"Broker error: {error}")
        return None


##############################################################################################################

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        prog='ai_wargame',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--max_turns', type=int, help='maximum number of turns')
    parser.add_argument('--alpha_beta', type=bool, help='alpha-beta heuristic on')
    parser.add_argument('--max_depth', type=int, help='maximum search depth')
    parser.add_argument('--max_time', type=float, help='maximum search time')
    parser.add_argument('--game_type', type=str, default="manual", help='game type: auto|attacker|defender|manual')
    parser.add_argument('--broker', type=str, help='play via a game broker')
    parser.add_argument('--heuristic', type=str, help='AI heuristic: e0|e1|e2')
    args = parser.parse_args()

    # Parse the game type and set the descriptive string accordingly
    if args.game_type == "attacker":
        game_type = GameType.AttackerVsComp
        play_mode = "player 1 = AI & player 2 = H"
    elif args.game_type == "defender":
        game_type = GameType.CompVsDefender
        play_mode = "player 1 = H & player 2 = AI"
    elif args.game_type == "manual":
        game_type = GameType.AttackerVsDefender
        play_mode = "player 1 = H & player 2 = H"
    else:
        game_type = GameType.CompVsComp
        play_mode = "player 1 = AI & player 2 = AI"

    # Set up game options
    options = Options(game_type=game_type)

    # Override class defaults via command line options
    # Added additional arguments properly needed
    if args.max_depth is not None:
        options.max_depth = args.max_depth
    if args.max_time is not None:
        options.max_time = args.max_time
    if args.broker is not None:
        options.broker = args.broker
    if args.max_turns is not None:
        options.max_turns = args.max_turns

    # Create a new game
    game = Game(options=options)

    # Initialize name of output file based on arguments
    # With proper argument parameters to have written
    global OUTPUT_FILE
    OUTPUT_FILE = 'gameTrace-{b}-{t}-{m}.txt'.format(b=args.alpha_beta if args.alpha_beta is not None else "false",
                                                     t=args.max_time if args.max_time is not None else options.max_time,
                                                     m=args.max_turns)

    # write game parameters to output file
    # Opens the file and writes to it with the proper arguments needed
    with open(OUTPUT_FILE, 'w') as f:
        f.write("----------------\n")
        f.write("GAME PARAMETERS: \nTurn timeout: {t} seconds\nMax turns: {m}\nPlay mode: {p}\n".format(
            t=args.max_time if args.max_time is not None else options.max_time, m=args.max_turns, p=play_mode))
        if args.game_type != "manual":
            f.write("Alpha-beta: {a}\nHeuristic: {h}\n".format(a="on" if args.alpha_beta else "off", h=args.heuristic))
        f.write("----------------\n")

    # The main game loop
    while game.turns_played <= game.options.max_turns:
        # Append initial configuration of board to output file
        if game.turns_played == 0:
            append_to_file("\nGAME START\n")
            append_to_file(game)
            append_to_file("----------------------")
        print()
        print(game)
        winner = game.has_winner()
        # Append to file if a winner is declared. (game is over)
        if winner is not None:
            print(f"{winner.name} won in {game.turns_played} turns!")
            append_to_file(f"{winner.name} won in {game.turns_played} turns!")
            break
        turn_info = "Turn # {turns}/{max}".format(turns=game.turns_played + 1, max=game.options.max_turns)
        append_to_file(turn_info)
        append_to_file("Player: {p}\n".format(p=game.next_player.name))
        if game.options.game_type == GameType.AttackerVsDefender:
            game.human_turn()
            # Append new board configuration to output file
            if game.turns_played != 0:
                append_to_file(game.board_only_to_string())
                append_to_file("----------------------")
        elif game.options.game_type == GameType.AttackerVsComp and game.next_player == Player.Attacker:
            game.human_turn()
        elif game.options.game_type == GameType.CompVsDefender and game.next_player == Player.Defender:
            game.human_turn()
        else:
            player = game.next_player
            move = game.computer_turn()
            if move is not None:
                game.post_move_to_broker(move)
            else:
                # If stalemate occurs, then game over
                append_to_file("Computer doesn't know what to do!!!")
                append_to_file(f"Game over")
                print("Computer doesn't know what to do!!!")
                print("Game over")
                exit(1)


##############################################################################################################

if __name__ == '__main__':
    main()
