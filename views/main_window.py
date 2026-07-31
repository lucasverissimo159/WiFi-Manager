#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""View: Janela principal — suporta rebuild para troca de tema ao vivo."""

import sys
from pathlib import Path
import tkinter as tk
import customtkinter as ctk
from views.styles import COLORS, FONTS, DIMS


class MainWindow(ctk.CTk):

    def __init__(self, app_dir: Path, theme: str = "dark"):
        super().__init__()
        self.app_dir = app_dir
        self._current_theme = theme

        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")

        self.title("UniFi Wi-Fi Manager")
        self.minsize(1100, 720)
        self.after(100, self._do_maximize)
        self._maximize_done = False

        self._set_icon()
        self._build_ui()

    def rebuild(self, theme: str):
        """Reconstrói toda a UI com o novo tema SEM destruir a janela raiz."""
        self._current_theme = theme
        ctk.set_appearance_mode(theme)
        # Destruir TODOS os filhos
        for child in self.winfo_children():
            child.destroy()
        # Reconfigurar fundo da raiz
        self.configure(fg_color=COLORS["bg_main"])
        # Reconstruir
        self._build_ui()

    def _build_ui(self):
        """Constrói toda a interface (chamado no init e no rebuild)."""
        self.configure(fg_color=COLORS["bg_main"])
        self._build_header()
        self._build_nav()
        self._build_pages()

    def _do_maximize(self):
        if self._maximize_done:
            return
        self._maximize_done = True
        try:
            if sys.platform == 'win32':
                self.state('zoomed')
            else:
                self.attributes('-zoomed', True)
        except Exception:
            self.geometry("1280x800")

    def _set_icon(self):
        """Carrega ícone para janela, taskbar e header."""
        self._app_icon_img = None  # CTkImage reutilizável
        icon_dir = self.app_dir / "resources" / "icon"
        if not icon_dir.exists():
            return

        ico_file = None
        img_file = None

        for f in icon_dir.iterdir():
            low = f.suffix.lower()
            if low == '.ico' and not ico_file:
                ico_file = f
            if low in ('.png', '.jpg', '.jpeg', '.ico') and not img_file:
                img_file = f

        # Ícone da janela + barra de tarefas
        if ico_file:
            try:
                self.iconbitmap(str(ico_file))
            except Exception:
                pass
            # No Windows, forçar ícone na barra de tarefas
            if sys.platform == 'win32':
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                        "unifi.wifimanager.app.1")
                except Exception:
                    pass

        # CTkImage para uso no header / títulos
        if img_file:
            try:
                from PIL import Image
                img = Image.open(str(img_file))
                self._app_icon_img = ctk.CTkImage(light_image=img, dark_image=img, size=(24, 24))
            except Exception:
                pass

    # ═══════════ HEADER ═══════════

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=COLORS["header_bg"], corner_radius=0,
                             height=DIMS["header_height"])
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tf = ctk.CTkFrame(hdr, fg_color="transparent")
        tf.pack(side="left", padx=20)

        # Ícone no header
        if self._app_icon_img:
            ctk.CTkLabel(tf, image=self._app_icon_img, text="").pack(side="left", padx=(0, 10))

        ctk.CTkLabel(tf, text="UniFi Wi-Fi Manager",
                      font=FONTS["header_title"], text_color=COLORS["accent_blue"]).pack(side="left")

        rf = ctk.CTkFrame(hdr, fg_color="transparent")
        rf.pack(side="right", padx=20)

        self.lbl_status = ctk.CTkLabel(rf, text="● Desconectado",
                                        font=FONTS["body"], text_color=COLORS["accent_red"])
        self.lbl_status.pack(side="right")

        # Botão tema: sol no dark (para ir pro light), lua no light (para ir pro dark)
        icon = "☀️" if self._current_theme == "dark" else "🌙"
        self.btn_theme = ctk.CTkButton(
            rf, text=icon, width=36, height=32, corner_radius=6,
            font=FONTS["body"], fg_color=COLORS["btn_secondary"],
            hover_color=COLORS["bg_hover"], text_color=COLORS["text_primary"],
            border_width=1, border_color=COLORS["border"])
        self.btn_theme.pack(side="right", padx=(0, 12))

        ctk.CTkFrame(self, fg_color=COLORS["header_border"], height=1, corner_radius=0).pack(fill="x")

    # ═══════════ NAV ═══════════

    def _build_nav(self):
        nav = ctk.CTkFrame(self, fg_color=COLORS["nav_bg"], corner_radius=0, height=42)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        self.nav_buttons = {}
        for key, label, icon in [("management", "Gerenciamento", "🖥️"),
                                  ("overview", "Visão Geral da Rede", "🌐")]:
            btn = ctk.CTkButton(
                nav, text=f"  {icon}  {label}  ", height=32, corner_radius=6,
                font=FONTS["btn_section"], fg_color="transparent",
                hover_color=COLORS["bg_hover"], text_color=COLORS["text_secondary"])
            btn.pack(side="left", padx=(10 if key == "management" else 4, 0), pady=5)
            self.nav_buttons[key] = btn
        ctk.CTkFrame(self, fg_color=COLORS["header_border"], height=1, corner_radius=0).pack(fill="x")

    # ═══════════ PAGES ═══════════

    def _build_pages(self):
        self.pages_container = ctk.CTkFrame(self, fg_color=COLORS["bg_main"])
        self.pages_container.pack(fill="both", expand=True)
        self.pages_container.grid_rowconfigure(0, weight=1)
        self.pages_container.grid_columnconfigure(0, weight=1)

        self.page_management = ctk.CTkFrame(self.pages_container, fg_color=COLORS["bg_main"])
        self.page_management.grid(row=0, column=0, sticky="nsew")
        self._build_management()

        self.page_overview = ctk.CTkFrame(self.pages_container, fg_color=COLORS["bg_main"])
        self._build_overview()

    # ═══════════ PÁG 1 ═══════════

    def _build_management(self):
        body = ctk.CTkFrame(self.page_management, fg_color=COLORS["bg_main"])
        body.pack(fill="both", expand=True, padx=16, pady=12)
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=0)
        body.grid_rowconfigure(0, weight=1)
        self._build_left(body)
        self._build_center(body)
        self._build_right(body)

    def _build_left(self, parent):
        p = ctk.CTkFrame(parent, fg_color=COLORS["bg_main"], width=DIMS["left_panel_width"])
        p.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        p.grid_propagate(False)

        # Conexão
        c1 = self._card(p); c1.pack(fill="x", pady=(0, 10))
        self._sec(c1, "CONEXÃO RÁPIDA")
        ctk.CTkLabel(c1, text="IP do Controller", font=FONTS["small"],
                      text_color=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self.entry_ip = ctk.CTkEntry(c1, placeholder_text="Ex: 192.0.2.1",
                                      font=(FONTS["mono"][0], 13), height=40,
                                      fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                                      text_color=COLORS["text_primary"])
        self.entry_ip.pack(fill="x", padx=16, pady=(2, 6))
        # Dropdown de autocomplete — filho da janela RAIZ com place(), flutua sobre tudo
        self._ip_dropdown_outer = tk.Frame(self, bg=COLORS["border"], bd=0)
        self.ip_dropdown = ctk.CTkScrollableFrame(
            self._ip_dropdown_outer,
            fg_color=COLORS["bg_card"],
            corner_radius=6,
            border_width=1,
            border_color=COLORS["border"],
            height=172)
        self.ip_dropdown.pack(fill="both", expand=True)
        # Começa oculto; controller posiciona via place() com coordenadas absolutas
        ctk.CTkLabel(c1, text="Credenciais → aba Configurações",
                      font=FONTS["tiny"], text_color=COLORS["text_muted"],
                      wraplength=250).pack(anchor="w", padx=16, pady=(0, 4))
        self.btn_connect = ctk.CTkButton(c1, text="Conectar", font=FONTS["body_bold"], height=42,
                                          fg_color=COLORS["accent_blue"], hover_color=COLORS["hover_blue"],
                                          text_color="#FFFFFF")
        self.btn_connect.pack(fill="x", padx=16, pady=(4, 16))

        # Ações
        c2 = self._card(p); c2.pack(fill="x")
        self._sec(c2, "AÇÕES")
        self.btn_activate = ctk.CTkButton(c2, text="⚡  Ativar Redes Wi-Fi", font=FONTS["btn_large"],
                                           height=DIMS["btn_height_large"], fg_color=COLORS["accent_green"],
                                           hover_color=COLORS["hover_green"], text_color="#FFFFFF", state="disabled")
        self.btn_activate.pack(fill="x", padx=16, pady=(0, 8))
        self.btn_check = ctk.CTkButton(c2, text="🔍  Verificar Vouchers", font=FONTS["btn_normal"],
                                        height=DIMS["btn_height_normal"], fg_color=COLORS["accent_orange"],
                                        hover_color=COLORS["hover_orange"], text_color="#FFFFFF", state="disabled")
        self.btn_check.pack(fill="x", padx=16, pady=(0, 8))
        self.btn_refresh = ctk.CTkButton(c2, text="🔄  Atualizar", font=FONTS["btn_normal"],
                                          height=DIMS["btn_height_normal"], fg_color=COLORS["btn_secondary"],
                                          hover_color=COLORS["bg_hover"], border_width=1,
                                          border_color=COLORS["border"], text_color=COLORS["text_primary"],
                                          state="disabled")
        self.btn_refresh.pack(fill="x", padx=16, pady=(0, 8))
        self.btn_report = ctk.CTkButton(c2, text="📄  Gerar Relatório", font=FONTS["btn_normal"],
                                         height=DIMS["btn_height_normal"], fg_color=COLORS["accent_purple"],
                                         hover_color=COLORS["hover_purple"], text_color="#FFFFFF", state="disabled")
        self.btn_report.pack(fill="x", padx=16, pady=(0, 16))

    def _build_center(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=COLORS["bg_main"])
        panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        wc = self._card(panel)
        wc.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        wh = ctk.CTkFrame(wc, fg_color="transparent")
        wh.pack(fill="x", padx=16, pady=(14, 4))
        self._sec_inline(wh, "REDES WI-FI")
        self.lbl_wlan_count = ctk.CTkLabel(wh, text="", font=FONTS["small"],
                                            text_color=COLORS["text_muted"])
        self.lbl_wlan_count.pack(side="right")
        self.wlan_container = ctk.CTkFrame(wc, fg_color="transparent")
        self.wlan_container.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(self.wlan_container, text="Conecte-se para ver as redes.",
                      font=FONTS["body"], text_color=COLORS["text_muted"]).pack(pady=10)

        tc = self._card(panel)
        tc.grid(row=1, column=0, sticky="nsew")
        tc.grid_rowconfigure(1, weight=1)
        tc.grid_columnconfigure(0, weight=1)

        tf = ctk.CTkFrame(tc, fg_color="transparent")
        tf.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        self.tab_buttons = {}
        for key, label, w in [("log", "Log", 80), ("devices", "Dispositivos", 110),
                               ("vouchers", "Vouchers", 100), ("settings", "⚙ Configurações", 130),
                               ("hosts", "🖥 Hosts", 90)]:
            btn = ctk.CTkButton(tf, text=label, width=w, height=DIMS["btn_height_small"],
                                 font=FONTS["tab"], fg_color=COLORS["bg_input"],
                                 hover_color=COLORS["bg_hover"], text_color=COLORS["text_secondary"],
                                 corner_radius=6)
            btn.pack(side="left", padx=(0, 4))
            self.tab_buttons[key] = btn

        self.tab_content = ctk.CTkFrame(tc, fg_color="transparent")
        self.tab_content.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.tab_content.grid_rowconfigure(0, weight=1)
        self.tab_content.grid_columnconfigure(0, weight=1)

        tb_cfg = dict(font=FONTS["mono"], fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"],
                       border_width=0, corner_radius=8, wrap="word", state="disabled")
        self.log_textbox = ctk.CTkTextbox(self.tab_content, **tb_cfg)
        self.log_textbox.grid(row=0, column=0, sticky="nsew")
        self.devices_textbox = ctk.CTkTextbox(self.tab_content, **tb_cfg)
        self.vouchers_textbox = ctk.CTkTextbox(self.tab_content, **tb_cfg)
        self.settings_frame = ctk.CTkScrollableFrame(self.tab_content, fg_color=COLORS["bg_input"],
                                                      corner_radius=8)
        self._build_settings()
        self.hosts_frame = ctk.CTkScrollableFrame(self.tab_content, fg_color=COLORS["bg_input"],
                                                   corner_radius=8)
        self._build_hosts_tab()

    def _build_settings(self):
        f = self.settings_frame

        ctk.CTkLabel(f, text="CREDENCIAIS", font=FONTS["section"],
                      text_color=COLORS["accent_blue"]).pack(anchor="w", padx=16, pady=(16, 2))
        ctk.CTkLabel(f, text="Usadas para todas as lojas — só o IP muda.",
                      font=FONTS["small"], text_color=COLORS["text_muted"],
                      wraplength=500).pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(f, text="Usuário", font=FONTS["small"],
                      text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16)
        self.cfg_user = ctk.CTkEntry(f, placeholder_text="admin", font=FONTS["body"], height=36,
                                      fg_color=COLORS["bg_card"], border_color=COLORS["border"],
                                      text_color=COLORS["text_primary"], width=350)
        self.cfg_user.pack(anchor="w", padx=16, pady=(2, 10))

        ctk.CTkLabel(f, text="Senha", font=FONTS["small"],
                      text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16)
        pf = ctk.CTkFrame(f, fg_color="transparent")
        pf.pack(anchor="w", padx=16, pady=(2, 10))
        self.cfg_pass = ctk.CTkEntry(pf, placeholder_text="••••••••", show="•", font=FONTS["body"],
                                      height=36, fg_color=COLORS["bg_card"], border_color=COLORS["border"],
                                      text_color=COLORS["text_primary"], width=290)
        self.cfg_pass.pack(side="left")
        self.btn_toggle_pass = ctk.CTkButton(pf, text="👁", width=50, height=36, font=FONTS["btn_normal"],
                                              fg_color=COLORS["btn_secondary"], hover_color=COLORS["bg_hover"],
                                              border_width=1, border_color=COLORS["border"],
                                              text_color=COLORS["text_primary"])
        self.btn_toggle_pass.pack(side="left", padx=(6, 0))

        ctk.CTkLabel(f, text="Porta", font=FONTS["small"],
                      text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16)
        self.cfg_port = ctk.CTkEntry(f, placeholder_text="8443", font=FONTS["mono"], height=36,
                                      fg_color=COLORS["bg_card"], border_color=COLORS["border"],
                                      text_color=COLORS["text_primary"], width=120)
        self.cfg_port.insert(0, "8443")
        self.cfg_port.pack(anchor="w", padx=16, pady=(2, 14))

        self._div(f)

        ctk.CTkLabel(f, text="VALIDAÇÃO DE CPF", font=FONTS["section"],
                      text_color=COLORS["accent_blue"]).pack(anchor="w", padx=16, pady=(12, 4))
        self.switch_online = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(f, text="Consultar CPF online (BrasilAPI)", font=FONTS["body"],
                        text_color=COLORS["text_primary"], variable=self.switch_online,
                        progress_color=COLORS["accent_green"], button_color=COLORS["accent_blue"],
                        button_hover_color=COLORS["hover_blue"]).pack(anchor="w", padx=16, pady=(0, 14))

        self._div(f)

        ctk.CTkLabel(f, text="IPs PERSONALIZADOS", font=FONTS["section"],
                      text_color=COLORS["accent_blue"]).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(f, text="Adicione controllers à Visão Geral da Rede.",
                      font=FONTS["small"], text_color=COLORS["text_muted"],
                      wraplength=500).pack(anchor="w", padx=16, pady=(0, 8))
        ip_row = ctk.CTkFrame(f, fg_color="transparent")
        ip_row.pack(anchor="w", padx=16, fill="x", pady=(0, 6))
        self.entry_custom_ip = ctk.CTkEntry(ip_row, placeholder_text="Ex: 192.0.2.200",
                                             font=FONTS["mono"], height=36,
                                             fg_color=COLORS["bg_card"], border_color=COLORS["border"],
                                             text_color=COLORS["text_primary"], width=200)
        self.entry_custom_ip.pack(side="left")
        self.btn_add_ip = ctk.CTkButton(ip_row, text="+ Adicionar", font=FONTS["small_bold"],
                                         height=36, width=100, fg_color=COLORS["accent_blue"],
                                         hover_color=COLORS["hover_blue"], text_color="#FFFFFF")
        self.btn_add_ip.pack(side="left", padx=(8, 0))
        self.lbl_add_ip_status = ctk.CTkLabel(f, text="", font=FONTS["small"],
                                               text_color=COLORS["accent_green"])
        self.lbl_add_ip_status.pack(anchor="w", padx=16, pady=(4, 2))
        ctk.CTkLabel(f, text="💡 Para remover hosts acesse a aba  🖥 Hosts",
                      font=FONTS["tiny"], text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(0, 14))

        self._div(f)

        self.btn_save_cfg = ctk.CTkButton(f, text="💾  Salvar Configurações", font=FONTS["body_bold"],
                                           height=44, fg_color=COLORS["accent_green"],
                                           hover_color=COLORS["hover_green"], text_color="#FFFFFF")
        self.btn_save_cfg.pack(anchor="w", padx=16, pady=(12, 4))
        self.lbl_cfg_status = ctk.CTkLabel(f, text="", font=FONTS["small"],
                                            text_color=COLORS["accent_green"])
        self.lbl_cfg_status.pack(anchor="w", padx=16, pady=(0, 16))

    def _build_right(self, parent):
        p = ctk.CTkFrame(parent, fg_color=COLORS["bg_main"], width=DIMS["right_panel_width"])
        p.grid(row=0, column=2, sticky="ns"); p.grid_propagate(False)
        card = self._card(p); card.pack(fill="both", expand=True)
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(14, 4))
        self._sec_inline(hdr, "ANTENAS / APs")
        self.lbl_antenna_status = ctk.CTkLabel(hdr, text="", font=FONTS["tiny"],
                                                text_color=COLORS["text_muted"])
        self.lbl_antenna_status.pack(side="right")
        self.lbl_auto_refresh = ctk.CTkLabel(card, text="", font=FONTS["tiny"],
                                              text_color=COLORS["accent_blue"])
        self.lbl_auto_refresh.pack(anchor="w", padx=14, pady=(0, 4))
        self.antenna_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent", corner_radius=6)
        self.antenna_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        ctk.CTkLabel(self.antenna_scroll, text="Conecte-se para ver\nos dispositivos.",
                      font=FONTS["small"], text_color=COLORS["text_muted"],
                      justify="center").pack(pady=30)

    # ═══════════ PÁG 2 ═══════════

    def _build_overview(self):
        body = ctk.CTkFrame(self.page_overview, fg_color=COLORS["bg_main"])
        body.pack(fill="both", expand=True, padx=16, pady=12)
        body.grid_rowconfigure(2, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # ── Linha 1: Título + controles ──
        top = ctk.CTkFrame(body, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        if self._app_icon_img:
            ctk.CTkLabel(top, image=self._app_icon_img, text="").pack(side="left", padx=(0, 8))
        ctk.CTkLabel(top, text="Conectividade de todas as lojas",
                      font=FONTS["title"], text_color=COLORS["text_primary"]).pack(side="left")

        self.btn_scan_all = ctk.CTkButton(
            top, text="🔍  Escanear", font=FONTS["body_bold"], height=38,
            fg_color=COLORS["accent_blue"], hover_color=COLORS["hover_blue"], text_color="#FFFFFF")
        self.btn_scan_all.pack(side="right", padx=(10, 0))

        self.overview_auto_var = ctk.BooleanVar(value=True)
        self.chk_auto_scan = ctk.CTkCheckBox(
            top, text="Auto (10s)", font=FONTS["small"],
            text_color=COLORS["text_primary"], variable=self.overview_auto_var,
            checkbox_width=18, checkbox_height=18,
            fg_color=COLORS["accent_blue"], hover_color=COLORS["hover_blue"])
        self.chk_auto_scan.pack(side="right", padx=(10, 0))

        self.lbl_scan_progress = ctk.CTkLabel(top, text="", font=FONTS["small"],
                                               text_color=COLORS["text_muted"])
        self.lbl_scan_progress.pack(side="right", padx=(0, 10))

        self.entry_search = ctk.CTkEntry(top, placeholder_text="🔎 Filtrar por IP...",
                                          font=FONTS["mono"], height=36, width=200,
                                          fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                                          text_color=COLORS["text_primary"])
        self.entry_search.pack(side="right", padx=(0, 10))

        # Filtro por status: Todos / Online / Offline
        self.overview_filter_var = ctk.StringVar(value="all")
        filter_frame = ctk.CTkFrame(top, fg_color=COLORS["bg_input"], corner_radius=6,
                                     border_width=1, border_color=COLORS["border"])
        filter_frame.pack(side="right", padx=(0, 10))
        self.overview_filter_btns = {}
        for key, label in [("all", "Todos"), ("online", "🟢 Online"), ("offline", "🔴 Offline")]:
            btn = ctk.CTkButton(
                filter_frame, text=label, height=30, width=90, corner_radius=4,
                font=FONTS["small_bold"], fg_color="transparent",
                hover_color=COLORS["bg_hover"], text_color=COLORS["text_secondary"])
            btn.pack(side="left", padx=2, pady=3)
            self.overview_filter_btns[key] = btn

        # ── Linha 2: Painel de resumo ──
        summary_card = self._card(body)
        summary_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        sf = ctk.CTkFrame(summary_card, fg_color="transparent")
        sf.pack(fill="x", padx=16, pady=10)

        # Cada stat é um bloquinho
        self._ov_stats = {}
        for key, icon, label, color in [
            ("online",  "🟢", "Online",   COLORS["accent_green"]),
            ("offline", "🔴", "Offline",  COLORS["accent_red"]),
            ("clients", "👥", "Clientes", COLORS["accent_blue"]),
            ("wlans",   "📶", "Redes",    COLORS["accent_purple"]),
        ]:
            block = ctk.CTkFrame(sf, fg_color="transparent")
            block.pack(side="left", padx=(0, 30))
            val_lbl = ctk.CTkLabel(block, text="—", font=FONTS["title"], text_color=color)
            val_lbl.pack(side="left")
            desc = ctk.CTkFrame(block, fg_color="transparent")
            desc.pack(side="left", padx=(6, 0))
            ctk.CTkLabel(desc, text=icon, font=FONTS["small"]).pack(anchor="w")
            ctk.CTkLabel(desc, text=label, font=FONTS["tiny"],
                          text_color=COLORS["text_muted"]).pack(anchor="w")
            self._ov_stats[key] = val_lbl

        # Timestamp do último scan
        self.lbl_last_scan = ctk.CTkLabel(sf, text="", font=FONTS["tiny"],
                                           text_color=COLORS["text_muted"])
        self.lbl_last_scan.pack(side="right")

        # ── Linha 3: Lista de lojas ──
        lc = self._card(body)
        lc.grid(row=2, column=0, sticky="nsew")
        lc.grid_rowconfigure(0, weight=1)
        lc.grid_columnconfigure(0, weight=1)
        self.overview_scroll = ctk.CTkScrollableFrame(lc, fg_color="transparent", corner_radius=6)
        self.overview_scroll.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)


    def _build_hosts_tab(self):
        f = self.hosts_frame

        ctk.CTkLabel(f, text="GERENCIAR HOSTS", font=FONTS["section"],
                      text_color=COLORS["accent_blue"]).pack(anchor="w", padx=16, pady=(16, 2))
        ctk.CTkLabel(f, text="Gerencie todos os controllers da Visão Geral da Rede.",
                      font=FONTS["small"], text_color=COLORS["text_muted"],
                      wraplength=500).pack(anchor="w", padx=16, pady=(0, 8))

        # Campo de busca por host
        self.hosts_search = ctk.CTkEntry(
            f, placeholder_text="🔎  Filtrar por IP...",
            font=FONTS["mono"], height=34, width=260,
            fg_color=COLORS["bg_card"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"])
        self.hosts_search.pack(anchor="w", padx=16, pady=(0, 8))

        self._div(f)

        self.hosts_ip_list = ctk.CTkFrame(f, fg_color="transparent")
        self.hosts_ip_list.pack(anchor="w", padx=16, fill="x", pady=(8, 16))

    # ═══════════ HELPERS ═══════════

    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=DIMS["card_corner"],
                             border_width=DIMS["card_border"], border_color=COLORS["border"])

    def _sec(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=FONTS["section"],
                      text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(14, 8))

    def _sec_inline(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=FONTS["section"],
                      text_color=COLORS["text_secondary"]).pack(side="left")

    def _div(self, parent):
        ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1).pack(fill="x", padx=16, pady=6)