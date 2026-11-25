import sys
import os
import serial
import serial.tools.list_ports
import math
import numpy as np
import pyqtgraph.opengl as gl
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLineEdit, QLabel, QTextEdit,
                             QSlider, QFileDialog, QListWidget, QGroupBox, QComboBox, QColorDialog, QGridLayout)
from PyQt5.QtCore import QThread, pyqtSignal, Qt


class SerialThread(QThread):
    new_point = pyqtSignal(float, float, float)
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser = None
        self.running = True
        self.korekta_pion = 1.0

    def connect_serial(self, port, baud=115200):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = serial.Serial(port, baud, timeout=0.1)
            return True
        except Exception as e:
            self.log_signal.emit(f"Blad: {e}")
            return False

    def run(self):
        while self.running:
            if self.ser and self.ser.is_open:
                if self.ser.in_waiting:
                    try:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            self.log_signal.emit(line)
                            if "Pion:" in line and "Dist:" in line:
                                p = line.split('|')
                                ang_pion = float(p[0].split(':')[1])
                                ang_poz = float(p[1].split(':')[1])
                                dist = float(p[2].split(':')[1])
                                if dist > 0:
                                    rad_pion = math.radians(ang_pion)
                                    rad_poz = math.radians(ang_poz)
                                    offset_pion = 4.5
                                    offset_poziom = 1.5

                                    lens_x_offset = offset_poziom * math.cos(rad_pion)
                                    lens_z_offset = offset_pion + (offset_poziom * math.sin(rad_pion))

                                    d_xy_beam = dist * math.cos(rad_pion)
                                    dist_total_horizontal = d_xy_beam + lens_x_offset

                                    x = dist_total_horizontal * math.cos(rad_poz)
                                    y = dist_total_horizontal * math.sin(rad_poz)
                                    z = lens_z_offset + (dist * math.sin(rad_pion))

                                    print(f"Z = {z:.2f}, X = {x:.2f}, Y = {y:.2f}, D = {dist:.2f}")

                                    self.new_point.emit(x, y, z)
                    except Exception as e:
                        pass
            self.msleep(1)

    def send(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((cmd + '\n').encode())
            except:
                self.log_signal.emit("Blad wysylania")

class LidarGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Radar GUI")
        self.setGeometry(50, 50, 1500, 900)
        self.scans = {}
        self.serial_thread = SerialThread()
        wid = QWidget()
        self.setCentralWidget(wid)
        main_lay = QHBoxLayout(wid)

        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=500, elevation=30, azimuth=-90)
        grid = gl.GLGridItem()
        grid.scale(20, 20, 1)
        self.view.addItem(grid)

        self.marker = gl.GLScatterPlotItem(pos=np.array([[0, 0, 0]]), color=(1, 0, 0, 1), size=10)
        self.view.addItem(self.marker)
        main_lay.addWidget(self.view, 7)

        ctrl_panel = QWidget()
        self.ctrl_lay = QVBoxLayout(ctrl_panel)
        main_lay.addWidget(ctrl_panel, 3)

        pbox = QGroupBox("POŁĄCZENIE")
        play = QVBoxLayout()
        self.cb_ports = QComboBox()
        h_conn = QHBoxLayout()
        btn_refr = QPushButton("Odśwież")
        btn_refr.clicked.connect(self.refresh_ports)
        btn_conn = QPushButton("Połącz")
        btn_conn.clicked.connect(self.handle_connect)
        h_conn.addWidget(btn_refr)
        h_conn.addWidget(btn_conn)
        play.addWidget(self.cb_ports)
        play.addLayout(h_conn)
        pbox.setLayout(play)
        self.ctrl_lay.addWidget(pbox)


        ebox = QGroupBox("STEROWANIE")
        elay = QVBoxLayout()
        h_btn = QHBoxLayout()
        for t, c in [("START", "PELNYSKAN"), ("STOP", "STOP"), ("ZERO", "ZERO")]:
            b = QPushButton(t)
            b.clicked.connect(lambda ch, cmd=c: self.serial_thread.send(cmd))
            h_btn.addWidget(b)
        elay.addLayout(h_btn)

        self.combo_speed = self.create_combo_row(elay, "Prędkość:", ["5", "10", "20", "50"], "predkosc")
        self.combo_pitch = self.create_combo_row(elay, "Skok Pion:", ["1", "2", "5", "10"], "skokpion")
        self.combo_speed.setCurrentText("20")
        self.combo_pitch.setCurrentText("5")

        ebox.setLayout(elay)
        self.ctrl_lay.addWidget(ebox)
        lbox = QGroupBox("WARSTWY")
        llay = QVBoxLayout()
        self.list_w = QListWidget()
        self.list_w.itemClicked.connect(self.select_layer)
        llay.addWidget(self.list_w)

        h_lbtn = QHBoxLayout()
        btn_f = QPushButton("DODAJ PLIK")
        btn_f.clicked.connect(self.load_scan)
        btn_n = QPushButton("NOWA WARSTWA")
        btn_n.clicked.connect(self.new_live_layer)
        h_lbtn.addWidget(btn_f)
        h_lbtn.addWidget(btn_n)
        llay.addLayout(h_lbtn)

        self.combo_post = QComboBox()
        self.combo_post.addItems([
            "Rownanie scian",
            "Analiza krzyzowa",
            "Rekonstrukcja piramidalna",
            "Czolganie"
        ])
        self.combo_post.setStyleSheet("background-color: #2D2D2D; color: white; padding: 5px;")
        llay.addWidget(self.combo_post)

        btn_apply = QPushButton("POST-FX")
        btn_apply.clicked.connect(self.apply_selected_post_process)
        btn_apply.setStyleSheet("background-color: #4B0082; color: white; font-weight: bold; height: 30px;")
        llay.addWidget(btn_apply)


        lbox_trans = QGroupBox("")
        tlay = QVBoxLayout()
        grid_main = QGridLayout()
        btn_fwd = QPushButton("▲")
        btn_back = QPushButton("▼")
        btn_left = QPushButton("◀")
        btn_right = QPushButton("▶")
        btn_up = QPushButton("+Z")
        btn_down = QPushButton("-Z")
        btn_rotl = QPushButton("ROT ◀")
        btn_rotr = QPushButton("ROT ▶")

        btn_fwd.clicked.connect(lambda: self.move_layer(0, 5, 0))
        btn_back.clicked.connect(lambda: self.move_layer(0, -5, 0))
        btn_left.clicked.connect(lambda: self.move_layer(-5, 0, 0))
        btn_right.clicked.connect(lambda: self.move_layer(5, 0, 0))
        btn_up.clicked.connect(lambda: self.move_layer(0, 0, 5))
        btn_down.clicked.connect(lambda: self.move_layer(0, 0, -5))
        btn_rotl.clicked.connect(lambda: self.rotate_layer(-5))
        btn_rotr.clicked.connect(lambda: self.rotate_layer(5))

        grid_main.addWidget(btn_rotl, 0, 0)
        grid_main.addWidget(btn_fwd, 0, 1)
        grid_main.addWidget(btn_rotr, 0, 2)
        grid_main.addWidget(btn_left, 1, 0)
        grid_main.addWidget(btn_right, 1, 2)
        grid_main.addWidget(btn_up, 2, 0)
        grid_main.addWidget(btn_back, 2, 1)
        grid_main.addWidget(btn_down, 2, 2)

        tlay.addLayout(grid_main)
        lbox_trans.setLayout(tlay)
        llay.addWidget(lbox_trans)
        self.btn_color = QPushButton("KOLOR WARSTWY")
        self.btn_color.clicked.connect(self.open_color_picker)
        self.btn_color.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; height: 30px;")
        llay.addWidget(self.btn_color)

        h_manage = QHBoxLayout()
        btn_clr = QPushButton("WYCZYŚĆ")
        btn_clr.clicked.connect(self.clear_layer)
        btn_del = QPushButton("USUŃ WARSTWĘ")
        btn_del.clicked.connect(self.delete_layer)
        btn_del.setStyleSheet("background-color: #8B0000; color: white;")
        h_manage.addWidget(btn_clr)
        h_manage.addWidget(btn_del)
        llay.addLayout(h_manage)

        lbox.setLayout(llay)
        self.ctrl_lay.addWidget(lbox)
        btn_sav = QPushButton("ZAPISZ JAKO...")
        btn_sav.clicked.connect(self.save_as_dialog)
        btn_sav.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; height: 35px;")
        llay.addWidget(btn_sav)

        log_box = QGroupBox("KONSOLA")
        log_lay = QVBoxLayout()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.cmd_line = QLineEdit()
        self.cmd_line.setPlaceholderText("Wpisz komende...")
        self.cmd_line.returnPressed.connect(self.send_from_line)
        log_lay.addWidget(self.log)
        log_lay.addWidget(self.cmd_line)
        log_box.setLayout(log_lay)
        self.ctrl_lay.addWidget(log_box)


        self.serial_thread.new_point.connect(self.update_live)
        self.serial_thread.log_signal.connect(self.log.append)
        self.serial_thread.start()

        self.refresh_ports()
        self.current_live_name = "Skan_1"
        self.add_layer(self.current_live_name, (1, 1, 1, 1))

    def create_combo_row(self, lay, lbl, items, cmd):
        h = QHBoxLayout()
        h.addWidget(QLabel(lbl))
        cb = QComboBox()
        cb.addItems(items)
        cb.currentTextChanged.connect(lambda val: self.serial_thread.send(f"{cmd}:{val}"))
        h.addWidget(cb)
        lay.addLayout(h)
        return cb

    def update_move_step(self, val):
        self.move_step = float(val)

    def save_as_dialog(self):
        all_points = []
        for name, data in self.scans.items():
            if len(data['pts']) > 0:
                ang = math.radians(data['rot'])
                rmat = np.array([
                    [math.cos(ang), -math.sin(ang), 0],
                    [math.sin(ang), math.cos(ang), 0],
                    [0, 0, 1]
                ])
                transformed = np.dot(data['pts'], rmat.T) + np.array(data['off'])
                all_points.extend(transformed)
        if not all_points:
            self.log.append("Blad, brak danych zapisu!")
            return
        all_points = np.array(all_points)
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Zapisz jako", "skan_lidar",
            "RadAR (*.rr);; Numpy (*.npy);; OBJ (*.obj);; CSV (*.csv);; PNG (*.png)"
        )
        if path:
            if ".npy" in selected_filter:
                np.save(path, all_points)
            elif ".rr" in selected_filter:
                self.save_to_radAr(path, all_points)
            elif ".csv" in selected_filter:
                self.save_to_csv(path, all_points)
            elif ".obj" in selected_filter:
                self.save_to_obj(path, np.array(all_points))
            elif ".png" in selected_filter:
                self.save_to_image(path)

    def save_to_csv(self, path, points):
        try:
            np.savetxt(path, points, delimiter=',', header='X,Y,Z', comments='')
            self.log.append(f"Zapisano CSV: {path}")
        except Exception as e:
            self.log.append(f"Blad zapisu: {e}")

    def save_to_radAr(self, path, points):
        try:
            pts = np.array(points, dtype=np.float32)
            if pts.size == 0:
                self.log.append("Blad, brak punktow")
                return
            pts = pts[~np.all(pts == 0, axis=1)]
            if not path.lower().endswith('.rr'):
                path += '.rr'
            with open(path, 'w', encoding='utf-8') as f:
                for p in pts:
                    f.write(f"{p[0]:.4f},{p[1]:.4f},{p[2]:.4f}\n")
            self.log.append(f"RadAR zapisany {os.path.basename(path)}")
        except Exception as e:
            self.log.append(f"Blad zapisu: {e}")

    def save_to_image(self, path):
        try:
            img = self.view.readQImage()
            img.save(path, "PNG")
            self.log.append(f"Zapisano PNG: {path}")
        except Exception as e:
            self.log.append(f"Blad zapisu: {e}")

    def save_to_obj(self, path, points):
        # Jesli to czytasz, wiedz ze zmarnowalem przy tym wiele godzin. Nie probuj tego naprawiac,
        # zostaw to jak lezy. Z poczatku wiedzialem co dzieje sie w tym kodzie, teraz tego nie wie juz nikt.
        # Nie daj sie wciagnac w naprawianie warstw tych siatek, zwariujesz.
        # JN
        try:
            pts = np.array(points, dtype=np.float32)
            if pts.size == 0:
                self.log.append("Blad brak punktow")
                return
            pts = pts[~np.all(pts == 0, axis=1)]
            centroid = np.mean(pts, axis=0)
            pts = pts - centroid
            max_bound = np.max(np.abs(pts))
            if max_bound > 0:
                scale_factor = 100.0 / max_bound
                pts = pts * scale_factor
            with open(path, 'w', encoding='utf-8') as f:
                f.write("# OBJ Fixed Export\n")
                f.write("g LidarScan\n")
                for p in pts:
                    f.write(f"v {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n")
                f.write("vn 0.0 1.0 0.0\n")
                f.write("\n# Faces\n")
                max_dist = 5.0
                for i in range(len(pts) - 2):
                    p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2]
                    d1 = np.linalg.norm(p1 - p2)
                    d2 = np.linalg.norm(p2 - p3)
                    if d1 < max_dist and d2 < max_dist:
                        f.write(f"f {i + 1}//1 {i + 2}//1 {i + 3}//1\n")

            self.log.append(f"Model OBJ wygenerowany w {path}")
        except Exception as e:
            self.log.append(f"Blad generowania OBJ {e}")

    def move_layer(self, dx, dy, dz):
        it = self.list_w.currentItem()
        if it:
            name = it.text()
            s = self.scans[name]
            s['off'][0] += dx
            s['off'][1] += dy
            s['off'][2] += dz
            self.refresh_view(name)

    def rotate_layer(self, dr):
        it = self.list_w.currentItem()
        if it:
            name = it.text()
            s = self.scans[name]
            s['rot'] = (s['rot'] + dr) % 360
            self.refresh_view(name)

    def open_color_picker(self):
        it = self.list_w.currentItem()
        name = it.text()
        s = self.scans[name]
        r, g, b = int(s['col'][0] * 255), int(s['col'][1] * 255), int(s['col'][2] * 255)
        current_qcolor = QColor(r, g, b)
        color = QColorDialog.getColor(current_qcolor, self, "Wybierz kolor warstwy")
        if color.isValid():
            r, g, b, _ = color.getRgbF()
            s['col'] = [r, g, b, 1]
            s['item'].setData(color=(r, g, b, 1))
            self.btn_color.setStyleSheet(f"background-color: {color.name()};")

    def apply_selected_post_process(self):
        index = self.combo_post.currentIndex()
        self.log.append(f"Uruchamiam:  {self.combo_post.currentText()}")

        if index == 0:
            self.post_process_layer_1()
        elif index == 1:
            self.post_process_layer_2()
        elif index == 2:
            self.post_process_layer_3()
        elif index == 3:
            self.post_process_layer_4()

    def send_from_line(self):
        cmd = self.cmd_line.text()
        if cmd:
            self.serial_thread.send(cmd)
            self.log.append(f"> {cmd}")
            self.cmd_line.clear()

    def post_process_layer_1(self):
        it = self.list_w.currentItem()
        if not it: return
        name = it.text()
        s = self.scans[name]
        pts = s['pts'].copy()

        if len(pts) < 10: return
        self.log.append(f"[POST-FX] Rozpoczynam rownanie scian {name}...")
        def get_dominant_coords(data, tolerance=20.0):
            hist, bins = np.histogram(data, bins=100)
            peaks = bins[np.where(hist > np.mean(hist) * 1.2)]
            return peaks

        dom_x = get_dominant_coords(pts[:, 0])
        dom_y = get_dominant_coords(pts[:, 1])

        for i in range(len(pts)):
            for target_x in dom_x:
                if abs(pts[i, 0] - target_x) < 25.0:
                    pts[i, 0] = pts[i, 0] * 0.2 + target_x * 0.8
                    break
            for target_y in dom_y:
                if abs(pts[i, 1] - target_y) < 25.0:
                    pts[i, 1] = pts[i, 1] * 0.2 + target_y * 0.8
                    break
        for i in range(2, len(pts) - 2):
            pts[i, 0] = np.mean(pts[i - 2:i + 2, 0])
            pts[i, 1] = np.mean(pts[i - 2:i + 2, 1])
        s['pts'] = pts
        self.refresh_view(name)
        self.log.append("[POST-FX] Rownanie scian zakonczone.")

    def post_process_layer_2(self):
        it = self.list_w.currentItem()
        if not it: return
        name = it.text()
        s = self.scans[name]
        pts = s['pts'].copy()

        num_pts = len(pts)
        if num_pts < 100: return
        self.log.append(f"[POST-FX] Rozpoczynam analize krzyzowa {name}...")
        points_per_layer = 180
        new_pts = pts.copy()
        PROG_KATA = 12.0

        for i in range(num_pts):
            idx_mid = i
            idx_l = max(0, i - 1)
            idx_r = min(num_pts - 1, i + 1)
            idx_up = max(0, i - points_per_layer)
            idx_dn = min(num_pts - 1, i + points_per_layer)
            neighbors_idx = [idx_l, idx_r, idx_up, idx_dn]
            valid_neighbors = []
            for n_idx in neighbors_idx:
                dist = np.linalg.norm(pts[idx_mid] - pts[n_idx])
                if dist < PROG_KATA:
                    valid_neighbors.append(pts[n_idx])
            if len(valid_neighbors) >= 2:
                cluster = np.array(valid_neighbors + [pts[idx_mid]])
                avg_pos = np.mean(cluster, axis=0)
                new_pts[i, 0] = avg_pos[0]
                new_pts[i, 1] = avg_pos[1]
                if abs(pts[idx_mid, 2] - avg_pos[2]) < 3.0:
                    new_pts[i, 2] = avg_pos[2]
            else:
                new_pts[i] = pts[i]
        for i in range(1, len(new_pts) - 1):
            if np.linalg.norm(new_pts[i] - new_pts[i - 1]) < 5.0:
                new_pts[i, :2] = np.mean(new_pts[i - 1:i + 2, :2], axis=0)

        s['pts'] = new_pts
        self.refresh_view(name)
        self.log.append("[POST-FX] Analiza krzyzowa zakonczona.")

    def post_process_layer_3(self):
        it = self.list_w.currentItem()
        if not it: return
        name = it.text()
        s = self.scans[name]
        pts = s['pts'].copy()

        num_pts = len(pts)
        if num_pts < 500: return
        self.log.append(f"[POST-FX] Rozpoczynam rekonstrukcje piramidalna... ")
        STEP = 180
        new_pts = pts.copy()

        def get_neighbors(idx, radius):
            n_list = []
            for r in range(1, radius + 1):
                offsets = [-r, r, -r * STEP, r * STEP]
                for off in offsets:
                    if 0 <= idx + off < num_pts:
                        if np.linalg.norm(pts[idx] - pts[idx + off]) < 40.0:
                            n_list.append(pts[idx + off])
            return np.array(n_list)
        self.log.append("> stabilizacja punktowa")
        for i in range(num_pts):
            nb = get_neighbors(i, 1)
            if len(nb) > 0:
                new_pts[i, :2] = (new_pts[i, :2] * 0.5) + (np.mean(nb, axis=0)[:2] * 0.5)
        self.log.append("> grupowanie")
        temp_pts = new_pts.copy()
        for i in range(0, num_pts, 2):
            nb = get_neighbors(i, 4)
            if len(nb) > 5:
                centroid = np.mean(nb, axis=0)
                if np.linalg.norm(new_pts[i] - centroid) < 15.0:
                    temp_pts[i, :2] = centroid[:2]
        self.log.append("> prostowanie")
        for i in range(num_pts):
            nb_long = get_neighbors(i, 8)
            if len(nb_long) > 10:
                std_x = np.std(nb_long[:, 0])
                std_y = np.std(nb_long[:, 1])

                if std_x < 6.0:
                    temp_pts[i, 0] = np.median(nb_long[:, 0])
                if std_y < 6.0:
                    temp_pts[i, 1] = np.median(nb_long[:, 1])
        s['pts'] = temp_pts
        self.refresh_view(name)
        self.log.append("[POST-FX] Rekonstrukcja piramidalna zakonczona.")

    def post_process_layer_4(self):
        it = self.list_w.currentItem()
        if not it: return
        name = it.text()
        s = self.scans[name]
        pts = s['pts'].copy()

        num_pts = len(pts)
        if num_pts < 500: return
        self.log.append(f"[POST-FX] Rozpoczynam czolganie {name}...")
        STEP = 180
        new_pts = pts.copy()
        SEARCH_DIST = 20.0
        DETAIL_THRESH = 10.0
        ITERATIONS = 3

        for iteration in range(ITERATIONS):
            self.log.append(f"> przebieg {iteration + 1}...")
            current_pass = new_pts.copy()

            for i in range(0, num_pts):
                p = new_pts[i]
                idx_start = max(0, i - 400)
                idx_end = min(num_pts, i + 400)
                potential_neighbors = new_pts[idx_start:idx_end]

                diffs = potential_neighbors - p
                dists = np.linalg.norm(diffs, axis=1)

                mask = dists < SEARCH_DIST
                valid_neighbors = potential_neighbors[mask]
                valid_dists = dists[mask]

                if len(valid_neighbors) > 3:
                    weights = np.exp(-valid_dists ** 2 / (2 * (SEARCH_DIST / 2) ** 2))
                    for j in range(len(valid_neighbors)):
                        if valid_dists[j] > DETAIL_THRESH:
                            weights[j] *= 0.1
                    if np.sum(weights) > 0:
                        weighted_avg = np.average(valid_neighbors, axis=0, weights=weights)
                        current_pass[i, :2] = p[:2] * 0.5 + weighted_avg[:2] * 0.5
            new_pts = current_pass
        for i in range(1, num_pts):
            if abs(new_pts[i, 0] - new_pts[i - 1, 0]) < 2.0:
                new_pts[i, 0] = new_pts[i - 1, 0]
            if abs(new_pts[i, 1] - new_pts[i - 1, 1]) < 2.0:
                new_pts[i, 1] = new_pts[i - 1, 1]
        s['pts'] = new_pts
        self.refresh_view(name)
        self.log.append("[POST-FX] Czolganie zakonczone.")

    def refresh_view(self, name):
        s = self.scans[name]
        if len(s['pts']) > 0:
            ang = math.radians(s['rot'])
            rmat = np.array([
                [math.cos(ang), -math.sin(ang), 0],
                [math.sin(ang), math.cos(ang), 0],
                [0, 0, 1]
            ])
            trans = np.dot(s['pts'], rmat.T) + np.array(s['off'])
            s['item'].setData(pos=trans)

    def refresh_ports(self):
        self.cb_ports.clear()
        self.cb_ports.addItems([p.device for p in serial.tools.list_ports.comports()])

    def handle_connect(self):
        port = self.cb_ports.currentText()
        if port and self.serial_thread.connect_serial(port):
            self.log.append(f"Polaczono z {port}")

    def create_input_row(self, lay, lbl, cmd):
        h = QHBoxLayout();
        h.addWidget(QLabel(lbl));
        e = QLineEdit();
        b = QPushButton("Set")
        b.clicked.connect(lambda: self.serial_thread.send(f"{cmd}:{e.text()}"))
        h.addWidget(e);
        h.addWidget(b);
        lay.addLayout(h)

    def create_slider(self, lay):
        s = QSlider(Qt.Horizontal)
        s.setRange(0, 255)
        s.setValue(255)
        s.valueChanged.connect(self.update_style)
        lay.addWidget(s)
        return s

    def add_layer(self, name, color):
        base_name = name
        counter = 1
        while name in self.scans:
            name = f"{base_name} ({counter})"
            counter += 1
        scat = gl.GLScatterPlotItem(pos=np.empty((0, 3)), color=color, size=3)
        self.view.addItem(scat)
        self.scans[name] = {
            'pts': np.empty((0, 3)),
            'item': scat,
            'col': list(color),
            'off': [0, 0, 0],
            'rot': 0.0
        }
        self.list_w.addItem(name)
        last_item = self.list_w.item(self.list_w.count() - 1)
        self.list_w.setCurrentItem(last_item)
        self.current_live_name = name

    def new_live_layer(self):
        self.current_live_name = f"Skan_{self.list_w.count() + 1}"
        self.add_layer(self.current_live_name, (1, 1, 1, 1))

    def update_live(self, x, y, z):
        if self.current_live_name in self.scans:
            s = self.scans[self.current_live_name]
            s['pts'] = np.append(s['pts'], [[x, y, z]], axis=0)
            if len(s['pts']) % 5 == 0: self.refresh_view(self.current_live_name)

    def select_layer(self, item):
        name = item.text()
        s = self.scans[name]
        self.current_live_name = name
        r, g, b = int(s['col'][0] * 255), int(s['col'][1] * 255), int(s['col'][2] * 255)
        self.btn_color.setStyleSheet(f"background-color: rgb({r},{g},{b});")

    def update_style(self):
        it = self.list_w.currentItem()
        if it:
            n = it.text()
            r, g, b = self.sr.value() / 255, self.sg.value() / 255, self.sb.value() / 255
            self.scans[n]['col'] = [r, g, b, 1]
            self.scans[n]['item'].setData(color=(r, g, b, 1))

    def refresh_view(self, name):
        s = self.scans[name]
        if len(s['pts']) > 0:
            ang = math.radians(s['rot'])
            rmat = np.array([[math.cos(ang), -math.sin(ang), 0], [math.sin(ang), math.cos(ang), 0], [0, 0, 1]])
            trans = np.dot(s['pts'], rmat.T) + np.array(s['off'])
            s['item'].setData(pos=trans)

    def clear_layer(self):
        it = self.list_w.currentItem()
        if it:
            n = it.text()
            self.scans[n]['pts'] = np.empty((0, 3))
            self.scans[n]['item'].setData(pos=np.empty((0, 3)))

    def delete_layer(self):
        it = self.list_w.currentItem()
        if it and self.list_w.count() > 1:
            name = it.text()
            self.view.removeItem(self.scans[name]['item'])
            del self.scans[name]
            self.list_w.takeItem(self.list_w.row(it))
            self.current_live_name = self.list_w.item(0).text()
            self.list_w.setCurrentRow(0)

    def load_scan(self):
        f, _ = QFileDialog.getOpenFileName(self, "Otworz skan", "", "Lidar Files (*.npy *.rr)")

        if f:
            file_name = os.path.basename(f)
            try:
                if f.lower().endswith('.rr'):
                    points = []
                    with open(f, 'r', encoding='utf-8') as file:
                        for line in file:
                            line = line.strip()
                            if line:
                                coords = [float(x) for x in line.split(',')]
                                if len(coords) == 3:
                                    points.append(coords)
                    pts = np.array(points, dtype=np.float32)
                    self.log.append(f"Zaladowano format .rr: {file_name}")

                else:
                    pts = np.load(f)
                    self.log.append(f"Zaladowano format .npy: {file_name}")

                if pts.size > 0:
                    self.add_layer(file_name, (1, 1, 1, 1))
                    actual_name = self.list_w.currentItem().text()
                    self.scans[actual_name]['pts'] = pts
                    self.refresh_view(actual_name)
                else:
                    self.log.append("Ostrzeżenie: Plik jest pusty.")

            except Exception as e:
                self.log.append(f"Blad ladowania: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LidarGui()
    win.show()
    sys.exit(app.exec_())
