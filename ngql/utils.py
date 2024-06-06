import pprint
from typing import Any, ClassVar, Dict, Optional


class FancyPrinter:
    pp = pprint.PrettyPrinter(indent=2, sort_dicts=False)
    # Thanks to https://www.learnui.design/tools/data-color-picker.html
    COLORS_rgb: ClassVar[Dict[str, str]] = {
        "dark_blue": "38;2;0;63;92",
        "blue": "38;2;47;75;124",
        "light_blue": "38;2;0;120;215",
        "green": "38;2;0;135;107",
        "light_green": "38;2;102;187;106",
        "purple": "38;2;102;81;145",
        "magenta": "38;2;160;81;149",
        "pink": "38;2;212;80;135",
        "red": "38;2;249;93;106",
        "orange": "38;2;255;124;67",
        "yellow": "38;2;255;166;0",
    }

    color_idx: int = 0

    def __call__(self, val: Any, color: Optional[str] = None):
        if color in self.COLORS_rgb:
            self.color_idx = list(self.COLORS_rgb.keys()).index(color)
            color = self.COLORS_rgb[color]
        else:
            self.color_idx += 1
            self.color_idx %= len(self.COLORS_rgb)
            color = list(self.COLORS_rgb.values())[self.color_idx]

        if isinstance(val, str):
            print(f"\033[1;3;{color}m{val}\033[0m")
        else:
            text = self.pp.pformat(val)
            print(f"\033[1;3;{color}m{text}\033[0m")
