import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import sys
import shutil
import json
import tempfile
import threading
import struct
import zipfile
import cv2
import numpy as np
from PIL import Image, ImageTk

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
    "Verde (Green)": "Verde",
    "Beige": "Beige",
    "Blanco (White)": "Blanco",
    "Negro (Black)": "Negro",
    "Rojo (Red)": "Rojo",
    "Azul (Blue)": "Azul",
    "Azul Claro (Light Blue)": "Azul Claro",
    "Azul Oscuro (Dark Blue)": "Azul Oscuro",
    "Amarillo (Yellow)": "Amarillo",
    "Naranja (Orange)": "Naranja",
    "Gris (Gray)": "Gris",
    "Marrón (Brown)": "Marrón",
    "Morado (Purple)": "Morado",
    "Rosa (Pink)": "Rosa",
    "Turquesa (Turquoise)": "Turquesa",
    "Verde Claro (Light Green)": "Verde Claro",
    "Verde Oscuro (Dark Green)": "Verde Oscuro",
}

COLOR_RGB_MAP = {
    "Verde": (46, 125, 50),
    "Beige": (245, 245, 220),
    "Blanco": (255, 255, 255),
    "Negro": (38, 38, 38),
    "Rojo": (211, 47, 47),
    "Azul": (25, 118, 210),
    "Azul Claro": (79, 195, 247),
    "Azul Oscuro": (13, 71, 161),
    "Amarillo": (251, 192, 45),
    "Naranja": (245, 124, 0),
    "Gris": (117, 117, 117),
    "Marrón": (121, 85, 72),
    "Morado": (123, 31, 162),
    "Rosa": (233, 30, 99),
    "Turquesa": (0, 188, 212),
    "Verde Claro": (139, 195, 74),
    "Verde Oscuro": (27, 94, 32)
}

COLOR_HEX_MAP = {
    k: f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
    for k, rgb in COLOR_RGB_MAP.items()
}

def parse_stl(filepath):
    if not os.path.exists(filepath):
        return [], []
    with open(filepath, 'rb') as f:
        head = f.read(5)
        f.seek(0)
        if head == b'solid':
            try:
                content = f.read().decode('utf-8', errors='ignore')
                lines = content.splitlines()
                if any('facet normal' in line for line in lines[:20]):
                    return _parse_stl_ascii(lines)
            except Exception:
                f.seek(0)
        return _parse_stl_binary(f)

def _parse_stl_binary(f):
    f.seek(80)
    count_data = f.read(4)
    if len(count_data) < 4:
        return [], []
    num_triangles = struct.unpack('<I', count_data)[0]

    vertices = []
    triangles = []
    v_map = {}

    for _ in range(num_triangles):
        data = f.read(50)
        if len(data) < 50:
            break
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
    vertices = []
    triangles = []
    v_map = {}
    current_tri = []

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
        '  <metadata name="Application">Parametric Keychain Maker</metadata>',
        '  <resources>',
        '    <m:colorgroup id="1">',
        f'      <m:color color="{base_hex}FF"/>',
        f'      <m:color color="{text_hex}FF"/>',
        '    </m:colorgroup>',
        '    <object id="2" type="model" name="Base" pid="1" pindex="0">',
        '      <mesh>',
        '        <vertices>'
    ]
    for x, y, z in base_v:
        model_xml.append(f'          <vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>')
    model_xml.extend([
        '        </vertices>',
        '        <triangles>'
    ])
    for v1, v2, v3 in base_t:
        model_xml.append(f'          <triangle v1="{v1}" v2="{v2}" v3="{v3}" pid="1" p1="0"/>')
    model_xml.extend([
        '        </triangles>',
        '      </mesh>',
        '    </object>'
    ])

    if text_v and text_t:
        model_xml.extend([
            '    <object id="3" type="model" name="Letters" pid="1" pindex="1">',
            '      <mesh>',
            '        <vertices>'
        ])
        for x, y, z in text_v:
            model_xml.append(f'          <vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>')
        model_xml.extend([
            '        </vertices>',
            '        <triangles>'
        ])
        for v1, v2, v3 in text_t:
            model_xml.append(f'          <triangle v1="{v1}" v2="{v2}" v3="{v3}" pid="1" p1="1"/>')
        model_xml.extend([
            '        </triangles>',
            '      </mesh>',
            '    </object>',
            '    <object id="4" type="model" name="Keychain_Assembly">',
            '      <components>',
            '        <component objectid="2"/>',
            '        <component objectid="3"/>',
            '      </components>',
            '    </object>',
            '  </resources>',
            '  <build>',
            '    <item objectid="4"/>',
            '  </build>',
            '</model>'
        ])
    else:
        model_xml.extend([
            '  </resources>',
            '  <build>',
            '    <item objectid="2"/>',
            '  </build>',
            '</model>'
        ])

    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        '</Types>'
    )

    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>'
    )

    bambu_config = f"""<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value="Base"/>
    <part id="1" name="Base">
      <metadata key="name" value="Base"/>
      <color>{base_hex}</color>
    </part>
  </object>
  <object id="3">
    <metadata key="name" value="Letters"/>
    <part id="1" name="Letters">
      <metadata key="name" value="Letters"/>
      <color>{text_hex}</color>
    </part>
  </object>
</config>
"""

    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('3D/3dmodel.model', '\n'.join(model_xml))
        z.writestr('Metadata/model_settings.config', bambu_config)

class KeychainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Parametric 3D Mechanical Keychain Maker")
        self.root.geometry("1020x880")
        self.root.minsize(900, 780)

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
        self.style.configure("Dim.TLabel", foreground="#555555", font=("Segoe UI", 9))
        self.style.configure("Status.TLabel", font=("Segoe UI", 9))

        self.openscad_path = self.locate_openscad()
        self.openscad_path_var = tk.StringVar(value=self.openscad_path)

        self.name_var = tk.StringVar(value="ALBERTO")
        self.font_var = tk.StringVar(value="Impact")
        self.font_size_var = tk.DoubleVar(value=10.0)
        self.thickness_var = tk.DoubleVar(value=1.0)
        self.uppercase_var = tk.BooleanVar(value=True)

        self.loop_var = tk.BooleanVar(value=True)
        self.base_color_var = tk.StringVar(value="Verde (Green)")
        self.letter_color_var = tk.StringVar(value="Beige")

        self.alto_var = tk.DoubleVar(value=6.0)
        self.ancho_var = tk.DoubleVar(value=12.0)
        self.largo_var = tk.DoubleVar(value=15.0)

        self.base_mesh_data = None
        self.text_mesh_data = None
        self.has_3d_data = False

        self.rot_x = -0.75
        self.rot_y = 0.0
        self.rot_z = 0.55
        self.zoom_3d = 5.2
        self.pan_x = 0
        self.pan_y = 0

        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_wireframe = False
        self.auto_rotate = False
        self.canvas_photo_image = None
        self.is_processing = False

        self.font_map = {
            "Impact": "Impact",
            "Arial Black": "Arial Black",
            "Arial Bold": "Arial:style=Bold",
            "Tahoma Bold": "Tahoma:style=Bold",
            "Verdana Bold": "Verdana:style=Bold",
            "Courier New Bold": "Courier New:style=Bold",
            "Bungee": "Bungee",
            "Archivo Black": "Archivo Black",
            "Bangers": "Bangers",
            "Changa One": "Changa One",
            "Bebas Neue": "Bebas Neue",
            "Poppins Black": "Poppins Black"
        }

        self.setup_ui()
        self.update_dimensions_estimate()

        if os.path.exists(self.openscad_path) and os.path.exists(SCAD_FILE):
            self.root.after(300, self.update_in_app_3d)

    def locate_openscad(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    saved = cfg.get("openscad_path")
                    if saved and os.path.exists(saved):
                        return saved
            except Exception:
                pass

        path_which = shutil.which("openscad")
        if path_which and os.path.exists(path_which):
            return path_which

        for candidate in DEFAULT_OPENSCAD_PATHS:
            if os.path.exists(candidate):
                return candidate
        return "openscad.exe"

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"openscad_path": self.openscad_path}, f, indent=2)
        except Exception as e:
            pass

    def browse_openscad(self):
        chosen = filedialog.askopenfilename(
            title="Select OpenSCAD Executable",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if chosen and os.path.exists(chosen):
            self.openscad_path = chosen
            self.openscad_path_var.set(chosen)
            self.save_config()
            self.status_label.config(text="OpenSCAD path updated.")

    def setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=8, pady=8)

        left_frame = ttk.Frame(main_paned, width=440)
        main_paned.add(left_frame, weight=1)

        right_frame = ttk.Frame(main_paned, width=580)
        main_paned.add(right_frame, weight=2)

        self.setup_left_controls(left_frame)
        self.setup_right_3d_viewport(right_frame)

    def setup_left_controls(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, pady=(0, 6))

        tab_general = ttk.Frame(notebook, padding=10)
        notebook.add(tab_general, text="  Text & Typography  ")

        tab_appearance = ttk.Frame(notebook, padding=10)
        notebook.add(tab_appearance, text="  Colors & Links  ")

        tab_dimensions = ttk.Frame(notebook, padding=10)
        notebook.add(tab_dimensions, text="  Dimensions & Path  ")

        ttk.Label(tab_general, text="Keychain Name / Text:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 2))
        name_entry = ttk.Entry(tab_general, textvariable=self.name_var, font=("Segoe UI", 11))
        name_entry.pack(fill="x", pady=(0, 6))
        self.name_var.trace_add("write", lambda *args: self.update_dimensions_estimate())

        ttk.Checkbutton(tab_general, text="Force UPPERCASE text", variable=self.uppercase_var).pack(anchor="w", pady=(0, 10))

        ttk.Label(tab_general, text="Font Style:").pack(anchor="w", pady=(2, 2))
        font_dropdown = ttk.Combobox(
            tab_general, textvariable=self.font_var,
            values=list(self.font_map.keys()), state="readonly"
        )
        font_dropdown.pack(fill="x", pady=(0, 12))

        ttk.Label(tab_general, text="Font Size (mm):").pack(anchor="w", pady=(2, 2))
        size_frame = ttk.Frame(tab_general)
        size_frame.pack(fill="x", pady=(0, 12))
        size_slider = ttk.Scale(size_frame, from_=6.0, to=16.0, variable=self.font_size_var, orient="horizontal")
        size_slider.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.font_size_label = ttk.Label(size_frame, text="10.0 mm", width=8)
        self.font_size_label.pack(side="right")
        self.font_size_var.trace_add("write", self.update_font_size_label)

        ttk.Label(tab_general, text="Letter Relief Depth:").pack(anchor="w", pady=(2, 2))
        thick_frame = ttk.Frame(tab_general)
        thick_frame.pack(fill="x", pady=(0, 4))
        thick_slider = ttk.Scale(thick_frame, from_=-5.0, to=5.0, variable=self.thickness_var, orient="horizontal")
        thick_slider.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.thickness_label = ttk.Label(thick_frame, text="+1.0 mm (Raised)", width=18)
        self.thickness_label.pack(side="right")
        self.thickness_var.trace_add("write", self.update_thickness_label)

        ttk.Label(tab_general, text="Tip: Positive (+) values emboss/raise letters.", style="Dim.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Label(tab_appearance, text="Keyring Attachment:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 2))
        ttk.Checkbutton(tab_appearance, text="Include keyring attachment hole", variable=self.loop_var, command=self.update_dimensions_estimate).pack(anchor="w", pady=(0, 14))

        ttk.Label(tab_appearance, text="Base Block Color:").pack(anchor="w", pady=(2, 2))
        base_color_cb = ttk.Combobox(tab_appearance, textvariable=self.base_color_var, values=list(COLOR_MAP.keys()), state="readonly")
        base_color_cb.pack(fill="x", pady=(0, 12))
        base_color_cb.bind("<<ComboboxSelected>>", lambda e: self.render_3d())

        ttk.Label(tab_appearance, text="Letters Color:").pack(anchor="w", pady=(2, 2))
        letter_color_cb = ttk.Combobox(tab_appearance, textvariable=self.letter_color_var, values=list(COLOR_MAP.keys()), state="readonly")
        letter_color_cb.pack(fill="x", pady=(0, 12))
        letter_color_cb.bind("<<ComboboxSelected>>", lambda e: self.render_3d())

        ttk.Label(tab_dimensions, text="Block Dimensions (mm):", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 6))
        dim_grid = ttk.Frame(tab_dimensions)
        dim_grid.pack(fill="x", pady=(0, 14))
        ttk.Label(dim_grid, text="Thickness (Alto):").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Spinbox(dim_grid, from_=4.0, to=14.0, increment=0.5, textvariable=self.alto_var, width=8, command=self.update_dimensions_estimate).grid(row=0, column=1, sticky="e", pady=4, padx=8)
        ttk.Label(dim_grid, text="Width (Ancho):").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Spinbox(dim_grid, from_=8.0, to=25.0, increment=1.0, textvariable=self.ancho_var, width=8, command=self.update_dimensions_estimate).grid(row=1, column=1, sticky="e", pady=4, padx=8)
        ttk.Label(dim_grid, text="Link Length (Largo):").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Spinbox(dim_grid, from_=10.0, to=30.0, increment=1.0, textvariable=self.largo_var, width=8, command=self.update_dimensions_estimate).grid(row=2, column=1, sticky="e", pady=4, padx=8)

        ttk.Separator(tab_dimensions, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(tab_dimensions, text="OpenSCAD Path:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 2))
        path_box = ttk.Frame(tab_dimensions)
        path_box.pack(fill="x", pady=(2, 6))
        ttk.Entry(path_box, textvariable=self.openscad_path_var).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(path_box, text="Browse...", command=self.browse_openscad).pack(side="right")

        dim_card = ttk.LabelFrame(parent, text="📏 Estimated 3D Print Size", padding=8)
        dim_card.pack(fill="x", pady=(0, 6))
        self.dimension_label = ttk.Label(dim_card, text="", justify="left", font=("Segoe UI", 9, "bold"))
        self.dimension_label.pack(anchor="w")

        btn_box = ttk.Frame(parent)
        btn_box.pack(fill="x", pady=(0, 4))
        self.btn_refresh_3d = ttk.Button(btn_box, text="🔄 Update 3D Model Inside App", style="Accent.TButton", command=self.update_in_app_3d)
        self.btn_refresh_3d.pack(fill="x", pady=(0, 6))

        save_row = ttk.Frame(btn_box)
        save_row.pack(fill="x", pady=(0, 5))
        self.btn_3mf = ttk.Button(save_row, text="🎨 Save as 3MF (Multi-Color)", command=self.save_multicolor_3mf)
        self.btn_3mf.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.btn_stl = ttk.Button(save_row, text="💾 Save as STL", command=self.save_stl)
        self.btn_stl.pack(side="right", fill="x", expand=True, padx=(3, 0))

        sub_row = ttk.Frame(btn_box)
        sub_row.pack(fill="x")
        self.btn_multipart = ttk.Button(sub_row, text="🧩 Export Multi-Part (STLs)", command=self.export_multipart_stls)
        self.btn_multipart.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.btn_openscad = ttk.Button(sub_row, text="📐 Open in OpenSCAD", command=self.open_in_openscad)
        self.btn_openscad.pack(side="right", fill="x", expand=True, padx=(3, 0))

        self.prog_bar = ttk.Progressbar(parent, mode="indeterminate")
        self.prog_bar.pack(fill="x", pady=(6, 2))
        self.status_label = ttk.Label(parent, text="Ready", style="Status.TLabel", wraplength=400)
        self.status_label.pack(anchor="w")

    def setup_right_3d_viewport(self, parent):
        viewport_group = ttk.LabelFrame(parent, text="In-App 3D Interactive Viewport (360° Real-Time)", padding=6)
        viewport_group.pack(fill="both", expand=True)

        toolbar = ttk.Frame(viewport_group)
        toolbar.pack(fill="x", pady=(0, 6))
        self.btn_autorotate = ttk.Button(toolbar, text="🔄 Auto-Rotate", width=13, command=self.toggle_auto_rotate)
        self.btn_autorotate.pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="↺ Reset View", width=11, command=self.reset_3d_view).pack(side="left", padx=2)
        ttk.Button(toolbar, text="📐 Wireframe", width=11, command=self.toggle_wireframe).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔍 Zoom In", width=9, command=self.zoom_in_3d).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔎 Zoom Out", width=10, command=self.zoom_out_3d).pack(side="left", padx=2)

        self.canvas_3d = tk.Canvas(viewport_group, bg="#181d24", cursor="fleur", highlightthickness=1, highlightbackground="#374151")
        self.canvas_3d.pack(fill="both", expand=True)
        
        self.canvas_3d.bind("<ButtonPress-1>", self.on_3d_press)
        self.canvas_3d.bind("<B1-Motion>", self.on_3d_drag_rotate)
        self.canvas_3d.bind("<ButtonPress-3>", self.on_3d_press)
        self.canvas_3d.bind("<B3-Motion>", self.on_3d_drag_pan)
        self.canvas_3d.bind("<MouseWheel>", self.on_3d_wheel)
        self.canvas_3d.bind("<Configure>", lambda e: self.render_3d())

    def update_dimensions_estimate(self, *args):
        text = self.get_clean_name()
        n = max(1, len(text))
        try:
            largo = float(self.largo_var.get())
            ancho = float(self.ancho_var.get())
            alto = float(self.alto_var.get())
        except ValueError:
            largo, ancho, alto = 15.0, 12.0, 6.0

        loop = self.loop_var.get()
        first_len = largo if loop else (largo - 2.0)
        total_len = first_len + (n - 1) * (largo + 1.0)
        self.dimension_label.config(text=f"Total Length: ~{total_len:.1f} mm\nWidth: {ancho:.1f} mm | Thickness: {alto:.1f} mm")

    def update_thickness_label(self, *args):
        try:
            val = round(self.thickness_var.get(), 1)
            self.thickness_label.config(text=f"+{val} mm (Raised)" if val > 0 else (f"{val} mm (Engraved)" if val < 0 else "0.0 mm (Flush)"))
        except tk.TclError: pass

    def update_font_size_label(self, *args):
        try: self.font_size_label.config(text=f"{round(self.font_size_var.get(), 1)} mm")
        except tk.TclError: pass

    def get_clean_name(self):
        raw = self.name_var.get().strip()
        if self.uppercase_var.get(): raw = raw.upper()
        return raw if raw else " "

    def build_openscad_command(self, output_file, export_mode="todo"):
        name = self.get_clean_name().replace('\\', '\\\\').replace('"', '\\"')
        scad_font = self.font_map.get(self.font_var.get(), "Impact")
        thickness = round(self.thickness_var.get(), 2)
        font_size = round(self.font_size_var.get(), 1)
        base_color = COLOR_MAP.get(self.base_color_var.get(), "Verde")
        letter_color = COLOR_MAP.get(self.letter_color_var.get(), "Beige")
        loop_flag = "true" if self.loop_var.get() else "false"
        alto = round(self.alto_var.get(), 1)
        ancho = round(self.ancho_var.get(), 1)
        largo = round(self.largo_var.get(), 1)

        return [
            self.openscad_path, "-o", output_file, "--export-format", "binstl",
            "-D", f'texto="{name}"',
            "-D", f'fuente_seleccionada="{scad_font}"',
            "-D", f'tamano_letra={font_size}',
            "-D", f'altura_letra={thickness}',
            "-D", f'eslabon_primer_elemento={loop_flag}',
            "-D", f'color_base="{base_color}"',
            "-D", f'color_letras="{letter_color}"',
            "-D", f'alto={alto}',
            "-D", f'ancho={ancho}',
            "-D", f'largo={largo}',
            "-D", f'modo_exportacion="{export_mode}"',
            SCAD_FILE
        ]

    def execute_openscad_process(self, command):
        startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
        if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.run(command, capture_output=True, startupinfo=startupinfo)

    def set_busy_state(self, busy, message=""):
        self.is_processing = busy
        state = "disabled" if busy else "normal"
        if busy: self.prog_bar.start(10)
        else: self.prog_bar.stop()
        self.btn_refresh_3d.config(state=state)
        self.btn_3mf.config(state=state)
        self.btn_stl.config(state=state)
        self.btn_multipart.config(state=state)
        self.btn_openscad.config(state=state)
        self.status_label.config(text=message)

    def update_in_app_3d(self):
        if self.is_processing: return
        self.set_busy_state(True, "Rendering 3D model inside application...")
        def worker():
            name = self.get_clean_name()
            base_temp = os.path.join(tempfile.gettempdir(), f"_inapp_base_{name}.stl")
            text_temp = os.path.join(tempfile.gettempdir(), f"_inapp_text_{name}.stl")
            try:
                cmd_b = self.build_openscad_command(base_temp, export_mode="base")
                res_b = self.execute_openscad_process(cmd_b)
                cmd_t = self.build_openscad_command(text_temp, export_mode="texto")
                res_t = self.execute_openscad_process(cmd_t)
                if res_b.returncode == 0:
                    base_v, base_t = parse_stl(base_temp)
                    text_v, text_t = parse_stl(text_temp) if res_t.returncode == 0 else ([], [])
                    b_data = (np.array(base_v, dtype=np.float32), np.array(base_t, dtype=np.int32)) if base_t else None
                    t_data = (np.array(text_v, dtype=np.float32), np.array(text_t, dtype=np.int32)) if text_t else None
                    self.root.after(0, lambda: self.on_3d_data_ready(b_data, t_data))
                else:
                    self.root.after(0, lambda: self.on_3d_error(res_b.stderr.decode('utf-8', errors='replace')))
            except Exception as ex:
                self.root.after(0, lambda: self.on_3d_error(str(ex)))
        threading.Thread(target=worker, daemon=True).start()

    def on_3d_data_ready(self, base_data, text_data):
        self.base_mesh_data = base_data
        self.text_mesh_data = text_data
        self.has_3d_data = True
        self.set_busy_state(False, "3D Model loaded!")
        self.render_3d()

    def on_3d_error(self, err_msg):
        self.set_busy_state(False, "Failed to load 3D model.")
        messagebox.showerror("3D Render Error", err_msg)

    def draw_3d_grid(self, img, w, h):
        cx, cy = w // 2, h // 2
        for i in range(-50, 51, 10):
            pt1 = self.project_pt((i, -50, 0), w, h)
            pt2 = self.project_pt((i, 50, 0), w, h)
            if pt1 and pt2: cv2.line(img, pt1, pt2, (50, 50, 50), 1)
            pt3 = self.project_pt((-50, i, 0), w, h)
            pt4 = self.project_pt((50, i, 0), w, h)
            if pt3 and pt4: cv2.line(img, pt3, pt4, (50, 50, 50), 1)

    def project_pt(self, pt, w, h):
        cx, sx = np.cos(self.rot_x), np.sin(self.rot_x)
        cy, sy = np.cos(self.rot_y), np.sin(self.rot_y)
        cz, sz = np.cos(self.rot_z), np.sin(self.rot_z)
        Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float32)
        R = Rz @ Ry @ Rx
        v = np.array(pt, dtype=np.float32)
        v = R @ v
        v[0] += self.pan_x
        v[1] += self.pan_y
        z = v[2] + 100
        if z <= 0.1: return None
        scale = self.zoom_3d * 200 / z
        x = int(w/2 + v[0] * scale)
        y = int(h/2 - v[1] * scale)
        return (x, y)

    def render_3d(self):
        if not self.has_3d_data: return
        w = max(100, self.canvas_3d.winfo_width())
        h = max(100, self.canvas_3d.winfo_height())
        img = np.full((h, w, 3), (36, 29, 24), dtype=np.uint8)
        self.draw_3d_grid(img, w, h)

        cx, sx = np.cos(self.rot_x), np.sin(self.rot_x)
        cy, sy = np.cos(self.rot_y), np.sin(self.rot_y)
        cz, sz = np.cos(self.rot_z), np.sin(self.rot_z)
        Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float32)
        R = Rz @ Ry @ Rx

        light_dir = np.array([0, 0, 1], dtype=np.float32)
        
        polygons = []
        
        def process_mesh(data, rgb_color):
            if not data: return
            v_np, t_np = data
            v_rot = v_np @ R.T
            v_rot[:, 0] += self.pan_x
            v_rot[:, 1] += self.pan_y
            v_rot[:, 2] += 100
            scale = self.zoom_3d * 200 / v_rot[:, 2]
            px = (w/2 + v_rot[:, 0] * scale).astype(np.int32)
            py = (h/2 - v_rot[:, 1] * scale).astype(np.int32)
            for t in t_np:
                p1, p2, p3 = v_rot[t[0]], v_rot[t[1]], v_rot[t[2]]
                z_avg = (p1[2] + p2[2] + p3[2]) / 3.0
                if p1[2] < 1 or p2[2] < 1 or p3[2] < 1: continue
                v1, v2 = p2 - p1, p3 - p1
                normal = np.cross(v1, v2)
                norm_len = np.linalg.norm(normal)
                if norm_len > 0: normal /= norm_len
                intensity = np.dot(normal, light_dir)
                intensity = max(0.2, min(1.0, intensity))
                shade = (int(rgb_color[2]*intensity), int(rgb_color[1]*intensity), int(rgb_color[0]*intensity))
                pts = np.array([[px[t[0]], py[t[0]]], [px[t[1]], py[t[1]]], [px[t[2]], py[t[2]]]], dtype=np.int32)
                polygons.append((z_avg, pts, shade))

        base_color = COLOR_RGB_MAP.get(COLOR_MAP.get(self.base_color_var.get(), "Verde"), (46, 125, 50))
        text_color = COLOR_RGB_MAP.get(COLOR_MAP.get(self.letter_color_var.get(), "Beige"), (245, 245, 220))
        
        process_mesh(self.base_mesh_data, base_color)
        process_mesh(self.text_mesh_data, text_color)
        
        polygons.sort(key=lambda x: x[0], reverse=True)
        for z, pts, shade in polygons:
            if self.is_wireframe: cv2.polylines(img, [pts], True, shade, 1)
            else:
                cv2.fillPoly(img, [pts], shade)
                cv2.polylines(img, [pts], True, (max(0, shade[0]-20), max(0, shade[1]-20), max(0, shade[2]-20)), 1)
        
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)
        self.canvas_photo_image = ImageTk.PhotoImage(pil_img)
        self.canvas_3d.create_image(0, 0, image=self.canvas_photo_image, anchor="nw")

    def toggle_wireframe(self):
        self.is_wireframe = not self.is_wireframe
        self.render_3d()

    def reset_3d_view(self):
        self.rot_x = -0.75
        self.rot_y = 0.0
        self.rot_z = 0.55
        self.zoom_3d = 5.2
        self.pan_x = 0
        self.pan_y = 0
        self.render_3d()

    def zoom_in_3d(self):
        self.zoom_3d *= 1.2
        self.render_3d()

    def zoom_out_3d(self):
        self.zoom_3d /= 1.2
        self.render_3d()

    def toggle_auto_rotate(self):
        self.auto_rotate = not self.auto_rotate
        if self.auto_rotate: self.auto_rotate_step()

    def auto_rotate_step(self):
        if self.auto_rotate:
            self.rot_z += 0.05
            self.render_3d()
            self.root.after(30, self.auto_rotate_step)

    def on_3d_press(self, event):
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def on_3d_drag_rotate(self, event):
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        self.rot_z += dx * 0.01
        self.rot_x += dy * 0.01
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.render_3d()

    def on_3d_drag_pan(self, event):
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        self.pan_x += dx * (self.zoom_3d / 10.0)
        self.pan_y -= dy * (self.zoom_3d / 10.0)
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.render_3d()

    def on_3d_wheel(self, event):
        if event.delta > 0: self.zoom_in_3d()
        else: self.zoom_out_3d()

    def export_multipart_stls(self):
        d = filedialog.askdirectory(title="Select Folder to Export Parts")
        if not d: return
        self.set_busy_state(True, "Exporting Multi-Part STLs...")
        def worker():
            name = self.get_clean_name()
            b = os.path.join(d, f"{name}_BASE.stl")
            t = os.path.join(d, f"{name}_TEXT.stl")
            subprocess.run(self.build_cmd(b, "base"), capture_output=True, startupinfo=subprocess.STARTUPINFO() if os.name=='nt' else None)
            subprocess.run(self.build_cmd(t, "texto"), capture_output=True, startupinfo=subprocess.STARTUPINFO() if os.name=='nt' else None)
            self.root.after(0, lambda: self.set_busy_state(False, f"Exported multi-parts to {d}"))
            self.root.after(0, lambda: messagebox.showinfo("Done", "Exported successfully!"))
        threading.Thread(target=worker, daemon=True).start()

    def build_cmd(self, out, mode):
        return self.build_openscad_command(out, mode)

    def save_multicolor_3mf(self):
        out = filedialog.asksaveasfilename(title="Save Multi-Color 3MF", filetypes=[("3MF File", "*.3mf")])
        if not out: return
        self.set_busy_state(True, "Building Multi-Color 3MF...")
        def worker():
            tmp = tempfile.gettempdir()
            b = os.path.join(tmp, "m3mf_b.stl")
            t = os.path.join(tmp, "m3mf_t.stl")
            subprocess.run(self.build_cmd(b, "base"), capture_output=True, startupinfo=subprocess.STARTUPINFO() if os.name=='nt' else None)
            subprocess.run(self.build_cmd(t, "texto"), capture_output=True, startupinfo=subprocess.STARTUPINFO() if os.name=='nt' else None)
            bv, bt = parse_stl(b)
            tv, tt = parse_stl(t)
            bc = COLOR_HEX_MAP.get(COLOR_MAP.get(self.base_color_var.get(), "Verde"), "#2E7D32")
            tc = COLOR_HEX_MAP.get(COLOR_MAP.get(self.letter_color_var.get(), "Beige"), "#F5F5DC")
            build_multicolor_3mf(bv, bt, tv, tt, bc, tc, out)
            self.root.after(0, lambda: self.set_busy_state(False, "3MF Exported!"))
            self.root.after(0, lambda: messagebox.showinfo("Done", "3MF saved successfully!"))
        threading.Thread(target=worker, daemon=True).start()

    def save_stl(self):
        out = filedialog.asksaveasfilename(title="Save STL", filetypes=[("STL File", "*.stl")])
        if not out: return
        self.set_busy_state(True, "Generating STL...")
        def worker():
            subprocess.run(self.build_cmd(out, "todo"), capture_output=True, startupinfo=subprocess.STARTUPINFO() if os.name=='nt' else None)
            self.root.after(0, lambda: self.set_busy_state(False, "STL Exported!"))
            self.root.after(0, lambda: messagebox.showinfo("Done", "STL saved successfully!"))
        threading.Thread(target=worker, daemon=True).start()

    def open_in_openscad(self):
        threading.Thread(target=lambda: subprocess.run([self.openscad_path, SCAD_FILE]), daemon=True).start()

if __name__ == "__main__":
    app = tk.Tk()
    KeychainApp(app)
    app.mainloop()
