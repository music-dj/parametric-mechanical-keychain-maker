import sys
import os
import subprocess
import json
import tempfile
import struct
import zipfile
import shutil
import base64
import webbrowser

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox, 
    QPushButton, QLabel, QGroupBox, QTabWidget, QSplitter, 
    QFileDialog, QMessageBox, QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor, QPixmap

# --- Constants & Default Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCAD_FILE = os.path.join(SCRIPT_DIR, "template.scad")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "keychain_config.json")

DEFAULT_OPENSCAD_PATHS = [
    r"D:\program files\openscad-2021.01\openscad.exe",
    r"C:\Program Files\OpenSCAD\openscad.exe",
    r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
]

COLOR_MAP = {
    "Verde (Green)": "Verde", "Beige": "Beige", "Blanco (White)": "Blanco",
    "Negro (Black)": "Negro", "Rojo (Red)": "Rojo", "Azul (Blue)": "Azul",
    "Azul Claro (Light Blue)": "Azul Claro", "Azul Oscuro (Dark Blue)": "Azul Oscuro",
    "Amarillo (Yellow)": "Amarillo", "Naranja (Orange)": "Naranja",
    "Gris (Gray)": "Gris", "Marrón (Brown)": "Marrón", "Morado (Purple)": "Morado",
    "Rosa (Pink)": "Rosa", "Turquesa (Turquoise)": "Turquesa",
    "Verde Claro (Light Green)": "Verde Claro", "Verde Oscuro (Dark Green)": "Verde Oscuro"
}

COLOR_RGB_MAP = {
    "Verde": (46, 125, 50), "Beige": (245, 245, 220), "Blanco": (255, 255, 255),
    "Negro": (38, 38, 38), "Rojo": (211, 47, 47), "Azul": (25, 118, 210),
    "Azul Claro": (79, 195, 247), "Azul Oscuro": (13, 71, 161),
    "Amarillo": (251, 192, 45), "Naranja": (245, 124, 0),
    "Gris": (117, 117, 117), "Marrón": (121, 85, 72), "Morado": (123, 31, 162),
    "Rosa": (233, 30, 99), "Turquesa": (0, 188, 212),
    "Verde Claro": (139, 195, 74), "Verde Oscuro": (27, 94, 32)
}

COLOR_HEX_MAP = {k: f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}" for k, rgb in COLOR_RGB_MAP.items()}

FONT_MAP = {
    "Impact": "Impact", "Arial Black": "Arial Black", "Arial Bold": "Arial:style=Bold",
    "Tahoma Bold": "Tahoma:style=Bold", "Verdana Bold": "Verdana:style=Bold",
    "Courier New Bold": "Courier New:style=Bold", "Bungee": "Bungee",
    "Archivo Black": "Archivo Black", "Bangers": "Bangers",
    "Changa One": "Changa One", "Bebas Neue": "Bebas Neue", "Poppins Black": "Poppins Black"
}

# --- STL Parser (Binary & ASCII) ---
def parse_stl(filepath):
    if not os.path.exists(filepath): return [], []
    with open(filepath, 'rb') as f:
        head = f.read(5)
        f.seek(0)
        if head == b'solid':
            try:
                lines = f.read().decode('utf-8', errors='ignore').splitlines()
                if any('facet normal' in line for line in lines[:20]):
                    return _parse_stl_ascii(lines)
            except Exception: f.seek(0)
        return _parse_stl_binary(f)

def _parse_stl_binary(f):
    f.seek(80)
    count_data = f.read(4)
    if len(count_data) < 4: return [], []
    num_triangles = struct.unpack('<I', count_data)[0]
    vertices, triangles, v_map = [], [], {}
    for _ in range(num_triangles):
        data = f.read(50)
        if len(data) < 50: break
        v = struct.unpack('<9f', data[12:48])
        tri_idx = []
        for i in range(3):
            pt = (round(v[i*3], 4), round(v[i*3+1], 4), round(v[i*3+2], 4))
            idx = v_map.get(pt)
            if idx is None:
                idx = len(vertices)
                v_map[pt] = idx
                vertices.append(pt)
            tri_idx.append(idx)
        triangles.append(tri_idx)
    return vertices, triangles

def _parse_stl_ascii(lines):
    vertices, triangles, v_map, current_tri = [], [], {}, []
    for line in lines:
        parts = line.strip().split()
        if parts and parts[0] == 'vertex':
            pt = (round(float(parts[1]), 4), round(float(parts[2]), 4), round(float(parts[3]), 4))
            idx = v_map.get(pt)
            if idx is None:
                idx = len(vertices)
                v_map[pt] = idx
                vertices.append(pt)
            current_tri.append(idx)
            if len(current_tri) == 3:
                triangles.append(current_tri)
                current_tri = []
    return vertices, triangles

def build_multicolor_3mf(base_v, base_t, text_v, text_t, base_hex, text_hex, output_path):
    model_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">',
        '  <metadata name="Title">Multi-Color Mechanical Keychain</metadata>',
        '  <resources>',
        '    <m:colorgroup id="1">',
        f'      <m:color color="{base_hex}FF"/>',
        f'      <m:color color="{text_hex}FF"/>',
        '    </m:colorgroup>',
        '    <object id="2" type="model" name="Base" pid="1" pindex="0">',
        '      <mesh>',
        '        <vertices>'
    ]
    for x, y, z in base_v: model_xml.append(f'          <vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>')
    model_xml.extend(['        </vertices>', '        <triangles>'])
    for v1, v2, v3 in base_t: model_xml.append(f'          <triangle v1="{v1}" v2="{v2}" v3="{v3}" pid="1" p1="0"/>')
    model_xml.extend(['        </triangles>', '      </mesh>', '    </object>'])

    if text_v and text_t:
        model_xml.extend(['    <object id="3" type="model" name="Letters" pid="1" pindex="1">', '      <mesh>', '        <vertices>'])
        for x, y, z in text_v: model_xml.append(f'          <vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>')
        model_xml.extend(['        </vertices>', '        <triangles>'])
        for v1, v2, v3 in text_t: model_xml.append(f'          <triangle v1="{v1}" v2="{v2}" v3="{v3}" pid="1" p1="1"/>')
        model_xml.extend(['        </triangles>', '      </mesh>', '    </object>',
                          '    <object id="4" type="model" name="Keychain_Assembly">',
                          '      <components>', '        <component objectid="2"/>', '        <component objectid="3"/>', '      </components>',
                          '    </object>', '  </resources>', '  <build>', '    <item objectid="4"/>', '  </build>', '</model>'])
    else:
        model_xml.extend(['  </resources>', '  <build>', '    <item objectid="2"/>', '  </build>', '</model>'])

    content_types = '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n</Types>'
    rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>'
    bambu_config = """<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <object id="4">\n    <metadata key="name" value="Keychain_Assembly"/>\n    <part id="2" name="Base">\n      <metadata key="extruder" value="1"/>\n    </part>\n    <part id="3" name="Letters">\n      <metadata key="extruder" value="2"/>\n    </part>\n  </object>\n</config>"""
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('3D/3dmodel.model', '\n'.join(model_xml))
        z.writestr('Metadata/model_settings.config', bambu_config)


# --- Workers ---
class RenderWorker(QThread):
    finished = pyqtSignal(str, str, str)
    def __init__(self, cmd_iso, cmd_top, img_iso, img_top):
        super().__init__()
        self.cmd_iso, self.cmd_top, self.img_iso, self.img_top = cmd_iso, cmd_top, img_iso, img_top
    def run(self):
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(self.cmd_iso, capture_output=True, startupinfo=startupinfo)
            subprocess.run(self.cmd_top, capture_output=True, startupinfo=startupinfo)
            self.finished.emit(self.img_iso, self.img_top, "")
        except Exception as e:
            self.finished.emit("", "", str(e))

class SaveWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, target):
        super().__init__()
        self.target = target
    def run(self):
        try:
            self.target()
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))

class BrowserViewerWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, cmd_b, cmd_t, b_tmp, t_tmp, bc, tc):
        super().__init__()
        self.cmd_b, self.cmd_t, self.b_tmp, self.t_tmp, self.bc, self.tc = cmd_b, cmd_t, b_tmp, t_tmp, bc, tc
    def run(self):
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(self.cmd_b, capture_output=True, startupinfo=startupinfo)
            subprocess.run(self.cmd_t, capture_output=True, startupinfo=startupinfo)
            
            with open(self.b_tmp, "rb") as f: b_b64 = base64.b64encode(f.read()).decode('utf-8')
            t_b64 = ""
            if os.path.exists(self.t_tmp):
                with open(self.t_tmp, "rb") as f: t_b64 = base64.b64encode(f.read()).decode('utf-8')

            html_code = f"""<!DOCTYPE html>
<html>
<head>
    <title>3D Viewer</title>
    <style>body {{ margin: 0; overflow: hidden; background: #222; font-family: sans-serif; }}
    #info {{ position: absolute; top: 10px; width: 100%; text-align: center; color: white; pointer-events: none; }}
    </style>
</head>
<body>
    <div id="info">Drag to rotate | Scroll to zoom | Right-click to pan</div>
    <script src='https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js'></script>
    <script src='https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js'></script>
    <script src='https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js'></script>
    <script>

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 1000);
        camera.position.set(0, -50, 50);

        const renderer = new THREE.WebGLRenderer({{antialias: true}});
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.autoRotate = true;
        controls.autoRotateSpeed = 2.0;
        
        scene.add(new THREE.AmbientLight(0xffffff, 0.6));
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(1, 1, 2);
        scene.add(dirLight);

        const loader = new THREE.STLLoader();

        function loadBase64STL(b64, colorHex) {{
            if (!b64) return;
            const binaryString = window.atob(b64);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) bytes[i] = binaryString.charCodeAt(i);
            const geometry = loader.parse(bytes.buffer);
            geometry.computeVertexNormals();
            const material = new THREE.MeshStandardMaterial({{color: colorHex, roughness: 0.4, metalness: 0.1}});
            const mesh = new THREE.Mesh(geometry, material);
            scene.add(mesh);
        }}

        loadBase64STL("{b_b64}", "{self.bc}");
        loadBase64STL("{t_b64}", "{self.tc}");

        function animate() {{
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }}
        animate();
        
        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
    </script>
</body>
</html>"""
            html_path = os.path.join(tempfile.gettempdir(), "viewer.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_code)
            
            webbrowser.open("file://" + html_path)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


# --- Main App ---
class KeychainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parametric Mechanical Keychain Maker (Modern 2D/3D)")
        self.resize(1100, 800)
        self.apply_dark_theme()
        
        self.openscad_path = self.locate_openscad()
        
        self.setup_ui()
        self.update_dimensions()
        
        if os.path.exists(self.openscad_path) and os.path.exists(SCAD_FILE):
            self.update_previews()

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(palette)
        self.setStyleSheet("""
            QTabBar::tab { background: #333; color: white; padding: 10px; margin: 2px; }
            QTabBar::tab:selected { background: #555; }
            QGroupBox { border: 1px solid #555; margin-top: 10px; padding-top: 15px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)

    def locate_openscad(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f).get("openscad_path", "openscad.exe")
            except: pass
        if shutil.which("openscad"): return shutil.which("openscad")
        for c in DEFAULT_OPENSCAD_PATHS:
            if os.path.exists(c): return c
        return "openscad.exe"

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        tabs = QTabWidget()
        left_layout.addWidget(tabs)
        
        # Tab 1: Typography
        tab1 = QWidget()
        form1 = QFormLayout(tab1)
        self.name_input = QLineEdit("ALBERTO")
        self.name_input.textChanged.connect(self.update_dimensions)
        form1.addRow("Text:", self.name_input)
        self.uppercase_check = QCheckBox("Force UPPERCASE")
        self.uppercase_check.setChecked(True)
        form1.addRow("", self.uppercase_check)
        self.font_combo = QComboBox()
        self.font_combo.addItems(list(FONT_MAP.keys()))
        form1.addRow("Font Style:", self.font_combo)
        self.font_size_spin = QDoubleSpinBox()
        self.font_size_spin.setRange(6.0, 16.0)
        self.font_size_spin.setValue(10.0)
        form1.addRow("Font Size (mm):", self.font_size_spin)
        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(-5.0, 5.0)
        self.thickness_spin.setValue(1.0)
        form1.addRow("Relief Depth:", self.thickness_spin)
        tabs.addTab(tab1, "Typography")
        
        # Tab 2: Colors
        tab2 = QWidget()
        form2 = QFormLayout(tab2)
        self.loop_check = QCheckBox("Include keyring hole")
        self.loop_check.setChecked(True)
        self.loop_check.toggled.connect(self.update_dimensions)
        form2.addRow("", self.loop_check)
        self.base_color_combo = QComboBox()
        self.base_color_combo.addItems(list(COLOR_MAP.keys()))
        form2.addRow("Base Color:", self.base_color_combo)
        self.text_color_combo = QComboBox()
        self.text_color_combo.addItems(list(COLOR_MAP.keys()))
        self.text_color_combo.setCurrentText("Beige")
        form2.addRow("Letters Color:", self.text_color_combo)
        tabs.addTab(tab2, "Colors & Links")
        
        # Tab 3: Dimensions
        tab3 = QWidget()
        form3 = QFormLayout(tab3)
        self.alto_spin = QDoubleSpinBox()
        self.alto_spin.setRange(4.0, 14.0)
        self.alto_spin.setValue(6.0)
        self.alto_spin.valueChanged.connect(self.update_dimensions)
        form3.addRow("Thickness (Alto):", self.alto_spin)
        self.ancho_spin = QDoubleSpinBox()
        self.ancho_spin.setRange(8.0, 25.0)
        self.ancho_spin.setValue(12.0)
        self.ancho_spin.valueChanged.connect(self.update_dimensions)
        form3.addRow("Width (Ancho):", self.ancho_spin)
        self.largo_spin = QDoubleSpinBox()
        self.largo_spin.setRange(10.0, 30.0)
        self.largo_spin.setValue(15.0)
        self.largo_spin.valueChanged.connect(self.update_dimensions)
        form3.addRow("Link Length (Largo):", self.largo_spin)
        self.openscad_input = QLineEdit(self.openscad_path)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_scad)
        osc_box = QHBoxLayout()
        osc_box.addWidget(self.openscad_input)
        osc_box.addWidget(browse_btn)
        form3.addRow("OpenSCAD:", osc_box)
        tabs.addTab(tab3, "Dimensions & Path")
        
        # Info Box
        self.info_label = QLabel("Dimensions: ...")
        self.info_label.setStyleSheet("font-weight: bold; padding: 10px; background: #333; border-radius: 5px;")
        left_layout.addWidget(self.info_label)
        
        # Buttons
        self.btn_update = QPushButton("🔄 Generate Previews (Images)")
        self.btn_update.setStyleSheet("background-color: #0078D7; color: white; padding: 8px; font-weight: bold; margin-top: 10px;")
        self.btn_update.clicked.connect(self.update_previews)
        left_layout.addWidget(self.btn_update)
        
        self.btn_browser = QPushButton("🌐 View 3D in Browser (External)")
        self.btn_browser.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;")
        self.btn_browser.clicked.connect(self.view_in_browser)
        left_layout.addWidget(self.btn_browser)
        
        btn_layout = QHBoxLayout()
        self.btn_3mf = QPushButton("🎨 Save 3MF (Multi-Color)")
        self.btn_3mf.clicked.connect(self.save_3mf)
        self.btn_stl = QPushButton("💾 Save STL")
        self.btn_stl.clicked.connect(self.save_stl)
        btn_layout.addWidget(self.btn_3mf)
        btn_layout.addWidget(self.btn_stl)
        left_layout.addLayout(btn_layout)
        
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        left_layout.addWidget(self.progress)
        
        self.status = QLabel("Ready")
        left_layout.addWidget(self.status)
        
        # Right Panel (Previews)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        scroll_layout.addWidget(QLabel("<b>Isometric View</b>"))
        self.iso_label = QLabel("No preview generated.")
        self.iso_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.iso_label.setStyleSheet("background: #1e1e1e; border: 1px solid #555;")
        self.iso_label.setMinimumHeight(350)
        scroll_layout.addWidget(self.iso_label)
        
        scroll_layout.addWidget(QLabel("<b>Top View</b>"))
        self.top_label = QLabel("No preview generated.")
        self.top_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.top_label.setStyleSheet("background: #1e1e1e; border: 1px solid #555;")
        self.top_label.setMinimumHeight(350)
        scroll_layout.addWidget(self.top_label)
        
        scroll.setWidget(scroll_content)
        right_layout.addWidget(scroll)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 700])

    def browse_scad(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select OpenSCAD", "", "Executable (*.exe)")
        if path:
            self.openscad_path = path
            self.openscad_input.setText(path)
            with open(CONFIG_FILE, "w") as f: json.dump({"openscad_path": path}, f)

    def get_clean_name(self):
        raw = self.name_input.text().strip()
        if self.uppercase_check.isChecked(): raw = raw.upper()
        return raw if raw else " "

    def update_dimensions(self):
        text = self.get_clean_name()
        n = max(1, len(text))
        largo = self.largo_spin.value()
        ancho = self.ancho_spin.value()
        alto = self.alto_spin.value()
        first_len = largo if self.loop_check.isChecked() else (largo - 2.0)
        total_len = first_len + (n - 1) * (largo + 1.0)
        self.info_label.setText(f"📏 Estimated Print Size:\nTotal Length: ~{total_len:.1f} mm\nWidth: {ancho:.1f} mm | Thickness: {alto:.1f} mm\nLinks: {n}")

    def build_cmd(self, out_file, mode="todo", camera=None, img_size="800,800"):
        name = self.get_clean_name().replace('\\', '\\\\').replace('"', '\\"')
        font = FONT_MAP.get(self.font_combo.currentText(), "Impact")
        
        cmd = [self.openscad_path, "-o", out_file]
        if out_file.endswith(".png"):
            cmd.extend(["--export-format", "png", "--autocenter", "--viewall", "--colorscheme", "Tomorrow Night", "--imgsize", img_size])
            if camera: cmd.extend(["--camera", camera])
        else:
            cmd.extend(["--export-format", "binstl"])

        cmd.extend([
            "-D", f'texto="{name}"',
            "-D", f'fuente_seleccionada="{font}"',
            "-D", f'tamano_letra={self.font_size_spin.value()}',
            "-D", f'altura_letra={self.thickness_spin.value()}',
            "-D", f'eslabon_primer_elemento={"true" if self.loop_check.isChecked() else "false"}',
            "-D", f'color_base="{COLOR_MAP.get(self.base_color_combo.currentText(), "Verde")}"',
            "-D", f'color_letras="{COLOR_MAP.get(self.text_color_combo.currentText(), "Beige")}"',
            "-D", f'alto={self.alto_spin.value()}',
            "-D", f'ancho={self.ancho_spin.value()}',
            "-D", f'largo={self.largo_spin.value()}',
            "-D", f'modo_exportacion="{mode}"',
            SCAD_FILE
        ])
        return cmd

    def set_busy(self, busy, msg=""):
        self.btn_update.setEnabled(not busy)
        self.btn_browser.setEnabled(not busy)
        self.btn_3mf.setEnabled(not busy)
        self.btn_stl.setEnabled(not busy)
        self.status.setText(msg)
        if busy: self.progress.setRange(0, 0)
        else: self.progress.setRange(0, 100); self.progress.setValue(100)

    def update_previews(self):
        self.set_busy(True, "Generating images via OpenSCAD...")
        tmp = tempfile.gettempdir()
        self.img_iso = os.path.join(tmp, "_prev_iso.png")
        self.img_top = os.path.join(tmp, "_prev_top.png")
        
        cmd_iso = self.build_cmd(self.img_iso, mode="todo", camera="0,0,0,55,0,25,0")
        cmd_top = self.build_cmd(self.img_top, mode="todo", camera="0,0,0,0,0,0,0")
        
        self.worker = RenderWorker(cmd_iso, cmd_top, self.img_iso, self.img_top)
        self.worker.finished.connect(self.on_render_done)
        self.worker.start()

    def on_render_done(self, iso_path, top_path, err):
        self.set_busy(False, "Ready")
        if err:
            QMessageBox.critical(self, "Error", err)
            return
        
        if os.path.exists(iso_path):
            pix = QPixmap(iso_path)
            self.iso_label.setPixmap(pix.scaled(self.iso_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        if os.path.exists(top_path):
            pix = QPixmap(top_path)
            self.top_label.setPixmap(pix.scaled(self.top_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def view_in_browser(self):
        self.set_busy(True, "Preparing Browser 3D Viewer...")
        tmp = tempfile.gettempdir()
        b = os.path.join(tmp, "_browser_b.stl")
        t = os.path.join(tmp, "_browser_t.stl")
        
        bc = COLOR_HEX_MAP.get(COLOR_MAP.get(self.base_color_combo.currentText(), "Verde"), "#2E7D32")
        tc = COLOR_HEX_MAP.get(COLOR_MAP.get(self.text_color_combo.currentText(), "Beige"), "#F5F5DC")

        self.browser_worker = BrowserViewerWorker(
            self.build_cmd(b, "base"), self.build_cmd(t, "texto"), b, t, bc, tc
        )
        self.browser_worker.finished.connect(lambda ok, err: self.on_save_done(ok, err, "Opened in browser!"))
        self.browser_worker.start()

    def save_3mf(self):
        out, _ = QFileDialog.getSaveFileName(self, "Save 3MF", f"Keychain_{self.get_clean_name()}.3mf", "3MF Files (*.3mf)")
        if not out: return
        self.set_busy(True, "Generating 3MF...")
        def task():
            tmp = tempfile.gettempdir()
            b = os.path.join(tmp, "_export_b.stl")
            t = os.path.join(tmp, "_export_t.stl")
            subprocess.run(self.build_cmd(b, "base"), capture_output=True, startupinfo=subprocess.STARTUPINFO() if os.name=='nt' else None)
            subprocess.run(self.build_cmd(t, "texto"), capture_output=True, startupinfo=subprocess.STARTUPINFO() if os.name=='nt' else None)
            bv, bt = parse_stl(b)
            tv, tt = parse_stl(t)
            bc = COLOR_HEX_MAP.get(COLOR_MAP.get(self.base_color_combo.currentText(), "Verde"), "#2E7D32")
            tc = COLOR_HEX_MAP.get(COLOR_MAP.get(self.text_color_combo.currentText(), "Beige"), "#F5F5DC")
            build_multicolor_3mf(bv, bt, tv, tt, bc, tc, out)
        self.save_worker = SaveWorker(task)
        self.save_worker.finished.connect(lambda ok, err: self.on_save_done(ok, err, "3MF saved successfully!"))
        self.save_worker.start()

    def save_stl(self):
        out, _ = QFileDialog.getSaveFileName(self, "Save STL", f"Keychain_{self.get_clean_name()}.stl", "STL Files (*.stl)")
        if not out: return
        self.set_busy(True, "Generating STL...")
        def task():
            subprocess.run(self.build_cmd(out, "todo"), capture_output=True, startupinfo=subprocess.STARTUPINFO() if os.name=='nt' else None)
        self.save_worker = SaveWorker(task)
        self.save_worker.finished.connect(lambda ok, err: self.on_save_done(ok, err, "STL saved successfully!"))
        self.save_worker.start()

    def on_save_done(self, ok, err, msg):
        self.set_busy(False, "Ready")
        if not ok: QMessageBox.critical(self, "Error", err)
        else: self.status.setText(msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = KeychainApp()
    window.show()
    sys.exit(app.exec())
