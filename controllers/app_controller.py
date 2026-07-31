#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controller: tema ao vivo via rebuild, polling completo 10s."""

import os
import sys
import re
import queue
import threading
from datetime import datetime
from time import sleep
from pathlib import Path
from tkinter import messagebox, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed

import customtkinter as ctk

from models import (
    ConfigManager, UniFiController, CPFValidationResult,
    validar_cpf, extrair_cpf_de_notes, gerar_ips_lojas,
)
from views.styles import COLORS, FONTS, apply_theme
from views import MainWindow
from utils.reports import gerar_relatorio_pdf, gerar_relatorio_txt


class AppController:

    POLL_INTERVAL = 10_000  # 10s

    def __init__(self, app_dir: Path, config: ConfigManager):
        self.app_dir = app_dir
        self.config = config
        self.unifi: UniFiController | None = None

        self.vouchers_irregulares: list[dict] = []
        self.current_tab = "log"
        self.current_page = "management"
        self._pass_visible = False
        self._poll_job = None
        self._first_activation = True
        self._log_history: list[str] = []

        self._overview_rows: dict[str, dict] = {}
        self._overview_order: list[str] = []  # preserva ordem antiga da lista (inserção)
        self._scan_running = False
        self._closing = False
        self._overview_poll_job = None

        # Fila thread-safe para resultados do scan (evita inundar a event-loop do Tkinter)
        self._scan_queue: queue.Queue = queue.Queue()
        self._scan_queue_job = None

        # Tokens para ignorar callbacks atrasados (evita bug visual ao trocar tema/filtro durante update)
        self._poll_token = 0
        self._scan_token = 0
        self._active_scan_token = 0

        theme = self.config.get("theme", "dark")
        apply_theme(theme)

        self.window = MainWindow(app_dir, theme=theme)
        self._bind_all()
        self._load_saved_config()
        self._refresh_hosts_list()

        self._log("Sistema iniciado. Insira o IP e clique em 'Conectar'.")
        if self.config.get("username"):
            self._log(f"Config carregada (usuário: {self.config.get('username')}, porta: {self.config.get('port')}).")
        else:
            self._log("Sem configuração salva — vá em 'Configurações'.", "warning")

    def run(self):
        self.window.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.window.mainloop()

    # ════════════════════════════════════════
    #  BINDINGS
    # ════════════════════════════════════════

    def _bind_all(self):
        w = self.window
        w.nav_buttons["management"].configure(command=lambda: self._switch_page("management"))
        w.nav_buttons["overview"].configure(command=lambda: self._switch_page("overview"))
        w.btn_theme.configure(command=self._on_toggle_theme)
        w.btn_connect.configure(command=self._on_connect)
        w.btn_activate.configure(command=self._on_activate)
        w.btn_check.configure(command=self._on_check_vouchers)
        w.btn_refresh.configure(command=self._on_refresh_clients)
        w.btn_report.configure(command=self._on_generate_report)
        for key, btn in w.tab_buttons.items():
            btn.configure(command=lambda k=key: self._switch_tab(k))
        w.btn_save_cfg.configure(command=self._on_save_settings)
        w.btn_toggle_pass.configure(command=self._toggle_pass)
        w.btn_add_ip.configure(command=self._on_add_custom_ip)
        w.btn_scan_all.configure(command=self._on_scan_all)
        w.entry_search.bind("<KeyRelease>", lambda e: (self._scroll_overview_to_top(), self._filter_overview()))
        w.hosts_search.bind("<KeyRelease>", lambda e: self._filter_hosts_list())
        for key, btn in w.overview_filter_btns.items():
            btn.configure(command=lambda k=key: self._set_overview_filter(k))
        # Aplicar visual do filtro sem chamar _filter_overview (widgets podem não existir ainda)
        for k, btn in w.overview_filter_btns.items():
            if k == "all":
                btn.configure(fg_color=COLORS["accent_blue"], text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])
        w.overview_filter_var.set("all")
        # Autocomplete do campo IP
        w.entry_ip.bind("<KeyRelease>", lambda e: self._on_ip_keyrelease())
        w.entry_ip.bind("<FocusOut>",   lambda e: w.after(150, self._hide_ip_dropdown))
        w.entry_ip.bind("<Escape>",     lambda e: self._hide_ip_dropdown())
        w.entry_ip.bind("<Return>",     lambda e: (self._hide_ip_dropdown(), self._on_connect()))
        self._switch_tab("log")
        self._switch_page("management")

    # ════════════════════════════════════════
    #  AUTOCOMPLETE DO CAMPO IP
    # ════════════════════════════════════════

    MAX_SUGGESTIONS = 9999

    def _all_ips(self) -> list[str]:
        """Lista todos os IPs disponíveis (padrão + custom, sem excluídos)."""
        port = self.config.get("port", "8443")
        custom = self.config.get("custom_ips", [])
        excluded = set(self.config.get("excluded_ips", []))
        return [l["ip"] for l in gerar_ips_lojas(port, custom) if l["ip"] not in excluded]

    def _on_ip_keyrelease(self):
        query = self.window.entry_ip.get().strip()
        if not query:
            self._hide_ip_dropdown()
            return
        matches = [ip for ip in self._all_ips() if query in ip][:self.MAX_SUGGESTIONS]
        if not matches or (len(matches) == 1 and matches[0] == query):
            self._hide_ip_dropdown()
            return
        self._show_ip_dropdown(matches)

    def _show_ip_dropdown(self, ips: list[str]):
        w = self.window
        dd = w.ip_dropdown            # CTkScrollableFrame
        outer = w._ip_dropdown_outer  # tk.Frame filho da janela raiz

        # Limpa sugestões antigas
        for child in list(dd.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        for ip in ips:
            btn = ctk.CTkButton(
                dd, text=ip, anchor="w", height=30, corner_radius=4,
                font=FONTS["mono"], fg_color="transparent",
                hover_color=COLORS["bg_hover"], text_color=COLORS["text_primary"],
                command=lambda i=ip: self._pick_ip(i))
            btn.pack(fill="x", padx=4, pady=1)

        # Rola para o topo sempre que a lista é atualizada
        dd.update_idletasks()
        for attr in ("_parent_canvas", "_canvas", "canvas"):
            c = getattr(dd, attr, None)
            if c is not None:
                try:
                    c.yview_moveto(0.0)
                    break
                except Exception:
                    pass

        # Posição absoluta do entry_ip na janela raiz
        entry = w.entry_ip
        entry.update_idletasks()
        abs_x = entry.winfo_rootx() - w.winfo_rootx()
        abs_y = entry.winfo_rooty() - w.winfo_rooty() + entry.winfo_height() + 2
        ew = entry.winfo_width()
        # place() relativo à janela raiz — flutua sobre todos os outros widgets
        outer.place(x=abs_x, y=abs_y, width=ew, height=172)
        outer.lift()

    def _hide_ip_dropdown(self):
        try:
            self.window._ip_dropdown_outer.place_forget()
        except Exception:
            pass

    def _pick_ip(self, ip: str):
        w = self.window
        w.entry_ip.delete(0, "end")
        w.entry_ip.insert(0, ip)
        self._hide_ip_dropdown()


    def _load_saved_config(self):
        w = self.window
        cfg = self.config
        if cfg.get("last_ip"):
            w.entry_ip.insert(0, cfg.get("last_ip"))
        if cfg.get("username"):
            w.cfg_user.insert(0, cfg.get("username"))
        if cfg.get("password"):
            w.cfg_pass.insert(0, cfg.get("password"))
        if cfg.get("port"):
            w.cfg_port.delete(0, "end")
            w.cfg_port.insert(0, cfg.get("port"))
        w.switch_online.set(cfg.get("validate_cpf_online", True))

    # ════════════════════════════════════════
    #  TEMA — TROCA INSTANTÂNEA VIA REBUILD
    # ════════════════════════════════════════

    def _on_toggle_theme(self):
        """Troca o tema reconstruindo a UI dentro da mesma janela."""
        current = self.config.get("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"

        self.config.set("theme", new_theme)
        self.config.save()

        # Invalida callbacks em voo (evita glitch ao trocar tema durante atualização/scan)
        self._poll_token += 1
        self._scan_token += 1
        self._active_scan_token = self._scan_token
        self._scan_running = False

        # Salvar estado
        connected = self.unifi is not None and self.unifi.logged_in
        saved_tab = self.current_tab
        saved_page = self.current_page

        # Salvar dados do scan da visão geral (só os dados, não os widgets)
        saved_scan: dict[str, dict | None] = {}
        saved_scan_order: list[str] = []
        for ip, row in self._overview_rows.items():
            saved_scan[ip] = row.get("data")
            saved_scan_order.append(ip)

        # Parar polling
        self._stop_polling()
        self._stop_overview_polling()
        self._overview_rows.clear()

        # Atualizar paleta global
        apply_theme(new_theme)

        # Reconstruir toda a UI (sem destruir a janela raiz)
        self.window.rebuild(new_theme)

        # Re-bind tudo nos novos widgets
        self._bind_all()
        self._load_saved_config()
        self._refresh_hosts_list()

        # Restaurar log
        tb = self.window.log_textbox
        tb.configure(state="normal")
        for line in self._log_history:
            tb.insert("end", line)
        tb.see("end")
        tb.configure(state="disabled")

        # Restaurar estado de conexão
        if connected:
            self.window.lbl_status.configure(text="● Conectado", text_color=COLORS["accent_green"])
            self.window.btn_connect.configure(text="Reconectar")
            self._set_actions("normal")
            self._load_wlans()
            self._load_devices()
            self._start_polling()
            # Reinicia o scan background (foi parado pelo _stop_overview_polling acima).
            # _start_overview_polling é idempotente, então é seguro chamar aqui mesmo
            # que _switch_page(saved_page) logo abaixo também o chame para a overview.
            self._start_overview_polling()

        # Restaurar visão geral da rede (recriar linhas com dados salvos)
        if saved_scan:
            self._overview_rows.clear()
            for ip in saved_scan_order:
                self._create_row(ip)
                data = saved_scan[ip]
                if data is not None:
                    self._update_row(ip, data, 0, 0)
            # Atualizar progresso
            total = len(saved_scan)
            online = sum(1 for d in saved_scan.values() if d and d.get("status") == "online")
            self.window.lbl_scan_progress.configure(
                text=f"✓ {online}/{total} online")
            self._update_summary_panel()

        # Restaurar página e tab
        self._switch_page(saved_page)
        self._switch_tab(saved_tab)

        # Reaplicar filtro com ordenação correta após rebuild
        if saved_scan:
            self._filter_overview()

        self._log(f"Tema: {'Claro' if new_theme == 'light' else 'Escuro'}.", "success")

    # ════════════════════════════════════════
    #  NAVEGAÇÃO
    # ════════════════════════════════════════

    def _switch_page(self, page):
        self.current_page = page
        w = self.window
        for k, btn in w.nav_buttons.items():
            if k == page:
                btn.configure(fg_color=COLORS["accent_blue"], text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])
        w.page_management.grid_forget()
        w.page_overview.grid_forget()
        (w.page_management if page == "management" else w.page_overview).grid(row=0, column=0, sticky="nsew")

        if page == "overview":
            # Garante que o polling está ativo
            self._start_overview_polling()
            # Força o Tkinter a processar eventos de layout pendentes ANTES do filtro.
            # Sem isso, na primeira visita o CTkScrollableFrame ainda tem canvas 0×0
            # (nunca foi exibido) e as linhas já criadas em background ficam invisíveis.
            w.update_idletasks()
            # Delay maior (150ms) garante que o Configure do canvas já disparou
            # e que a largura real do scroll foi propagada antes de pack/pack_forget.
            def _first_refresh():
                try:
                    w.overview_scroll.update_idletasks()
                except Exception:
                    pass
                self._update_summary_panel()
                self._filter_overview()
            w.after(150, _first_refresh)
        # Ao SAIR da overview o scan NÃO é parado — continua em background.
        # Assim, quando o usuário voltar, os dados já estarão atualizados.

    def _switch_tab(self, tab):
        self.current_tab = tab
        w = self.window
        for widget in [w.log_textbox, w.devices_textbox, w.vouchers_textbox,
                        w.settings_frame, w.hosts_frame]:
            widget.grid_forget()
        for btn in w.tab_buttons.values():
            btn.configure(fg_color=COLORS["bg_input"], text_color=COLORS["text_secondary"], font=FONTS["tab"])
        m = {"log": w.log_textbox, "devices": w.devices_textbox,
             "vouchers": w.vouchers_textbox, "settings": w.settings_frame,
             "hosts": w.hosts_frame}
        t = m.get(tab)
        if t:
            t.grid(row=0, column=0, sticky="nsew")
            w.tab_buttons[tab].configure(fg_color=COLORS["accent_blue"], text_color="#FFFFFF", font=FONTS["tab_active"])

    # ════════════════════════════════════════
    #  LOG
    # ════════════════════════════════════════

    def _log(self, msg, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        px = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "•")
        line = f"[{ts}] {px}  {msg}\n"
        self._log_history.append(line)
        if len(self._log_history) > 500:
            self._log_history = self._log_history[-500:]
        tb = self.window.log_textbox
        tb.configure(state="normal")
        tb.insert("end", line)
        tb.see("end")
        tb.configure(state="disabled")

    # ════════════════════════════════════════
    #  CONFIG
    # ════════════════════════════════════════

    def _toggle_pass(self):
        self._pass_visible = not self._pass_visible
        self.window.cfg_pass.configure(show="" if self._pass_visible else "•")
        self.window.btn_toggle_pass.configure(text="🔒" if self._pass_visible else "👁")

    def _on_save_settings(self):
        w = self.window
        user = w.cfg_user.get().strip()
        pw = w.cfg_pass.get().strip()
        port = w.cfg_port.get().strip() or "8443"
        if not user:
            messagebox.showwarning("Atenção", "Informe o usuário.")
            return
        if not pw:
            messagebox.showwarning("Atenção", "Informe a senha.")
            return
        self.config.update(username=user, password=pw, port=port,
                           validate_cpf_online=w.switch_online.get())
        self.config.save()
        w.lbl_cfg_status.configure(text=f"✓  Salvo em {datetime.now().strftime('%H:%M:%S')}",
                                    text_color=COLORS["accent_green"])
        self._log("Configurações salvas.", "success")

    def _get_creds(self):
        u = self.window.cfg_user.get().strip()
        p = self.window.cfg_pass.get().strip()
        port = self.window.cfg_port.get().strip() or "8443"
        return (u, p, port) if u and p else None

    def _set_actions(self, state):
        w = self.window
        w.btn_activate.configure(state=state)
        w.btn_check.configure(state=state)
        w.btn_refresh.configure(state=state)
        if state == "normal" and self.vouchers_irregulares:
            w.btn_report.configure(state="normal")
        elif state == "disabled":
            w.btn_report.configure(state="disabled")

    # ════════════════════════════════════════
    #  IPs PERSONALIZADOS
    # ════════════════════════════════════════

    def _on_add_custom_ip(self):
        ip = self.window.entry_custom_ip.get().strip()
        if not ip:
            return
        if not re.match(r'^\d{1,3}(\.\d{1,3}){3}$', ip):
            messagebox.showwarning("IP inválido", f"'{ip}' não é um IP válido.")
            return
        custom = self.config.get("custom_ips", [])
        excluded = self.config.get("excluded_ips", [])
        if ip in custom:
            self._show_add_status(f"⚠  {ip} já está na lista.", warning=True)
            return
        # Se estava na lista de excluídos, remove da exclusão
        if ip in excluded:
            excluded.remove(ip)
            self.config.set("excluded_ips", excluded)
        custom.append(ip)
        self.config.set("custom_ips", custom)
        self.config.save()
        self.window.entry_custom_ip.delete(0, "end")
        self._refresh_hosts_list()
        self._log(f"Host adicionado: {ip}", "success")
        self._show_add_status(f"✓  {ip} adicionado com sucesso.")
        self._reset_overview_and_rescan()

    def _on_remove_host(self, ip):
        """Remove host: custom → tira da lista; padrão → adiciona aos excluídos."""
        custom = self.config.get("custom_ips", [])
        excluded = self.config.get("excluded_ips", [])
        if ip in custom:
            custom.remove(ip)
            self.config.set("custom_ips", custom)
        elif ip not in excluded:
            excluded.append(ip)
            self.config.set("excluded_ips", excluded)
        self.config.save()
        self._refresh_hosts_list()
        self._log(f"Host removido: {ip}", "info")
        self._reset_overview_and_rescan()

    def _restore_host(self, ip):
        excluded = self.config.get("excluded_ips", [])
        if ip in excluded:
            excluded.remove(ip)
            self.config.set("excluded_ips", excluded)
            self.config.save()
            self._refresh_hosts_list()
            self._log(f"Host restaurado: {ip}", "success")
            self._reset_overview_and_rescan()

    def _reset_overview_and_rescan(self):
        self._scan_token += 1
        self._active_scan_token = self._scan_token
        self._scan_running = False
        if self._scan_queue_job is not None:
            try:
                self.window.after_cancel(self._scan_queue_job)
            except Exception:
                pass
            self._scan_queue_job = None
        while not self._scan_queue.empty():
            try:
                self._scan_queue.get_nowait()
            except Exception:
                break
        for row in self._overview_rows.values():
            try:
                row["container"].destroy()
            except Exception:
                pass
        self._overview_rows.clear()
        self._overview_order.clear()
        try:
            for child in self.window.overview_scroll.winfo_children():
                child.destroy()
        except Exception:
            pass
        try:
            self.window.lbl_scan_progress.configure(text="")
        except Exception:
            pass
        creds = self._get_creds()
        if creds and not self._closing:
            self.window.after(200, lambda: self._run_scan(creds) if not self._closing else None)

    def _refresh_hosts_list(self, query: str = ""):
        """Popula a aba Hosts: ativos (com ✕ Remover) e excluídos (com ↩ Restaurar).

        Usa um frame interno regular como container dos itens para evitar
        problemas ao chamar winfo_children() + destroy() num CTkScrollableFrame.
        Se `query` for informado, exibe apenas hosts cujo IP contenha o texto.
        """
        outer = self.window.hosts_ip_list   # CTkScrollableFrame (altura fixa ~6 itens)

        # Destroi apenas o wrapper interno (não os frames internos do CTK)
        for child in outer.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(fill="x")

        port      = self.config.get("port", "8443")
        custom    = self.config.get("custom_ips", [])
        excluded  = set(self.config.get("excluded_ips", []))

        from models import gerar_ips_lojas
        ip_sort      = lambda x: tuple(int(p) for p in x.split('.'))
        default_set  = {l["ip"] for l in gerar_ips_lojas(port)}          # sem custom
        todos        = gerar_ips_lojas(port, custom)
        q            = query.strip().lower()
        ativos       = sorted([l["ip"] for l in todos if l["ip"] not in excluded and (not q or q in l["ip"])], key=ip_sort)
        inativos     = sorted([l["ip"] for l in todos if l["ip"] in excluded     and (not q or q in l["ip"])], key=ip_sort)

        def _row(ip, removable=True):
            is_default = ip in default_set
            row = ctk.CTkFrame(inner, fg_color=COLORS["bg_card"], corner_radius=6,
                                height=36, border_width=1, border_color=COLORS["border"])
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text="🔧" if is_default else "🖥", font=FONTS["small"],
                          text_color=COLORS["text_muted"]).pack(side="left", padx=(8, 4))
            ctk.CTkLabel(row, text=ip, font=FONTS["mono"],
                          text_color=COLORS["text_primary"]).pack(side="left")
            ctk.CTkLabel(row, text="Padrão" if is_default else "Personalizado",
                          font=FONTS["tiny"], text_color=COLORS["text_muted"]).pack(side="left", padx=(8, 0))
            if removable:
                ctk.CTkButton(row, text="✕ Remover", width=90, height=24, corner_radius=4,
                               font=FONTS["small_bold"], fg_color=COLORS["bg_error"],
                               hover_color=COLORS["hover_red"], text_color=COLORS["accent_red"],
                               command=lambda i=ip: self._on_remove_host(i)
                               ).pack(side="right", padx=(0, 6))
            else:
                ctk.CTkButton(row, text="↩ Restaurar", width=90, height=24, corner_radius=4,
                               font=FONTS["small_bold"], fg_color=COLORS["bg_warning"],
                               hover_color=COLORS["hover_orange"], text_color=COLORS["accent_orange"],
                               command=lambda i=ip: self._restore_host(i)
                               ).pack(side="right", padx=(0, 6))

        LIMIT = 5

        # ── Ativos ──
        ctk.CTkLabel(inner, text=f"HOSTS ATIVOS  ({len(ativos)})",
                      font=FONTS["small_bold"], text_color=COLORS["text_secondary"]
                      ).pack(anchor="w", pady=(0, 4))
        if not ativos:
            ctk.CTkLabel(inner, text="Nenhum host ativo.",
                          font=FONTS["small"], text_color=COLORS["text_muted"]).pack(anchor="w")
        else:
            # Mostra os primeiros LIMIT itens; os demais ficam num frame colapsável
            for ip in ativos[:LIMIT]:
                _row(ip, removable=True)

            extras = ativos[LIMIT:]
            if extras:
                extra_frame = ctk.CTkFrame(inner, fg_color="transparent")

                btn_expand = ctk.CTkButton(
                    inner, text=f"▼  Ver mais {len(extras)} host(s)",
                    font=FONTS["small"], height=28, corner_radius=6,
                    fg_color="transparent", hover_color=COLORS["bg_hover"],
                    border_width=1, border_color=COLORS["border"],
                    text_color=COLORS["text_secondary"])
                btn_expand.pack(anchor="w", pady=(4, 0))

                def _toggle(ef=extra_frame, ips=extras, btn=btn_expand):
                    if ef.winfo_ismapped():
                        ef.pack_forget()
                        btn.configure(text=f"▼  Ver mais {len(ips)} host(s)")
                        self._scroll_frame_to_top(self.window.hosts_frame)
                    else:
                        ef.pack(fill="x", before=btn)
                        btn.configure(text=f"▲  Recolher")
                        for ip in ips:
                            # cria as linhas dentro do extra_frame (só na primeira expansão)
                            if not ef.winfo_children():
                                for xip in ips:
                                    _row_in(xip, ef, removable=True)

                def _row_in(ip, parent, removable=True):
                    is_default = ip in default_set
                    row = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=6,
                                        height=36, border_width=1, border_color=COLORS["border"])
                    row.pack(fill="x", pady=2)
                    row.pack_propagate(False)
                    ctk.CTkLabel(row, text="🔧" if is_default else "🖥", font=FONTS["small"],
                                  text_color=COLORS["text_muted"]).pack(side="left", padx=(8, 4))
                    ctk.CTkLabel(row, text=ip, font=FONTS["mono"],
                                  text_color=COLORS["text_primary"]).pack(side="left")
                    ctk.CTkLabel(row, text="Padrão" if is_default else "Personalizado",
                                  font=FONTS["tiny"], text_color=COLORS["text_muted"]).pack(side="left", padx=(8, 0))
                    if removable:
                        ctk.CTkButton(row, text="✕ Remover", width=90, height=24, corner_radius=4,
                                       font=FONTS["small_bold"], fg_color=COLORS["bg_error"],
                                       hover_color=COLORS["hover_red"], text_color=COLORS["accent_red"],
                                       command=lambda i=ip: self._on_remove_host(i)
                                       ).pack(side="right", padx=(0, 6))
                    else:
                        ctk.CTkButton(row, text="↩ Restaurar", width=90, height=24, corner_radius=4,
                                       font=FONTS["small_bold"], fg_color=COLORS["bg_warning"],
                                       hover_color=COLORS["hover_orange"], text_color=COLORS["accent_orange"],
                                       command=lambda i=ip: self._restore_host(i)
                                       ).pack(side="right", padx=(0, 6))

                btn_expand.configure(command=_toggle)

        # ── Removidos ──
        if inativos:
            ctk.CTkFrame(inner, fg_color=COLORS["border"], height=1).pack(fill="x", pady=(10, 6))
            ctk.CTkLabel(inner, text=f"HOSTS REMOVIDOS  ({len(inativos)})",
                          font=FONTS["small_bold"], text_color=COLORS["text_secondary"]
                          ).pack(anchor="w", pady=(0, 4))
            for ip in inativos:
                _row(ip, removable=False)

    def _show_add_status(self, msg: str, warning: bool = False):
        """Feedback inline no campo de adicionar host (desaparece em 3s)."""
        lbl = getattr(self.window, "lbl_add_ip_status", None)
        if not lbl:
            return
        color = COLORS["accent_orange"] if warning else COLORS["accent_green"]
        lbl.configure(text=msg, text_color=color)
        self.window.after(3000, lambda: lbl.configure(text="") if lbl.winfo_exists() else None)

    
    # ════════════════════════════════════════
    #  CONEXÃO
    # ════════════════════════════════════════

    def _on_connect(self):
        w = self.window
        ip = w.entry_ip.get().strip()
        if not ip:
            messagebox.showwarning("Atenção", "Informe o IP.")
            return
        creds = self._get_creds()
        if not creds:
            messagebox.showwarning("Config", "Defina credenciais na aba Configurações.")
            self._switch_tab("settings")
            return
        user, pw, port = creds
        self.config.set("last_ip", ip)
        self.config.save()
        w.btn_connect.configure(state="disabled", text="Conectando...")
        self._log(f"Conectando a {ip}:{port}...")

        def _work():
            self.unifi = UniFiController(ip, port, user, pw)
            ok, msg = self.unifi.login()
            w.after(0, lambda: self._on_connect_done(ok, msg))

        threading.Thread(target=_work, daemon=True).start()

    def _on_connect_done(self, ok, msg):
        w = self.window
        if ok:
            self._log(msg, "success")
            w.lbl_status.configure(text="● Conectado", text_color=COLORS["accent_green"])
            w.btn_connect.configure(text="Reconectar", state="normal")
            self._set_actions("normal")
            self._load_wlans()
            self._load_devices()
            # Iniciar polling contínuo (devices + vouchers + antenas a cada 10s)
            self._start_polling()
            # Inicia scan de visão geral em background imediatamente após conectar,
            # mesmo que o usuário esteja na aba de Gerenciamento. Assim, quando
            # navegar para Visão Geral, os dados já estarão prontos ou atualizando.
            self._start_overview_polling()
        else:
            self._log(msg, "error")
            w.btn_connect.configure(text="Conectar", state="normal")
            messagebox.showerror("Erro", msg)

    # ════════════════════════════════════════════════════════════
    #  POLLING CONTÍNUO (10s) — ATUALIZA TUDO: DEVICES + VOUCHERS + ANTENAS
    # ════════════════════════════════════════════════════════════

    def _start_polling(self):
        """Inicia o polling que atualiza Dispositivos, Vouchers e Antenas a cada 10s."""
        self._stop_polling()
        self._log("Polling ativo: Dispositivos, Vouchers e Antenas a cada 10s.")
        self.window.lbl_auto_refresh.configure(text="🟢 Atualizando a cada 10s",
                                                text_color=COLORS["accent_green"])
        self._poll_tick()

    def _stop_polling(self):
        # Invalida callbacks já em voo
        self._poll_token += 1
        if self._poll_job:
            self.window.after_cancel(self._poll_job)
            self._poll_job = None

    def _poll_tick(self):
        """Um ciclo: busca clients + devices + vouchers em thread, agenda o próximo."""
        if self._closing or not self.unifi or not self.unifi.logged_in:
            return

        # Token para descartar resultados atrasados (ex.: troca de tema durante update)
        self._poll_token += 1
        token = self._poll_token

        def _fetch(local_token=token):
            if self._closing:
                return
            try:
                clients = self.unifi.get_online_clients()
                devices = self.unifi.get_devices()
                vouchers = self.unifi.get_vouchers()
            except Exception:
                clients, devices, vouchers = [], [], []
            if not self._closing:
                self.window.after(0, lambda: self._on_poll_result(clients, devices, vouchers, local_token))

        threading.Thread(target=_fetch, daemon=True).start()
        # Agendar próximo tick independente do resultado
        self._poll_job = self.window.after(self.POLL_INTERVAL, self._poll_tick)

    def _on_poll_result(self, clients, devices, vouchers, token=None):
        """Callback do polling — atualiza as 3 áreas."""
        if self._closing:
            return
        if token is not None and token != self._poll_token:
            # Resultado atrasado (ex.: usuário trocou tema/página no meio do update)
            return
        # 1) Aba Dispositivos
        self._update_devices_textbox(clients, silent=True)
        # 2) Painel Antenas (direita)
        self._display_devices_panel(devices)
        # 3) Aba Vouchers
        self._update_vouchers_textbox(vouchers)
        # Timestamp
        ts = datetime.now().strftime('%H:%M:%S')
        self.window.lbl_auto_refresh.configure(text=f"🟢 {ts}  •  a cada 10s")

    # ════════════════════════════════════════
    #  VOUCHERS — ATUALIZAÇÃO PERIÓDICA
    # ════════════════════════════════════════

    def _update_vouchers_textbox(self, vouchers):
        """Atualiza a aba Vouchers com dados atuais (sem re-validar CPF)."""
        tb = self.window.vouchers_textbox
        tb.configure(state="normal")
        tb.delete("1.0", "end")

        if not vouchers:
            tb.insert("end", "  Nenhum voucher ativo.\n")
        else:
            tb.insert("end", f"  VOUCHERS ATIVOS ({len(vouchers)}):\n")
            tb.insert("end", "  " + "─" * 80 + "\n")
            tb.insert("end", f"  {'CÓDIGO':<14} {'CRIAÇÃO':<18} {'NOTES':<35} {'USOS':<10}\n")
            tb.insert("end", "  " + "─" * 80 + "\n")
            for v in vouchers:
                code = v.get('code', 'N/A')
                ct = v.get('create_time', 0)
                try:
                    cs = datetime.fromtimestamp(ct).strftime('%d/%m/%Y %H:%M') if ct else 'N/A'
                except Exception:
                    cs = '—'
                notes = (v.get('note', v.get('notes', '')) or '—')[:33]
                used = f"{v.get('used', 0)}/{v.get('quota', 1)}"
                tb.insert("end", f"  {code:<14} {cs:<18} {notes:<35} {used:<10}\n")
            tb.insert("end", f"\n  Atualizado: {datetime.now().strftime('%H:%M:%S')}\n")

        # Irregulares da última verificação
        if self.vouchers_irregulares:
            tb.insert("end", f"\n  {'═' * 80}\n")
            tb.insert("end", f"  IRREGULARES ({len(self.vouchers_irregulares)}):\n")
            tb.insert("end", f"  {'═' * 80}\n\n")
            for i, v in enumerate(self.vouchers_irregulares, 1):
                code = v.get('code', 'N/A')
                val = v.get('_validation')
                tb.insert("end", f"  [{i}] {code}")
                if val:
                    ic = {"invalid": " ❌", "suspect": " ⚠️", "valid": " ✅"}.get(val.risk_level, "")
                    lb = {"invalid": "INVÁLIDO", "suspect": "SUSPEITO", "valid": "VÁLIDO"}.get(val.risk_level, "?")
                    tb.insert("end", f"  {ic} {lb}")
                    if val.risk_reasons:
                        tb.insert("end", f"  — {', '.join(val.risk_reasons)}")
                else:
                    tb.insert("end", "  ❌ Sem CPF")
                tb.insert("end", "\n")

        tb.configure(state="disabled")

    # ════════════════════════════════════════
    #  DISPOSITIVOS CONECTADOS
    # ════════════════════════════════════════

    def _update_devices_textbox(self, clients, silent=False):
        tb = self.window.devices_textbox
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        if not clients:
            tb.insert("end", "  Nenhum dispositivo conectado.\n")
        else:
            tb.insert("end", f"  {'DISPOSITIVO':<28} {'IP':<17} {'MAC':<20} {'REDE':<18} {'SINAL':<8}\n")
            tb.insert("end", "  " + "─" * 91 + "\n")
            for c in sorted(clients, key=lambda x: x.get('essid', '')):
                nm = c.get('name', c.get('hostname', 'Desconhecido'))[:26]
                ip = c.get('ip', 'N/A')
                mac = c.get('mac', 'N/A')
                ssid = c.get('essid', 'N/A')[:16]
                sig = c.get('signal', c.get('rssi', 'N/A'))
                ss = f"{sig} dBm" if isinstance(sig, int) else str(sig)
                tb.insert("end", f"  {nm:<28} {ip:<17} {mac:<20} {ssid:<18} {ss:<8}\n")
            tb.insert("end", f"\n  Total: {len(clients)} • {datetime.now().strftime('%H:%M:%S')}\n")
        tb.configure(state="disabled")
        if not silent:
            self._log(f"{len(clients)} dispositivo(s) conectado(s).")
            self._switch_tab("devices")

    # ════════════════════════════════════════
    #  WLANs
    # ════════════════════════════════════════

    def _load_wlans(self):
        if not self.unifi:
            return
        def _work():
            wlans = self.unifi.get_wlans()
            self.window.after(0, lambda: self._display_wlans(wlans))
        threading.Thread(target=_work, daemon=True).start()

    def _display_wlans(self, wlans):
        w = self.window
        for child in w.wlan_container.winfo_children():
            child.destroy()
        if not wlans:
            ctk.CTkLabel(w.wlan_container, text="Nenhuma rede encontrada.",
                          font=FONTS["body"], text_color=COLORS["text_muted"]).pack(pady=10)
            return
        w.lbl_wlan_count.configure(text=f"{len(wlans)} rede(s)")
        for wlan in wlans:
            name = wlan.get('name', 'N/A')
            enabled = wlan.get('enabled', False)
            security = wlan.get('security', 'N/A')
            is_guest = wlan.get('is_guest', False)
            row = ctk.CTkFrame(w.wlan_container, fg_color=COLORS["bg_input"], corner_radius=6, height=36)
            row.pack(fill="x", pady=2); row.pack_propagate(False)
            sc = COLORS["accent_green"] if enabled else COLORS["accent_red"]
            ctk.CTkLabel(row, text="●", font=FONTS["body"], text_color=sc).pack(side="left", padx=(10, 6))
            ctk.CTkLabel(row, text=name, font=FONTS["mono_bold"],
                          text_color=COLORS["text_primary"]).pack(side="left")
            if is_guest:
                ctk.CTkLabel(row, text="GUEST", font=FONTS["badge"], text_color=COLORS["accent_orange"],
                              fg_color=COLORS["bg_warning"], corner_radius=4, width=48).pack(side="left", padx=(8, 0))
            ctk.CTkLabel(row, text=security.upper(), font=FONTS["tiny"],
                          text_color=COLORS["text_muted"]).pack(side="left", padx=(8, 0))
            ctk.CTkLabel(row, text="ON" if enabled else "OFF", font=FONTS["small_bold"],
                          text_color=sc, width=30).pack(side="right", padx=(0, 12))
        ec = sum(1 for x in wlans if x.get('enabled'))
        self._log(f"Redes: {len(wlans)} total, {ec} ativa(s).")

    # ════════════════════════════════════════
    #  ANTENAS
    # ════════════════════════════════════════

    def _load_devices(self):
        if not self.unifi:
            return
        def _work():
            devices = self.unifi.get_devices()
            self.window.after(0, lambda: self._display_devices_panel(devices))
        threading.Thread(target=_work, daemon=True).start()

    def _display_devices_panel(self, devices):
        w = self.window
        scroll = w.antenna_scroll
        for child in scroll.winfo_children():
            child.destroy()
        if not devices:
            ctk.CTkLabel(scroll, text="Nenhum dispositivo.", font=FONTS["small"],
                          text_color=COLORS["text_muted"]).pack(pady=30)
            w.lbl_antenna_status.configure(text="0")
            return
        w.lbl_antenna_status.configure(text=f"{len(devices)}")
        for dev in devices:
            name = dev.get('name', dev.get('model', 'Desconhecido'))
            model = dev.get('model', '')
            dt = dev.get('type', '')
            state = dev.get('state', 0)
            adopted = dev.get('adopted', False)
            ip = dev.get('ip', 'N/A')
            uptime = dev.get('uptime', 0)
            if state == 1 and adopted:
                st, sc, sb = "Conectado", COLORS["accent_green"], COLORS["bg_success"]
            elif state in (1, 5):
                st, sc, sb = "Provisionando", COLORS["accent_orange"], COLORS["bg_warning"]
            elif state == 2:
                st, sc, sb = "Adotando", COLORS["accent_blue"], COLORS["bg_info"]
            elif state == 4:
                st, sc, sb = "Atualizando", COLORS["accent_purple"], COLORS["bg_info"]
            else:
                st, sc, sb = "Offline", COLORS["accent_red"], COLORS["bg_error"]
            icon = {"uap": "📡", "usw": "🔗", "ugw": "🌐", "udm": "🏠"}.get(dt, "📦")
            if uptime and state == 1:
                d, h, m = uptime // 86400, (uptime % 86400) // 3600, (uptime % 3600) // 60
                ut = f"{d}d {h}h" if d else (f"{h}h {m}m" if h else f"{m}m")
            else:
                ut = "—"
            card = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"], corner_radius=8,
                                 border_width=1, border_color=COLORS["border_light"])
            card.pack(fill="x", pady=3, padx=2)
            r1 = ctk.CTkFrame(card, fg_color="transparent")
            r1.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(r1, text=icon, font=FONTS["body"], width=22).pack(side="left")
            ctk.CTkLabel(r1, text=name, font=FONTS["small_bold"],
                          text_color=COLORS["text_primary"]).pack(side="left", padx=(4, 0))
            ctk.CTkLabel(r1, text=st, font=FONTS["badge"], text_color=sc,
                          fg_color=sb, corner_radius=4, width=85, height=20).pack(side="right")
            r2 = ctk.CTkFrame(card, fg_color="transparent")
            r2.pack(fill="x", padx=10, pady=(0, 8))
            ctk.CTkLabel(r2, text=f"{model}  •  {ip}  •  ⏱ {ut}",
                          font=FONTS["tiny"], text_color=COLORS["text_muted"]).pack(side="left")

    # ════════════════════════════════════════
    #  ATIVAR REDES
    # ════════════════════════════════════════

    def _on_activate(self):
        if not self.unifi or not self.unifi.logged_in:
            return
        self.window.btn_activate.configure(state="disabled", text="Ativando...")
        self._log("Iniciando ativação...")
        use_online = self.window.switch_online.get()

        def _work():
            wlans = self.unifi.get_wlans()
            activated, errors = [], []
            for wl in wlans:
                n, wid, en = wl.get('name', ''), wl.get('_id', ''), wl.get('enabled', False)
                if not en:
                    (activated if self.unifi.enable_wlan(wid, n) else errors).append(n)
            vouchers = self.unifi.get_vouchers()
            irreg = self._analisar_vouchers(vouchers, use_online)
            deletados = [v for v in irreg if v.get('_id') and self.unifi.delete_voucher(v['_id'])]
            sleep(3)
            clients = self.unifi.get_online_clients()
            devices = self.unifi.get_devices()
            updated_wlans = self.unifi.get_wlans()
            self.window.after(0, lambda: self._on_activate_done(
                activated, errors, irreg, deletados, clients, devices, updated_wlans))

        threading.Thread(target=_work, daemon=True).start()

    def _analisar_vouchers(self, vouchers, use_online):
        irregulares = []
        for v in vouchers:
            notes = v.get('note', v.get('notes', ''))
            cpf_str = extrair_cpf_de_notes(notes) if notes else None
            if not notes or not notes.strip():
                v['_validation'] = None; irregulares.append(v)
            elif cpf_str is None:
                v['_validation'] = None; irregulares.append(v)
            else:
                result = validar_cpf(cpf_str, tentar_online=use_online)
                v['_validation'] = result
                if result.risk_level in ("invalid", "suspect"):
                    irregulares.append(v)
        return irregulares

    def _on_activate_done(self, activated, errors, irreg, deletados, clients, devices, wlans):
        w = self.window
        w.btn_activate.configure(state="normal", text="⚡  Ativar Redes Wi-Fi")
        for n in activated:
            self._log(f"Rede '{n}' ATIVADA!", "success")
        if not activated:
            self._log("Redes já estavam ativas.", "info")
        for n in errors:
            self._log(f"FALHA '{n}'!", "error")
        if irreg:
            self._log(f"{len(irreg)} voucher(s) irregular(es).", "warning")
            for v in irreg:
                code = v.get('code', '?')
                val = v.get('_validation')
                if val and val.risk_level == "suspect":
                    self._log(f"  {code}: SUSPEITO — {', '.join(val.risk_reasons)}", "warning")
                elif val and val.risk_level == "invalid":
                    self._log(f"  {code}: INVÁLIDO — {', '.join(val.risk_reasons)}", "error")
                else:
                    self._log(f"  {code}: Sem CPF", "error")
            self.vouchers_irregulares = irreg
            w.btn_report.configure(state="normal")
            if deletados:
                self._log(f"{len(deletados)} deletado(s).", "success")
        else:
            self._log("Vouchers OK.", "success")
            self.vouchers_irregulares = []
        self._update_devices_textbox(clients)
        self._display_devices_panel(devices)
        self._display_wlans(wlans)
        self._log("Ativação concluída!", "success")
        if self._first_activation:
            self._first_activation = False
            self._switch_tab("devices")

    # ════════════════════════════════════════
    #  CHECK VOUCHERS / REFRESH / RELATÓRIO
    # ════════════════════════════════════════

    def _on_check_vouchers(self):
        if not self.unifi or not self.unifi.logged_in:
            return
        self.window.btn_check.configure(state="disabled", text="Verificando...")
        use_online = self.window.switch_online.get()
        def _work():
            vouchers = self.unifi.get_vouchers()
            irreg = self._analisar_vouchers(vouchers, use_online)
            self.window.after(0, lambda: self._on_check_done(vouchers, irreg))
        threading.Thread(target=_work, daemon=True).start()

    def _on_check_done(self, all_v, irreg):
        w = self.window
        w.btn_check.configure(state="normal", text="🔍  Verificar Vouchers")
        self._log(f"Total: {len(all_v)} vouchers")
        if irreg:
            self.vouchers_irregulares = irreg
            self._log(f"{len(irreg)} irregular(es).", "warning")
            w.btn_report.configure(state="normal")
            self._switch_tab("vouchers")
        else:
            self._log("Todos com CPF válido.", "success")
            self.vouchers_irregulares = []

    def _on_refresh_clients(self):
        if not self.unifi or not self.unifi.logged_in:
            return
        self.window.btn_refresh.configure(state="disabled", text="Carregando...")
        def _work():
            clients = self.unifi.get_online_clients()
            devices = self.unifi.get_devices()
            self.window.after(0, lambda: self._on_refresh_done(clients, devices))
        threading.Thread(target=_work, daemon=True).start()

    def _on_refresh_done(self, clients, devices):
        self.window.btn_refresh.configure(state="normal", text="🔄  Atualizar")
        self._update_devices_textbox(clients)
        self._display_devices_panel(devices)

    def _on_generate_report(self):
        if not self.vouchers_irregulares:
            messagebox.showinfo("Info", "Sem vouchers irregulares.")
            return
        fp = filedialog.asksaveasfilename(
            title="Salvar Relatório",
            initialfile=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf"), ("Texto", "*.txt")])
        if not fp:
            return
        ip_loja = self.window.entry_ip.get().strip() + ":" + self.window.cfg_port.get().strip()
        try:
            result = (gerar_relatorio_txt if fp.endswith('.txt') else gerar_relatorio_pdf)(
                self.vouchers_irregulares, fp, ip_loja)
            self._log(f"Relatório: {result}", "success")
            messagebox.showinfo("Sucesso", f"Salvo em:\n{result}")
            if sys.platform == 'win32':
                os.startfile(result)
        except Exception as e:
            self._log(f"Erro: {e}", "error")

    # ════════════════════════════════════════════════════════════
    #  PÁGINA 2: VISÃO GERAL — AUTO-SCAN + MANUAL + RESUMO
    # ════════════════════════════════════════════════════════════

    OVERVIEW_POLL_INTERVAL = 10_000  # 10s

    def _start_overview_polling(self):
        """Garante que o loop de auto-scan está ativo.

        Idempotente: se o timer já estiver agendado, não faz nada.
        Isso evita matar um scan em andamento ao navegar entre páginas,
        que era a causa dos valores de progresso e horário ficarem congelados.
        """
        if self._closing:
            return
        # Timer já rodando → não reinicia (não mata scan em andamento)
        if self._overview_poll_job is not None:
            return
        self._overview_poll_tick()

    def _stop_overview_polling(self):
        """Para completamente o polling e invalida qualquer scan em voo.

        Deve ser chamado APENAS em reset real: troca de tema, reconexão ou
        fechamento do app. NÃO ao simplesmente navegar entre páginas.
        """
        self._scan_token += 1
        self._active_scan_token = self._scan_token
        self._scan_running = False

        if self._overview_poll_job:
            self.window.after_cancel(self._overview_poll_job)
            self._overview_poll_job = None

        # Cancela o drenador da fila de resultados
        if self._scan_queue_job is not None:
            try:
                self.window.after_cancel(self._scan_queue_job)
            except Exception:
                pass
            self._scan_queue_job = None

    def _overview_poll_tick(self):
        """Dispara um scan se auto está ligado e não tem scan rodando."""
        if self._closing:
            return
        # Watchdog: se _scan_running ficou preso (queue processor morreu por exceção),
        # reseta para que o próximo tick possa iniciar um novo scan.
        if self._scan_running and self._scan_queue_job is None:
            self._scan_running = False
        if self.window.overview_auto_var.get() and not self._scan_running:
            creds = self._get_creds()
            if creds:
                self._run_scan(creds)
        # Agendar próximo tick sempre
        self._overview_poll_job = self.window.after(self.OVERVIEW_POLL_INTERVAL, self._overview_poll_tick)

    def _on_scan_all(self):
        """Scan manual — dispara independente do checkbox."""
        creds = self._get_creds()
        if not creds:
            messagebox.showwarning("Config", "Defina credenciais na aba Configurações.")
            self._switch_page("management"); self._switch_tab("settings")
            return
        if self._scan_running:
            return
        self._run_scan(creds)

    def _run_scan(self, creds):
        """Executa o scan de todas as lojas em paralelo.

        Os resultados são enfileirados via queue.Queue e drenados em lotes de
        150 ms pelo _process_scan_queue, evitando inundar a event-loop do Tkinter
        com dezenas de after(0) simultâneos (causa do travamento na Visão Geral).
        """
        if self._scan_running or self._closing:
            return

        # Token do scan atual (ignora updates atrasados ao trocar tema/filtros)
        self._scan_token += 1
        token = self._scan_token
        self._active_scan_token = token

        self._scan_running = True
        user, pw, port = creds
        custom = self.config.get("custom_ips", [])
        lojas = gerar_ips_lojas(port, custom)
        total = len(lojas)
        w = self.window
        w.btn_scan_all.configure(state="disabled", text="Escaneando...")
        w.lbl_scan_progress.configure(text=f"0 / {total}")

        # Filtra IPs excluídos pelo usuário
        excluded = set(self.config.get("excluded_ips", []))
        lojas = [l for l in lojas if l["ip"] not in excluded]

        # Na primeira vez cria todas as linhas; nas seguintes adiciona apenas IPs novos
        ips_novos = [l["ip"] for l in lojas]
        ips_existentes = set(self._overview_rows.keys())
        if not ips_existentes:
            for child in w.overview_scroll.winfo_children():
                child.destroy()
            self._overview_order = list(ips_novos)
            for ip in ips_novos:
                self._create_row(ip)
        else:
            for ip in ips_novos:
                if ip not in ips_existentes:
                    self._overview_order.append(ip)
                    self._create_row(ip)

        # Esvaziar fila de scan anterior (segurança)
        while not self._scan_queue.empty():
            try:
                self._scan_queue.get_nowait()
            except Exception:
                pass

        def _scan():
            done = 0
            try:
                with ThreadPoolExecutor(max_workers=15) as pool:
                    futs = {pool.submit(self._probe, ip_s, port, user, pw): ip_s for ip_s in ips_novos}
                    for f in as_completed(futs):
                        if self._closing:
                            return
                        ip_s = futs[f]
                        try:
                            r = f.result()
                        except Exception:
                            r = {"status": "error", "wlans": [], "clients": []}
                        done += 1
                        self._scan_queue.put((token, ip_s, r, done, total))
                if not self._closing:
                    self._scan_queue.put((token, None, None, done, total))
            except (KeyboardInterrupt, SystemExit):
                pass
            except Exception:
                pass

        threading.Thread(target=_scan, daemon=True).start()
        # Inicia o drenador periódico da fila (roda na main thread via after)
        self._start_scan_queue_processor(token, total)

    # ── Drenador da fila de scan ──────────────────────────────────────────────

    def _start_scan_queue_processor(self, token: int, total: int):
        """Cancela qualquer drenador anterior e inicia um novo para este scan."""
        if self._scan_queue_job is not None:
            try:
                self.window.after_cancel(self._scan_queue_job)
            except Exception:
                pass
            self._scan_queue_job = None
        self._process_scan_queue(token, total)

    def _process_scan_queue(self, token: int, total: int):
        """Drena até BATCH_SIZE itens da fila de resultados por tick (≈150 ms).

        Processar em lotes espaça as atualizações de widget no tempo e mantém
        a interface responsiva mesmo quando 60+ resultados chegam juntos.
        """
        BATCH_SIZE = 10  # widgets atualizados por tick

        if self._closing or token != self._active_scan_token:
            self._scan_queue_job = None
            return

        try:
            finished = False
            for _ in range(BATCH_SIZE):
                try:
                    item = self._scan_queue.get_nowait()
                except queue.Empty:
                    break

                t, ip, result, done, total_ = item

                # Descarta resultado de scan cancelado (troca de tema, navegação, etc.)
                if t != self._active_scan_token:
                    continue

                if ip is None:
                    # Sentinela: thread do scan concluiu
                    finished = True
                    break

                self._update_row(ip, result, done, total, token=t)

            if finished:
                self._scan_queue_job = None
                self._scan_done(total, token=token)
                return

        except Exception:
            # Nunca deixa o loop morrer silenciosamente — _scan_running ficaria preso
            self._scan_queue_job = None
            self._scan_running = False
            return

        # Agenda próxima drenagem; intervalo de 150 ms mantém UI fluida
        self._scan_queue_job = self.window.after(
            150, lambda: self._process_scan_queue(token, total)
        )

    def _probe(self, ip, port, user, pw):
        ctrl = UniFiController(ip, port, user, pw)
        ok, _ = ctrl.login()
        if not ok:
            return {"status": "offline", "wlans": [], "clients": []}
        wlans = ctrl.get_wlans()
        clients = ctrl.get_online_clients()
        ctrl.logout()
        # Palavra-chave da empresa para filtrar as WLANs (ex.: prefixo do SSID).
        # Fica em config local (nao versionado); vazio = aceita qualquer WLAN
        # de "CLIENTES" habilitada.
        company_kw = (self.config.get("wlan_company_filter", "") or "").upper()
        clientes_on = any(
            (not company_kw or company_kw in (w.get("name") or "").upper())
            and "CLIENTES" in (w.get("name") or "").upper()
            and w.get("enabled")
            for w in wlans
        )
        status = "online" if clientes_on else "offline"
        return {"status": status, "wlans": wlans, "clients": clients}

    def _create_row(self, ip):
        w = self.window
        container = ctk.CTkFrame(w.overview_scroll, fg_color="transparent")
        container.pack(fill="x", pady=1)
        header = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=6,
                               height=40, border_width=1, border_color=COLORS["border"])
        header.pack(fill="x"); header.pack_propagate(False)
        btn = ctk.CTkButton(header, text="+", width=32, height=28, corner_radius=4,
                              font=FONTS["body_bold"], fg_color=COLORS["bg_input"],
                              hover_color=COLORS["bg_hover"], text_color=COLORS["text_primary"],
                              command=lambda: self._toggle_row(ip))
        btn.pack(side="left", padx=(8, 6), pady=6)
        ctk.CTkLabel(header, text=ip, font=FONTS["mono_bold"],
                      text_color=COLORS["text_primary"], width=160).pack(side="left")
        badge = ctk.CTkLabel(header, text="...", font=FONTS["badge"],
                              text_color=COLORS["text_muted"], fg_color=COLORS["bg_input"],
                              corner_radius=4, width=90, height=22)
        badge.pack(side="left", padx=(10, 0))
        lbl = ctk.CTkLabel(header, text="", font=FONTS["small"], text_color=COLORS["text_muted"])
        lbl.pack(side="right", padx=(0, 12))
        det = ctk.CTkFrame(container, fg_color=COLORS["bg_input"], corner_radius=6)
        self._overview_rows[ip] = {"container": container, "btn": btn, "badge": badge,
                                    "lbl": lbl, "det": det, "expanded": False, "data": None}

    def _update_row(self, ip, result, done, total, token=None):
        if token is not None and token != self._active_scan_token:
            return
        if total > 0:
            try:
                self.window.lbl_scan_progress.configure(text=f"{done} / {total}")
            except Exception:
                pass
        row = self._overview_rows.get(ip)
        if not row:
            return

        # Salva o status anterior para detectar mudança de estado
        prev_status = (row["data"] or {}).get("status")
        row["data"] = result

        try:
            wlans   = result.get("wlans",   [])
            clients = result.get("clients", [])
            if result["status"] == "online":
                en = sum(1 for wl in wlans if wl.get('enabled'))
                row["badge"].configure(text="Online",
                                       text_color=COLORS["accent_green"],
                                       fg_color=COLORS["bg_success"])
                row["lbl"].configure(text=f"{len(clients)} cliente(s)  •  {en}/{len(wlans)} redes")
            elif wlans or clients:
                en = sum(1 for wl in wlans if wl.get('enabled'))
                row["badge"].configure(text="Offline",
                                       text_color=COLORS["accent_red"],
                                       fg_color=COLORS["bg_error"])
                row["lbl"].configure(text=f"{len(clients)} cliente(s)  •  {en}/{len(wlans)} redes")
            else:
                row["badge"].configure(text="Offline",
                                       text_color=COLORS["accent_red"],
                                       fg_color=COLORS["bg_error"])
                row["lbl"].configure(text="Sem resposta")

            # Só reconstrói detalhes se a linha está expandida
            if row["expanded"]:
                self._build_det(ip, result)

            # Se o status mudou (ex.: offline → online após ativar uma rede) E o usuário
            # está na overview, reaplica o filtro imediatamente para mover a linha para
            # a categoria correta e evitar a divergência badge Online / filtro Offline.
            if result["status"] != prev_status and self.current_page == "overview":
                self._filter_overview()

        except Exception:
            pass

    def _build_det(self, ip, result):
        row = self._overview_rows.get(ip)
        if not row:
            return
        det = row["det"]
        for child in det.winfo_children():
            child.destroy()
        wlans, clients = result["wlans"], result["clients"]
        if result["status"] != "online" and not wlans and not clients:
            ctk.CTkLabel(det, text="  Sem resposta.", font=FONTS["small"],
                          text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=8)
            return
        if wlans:
            ctk.CTkLabel(det, text="  REDES:", font=FONTS["small_bold"],
                          text_color=COLORS["text_secondary"]).pack(anchor="w", padx=12, pady=(8, 2))
            for wl in wlans:
                nm = wl.get('name', 'N/A')
                en = wl.get('enabled', False)
                g = "  [GUEST]" if wl.get('is_guest') else ""
                sc = COLORS["accent_green"] if en else COLORS["accent_red"]
                ctk.CTkLabel(det, text=f"    ● {nm}  {'ON' if en else 'OFF'}{g}",
                              font=FONTS["mono_small"], text_color=sc).pack(anchor="w", padx=12)
        if clients:
            ctk.CTkLabel(det, text=f"\n  CONECTADOS ({len(clients)}):", font=FONTS["small_bold"],
                          text_color=COLORS["text_secondary"]).pack(anchor="w", padx=12, pady=(4, 2))
            ctk.CTkLabel(det, text=f"    {'Nome':<24} {'IP':<16} {'Rede':<18}",
                          font=FONTS["mono_small"], text_color=COLORS["text_muted"]).pack(anchor="w", padx=12)
            for c in sorted(clients, key=lambda x: x.get('essid', ''))[:50]:
                nm = c.get('name', c.get('hostname', '—'))[:22]
                cip = c.get('ip', '—')
                ssid = c.get('essid', '—')[:16]
                ctk.CTkLabel(det, text=f"    {nm:<24} {cip:<16} {ssid:<18}",
                              font=FONTS["mono_small"], text_color=COLORS["text_primary"]).pack(anchor="w", padx=12)
            if len(clients) > 50:
                ctk.CTkLabel(det, text=f"    ... +{len(clients) - 50}",
                              font=FONTS["tiny"], text_color=COLORS["text_muted"]).pack(anchor="w", padx=12)
        ctk.CTkFrame(det, fg_color="transparent", height=8).pack()

    def _toggle_row(self, ip):
        row = self._overview_rows.get(ip)
        if not row:
            return
        if row["expanded"]:
            row["det"].pack_forget(); row["btn"].configure(text="+"); row["expanded"] = False
        else:
            # Construir detalhes na primeira expansão ou atualizar
            if row["data"]:
                self._build_det(ip, row["data"])
            row["det"].pack(fill="x", padx=(40, 0), pady=(0, 2)); row["btn"].configure(text="−"); row["expanded"] = True

    
    def _scroll_overview_to_top(self):
        """Força o scroll da visão geral (overview) para o topo."""
        w = getattr(self, "window", None)
        sf = getattr(w, "overview_scroll", None) if w else None
        self._scroll_frame_to_top(sf)

    def _scroll_frame_to_top(self, sf):
        """Força qualquer CTkScrollableFrame para o topo."""
        if sf is None:
            return
        try:
            sf.update_idletasks()
        except Exception:
            pass
        for attr in ("_parent_canvas", "_canvas", "canvas"):
            c = getattr(sf, attr, None)
            if c is not None:
                try:
                    c.yview_moveto(0.0)
                    return
                except Exception:
                    pass
        try:
            for child in sf.winfo_children():
                if "canvas" in child.winfo_class().lower():
                    try:
                        child.yview_moveto(0.0)
                        return
                    except Exception:
                        pass
        except Exception:
            pass

    def _filter_hosts_list(self):
        """Lê o campo de busca da aba Hosts e reconstrói a lista filtrada."""
        try:
            query = self.window.hosts_search.get().strip()
        except Exception:
            query = ""
        self._refresh_hosts_list(query=query)

    def _set_overview_filter(self, key):
        """Define o filtro ativo (all/online/offline) e atualiza visual dos botões."""
        w = self.window
        w.overview_filter_var.set(key)
        for k, btn in w.overview_filter_btns.items():
            if k == key:
                btn.configure(fg_color=COLORS["accent_blue"], text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])
        if getattr(self, '_last_overview_filter', None) != key:
            self._scroll_overview_to_top()
            self._last_overview_filter = key
        self._filter_overview()

    @staticmethod
    def _ip_sort_key(ip: str) -> tuple:
        """Converte IP em tupla numérica para ordenação crescente correta."""
        try:
            return tuple(int(p) for p in ip.split('.'))
        except Exception:
            return (999, 999, 999, 999)

    def _filter_overview(self):
        """Filtra linhas por IP (texto) e por status (all/online/offline).

        Exibe sempre em ordem crescente de IP (numerico), do menor ao maior.
        Não altera o estado visual dos itens que ainda estão sendo escaneados.
        """
        if self._closing:
            return

        query         = self.window.entry_search.get().strip().lower()
        status_filter = self.window.overview_filter_var.get()

        # Ordenação crescente por IP (numérica, não lexicográfica)
        all_ips     = list(self._overview_rows.keys())
        sorted_ips  = sorted(all_ips, key=self._ip_sort_key)

        visible   = []
        invisible = []

        for ip in sorted_ips:
            row = self._overview_rows.get(ip)
            if not row:
                continue
            try:
                ip_match = not query or query in ip

                data = row.get("data")
                if status_filter == "all":
                    status_match = True
                elif data is None:
                    # linha ainda pendente: mostra no "all" e oculta nos filtros
                    status_match = False
                elif status_filter == "online":
                    status_match = data.get("status") == "online"
                else:  # "offline"
                    status_match = data.get("status") != "online"

                if ip_match and status_match:
                    visible.append((ip, row))
                else:
                    invisible.append(row)
            except Exception:
                pass

        # 1) Esconde todos primeiro para evitar artefatos visuais de reordenação
        for row in invisible:
            try:
                row["container"].pack_forget()
            except Exception:
                pass

        for _, row in visible:
            try:
                row["container"].pack_forget()
            except Exception:
                pass

        # 2) Re-empacota na ordem crescente correta
        for _, row in visible:
            try:
                row["container"].pack(fill="x", pady=1)
            except Exception:
                pass

    def _update_summary_panel(self):
        """Atualiza o painel de resumo com totais calculados dos dados do scan."""
        w = self.window
        total_online = 0
        total_offline = 0
        total_clients = 0
        total_wlans_enabled = 0

        for row in self._overview_rows.values():
            data = row.get("data")
            if not data:
                continue
            if data["status"] == "online":
                total_online += 1
                total_clients += len(data.get("clients", []))
                total_wlans_enabled += sum(1 for wl in data.get("wlans", []) if wl.get("enabled"))
            else:
                total_offline += 1

        w._ov_stats["online"].configure(text=str(total_online))
        w._ov_stats["offline"].configure(text=str(total_offline))
        w._ov_stats["clients"].configure(text=str(total_clients))
        w._ov_stats["wlans"].configure(text=str(total_wlans_enabled))
        w.lbl_last_scan.configure(text=f"Último scan: {datetime.now().strftime('%H:%M:%S')}")

    def _scan_done(self, total, token=None):
        if token is not None and token != self._active_scan_token:
            return
        w = self.window
        w.btn_scan_all.configure(state="normal", text="🔍  Escanear")
        online = sum(1 for r in self._overview_rows.values() if r.get("data", {}).get("status") == "online")
        w.lbl_scan_progress.configure(text=f"✓ {online}/{total} online")
        self._update_summary_panel()
        self._filter_overview()   # Reaplicar filtro + ordenação crescente por IP
        self._scan_running = False

    # ════════════════════════════════════════
    #  FECHAR
    # ════════════════════════════════════════

    def _on_closing(self):
        self._closing = True
        self._stop_polling()
        self._stop_overview_polling()
        if self.unifi and self.unifi.logged_in:
            try:
                self.unifi.logout()
            except Exception:
                pass
        self.window.destroy()