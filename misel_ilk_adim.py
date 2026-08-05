import pygame
import networkx as nx
import random
import math
import time


# --- SCREEN SETTINGS ---
SCREEN_WIDTH, PANEL_WIDTH = 1100, 450
SCREEN_HEIGHT = 950
TOTAL_WIDTH = SCREEN_WIDTH + PANEL_WIDTH

WHITE = (255,255,255)
BLACK = (30,30,30)
GRAY = (200,200,200)
GREEN = (0,255,0)
BLUE = (0,100,255)
ORANGE = (255,140,0)
RED = (255,0,0)
PANEL_COLOR = (240,240,240)

# ---------------------------------------------------
# PACKET CLASS
# ---------------------------------------------------
class Packet:
    def __init__(self, path, pos_dict, color, speed):
        self.path = path
        self.pos_dict = pos_dict
        self.segment_index = 0
        self.progress = 0.0
        self.speed = speed
        self.current_pos = list(pos_dict[path[0]])
        self.color = color

    def advance(self):
        if self.segment_index < len(self.path)-1:
            if self.path[self.segment_index] not in self.pos_dict:
                return False
            if self.path[self.segment_index+1] not in self.pos_dict:
                return False

            start = self.pos_dict[self.path[self.segment_index]]
            end = self.pos_dict[self.path[self.segment_index+1]]

            self.progress += self.speed

            self.current_pos[0] = start[0] + (end[0]-start[0]) * self.progress
            self.current_pos[1] = start[1] + (end[1]-start[1]) * self.progress

            if self.progress >= 1.0:
                self.progress = 0.0
                self.segment_index += 1

            return True
        return False


# ---------------------------------------------------
# SLIDER CLASS
# ---------------------------------------------------
class Slider:
    def __init__(self, x,y,width,height,min_v,max_v,default_val,label):
        self.rect = pygame.Rect(x,y,width,height)
        self.min_v = min_v
        self.max_v = max_v
        self.value = default_val
        self.label = label
        self.dragging = False

    def draw(self, screen, font, text_color):
        pygame.draw.rect(screen, GRAY, self.rect)
        pos_x = self.rect.x + (self.value-self.min_v)/(self.max_v-self.min_v)*self.rect.w
        pygame.draw.circle(screen, BLUE, (int(pos_x), self.rect.centery), self.rect.h)

        txt = font.render(f"{self.label}: {self.value:.3f}", True, text_color)
        screen.blit(txt, (self.rect.x, self.rect.y-20))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.dragging = True

        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = max(0, min(event.pos[0]-self.rect.x, self.rect.w))
            self.value = self.min_v + (rel_x/self.rect.w)*(self.max_v-self.min_v)


# ---------------------------------------------------
# NETWORK CLASS
# ---------------------------------------------------
class MiselNetwork:
    def __init__(self, num_nodes):
        self.G = nx.Graph()
        self.pos = {}
        self.active_flows = []
        self.edge_usage = {}
        self.num_nodes = num_nodes
        self.path_memory = {}
        self.node_energy={}
        self.node_type = {}
        self.node_state = {}
        self.protected_nodes = set()
        self.charge_timer = {}
        self.charge_target = {}
        self.setup_graph()

        

        self.debug_info = {
            "source": "-",
            "target": "-",
            "selected": "-",
            "scores": [],
            "candidates": []
        }

    def setup_graph(self):
        for i in range(self.num_nodes):
            self.pos[i] = (
                random.randint(50, SCREEN_WIDTH-50),
                random.randint(50, SCREEN_HEIGHT-50)
            )
            self.G.add_node(i)

        self.auto_connect_edges()

        for n in self.G.nodes():

            self.node_energy[n] = random.uniform(0.6, 1.0)

            self.node_state[n] = "active"

            # %25 ihtimalle güçlü bataryalı telefon
            if random.random() < 0.25:
                self.node_type[n] = "battery"
            else:
                self.node_type[n] = "normal"

    def auto_connect_edges(self):
        for i in self.G.nodes():
            for j in self.G.nodes():
                if i < j:
                    dist = math.hypot(
                        self.pos[i][0]-self.pos[j][0],
                        self.pos[i][1]-self.pos[j][1]
                    )

                    if dist < 280:
                        if not self.G.has_edge(i,j):
                            self.G.add_edge(i,j,weight=2.0)
                            self.edge_usage[(i,j)] = 0

    # ---------------------------------------------
    # ROUTING SYSTEM
    # ---------------------------------------------
    def get_candidate_paths(self, source, target, k=3):
        try:
            generator = nx.shortest_simple_paths(
                self.G,
                source,
                target,
                weight=lambda u,v,d: 1.0 / d["weight"]
            )

            paths = []
            for _, path in zip(range(k), generator):
                paths.append(path)

            return paths
        except:
            return []

    def score_path(self, path):
        strength = 0
        congestion = 0

        for i in range(len(path)-1):
            u,v = path[i], path[i+1]

            strength += self.G[u][v]["weight"]

            key = (u,v) if (u,v) in self.edge_usage else (v,u)
            congestion += self.edge_usage.get(key,0)

        strength = strength / (len(path)-1)
        distance = len(path)-1
        memory = self.path_memory.get(tuple(path),0)

        energy_penalty = 0

        for node in path:
            #if self.node_state.get(node) != "active":
                #return -999
            energy_penalty +=(1-self.node_energy.get(node,1))
        energy_penalty /= len(path)

        score = (
            2.0 * strength
            - 1.5 * congestion
            - 1.0 * distance
            + 1.2 * memory
            -2.0 * energy_penalty
        )

        return score

    def choose_path(self, paths):
        if not paths:
            return None

        scored = []

        for p in paths:
            s = self.score_path(p)

            if s <= -999:
                continue

            scored.append((p, max(0.1, s)))

        if not scored:
                return None

        total = sum(score for _,score in scored)
        r = random.uniform(0,total)

        current = 0
        for path,score in scored:
            current += score
            if r <= current:
                return path

        return scored[0][0]

    
    def update(self, growth_rate, decay_rate):
        all_paths = []

        # usage reset
        for key in self.edge_usage:
            self.edge_usage[key] = 0

        for flow in self.active_flows[:]:
            try:
                paths = self.get_candidate_paths(
                    flow["source"],
                    flow["target"]
                )

                valid_paths = []

                for p in paths:

                    alive = True

                    for node in p:

                        if self.node_state.get(node) != "active":
                            alive = False
                            break

                    if alive:
                        valid_paths.append(p)

                path = self.choose_path(valid_paths)

                if path is None:
                    continue

                self.debug_info["source"] = str(flow["source"])
                self.debug_info["target"] = str(flow["target"])
                self.debug_info["selected"] = str(path)

                scores = []

                for p in paths:
                    s = round(self.score_path(p), 2)
                    scores.append(s)

                self.debug_info["scores"] = scores


                all_paths.append(path)

                # memory reward
                key_path = tuple(path)
                self.path_memory[key_path] = self.path_memory.get(key_path,0) + 0.05

                for i in range(len(path)-1):
                    u,v = path[i], path[i+1]

                    self.G[u][v]["weight"] = min(
                        10.0,
                        self.G[u][v]["weight"] + growth_rate
                    )

                    key = (u,v) if (u,v) in self.edge_usage else (v,u)
                    self.edge_usage[key] += 1

                    if u not in self.protected_nodes:

                        if self.node_type[u] == "battery":
                            self.node_energy[u] -= 0.0015
                        else:
                            self.node_energy[u] -= 0.003

                    self.node_energy[u] = max(0.0, self.node_energy[u])

                    if self.node_energy[u] <= 0:
                        self.node_state[u] = "dead"

            except Exception as e:
                print("UPDATE ERROR",e)

        # edge decay
        for u,v,d in self.G.edges(data=True):
            d["weight"] = max(0.1, d["weight"] - decay_rate)

        # memory decay
        for p in list(self.path_memory.keys()):
            self.path_memory[p] *= 0.995
            if self.path_memory[p] < 0.01:
                del self.path_memory[p]

        # CHARGING SYSTEM
        for node in list(self.charge_timer.keys()):

            self.charge_timer[node] -= 1

            if self.charge_timer[node] <= 0:

                target = self.charge_target[node]

                self.node_energy[node] = target

                self.node_state[node] = "active"

                del self.charge_timer[node]
                del self.charge_target[node]

        return all_paths
    
# ---------------------------------------------------
# EXPLOSION EFFECT
# ---------------------------------------------------
class Explosion:

    def __init__(self, x, y):

        self.x = x
        self.y = y

        self.radius = 10
        self.max_radius = 80

        self.life = 30

    def update(self):

        self.radius += 3
        self.life -= 1


    def draw(self, screen):

        if self.life > 0:

            color = (255, random.randint(80,180), 0)

            pygame.draw.circle(
                screen,
                color,
                (int(self.x), int(self.y)),
                int(self.radius),
                4
            )
# ---------------------------------------------------
# PANEL
# ---------------------------------------------------
def create_panel():
    slider_growth = Slider(SCREEN_WIDTH+20, 70, 220, 20, 0.01, 0.2, 0.08, "Edge Growth")

    slider_decay = Slider(SCREEN_WIDTH+20, 135, 220, 20,0.0001, 0.02, 0.005, "Edge Decay")

    slider_packet = Slider(SCREEN_WIDTH+20, 200, 220, 20,0.01, 0.2, 0.05, "Packet Speed")

    # MODE BUTTONS
    user_mode_btn = pygame.Rect(SCREEN_WIDTH+40, 255, 100, 38)
    auto_mode_btn = pygame.Rect(SCREEN_WIDTH+200, 255, 100, 38)

    # USER SIDE

    left_x = SCREEN_WIDTH + 20
    right_x = SCREEN_WIDTH + 185

    btn_w = 145
    btn_h = 38

    # USER MODE BUTTONS
    add_btn = pygame.Rect(left_x, 330, btn_w, btn_h)

    battery_btn = pygame.Rect(left_x, 380, btn_w, btn_h)

    remove_btn = pygame.Rect(left_x, 430, btn_w, btn_h)

    sender_btn = pygame.Rect(left_x, 480, btn_w, btn_h)

    receiver_btn = pygame.Rect(left_x, 530, btn_w, btn_h)

    charge_btn = pygame.Rect(left_x, 580, btn_w, btn_h)

    # AUTO MODE BUTTONS

    auto_add_btn = pygame.Rect(right_x, 330, btn_w, btn_h)

    auto_remove_btn = pygame.Rect(right_x, 380, btn_w, btn_h)

    auto_sender_btn = pygame.Rect(right_x, 430, btn_w, btn_h)

    auto_receiver_btn = pygame.Rect(right_x, 480, btn_w, btn_h)

    disaster_btn = pygame.Rect(right_x, 530, btn_w, btn_h)

    auto_charge_btn = pygame.Rect(right_x, 580, btn_w, btn_h)

    # NIGHT MODE BUTTON
    night_btn = pygame.Rect(
        SCREEN_WIDTH + 270,
        80,
        140,
        35
    )

    # START
    start_btn = pygame.Rect(
        SCREEN_WIDTH + 270,
        140,
        140,
        35
    )

    

    return (
        slider_growth,
        slider_decay,
        slider_packet,

        user_mode_btn,
        auto_mode_btn,

        add_btn,
        battery_btn,
        remove_btn,
        sender_btn,
        receiver_btn,
        charge_btn,

        auto_add_btn,
        auto_remove_btn,
        auto_sender_btn,
        auto_receiver_btn,
        disaster_btn,
        auto_charge_btn,

        night_btn,
        start_btn
    )

# ---------------------------------------------------
# BUTTON DRAW
# ---------------------------------------------------
def draw_button(screen, rect, text, color, font):
    pygame.draw.rect(screen, color, rect, border_radius=8)
    txt = font.render(text, True, WHITE)
    txt_rect = txt.get_rect(center=rect.center)
    screen.blit(txt, txt_rect)


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((TOTAL_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Misel Network Simulation")
    font = pygame.font.SysFont("Arial",16)

    # SIREN SYSTEM
    
    print("TRYING TO LOAD SIREN")

    try:
        siren_sound = pygame.mixer.Sound("siren.wav")
        print("SIREN LOADED SUCCESSFULLY")

        

    except Exception as e:
        siren_sound = None
        print("SIREN ERROR:", e)
    

    misel = MiselNetwork(20)
    packets = []
    explosions = []
    clock = pygame.time.Clock()

    (
    slider_growth,
    slider_decay,
    slider_packet,

    user_mode_btn,
    auto_mode_btn,

    add_btn,
    battery_btn,
    remove_btn,
    sender_btn,
    receiver_btn,
    charge_btn,

    auto_add_btn,
    auto_remove_btn,
    auto_sender_btn,
    auto_receiver_btn,
    disaster_btn,
    auto_charge_btn,

    night_btn,
    start_btn
    ) = create_panel()

    mode = None
    traffic_mode = "user"
    night_mode = False

    flows = []
    selected_sender = None
    selected_node = None
    flow_colors = [
        (255,105,180),  # pembe
        (0,150,255),    # mavi
        (255,165,0),    # turuncu
        (180,0,255),    # mor
        (255,255,0),    # sarı
        (0,255,255)     # cyan
    ]

    sim_started = False
    auto_timer = 0

    # DISASTER SYSTEM
    disaster_active = False
    disaster_timer = 0

    # AUTO FLOW SYSTEM
    selected_auto_sender = None

    while True:
        if night_mode:
            BG_COLOR = (15,15,25)
            PANEL_BG = (25,25,35)
            TEXT_COLOR = (0,255,180)
            EDGE_COLOR = (80,80,120)
        else:
            BG_COLOR = WHITE
            PANEL_BG = PANEL_COLOR
            TEXT_COLOR = BLACK
            EDGE_COLOR = GRAY

        screen.fill(BG_COLOR)
        # --------------------------------
        # DISASTER COUNTDOWN
        # --------------------------------
        if disaster_active:
            disaster_timer -= 1

            if disaster_timer <= 0:
              
                if siren_sound:
                    siren_sound.stop()
                nodes = list(misel.G.nodes())

                remove_count = max(1, int(len(nodes) * 0.4))

                remove_nodes = random.sample(nodes, remove_count)

                for n in remove_nodes:

                    if n in misel.G.nodes():

                        x, y = misel.pos[n]

                        explosions.append(
                        Explosion(x, y)
                        )

                        misel.G.remove_node(n)

                        misel.pos.pop(n, None)
                        misel.node_energy.pop(n, None)

                disaster_active = False

        pygame.draw.rect(
            screen,
            PANEL_BG,
            (SCREEN_WIDTH,0,PANEL_WIDTH,SCREEN_HEIGHT)
        )

        # EVENTS
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

            slider_growth.handle_event(event)
            slider_decay.handle_event(event)
            slider_packet.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx,my = event.pos

                if night_btn.collidepoint(event.pos):
                    night_mode = not night_mode

                elif start_btn.collidepoint(event.pos):
                    sim_started = True

                elif mx > SCREEN_WIDTH:

                    # MODE BUTTONS
                    if user_mode_btn.collidepoint(event.pos):
                       traffic_mode = "user"

                    elif auto_mode_btn.collidepoint(event.pos):
                       traffic_mode = "auto"

                    # ---------------- USER MODE ----------------

                    elif add_btn.collidepoint(event.pos):

                        if traffic_mode == "user":
                            mode = "add"

                    elif battery_btn.collidepoint(event.pos):

                        if traffic_mode == "user":
                            mode = "battery_add"

                    elif remove_btn.collidepoint(event.pos):

                        if traffic_mode == "user":
                            mode = "remove"

                    elif sender_btn.collidepoint(event.pos):

                        if traffic_mode == "user":
                           mode = "sender"

                    elif receiver_btn.collidepoint(event.pos):

                        if traffic_mode == "user":
                           mode = "receiver"

                    elif charge_btn.collidepoint(event.pos):

                        if (
                            traffic_mode == "user"
                            and
                            selected_node is not None
                            and
                            selected_node in misel.G.nodes()
                        ):

                            misel.node_state[selected_node] = "charging"

                            misel.charge_timer[selected_node] = 180
                            misel.charge_target[selected_node] = 1.0

                    # ---------------- AUTO MODE ----------------

                    elif auto_add_btn.collidepoint(event.pos):

                        if traffic_mode == "auto":

                            new_id = max(misel.G.nodes(), default=-1) + 1

                            x = random.randint(50, SCREEN_WIDTH-50)
                            y = random.randint(50, SCREEN_HEIGHT-50)

                            misel.G.add_node(new_id)
                            misel.pos[new_id] = (x, y)

                            misel.node_energy[new_id] = random.uniform(0.6, 1.0)
                            misel.node_state[new_id] = "active"

                            if random.random() < 0.25:
                                misel.node_type[new_id] = "battery"
                            else:
                                misel.node_type[new_id] = "normal"

                            misel.auto_connect_edges()

                    elif auto_remove_btn.collidepoint(event.pos):

                        if traffic_mode == "auto":

                            nodes = list(misel.G.nodes())

                            if len(nodes) > 3:

                               remove_node = random.choice(nodes)
                               misel.G.remove_node(remove_node)
                               misel.pos.pop(remove_node, None)
                               misel.node_energy.pop(remove_node, None)

                               misel.node_type.pop(n, None)
                               misel.node_state.pop(n, None)

                    elif auto_sender_btn.collidepoint(event.pos):
                        if traffic_mode == "auto":
                            nodes = list(misel.G.nodes())
                            if len(nodes) >= 1:
                                selected_auto_sender = random.choice(nodes)

                    elif auto_receiver_btn.collidepoint(event.pos):
                        if traffic_mode == "auto":
                            nodes = list(misel.G.nodes())
                            if (
                                len(nodes) >= 2
                                and
                                selected_auto_sender is not None
                            ):
                                possible = [
                                    n for n in nodes
                                    if n != selected_auto_sender
                                ]

                                target = random.choice(possible)
                                color = flow_colors[
                                    len(flows) % len(flow_colors)
                                ]

                                flows.append({
                                    "source": selected_auto_sender,
                                    "target": target,
                                    "color": color,
                                    "life": random.randint(150,300)
                                })

                                misel.protected_nodes.add(selected_auto_sender)
                                misel.protected_nodes.add(target)

                                selected_auto_sender = None

                    elif auto_charge_btn.collidepoint(event.pos):

                        if traffic_mode == "auto":

                            candidates = [
                                n for n in misel.G.nodes()
                                if (
                                    n not in misel.protected_nodes
                                    and
                                    misel.node_energy[n] < 0.95
                                )
                            ]

                            if len(candidates) > 0:

                                count = min(
                                    len(candidates),
                                    random.randint(2, 6)
                                )

                                selected = random.sample(
                                    candidates,
                                    count
                                )

                                for node in selected:

                                    current = misel.node_energy[node]

                                    possible = [
                                        x for x in [0.25, 0.50, 0.75, 1.0]
                                        if x > current
                                    ]

                                    if possible:
                                        target = random.choice(possible)
                                    else:
                                        continue

                                    misel.node_state[node] = "charging"

                                    misel.charge_timer[node] = 180

                                    misel.charge_target[node] = target
    
                    elif disaster_btn.collidepoint(event.pos):

                        if traffic_mode == "auto" and not disaster_active:
                           disaster_active = True
                           disaster_timer = 500

                           if siren_sound:
                                siren_sound.play(-1)

                           


                elif sim_started:

                    # NODE INFO SELECT
                    for n in misel.G.nodes():

                        if math.hypot(
                            mx - misel.pos[n][0],
                            my - misel.pos[n][1]
                        ) < 20:

                            selected_node = n

                    if mode == "add":
                        new_id = max(misel.G.nodes(), default=-1)+1

                        misel.G.add_node(new_id)
                        misel.pos[new_id] = (mx,my)

                        misel.node_energy[new_id] = random.uniform(0.6, 1.0)
                        misel.node_state[new_id] = "active"
                        misel.node_type[new_id] = "normal"

                        misel.auto_connect_edges()

                    elif mode == "battery_add":
                        new_id = max(misel.G.nodes(), default=-1)+1

                        misel.G.add_node(new_id)
                        misel.pos[new_id] = (mx,my)

                        misel.node_energy[new_id] = random.uniform(0.8, 1.0)
                        misel.node_state[new_id] = "active"
                        misel.node_type[new_id] = "battery"

                        misel.auto_connect_edges()

                    elif mode == "remove":
                        for n in list(misel.G.nodes()):
                            if math.hypot(mx-misel.pos[n][0], my-misel.pos[n][1]) < 20:
                                misel.G.remove_node(n)
                                misel.pos.pop(n, None)
                                misel.node_energy.pop(n, None)

                                misel.node_type.pop(n, None)
                                misel.node_state.pop(n, None)

                                flows = [
                                    f for f in flows
                                    if f["source"] != n and f["target"] != n
                                ]
                                if selected_sender == n:
                                    selected_sender = None

                    elif mode == "sender":
                        for n in misel.G.nodes():
                            if math.hypot(mx-misel.pos[n][0], my-misel.pos[n][1]) < 20:
                                selected_sender = n

                    elif mode == "receiver":
                        for n in misel.G.nodes():
                            if math.hypot(mx-misel.pos[n][0], my-misel.pos[n][1]) < 20:
                                if selected_sender is not None and selected_sender != n:
                                    color = flow_colors[len(flows) % len(flow_colors)]
                                    flows.append({
                                        "source": selected_sender,
                                        "target": n,
                                        "color": color
                                    })

                                    misel.protected_nodes.add(selected_sender)
                                    misel.protected_nodes.add(n)

                                    selected_sender = None

            print("flows:", len(misel.active_flows))
            

        # SIMULATION
        active_paths = []

        if sim_started:
            misel.active_flows.clear()

            # USER MODE
            if traffic_mode == "user":
                for f in flows:
                    if (
                       f["source"] in misel.G.nodes()
                       and
                       f["target"] in misel.G.nodes()
                    ):
                        misel.active_flows.append({
                        "source": f["source"],
                        "target": f["target"]
                    })
                        
            # AUTO MODE
            elif traffic_mode == "auto":
  
                # FLOWLARI ROUTING SİSTEMİNE AKTAR
                for f in flows:

                    if (
                       f["source"] in misel.G.nodes()
                       and
                       f["target"] in misel.G.nodes()
                    ):

                       misel.active_flows.append({
                       "source": f["source"],
                       "target": f["target"]
                    })
                       
            # UPDATE NETWORK
            active_paths = misel.update(
            slider_growth.value,
            slider_decay.value
            )

            # PACKET CREATE
            for path in active_paths:

                if random.random() < 0.1:

                    packets.append(
                        Packet(
                           path,
                           misel.pos,
                           random.choice(flow_colors),
                           slider_packet.value
                        )
                    )

            

        # DRAW EDGES
        for u,v,d in misel.G.edges(data=True):
            key = (u,v) if (u,v) in misel.edge_usage else (v,u)
            usage = misel.edge_usage.get(key,0)

            if usage > 2:
                color = (255,60,60)
            else:
                color = EDGE_COLOR
            thickness = max(1, min(int(d["weight"]*3 + usage), 10))

            pygame.draw.line(
                screen,
                color,
                misel.pos[u],
                misel.pos[v],
                thickness
            )

        # DRAW PACKETS
        for p in packets[:]:
            if p.advance():
                pygame.draw.circle(
                    screen,
                    p.color,
                    (int(p.current_pos[0]), int(p.current_pos[1])),
                    5
                )
            else:
                packets.remove(p)

        # DRAW EXPLOSIONS
        for exp in explosions[:]:

            exp.update()
            exp.draw(screen)

            if exp.life <= 0:
                explosions.remove(exp)

        # DRAW NODES
        for n in misel.G.nodes():

            blink = True

            if misel.node_state.get(n) == "charging":
                blink = (pygame.time.get_ticks() // 200) % 2 == 0

            energy = misel.node_energy.get(n,1)
            r = int((1-energy)*255)
            g = int(energy*255)
            color = (r,g,0)

            if misel.node_state.get(n) == "charging":
                color = (0, 200, 255)

            if misel.node_state.get(n) == "dead":
                color = (60,60,60)

            # Flow renkleri
            for f in flows:
                if n == f["source"]:
                    color = f["color"]
                if n == f["target"]:
                    color = f["color"]

            if blink:
            
                if misel.node_type.get(n) == "battery":

                    pygame.draw.rect(
                        screen,
                        color,
                        (
                            misel.pos[n][0]-18,
                            misel.pos[n][1]-18,
                            36,
                            36
                        )
                    )

                else:

                    pygame.draw.circle(
                        screen,
                        color,
                        misel.pos[n],
                        18
                    )

        # PANEL
        slider_growth.draw(screen, font, TEXT_COLOR)
        slider_decay.draw(screen, font, TEXT_COLOR)
        slider_packet.draw(screen, font, TEXT_COLOR)

        # PANEL TITLES
        user_title = font.render("USER CONTROL", True, TEXT_COLOR)
        screen.blit(user_title, (SCREEN_WIDTH+35, 300))

        auto_title = font.render("AUTO CONTROL", True, TEXT_COLOR)
        screen.blit(auto_title, (SCREEN_WIDTH+205, 300))

        draw_button(screen, user_mode_btn, "User Mode",
                    GREEN if traffic_mode=="user" else GRAY, font)

        draw_button(screen, auto_mode_btn, "Auto Mode",
                    GREEN if traffic_mode=="auto" else GRAY, font)

        # USER PANEL
        draw_button(screen, add_btn, 
                "User Add Node", 
                (0,180,0), font)
        
        draw_button(screen, battery_btn,
                "Add Battery Node",
                (0,120,255),font)

        draw_button(screen, remove_btn,
            "User Remove Node",
            (180,0,0), font)

        draw_button(screen, sender_btn,
            "Select Sender",
            (0,100,200), font)

        draw_button(screen, receiver_btn,
            "Select Receiver",
            (200,100,0), font)
        
        draw_button(screen, charge_btn,
            "Charge Node",
            (0,180,180), font)

        # AUTO PANEL
        draw_button(screen, auto_add_btn,
            "Auto Add Random Node",
            (0,150,120), font)

        draw_button(screen, auto_remove_btn,
            "Auto Remove Random",
            (150,50,50), font)
        
        draw_button(screen, auto_sender_btn,
            "Auto Sender",
            (120,80,220), font)
        
        draw_button(screen, auto_receiver_btn,
            "Auto Receiver",
            (220,120,80), font)
        
        draw_button(screen, disaster_btn,
            "DISASTER (40% DELETE)",
            (255,50,50), font)
        
        draw_button(screen, auto_charge_btn,
            "Auto Charge",
            (0,180,180), font)
        
        draw_button(
            screen,
            night_btn,
            "Night Mode",
            (80, 80, 120) if not night_mode else (0, 180, 180),
            font
        )

        if not sim_started:
            draw_button(screen, start_btn, "Start Simulation", (50,200,50), font)

        # Current Mode
        info = font.render(f"Current Mode: {traffic_mode}", True, TEXT_COLOR)
        screen.blit(info, (SCREEN_WIDTH+20, 700))

        #DEBUG PANEL
        dbg = misel.debug_info

        y = 740

        title = font.render("=== DEBUG PANEL ===", True, TEXT_COLOR)
        screen.blit(title, (SCREEN_WIDTH+20, y))

        y += 25
        txt1 = font.render(
           f"Flow: {dbg['source']} -> {dbg['target']}",
           True, TEXT_COLOR
        )
        screen.blit(txt1, (SCREEN_WIDTH+20, y))

        y += 22
        txt2 = font.render(
           f"Selected: {dbg['selected'][:26]}",
           True, TEXT_COLOR
        )
        screen.blit(txt2, (SCREEN_WIDTH+20, y))

        y += 24
        for i in range(len(dbg["scores"])):
            line = f"P{i+1}: {dbg['scores'][i]}%"
            txt = font.render(line, True, TEXT_COLOR)
            screen.blit(txt, (SCREEN_WIDTH+20, y))
            y += 18 
        
        y += 26
        txt3 = font.render(
           f"Active Flows: {len(misel.active_flows)}",
           True, TEXT_COLOR
        )
        screen.blit(txt3, (SCREEN_WIDTH+20, y))

        y += 20
        txt4 = font.render(
           f"Packets: {len(packets)}",
           True, TEXT_COLOR
        )
        screen.blit(txt4, (SCREEN_WIDTH+20, y))

        # --------------------------------
        # NODE INFO PANEL
        # --------------------------------
        if selected_node is not None and selected_node in misel.G.nodes():

            node_y = 740

            pygame.draw.rect(
                screen,
                (225,225,225),
                (SCREEN_WIDTH+240, node_y-10, 230, 180),
                border_radius=10
            )

            title = font.render("=== NODE INFO ===", True, BLUE)
            screen.blit(title, (SCREEN_WIDTH+250, node_y))

            energy = round(
            misel.node_energy.get(selected_node, 0),
            2
            )

            pos = misel.pos[selected_node]

            neighbors = list(
            misel.G.neighbors(selected_node)
            )

            txt1 = font.render(
            f"Node ID: {selected_node}",
            True,
            BLACK
            )
            screen.blit(txt1, (SCREEN_WIDTH+250, node_y+20))

            txt2 = font.render(
            f"Energy: {energy}",
            True,
            BLACK
            )
            screen.blit(txt2, (SCREEN_WIDTH+250, node_y+40))

            txt3 = font.render(
            f"Type: {misel.node_type[selected_node]}",
            True,
            BLACK
            )
            screen.blit(txt3, (SCREEN_WIDTH+250, node_y+60))

            txt4 = font.render(
            f"Position: {pos}",
            True,
            BLACK
            )
            screen.blit(txt4, (SCREEN_WIDTH+250, node_y+80))

            txt5 = font.render(
            f"Connections: {len(neighbors)}",
            True,
            BLACK
            )
            screen.blit(txt5, (SCREEN_WIDTH+250, node_y+100))

            txt6 = font.render(
            f"Neighbors: {neighbors[:5]}",
            True,
            BLACK
            )
            screen.blit(txt6, (SCREEN_WIDTH+250, node_y+120))

            txt_state = font.render(
                f"State: {misel.node_state.get(selected_node, 'unknown')}",
                True,
                BLACK
            )

            screen.blit(
                txt_state,
                (SCREEN_WIDTH+250, node_y+140)
            )

        if disaster_active:

            seconds = math.ceil(disaster_timer / 40)

            txt = font.render(
            f"DISASTER IN: {seconds}",
            True,
            RED
            )

            screen.blit(txt, (SCREEN_WIDTH+20, 670))

        pygame.display.flip()
        clock.tick(60)



if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("CRASH:", e)
        input("ENTER")