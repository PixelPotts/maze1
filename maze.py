import pygame
import random
import sys
import math
from collections import deque

# ── Constants ──────────────────────────────────────────────
WINDOW      = 1000
CELL        = 100
GRID        = WINDOW // CELL          # 10x10
WALL_W      = 4
PLAYER_SZ   = 50
HALF        = PLAYER_SZ // 2
SUB_STEPS   = 4
GRUNT_SZ    = 14

BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
BLUE    = (0, 100, 255)
RED     = (255, 50, 50)
GREEN   = (0, 200, 60)
ORANGE  = (255, 160, 30)
GRAY    = (40, 40, 40)
DKGRAY  = (25, 25, 25)
LTGRAY  = (120, 120, 120)

# ── Mutable settings ──────────────────────────────────────
settings = {
    "slide_speed": 1600,     # px/sec primary
    "curve_speed": 100,      # px/sec lateral
    "player_size": 50,       # px
    "wall_thick":  4,        # px
    "grunt_count": 5,
    "grunt_hp":    3,
    "orbit_speed": 2.0,      # rad/s
    "orbit_radius": 70.0,    # px
    "burst_cooldown": 10.0,  # seconds
    "dodge_chance": 33.0,    # percent
}

SLIDER_DEFS = [
    ("slide_speed", "Slide Speed",  200, 4000, "{:.0f} px/s"),
    ("curve_speed", "Curve Speed",  10,  500,  "{:.0f} px/s"),
    ("player_size", "Player Size",  10,  90,   "{:.0f} px"),
    ("wall_thick",  "Wall Width",   1,   20,   "{:.0f} px"),
]

GRUNT_SLIDER_DEFS = [
    ("grunt_count",    "Grunt Count",     0,   20,  "{:.0f}"),
    ("grunt_hp",       "Grunt HP",        1,   10,  "{:.0f}"),
    ("orbit_speed",    "Orbit Speed",     0.5, 6.0, "{:.1f} rad/s"),
    ("orbit_radius",   "Orbit Radius",    30,  150, "{:.0f} px"),
    ("burst_cooldown", "Burst Cooldown",  3,   30,  "{:.0f} s"),
    ("dodge_chance",   "Dodge Chance",    0,   100, "{:.0f}%"),
]


# ── Utility ──────────────────────────────────────────────
def lerp(a, b, t):
    return a + (b - a) * t


# ── Maze generation (recursive back-tracker) ──────────────
def generate_maze(w, h):
    cells = [
        [{"N": True, "E": True, "S": True, "W": True} for _ in range(w)]
        for _ in range(h)
    ]
    visited = [[False] * w for _ in range(h)]
    dirs = {
        "N": (0, -1, "S"), "S": (0, 1, "N"),
        "E": (1, 0, "W"),  "W": (-1, 0, "E"),
    }
    stack = [(0, 0)]
    visited[0][0] = True
    while stack:
        x, y = stack[-1]
        nbrs = []
        for d, (dx, dy, opp) in dirs.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                nbrs.append((d, nx, ny, opp))
        if nbrs:
            d, nx, ny, opp = random.choice(nbrs)
            cells[y][x][d] = False
            cells[ny][nx][opp] = False
            visited[ny][nx] = True
            stack.append((nx, ny))
        else:
            stack.pop()
    return cells


# ── Player helpers ─────────────────────────────────────────
def make_player():
    cx = float(CELL // 2)
    cy = float(CELL // 2)
    return {
        "px": cx, "py": cy,
        "vx": 0.0, "vy": 0.0,
        "moving": False,
        "primary": None,
    }


def _cell(v):
    return max(0, min(GRID - 1, int(v) // CELL))


def _wall_in_rows(maze, col, wall, py, half):
    r0 = _cell(py - half)
    r1 = _cell(py + half - 0.001)
    return any(maze[r][col][wall] for r in range(r0, r1 + 1))


def _wall_in_cols(maze, row, wall, px, half):
    c0 = _cell(px - half)
    c1 = _cell(px + half - 0.001)
    return any(maze[row][c][wall] for c in range(c0, c1 + 1))


def update_player(maze, p, keys, curve, dt):
    if not p["moving"]:
        return

    spd = settings["slide_speed"]
    crv = settings["curve_speed"]
    half = settings["player_size"] // 2

    if p["primary"] == "x":
        neg, pos = curve["y"]
        p["vy"] = -crv if keys[neg] else crv if keys[pos] else 0.0
    else:
        neg, pos = curve["x"]
        p["vx"] = -crv if keys[neg] else crv if keys[pos] else 0.0

    sub_dt = dt / SUB_STEPS
    for _ in range(SUB_STEPS):
        if not p["moving"]:
            break

        npx = p["px"] + p["vx"] * sub_dt
        npy = p["py"] + p["vy"] * sub_dt

        cx = _cell(p["px"])
        cy = _cell(p["py"])

        hx = False
        if p["vx"] > 0:
            bnd = (cx + 1) * CELL
            if npx + half > bnd and _wall_in_rows(maze, cx, "E", p["py"], half):
                npx = bnd - half; hx = True
        elif p["vx"] < 0:
            bnd = cx * CELL
            if npx - half < bnd and _wall_in_rows(maze, cx, "W", p["py"], half):
                npx = bnd + half; hx = True
        p["px"] = npx

        hy = False
        if p["vy"] > 0:
            bnd = (cy + 1) * CELL
            if npy + half > bnd and _wall_in_cols(maze, cy, "S", p["px"], half):
                npy = bnd - half; hy = True
        elif p["vy"] < 0:
            bnd = cy * CELL
            if npy - half < bnd and _wall_in_cols(maze, cy, "N", p["px"], half):
                npy = bnd + half; hy = True
        p["py"] = npy

        if (p["primary"] == "x" and hx) or (p["primary"] == "y" and hy):
            p["vx"] = 0.0; p["vy"] = 0.0; p["moving"] = False
            break


# ── Enemies > Grunt ───────────────────────────────────────
def make_grunt(x, y, target_idx):
    return {
        "px": x, "py": y,
        "hp": int(settings["grunt_hp"]),
        "target": target_idx,
        "state": "approach",       # approach | orbit | burst | dodge
        "angle": 0.0,              # current orbit angle
        "burst_cd": 0.0,           # cooldown timer
        "burst_vx": 0.0,
        "burst_vy": 0.0,
        "burst_timer": 0.0,
        "dodge_vx": 0.0,
        "dodge_vy": 0.0,
        "dodge_timer": 0.0,
        "invuln": 0.0,             # invulnerability after dodge
        "trail": [],               # [(x, y, age), ...]
    }


def spawn_grunts(maze, players, count):
    grunts = []
    player_cells = set()
    for p in players:
        player_cells.add((_cell(p["px"]), _cell(p["py"])))

    far_cells = []
    for r in range(GRID):
        for c in range(GRID):
            if (c, r) not in player_cells:
                min_dist = min(abs(c - pc) + abs(r - pr) for pc, pr in player_cells)
                if min_dist >= 3:
                    far_cells.append((c, r))

    if not far_cells:
        far_cells = [(c, r) for r in range(GRID) for c in range(GRID)
                     if (c, r) not in player_cells]

    random.shuffle(far_cells)
    for i in range(min(count, len(far_cells))):
        c, r = far_cells[i]
        x = c * CELL + CELL // 2
        y = r * CELL + CELL // 2
        target = random.randint(0, len(players) - 1)
        grunts.append(make_grunt(float(x), float(y), target))
    return grunts


def bfs_next_cell(maze, start_col, start_row, goal_col, goal_row):
    if start_col == goal_col and start_row == goal_row:
        return goal_col, goal_row
    visited = [[False] * GRID for _ in range(GRID)]
    parent = {}
    q = deque()
    q.append((start_col, start_row))
    visited[start_row][start_col] = True
    dirs = {
        "N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0),
    }
    while q:
        cx, cy = q.popleft()
        if cx == goal_col and cy == goal_row:
            # Trace back to find the first step
            node = (goal_col, goal_row)
            while parent.get(node) != (start_col, start_row):
                node = parent[node]
            return node
        for d, (dx, dy) in dirs.items():
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < GRID and 0 <= ny < GRID and not visited[ny][nx]:
                if not maze[cy][cx][d]:
                    visited[ny][nx] = True
                    parent[(nx, ny)] = (cx, cy)
                    q.append((nx, ny))
    return start_col, start_row


def count_grouped(g, all_grunts):
    count = 0
    for other in all_grunts:
        if other is g:
            continue
        if other["target"] == g["target"] and other["state"] == "orbit":
            count += 1
    return count


def update_grunt(g, all_grunts, players, maze, dt):
    # Tick down timers
    g["burst_cd"] = max(0.0, g["burst_cd"] - dt)
    g["invuln"] = max(0.0, g["invuln"] - dt)

    # Age trail points
    g["trail"] = [(x, y, age + dt) for x, y, age in g["trail"] if age + dt < 0.3]

    if g["state"] == "burst":
        update_burst(g, dt)
        return
    if g["state"] == "dodge":
        update_dodge(g, dt)
        return

    target = players[g["target"]]
    tx, ty = target["px"], target["py"]
    dx = tx - g["px"]
    dy = ty - g["py"]
    dist = math.hypot(dx, dy)
    radius = settings["orbit_radius"]

    if g["state"] == "approach":
        if dist <= radius + 5:
            g["state"] = "orbit"
            g["angle"] = math.atan2(g["py"] - ty, g["px"] - tx)
        else:
            # BFS pathfinding toward target
            gc = _cell(g["px"])
            gr = _cell(g["py"])
            tc = _cell(tx)
            tr = _cell(ty)
            nc, nr = bfs_next_cell(maze, gc, gr, tc, tr)
            goal_x = nc * CELL + CELL // 2
            goal_y = nr * CELL + CELL // 2
            move_dx = goal_x - g["px"]
            move_dy = goal_y - g["py"]
            move_dist = math.hypot(move_dx, move_dy)
            approach_speed = 120.0
            if move_dist > 1:
                step = min(approach_speed * dt, move_dist)
                g["px"] += (move_dx / move_dist) * step
                g["py"] += (move_dy / move_dist) * step

    elif g["state"] == "orbit":
        # Check if target moved too far
        if dist > radius * 2.5:
            g["state"] = "approach"
            return

        # Orbit around the target (ignores walls)
        ospeed = settings["orbit_speed"]
        g["angle"] += ospeed * dt
        g["px"] = tx + math.cos(g["angle"]) * radius
        g["py"] = ty + math.sin(g["angle"]) * radius

        # Check burst trigger: 3+ grunts orbiting same target, cooldown expired
        if g["burst_cd"] <= 0:
            grouped = count_grouped(g, all_grunts)
            if grouped >= 2:  # 2 others + self = 3 total
                # Burst along orbit tangent
                tang_x = -math.sin(g["angle"])
                tang_y = math.cos(g["angle"])
                burst_speed = 2000.0
                g["burst_vx"] = tang_x * burst_speed
                g["burst_vy"] = tang_y * burst_speed
                g["burst_timer"] = 0.05  # 50ms
                g["state"] = "burst"
                g["burst_cd"] = settings["burst_cooldown"]


def update_burst(g, dt):
    g["trail"].append((g["px"], g["py"], 0.0))
    g["px"] += g["burst_vx"] * dt
    g["py"] += g["burst_vy"] * dt
    # Clamp to screen
    g["px"] = max(GRUNT_SZ // 2, min(WINDOW - GRUNT_SZ // 2, g["px"]))
    g["py"] = max(GRUNT_SZ // 2, min(WINDOW - GRUNT_SZ // 2, g["py"]))
    g["burst_timer"] -= dt
    if g["burst_timer"] <= 0:
        g["state"] = "orbit"


def update_dodge(g, dt):
    g["px"] += g["dodge_vx"] * dt
    g["py"] += g["dodge_vy"] * dt
    # Clamp to screen
    g["px"] = max(GRUNT_SZ // 2, min(WINDOW - GRUNT_SZ // 2, g["px"]))
    g["py"] = max(GRUNT_SZ // 2, min(WINDOW - GRUNT_SZ // 2, g["py"]))
    g["dodge_timer"] -= dt
    if g["dodge_timer"] <= 0:
        g["state"] = "orbit"
        g["invuln"] = 0.5


def trigger_dodge(g, player):
    dx = g["px"] - player["px"]
    dy = g["py"] - player["py"]
    dist = math.hypot(dx, dy)
    if dist < 1:
        dx, dy = 1.0, 0.0
        dist = 1.0
    # Perpendicular to player-grunt vector
    perp_x = -dy / dist
    perp_y = dx / dist
    # Pick the direction that keeps grunt more in-bounds
    test_x = g["px"] + perp_x * 60
    test_y = g["py"] + perp_y * 60
    if test_x < 0 or test_x > WINDOW or test_y < 0 or test_y > WINDOW:
        perp_x, perp_y = -perp_x, -perp_y
        test_x = g["px"] + perp_x * 60
        test_y = g["py"] + perp_y * 60
        if test_x < 0 or test_x > WINDOW or test_y < 0 or test_y > WINDOW:
            return False  # Both directions blocked

    dodge_speed = 1500.0
    g["dodge_vx"] = perp_x * dodge_speed
    g["dodge_vy"] = perp_y * dodge_speed
    g["dodge_timer"] = 0.04  # ~60px at 1500px/s
    g["state"] = "dodge"
    return True


def try_damage_grunt(g, player):
    if g["invuln"] > 0:
        return False
    if g["state"] == "dodge":
        return False

    phalf = settings["player_size"] // 2
    ghalf = GRUNT_SZ // 2
    # AABB collision
    if (abs(player["px"] - g["px"]) < phalf + ghalf and
            abs(player["py"] - g["py"]) < phalf + ghalf):
        # Only moving players deal damage
        if not player["moving"]:
            return False

        # Death dodge check
        if g["hp"] <= 1:
            chance = settings["dodge_chance"] / 100.0
            if random.random() < chance:
                if trigger_dodge(g, player):
                    return False

        g["hp"] -= 1
        return g["hp"] <= 0
    return False


def draw_grunt_trails(screen, grunts):
    trail_surf = pygame.Surface((WINDOW, WINDOW), pygame.SRCALPHA)
    for g in grunts:
        for tx, ty, age in g["trail"]:
            t = age / 0.3
            alpha = int(lerp(200, 0, t))
            radius = int(lerp(6, 2, t))
            if alpha > 0 and radius > 0:
                pygame.draw.circle(trail_surf, (255, 160, 30, alpha),
                                   (int(tx), int(ty)), radius)
    screen.blit(trail_surf, (0, 0))


def draw_grunts(screen, grunts):
    ghalf = GRUNT_SZ // 2
    for g in grunts:
        # Flash white during invuln
        if g["invuln"] > 0 and int(g["invuln"] * 20) % 2 == 0:
            color = WHITE
        elif g["state"] == "burst":
            color = ORANGE
        else:
            color = GREEN

        rect = pygame.Rect(int(g["px"]) - ghalf, int(g["py"]) - ghalf,
                           GRUNT_SZ, GRUNT_SZ)
        pygame.draw.rect(screen, color, rect)

        # Health bar
        max_hp = int(settings["grunt_hp"])
        if max_hp > 0 and g["hp"] < max_hp:
            bar_w = GRUNT_SZ + 4
            bar_h = 3
            bar_x = int(g["px"]) - bar_w // 2
            bar_y = int(g["py"]) - ghalf - 6
            pygame.draw.rect(screen, (80, 0, 0),
                             (bar_x, bar_y, bar_w, bar_h))
            fill_w = int(bar_w * g["hp"] / max_hp)
            pygame.draw.rect(screen, (0, 220, 0),
                             (bar_x, bar_y, fill_w, bar_h))


# ── Options menu (tabbed) ────────────────────────────────
class Slider:
    def __init__(self, x, y, w, h, key, label, lo, hi, fmt):
        self.rect = pygame.Rect(x, y, w, h)
        self.key = key
        self.label = label
        self.lo = lo
        self.hi = hi
        self.fmt = fmt
        self.dragging = False

    @property
    def t(self):
        return (settings[self.key] - self.lo) / (self.hi - self.lo)

    def val_from_x(self, mx):
        t = max(0.0, min(1.0, (mx - self.rect.x) / self.rect.w))
        settings[self.key] = self.lo + t * (self.hi - self.lo)

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect.collidepoint(ev.pos):
                self.dragging = True
                self.val_from_x(ev.pos[0])
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.dragging = False
        elif ev.type == pygame.MOUSEMOTION and self.dragging:
            self.val_from_x(ev.pos[0])

    def draw(self, surf, font):
        # Track background
        pygame.draw.rect(surf, DKGRAY, self.rect, border_radius=4)
        # Fill
        fill = pygame.Rect(self.rect.x, self.rect.y,
                           int(self.rect.w * self.t), self.rect.h)
        pygame.draw.rect(surf, LTGRAY, fill, border_radius=4)
        # Border
        pygame.draw.rect(surf, WHITE, self.rect, 1, border_radius=4)
        # Handle
        hx = self.rect.x + int(self.rect.w * self.t)
        handle = pygame.Rect(hx - 6, self.rect.y - 4, 12, self.rect.h + 8)
        pygame.draw.rect(surf, WHITE, handle, border_radius=3)
        # Label
        lbl = font.render(self.label, True, WHITE)
        surf.blit(lbl, (self.rect.x, self.rect.y - 28))
        # Value
        val = font.render(self.fmt.format(settings[self.key]), True, LTGRAY)
        surf.blit(val, (self.rect.right - val.get_width(), self.rect.y - 28))


def run_options(screen, clock):
    font = pygame.font.SysFont("monospace", 18)
    title_font = pygame.font.SysFont("monospace", 32, bold=True)
    tab_font = pygame.font.SysFont("monospace", 16, bold=True)

    panel_w, panel_h = 500, 520
    px = (WINDOW - panel_w) // 2
    py = (WINDOW - panel_h) // 2

    sx = px + 40
    sw = panel_w - 80
    sy_start = py + 115  # After title + tabs

    # Build sliders for both tabs
    general_sliders = []
    for i, (key, label, lo, hi, fmt) in enumerate(SLIDER_DEFS):
        sy = sy_start + i * 75
        general_sliders.append(Slider(sx, sy, sw, 20, key, label, lo, hi, fmt))

    grunt_sliders = []
    for i, (key, label, lo, hi, fmt) in enumerate(GRUNT_SLIDER_DEFS):
        sy = sy_start + i * 65
        grunt_sliders.append(Slider(sx, sy, sw, 20, key, label, lo, hi, fmt))

    overlay = pygame.Surface((WINDOW, WINDOW), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))

    active_tab = 0  # 0=General, 1=Enemy Grunts
    tab_labels = ["General", "Enemy Grunts"]
    tab_w = panel_w // 2 - 20
    tab_rects = [
        pygame.Rect(px + 15, py + 60, tab_w, 32),
        pygame.Rect(px + 15 + tab_w + 10, py + 60, tab_w, 32),
    ]

    while True:
        sliders = general_sliders if active_tab == 0 else grunt_sliders

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return
                if ev.key == pygame.K_o and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    return
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i, tr in enumerate(tab_rects):
                    if tr.collidepoint(ev.pos):
                        active_tab = i
            for s in sliders:
                s.handle_event(ev)

        screen.blit(overlay, (0, 0))

        # Panel
        panel = pygame.Rect(px, py, panel_w, panel_h)
        pygame.draw.rect(screen, GRAY, panel, border_radius=8)
        pygame.draw.rect(screen, WHITE, panel, 1, border_radius=8)

        # Title
        ttl = title_font.render("OPTIONS", True, WHITE)
        screen.blit(ttl, (px + (panel_w - ttl.get_width()) // 2, py + 18))

        # Tab buttons
        for i, (tr, label) in enumerate(zip(tab_rects, tab_labels)):
            if i == active_tab:
                pygame.draw.rect(screen, LTGRAY, tr, border_radius=5)
            else:
                pygame.draw.rect(screen, DKGRAY, tr, border_radius=5)
            pygame.draw.rect(screen, WHITE, tr, 1, border_radius=5)
            lbl = tab_font.render(label, True, WHITE)
            screen.blit(lbl, (tr.x + (tr.w - lbl.get_width()) // 2,
                              tr.y + (tr.h - lbl.get_height()) // 2))

        # Hint
        hint = font.render("Ctrl+O / Esc to close", True, LTGRAY)
        screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 32))

        for s in sliders:
            s.draw(screen, font)

        pygame.display.flip()
        clock.tick(60)


# ── Main loop ─────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW, WINDOW))
    pygame.display.set_caption("Maze")
    clock = pygame.time.Clock()

    maze = generate_maze(GRID, GRID)

    blue = make_player()
    red  = make_player()
    players = [blue, red]

    grunts = spawn_grunts(maze, players, int(settings["grunt_count"]))

    blue_launch = {
        pygame.K_w: (0, -1), pygame.K_s: (0, 1),
        pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
    }
    red_launch = {
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
        pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
    }
    blue_curve = {"x": (pygame.K_a, pygame.K_d), "y": (pygame.K_w, pygame.K_s)}
    red_curve  = {"x": (pygame.K_LEFT, pygame.K_RIGHT), "y": (pygame.K_UP, pygame.K_DOWN)}

    def launch(p, dx, dy):
        if p["moving"]:
            return
        p["vx"] = dx * settings["slide_speed"]
        p["vy"] = dy * settings["slide_speed"]
        p["moving"] = True
        p["primary"] = "x" if dx != 0 else "y"

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                if ev.key == pygame.K_o and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    prev_count = int(settings["grunt_count"])
                    run_options(screen, clock)
                    # Respawn grunts if count changed
                    new_count = int(settings["grunt_count"])
                    if new_count != prev_count:
                        grunts = spawn_grunts(maze, players, new_count)
                    # Update HP for existing grunts
                    for g in grunts:
                        g["hp"] = min(g["hp"], int(settings["grunt_hp"]))
                    continue
                if ev.key in blue_launch:
                    dx, dy = blue_launch[ev.key]
                    launch(blue, dx, dy)
                if ev.key in red_launch:
                    dx, dy = red_launch[ev.key]
                    launch(red, dx, dy)

        keys = pygame.key.get_pressed()
        update_player(maze, blue, keys, blue_curve, dt)
        update_player(maze, red, keys, red_curve, dt)

        # ── Update grunts ────────────────────────────────
        dead_grunts = []
        for g in grunts:
            update_grunt(g, grunts, players, maze, dt)

        # Check player-grunt collisions (only moving players damage)
        for g in grunts:
            for p in players:
                if try_damage_grunt(g, p):
                    dead_grunts.append(g)
                    break

        for dg in dead_grunts:
            if dg in grunts:
                grunts.remove(dg)

        # ── Draw ──────────────────────────────────────────
        screen.fill(BLACK)

        wt = int(settings["wall_thick"])
        for r in range(GRID):
            for c in range(GRID):
                cell = maze[r][c]
                x0, y0 = c * CELL, r * CELL
                x1, y1 = x0 + CELL, y0 + CELL
                if cell["N"]:
                    pygame.draw.line(screen, WHITE, (x0, y0), (x1, y0), wt)
                if cell["S"]:
                    pygame.draw.line(screen, WHITE, (x0, y1), (x1, y1), wt)
                if cell["E"]:
                    pygame.draw.line(screen, WHITE, (x1, y0), (x1, y1), wt)
                if cell["W"]:
                    pygame.draw.line(screen, WHITE, (x0, y0), (x0, y1), wt)

        # Draw order: walls > trails > grunts > players
        draw_grunt_trails(screen, grunts)
        draw_grunts(screen, grunts)

        psz = int(settings["player_size"])
        ph = psz // 2
        for p, color in [(blue, BLUE), (red, RED)]:
            rect = pygame.Rect(int(p["px"]) - ph, int(p["py"]) - ph, psz, psz)
            pygame.draw.rect(screen, color, rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
