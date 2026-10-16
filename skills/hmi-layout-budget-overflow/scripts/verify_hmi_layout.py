#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HMI Layout & Space Budget Verification Tool
===========================================
Профессиональный инструмент верификации геометрии, контроля переполнения,
наложений (коллизий) и плотности заполнения экранов для индустрии HMI (LVGL, Qt, Embedded Web).

Не имеет внешних зависимостей (только стандартная библиотека Python 3).

Использование:
    python verify_hmi_layout.py [spec_file.json] [--html report.html] [--min-touch 44]
"""

import sys
import json
import argparse
from typing import List, Dict, Any, Tuple, Optional

# Цвета ANSI для терминала
C_RESET = "\033[0m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_BOLD = "\033[1m"


class Rect:
    def __init__(self, x: int, y: int, w: int, h: int, name: str = "", interactive: bool = False, parent: str = ""):
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.name = name
        self.interactive = interactive
        self.parent = parent

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)

    def intersects(self, other: 'Rect') -> bool:
        return (self.x < other.right and self.right > other.x and
                self.y < other.bottom and self.bottom > other.y)

    def intersection_area(self, other: 'Rect') -> int:
        if not self.intersects(other):
            return 0
        ix1 = max(self.x, other.x)
        iy1 = max(self.y, other.y)
        ix2 = min(self.right, other.right)
        iy2 = min(self.bottom, other.bottom)
        return (ix2 - ix1) * (iy2 - iy1)

    def contains(self, other: 'Rect') -> bool:
        return (self.x <= other.x and self.right >= other.right and
                self.y <= other.y and self.bottom >= other.bottom)


class HMISpecValidator:
    def __init__(self, spec: Dict[str, Any], min_touch_px: int = 44, min_gap_px: int = 6):
        self.screen_w = spec.get("screen", {}).get("width", 1024)
        self.screen_h = spec.get("screen", {}).get("height", 600)
        self.title = spec.get("screen", {}).get("name", "HMI Screen")
        self.safe_margin = spec.get("screen", {}).get("safe_margin", 4)
        self.min_touch_px = min_touch_px
        self.min_gap_px = min_gap_px
        
        # Загрузка элементов
        self.elements: List[Rect] = []
        for elem_data in spec.get("elements", []):
            rect = Rect(
                x=elem_data.get("x", 0),
                y=elem_data.get("y", 0),
                w=elem_data.get("width", elem_data.get("w", 0)),
                h=elem_data.get("height", elem_data.get("h", 0)),
                name=elem_data.get("name", "unnamed"),
                interactive=elem_data.get("interactive", False) or elem_data.get("clickable", False),
                parent=elem_data.get("parent", "")
            )
            self.elements.append(rect)

        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.collisions: List[Tuple[Rect, Rect, int]] = []
        self.overflows: List[Tuple[Rect, str]] = []
        self.touch_violations: List[Tuple[Rect, str]] = []

    def run_all_checks(self) -> bool:
        """Запускает полный цикл верификации геометрии"""
        self.check_screen_overflows()
        self.check_collisions()
        self.check_touch_ergonomics()
        self.check_space_budget()
        return len(self.errors) == 0

    def check_screen_overflows(self):
        """Проверка выхода за физические границы экрана (Viewport clipping)"""
        for el in self.elements:
            overflow_reasons = []
            if el.x < 0:
                overflow_reasons.append(f"X ({el.x}) < 0 (выход за левый край)")
            if el.y < 0:
                overflow_reasons.append(f"Y ({el.y}) < 0 (выход за верхний край)")
            if el.right > self.screen_w:
                overflow_reasons.append(f"Right ({el.right}) > Screen Width ({self.screen_w}), срез на {el.right - self.screen_w} px")
            if el.bottom > self.screen_h:
                overflow_reasons.append(f"Bottom ({el.bottom}) > Screen Height ({self.screen_h}), срез на {el.bottom - self.screen_h} px")

            if overflow_reasons:
                msg = f"Элемент '{el.name}' [{el.x},{el.y} {el.w}x{el.h}]: " + "; ".join(overflow_reasons)
                self.errors.append(f"[ОШИБКА ПЕРЕПОЛНЕНИЯ ЭКРАНА] {msg}")
                self.overflows.append((el, "; ".join(overflow_reasons)))
            elif (el.x < self.safe_margin or el.y < self.safe_margin or 
                  el.right > self.screen_w - self.safe_margin or 
                  el.bottom > self.screen_h - self.safe_margin):
                self.warnings.append(f"[ОПАСНАЯ ЗОНА] '{el.name}' ближе {self.safe_margin} px к физической рамке экрана")

    def check_collisions(self):
        """Проверка нежелательных пересечений и наложений элементов одного уровня (AABB)"""
        n = len(self.elements)
        for i in range(n):
            for j in range(i + 1, n):
                a = self.elements[i]
                b = self.elements[j]

                # Если один элемент - родительский контейнер другого, вложенность допустима
                if a.name == b.parent or b.name == a.parent:
                    continue
                if a.parent and b.parent and a.parent != b.parent:
                    # Разные непересекающиеся ветки дерева
                    pass

                if a.intersects(b):
                    area = a.intersection_area(b)
                    self.collisions.append((a, b, area))
                    self.errors.append(
                        f"[КОЛЛИЗИЯ / НАЛОЖЕНИЕ] '{a.name}' пересекается с '{b.name}'! "
                        f"Площадь наложения: {area} px²"
                    )

    def check_touch_ergonomics(self):
        """Проверка эргономики сенсорных кнопок и полей ввода (W3C / ISO 9241)"""
        for el in self.elements:
            if el.interactive:
                if el.w < self.min_touch_px or el.h < self.min_touch_px:
                    issue = (f"Размер {el.w}x{el.h} px меньше минимального стандарта "
                             f"подушечки пальца ({self.min_touch_px}x{self.min_touch_px} px)")
                    self.touch_violations.append((el, issue))
                    self.errors.append(f"[ДЕФЕКТ ТАЧ-ЭРГОНОМИКИ] Кнопка/контрол '{el.name}': {issue}")

    def check_space_budget(self) -> float:
        """Расчет бюджета заполнения экрана (Fill Factor / Negative Space)"""
        screen_area = self.screen_w * self.screen_h
        
        # Для расчета полезной площади берем крупные блоки верхнего уровня (контейнеры и карточки)
        top_elements = [el for el in self.elements if not el.parent]
        if not top_elements:
            top_elements = self.elements

        used_area = sum(el.area for el in top_elements)
        fill_ratio = (used_area / screen_area) * 100.0

        if fill_ratio < 55.0:
            status = "СЛИШКОМ ПУСТОЙ ЭКРАН (< 55%) — пространство экрана недоиспользовано, оператор видит пустоши"
            self.warnings.append(f"[БЮДЖЕТ ЭКРАНА] {status}. Заполнение: {fill_ratio:.1f}%")
        elif 65.0 <= fill_ratio <= 82.0:
            status = "ИДЕАЛЬНЫЙ ПРОМЫШЛЕННЫЙ БАЛАНС (65-82%) — оптимальный вес, воздух и читаемость"
            self.info.append(f"[БЮДЖЕТ ЭКРАНА] {status}. Заполнение: {fill_ratio:.1f}%")
        elif fill_ratio > 85.0:
            status = "ПЕРЕГРУЗКА ЭКРАНА (> 85%) — элементы стоят впритык, риск когнитивного перегруза оператора"
            self.warnings.append(f"[БЮДЖЕТ ЭКРАНА] {status}. Заполнение: {fill_ratio:.1f}%")
        else:
            status = "ПРИЕМЛЕМАЯ ПЛОТНОСТЬ (55-65% или 82-85%)"
            self.info.append(f"[БЮДЖЕТ ЭКРАНА] {status}. Заполнение: {fill_ratio:.1f}%")

        return fill_ratio

    def print_console_report(self):
        """Печать подробного структурированного отчета в консоль"""
        print(f"\n{C_BOLD}======================================================================{C_RESET}")
        print(f"{C_BOLD}{C_CYAN}    HMI SCREEN INTEGRITY & OVERFLOW REPORT: {self.title}{C_RESET}")
        print(f"{C_BOLD}    Разрешение: {self.screen_w}x{self.screen_h} px | Элементов: {len(self.elements)}{C_RESET}")
        print(f"{C_BOLD}======================================================================{C_RESET}\n")

        # 1. Ошибки
        if self.errors:
            print(f"{C_RED}{C_BOLD}[!] ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ ДЕФЕКТЫ ({len(self.errors)}):{C_RESET}")
            for err in self.errors:
                print(f"  {C_RED}✖ {err}{C_RESET}")
        else:
            print(f"{C_GREEN}{C_BOLD}[✓] КРИТИЧЕСКИХ ДЕФЕКТОВ НЕ ОБНАРУЖЕНО: Все элементы в пределах экрана и без наложений.{C_RESET}")

        # 2. Предупреждения
        if self.warnings:
            print(f"\n{C_YELLOW}{C_BOLD}[?] ПРЕДУПРЕЖДЕНИЯ ({len(self.warnings)}):{C_RESET}")
            for warn in self.warnings:
                print(f"  {C_YELLOW}⚠ {warn}{C_RESET}")

        # 3. Инфо и бюджет
        print(f"\n{C_BLUE}{C_BOLD}[i] МЕТРИКИ И БЮДЖЕТ ПРОСТРАНСТВА:{C_RESET}")
        for inf in self.info:
            print(f"  {C_BLUE}ℹ {inf}{C_RESET}")

        # Итоговая плашка
        print(f"\n{C_BOLD}----------------------------------------------------------------------{C_RESET}")
        if not self.errors:
            print(f"{C_GREEN}{C_BOLD}СТАТУС: ТЕСТ ПРОЙДЕН (PASS) — Геометрия HMI соответствует стандартам.{C_RESET}")
        else:
            print(f"{C_RED}{C_BOLD}СТАТУС: ТЕСТ ПРОВАЛЕН (FAIL) — Исправьте переполнения перед заливкой прошивки!{C_RESET}")
        print(f"{C_BOLD}----------------------------------------------------------------------{C_RESET}\n")

    def generate_html_report(self, output_path: str):
        """Генерирует интерактивный HTML-отчет с визуальной картой экрана и подсвеченными коллизиями"""
        elements_json = json.dumps([
            {
                "name": el.name,
                "x": el.x, "y": el.y, "w": el.w, "h": el.h,
                "interactive": el.interactive,
                "parent": el.parent
            } for el in self.elements
        ], ensure_ascii=False)

        errors_json = json.dumps(self.errors, ensure_ascii=False)
        warnings_json = json.dumps(self.warnings, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>HMI Layout Integrity Report - {self.title}</title>
<style>
  body {{
    margin: 0;
    padding: 24px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
    background: #0f172a;
    color: #e2e8f0;
  }}
  h1 {{ margin: 0 0 8px; font-size: 22px; color: #38bdf8; }}
  .subtitle {{ color: #94a3b8; margin-bottom: 20px; font-size: 14px; }}
  .metrics-bar {{
    display: flex; gap: 16px; margin-bottom: 24px;
  }}
  .metric-card {{
    background: #1e293b; padding: 14px 18px; border-radius: 8px; border: 1px solid #334155;
  }}
  .metric-val {{ font-size: 22px; font-weight: bold; color: #f8fafc; }}
  .metric-lbl {{ font-size: 12px; color: #64748b; text-transform: uppercase; }}
  .screen-viewport {{
    position: relative;
    width: {self.screen_w}px;
    height: {self.screen_h}px;
    background: #020617;
    border: 2px solid #38bdf8;
    box-shadow: 0 10px 30px rgba(0,0,0,0.7);
    margin-bottom: 24px;
    overflow: hidden;
  }}
  .hmi-elem {{
    position: absolute;
    box-sizing: border-box;
    border: 1px solid rgba(56, 189, 248, 0.6);
    background: rgba(30, 41, 59, 0.7);
    color: #f1f5f9;
    padding: 4px;
    font-size: 11px;
    border-radius: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .hmi-elem.interactive {{
    border-color: #10b981;
    background: rgba(16, 185, 129, 0.15);
  }}
  .hmi-elem.collision {{
    border: 2px solid #ef4444 !important;
    background: rgba(239, 68, 68, 0.4) !important;
    z-index: 100;
  }}
  .hmi-elem.overflow {{
    border: 2px dashed #f59e0b !important;
  }}
  .legend {{
    display: flex; gap: 20px; margin-bottom: 16px; font-size: 13px;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 8px; }}
  .legend-box {{ width: 14px; height: 14px; border-radius: 3px; }}
</style>
</head>
<body>
  <h1>HMI Layout Verification Map</h1>
  <div class="subtitle">{self.title} — {self.screen_w} × {self.screen_h} px</div>

  <div class="metrics-bar">
    <div class="metric-card">
      <div class="metric-val">{len(self.elements)}</div>
      <div class="metric-lbl">Элементов</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color: {'#10b981' if not self.errors else '#ef4444'}">{len(self.errors)}</div>
      <div class="metric-lbl">Ошибок коллизий</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color: #38bdf8">{len(self.warnings)}</div>
      <div class="metric-lbl">Предупреждений</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color: #a855f7">{self.check_space_budget():.1f}%</div>
      <div class="metric-lbl">Заполнение экрана</div>
    </div>
  </div>

  <div class="legend">
    <div class="legend-item"><div class="legend-box" style="background: rgba(30, 41, 59, 0.8); border: 1px solid #38bdf8;"></div> Обычный блок</div>
    <div class="legend-item"><div class="legend-box" style="background: rgba(16, 185, 129, 0.3); border: 1px solid #10b981;"></div> Сенсорная кнопка (>=44px)</div>
    <div class="legend-item"><div class="legend-box" style="background: rgba(239, 68, 68, 0.5); border: 2px solid #ef4444;"></div> Коллизия / Наложение</div>
  </div>

  <div class="screen-viewport" id="viewport"></div>

  <script>
    const elements = {elements_json};
    const viewport = document.getElementById('viewport');

    elements.forEach(el => {{
      const div = document.createElement('div');
      div.className = 'hmi-elem' + (el.interactive ? ' interactive' : '');
      div.style.left = el.x + 'px';
      div.style.top = el.y + 'px';
      div.style.width = el.w + 'px';
      div.style.height = el.h + 'px';
      div.title = `${{el.name}} (${{el.w}}x${{el.h}} at [${{el.x}},${{el.y}}])`;
      div.textContent = `${{el.name}} (${{el.w}}×${{el.h}})`;
      viewport.appendChild(div);
    }});
  </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"{C_CYAN}[HTML REPORT] Интерактивная карта экрана сохранена в: {output_path}{C_RESET}")


def get_default_sample_spec() -> Dict[str, Any]:
    """Пример промышленного экрана намоточного станка (1024x600, рабочая зона 1024x550)"""
    return {
        "screen": {
            "name": "Winder Machine HMI (1024x600, Tab Area 1024x550)",
            "width": 1024,
            "height": 550,
            "safe_margin": 6
        },
        "elements": [
            {"name": "card_left_meter", "x": 10, "y": 8, "width": 520, "height": 264, "interactive": False},
            {"name": "card_right_preset", "x": 536, "y": 8, "width": 478, "height": 130, "interactive": False},
            {"name": "card_right_bobbin", "x": 536, "y": 142, "width": 478, "height": 130, "interactive": False},
            {"name": "card_progress_bar", "x": 10, "y": 278, "width": 1004, "height": 76, "interactive": False},
            {"name": "card_telemetry_grid", "x": 10, "y": 360, "width": 1004, "height": 98, "interactive": False},
            {"name": "btn_start", "x": 10, "y": 464, "width": 190, "height": 74, "interactive": True},
            {"name": "btn_pause", "x": 208, "y": 464, "width": 150, "height": 74, "interactive": True},
            {"name": "btn_stop", "x": 366, "y": 464, "width": 150, "height": 74, "interactive": True},
            {"name": "btn_jog", "x": 524, "y": 464, "width": 150, "height": 74, "interactive": True},
            {"name": "btn_reset", "x": 864, "y": 464, "width": 150, "height": 74, "interactive": True}
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="HMI Screen Layout & Overflow Verification Tool")
    parser.add_argument("spec", nargs="?", help="JSON file with screen layout specification")
    parser.add_argument("--html", help="Path to generate HTML interactive layout map")
    parser.add_argument("--min-touch", type=int, default=44, help="Minimum touch target size in pixels (default 44)")
    args = parser.parse_args()

    if args.spec:
        with open(args.spec, "r", encoding="utf-8") as f:
            spec = json.load(f)
    else:
        print(f"{C_YELLOW}[!] Файл спецификации не указан. Запуск встроенной эталонной спецификации HMI.{C_RESET}")
        spec = get_default_sample_spec()

    validator = HMISpecValidator(spec, min_touch_px=args.min_touch)
    success = validator.run_all_checks()
    validator.print_console_report()

    if args.html:
        validator.generate_html_report(args.html)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
