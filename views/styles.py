#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Definição de estilos — Tema Claro e Escuro."""

LIGHT = {
    "bg_main": "#F0F2F5", "bg_card": "#FFFFFF", "bg_input": "#F6F8FA",
    "bg_hover": "#EEF1F5", "border": "#D0D7DE", "border_focus": "#0969DA",
    "border_light": "#E8EBEF", "text_primary": "#1F2328",
    "text_secondary": "#656D76", "text_muted": "#8C959F", "text_inverse": "#FFFFFF",
    "accent_blue": "#0969DA", "accent_green": "#1A7F37", "accent_red": "#CF222E",
    "accent_orange": "#BF8700", "accent_purple": "#8250DF", "accent_cyan": "#0E7C86",
    "hover_blue": "#0757B5", "hover_green": "#146C2E", "hover_red": "#A40E26",
    "hover_orange": "#9A6700", "hover_purple": "#6639BA",
    "bg_success": "#DAFBE1", "bg_error": "#FFEBE9", "bg_warning": "#FFF8C5",
    "bg_info": "#DDF4FF", "header_bg": "#FFFFFF", "header_border": "#D8DEE4",
    "btn_secondary": "#F6F8FA", "nav_bg": "#FFFFFF",
}

DARK = {
    "bg_main": "#0D1117", "bg_card": "#161B22", "bg_input": "#21262D",
    "bg_hover": "#30363D", "border": "#30363D", "border_focus": "#58A6FF",
    "border_light": "#21262D", "text_primary": "#E6EDF3",
    "text_secondary": "#8B949E", "text_muted": "#6E7681", "text_inverse": "#FFFFFF",
    "accent_blue": "#58A6FF", "accent_green": "#3FB950", "accent_red": "#F85149",
    "accent_orange": "#D29922", "accent_purple": "#BC8CFF", "accent_cyan": "#39D2C0",
    "hover_blue": "#79C0FF", "hover_green": "#56D364", "hover_red": "#FF7B72",
    "hover_orange": "#E3B341", "hover_purple": "#D2A8FF",
    "bg_success": "#12261E", "bg_error": "#2D1214", "bg_warning": "#2B2000",
    "bg_info": "#0C2D48", "header_bg": "#161B22", "header_border": "#30363D",
    "btn_secondary": "#21262D", "nav_bg": "#161B22",
}

COLORS: dict[str, str] = dict(DARK)


def apply_theme(theme: str):
    """Aplica tema 'light' ou 'dark'."""
    COLORS.clear()
    COLORS.update(LIGHT if theme == "light" else DARK)


FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"

FONTS = {
    "title": (FONT_FAMILY, 17, "bold"), "section": (FONT_FAMILY, 11, "bold"),
    "body": (FONT_FAMILY, 12), "body_bold": (FONT_FAMILY, 12, "bold"),
    "small": (FONT_FAMILY, 10), "small_bold": (FONT_FAMILY, 10, "bold"),
    "tiny": (FONT_FAMILY, 9), "mono": (FONT_MONO, 11),
    "mono_bold": (FONT_MONO, 12, "bold"), "mono_small": (FONT_MONO, 10),
    "btn_large": (FONT_FAMILY, 14, "bold"), "btn_normal": (FONT_FAMILY, 12),
    "btn_section": (FONT_FAMILY, 11), "badge": (FONT_FAMILY, 9, "bold"),
    "header_title": (FONT_FAMILY, 17, "bold"),
    "tab": (FONT_FAMILY, 11), "tab_active": (FONT_FAMILY, 11, "bold"),
}

DIMS = {
    "left_panel_width": 300, "right_panel_width": 285, "card_corner": 10,
    "card_border": 1, "btn_height_large": 48, "btn_height_normal": 38,
    "btn_height_small": 30, "input_height": 38, "header_height": 56,
}
