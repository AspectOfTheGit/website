import json
import html
import re
from markupsafe import Markup
from src.config import COLOURS

HEX_COLOUR = re.compile(r'^#?[0-9A-Fa-f]{6}$')

def mc_to_html(message):
    if isinstance(message, str):
        try:
            message = json.loads(message)
        except json.JSONDecodeError:
            return html.escape(message)

    def render_part(part):
        if not isinstance(part, dict):
            return html.escape(str(part)).replace("\n", "<br>")
    
        text = html.escape(part.get("text", "")).replace("\n", "<br>")
    
        style_info = part.get("style", {})
        color = style_info.get("color")
        if isinstance(color, int):
            color = f"#{color:06X}"
    
        bold = style_info.get("isBold", False)
        italic = style_info.get("isItalic", False)
        underline = style_info.get("isUnderlined", False)
        strikethrough = style_info.get("isStrikethrough", False)
    
        styles = []
        if color:
            styles.append(f"color:{color}")
        if bold:
            styles.append("font-weight:bold")
        if italic:
            styles.append("font-style:italic")
        if underline and strikethrough:
            styles.append("text-decoration:underline line-through")
        elif underline:
            styles.append("text-decoration:underline")
        elif strikethrough:
            styles.append("text-decoration:line-through")
    
        span_start = f'<span style="{";".join(styles)}">' if styles else ""
        span_end = "</span>" if styles else ""
    
        extra_html = "".join(render_part(e) for e in part.get("extra", []))
    
        return f"{span_start}{text}{extra_html}{span_end}"

    if isinstance(message, dict) and "components" in message:
        html_output = "".join(render_part(part) for part in message["components"])
    else:
        html_output = message

    return str(html_output.replace("\n", "<br>"))


def raw_to_html(component):
    if isinstance(component, str):
        try:
            component = json.loads(component)
        except json.JSONDecodeError:
            return Markup(component)
    segments = []
    def collect(c, inherited=None):
        if isinstance(c, str):
            style_str = inherited.get("_style_str", "") if inherited else ""
            segments.append((c, style_str))
            return
        if inherited is None:
            inherited = {}
            
        text = c.get("text", "")
        color = c.get("color", inherited.get("color"))
        italic = c.get("italic", inherited.get("italic", False))
        bold = c.get("bold", inherited.get("bold", False))
        underlined = c.get("underlined", inherited.get("underlined", False))
        strikethrough = c.get("strikethrough", inherited.get("strikethrough", False))

        resolved_color = None
        if color:
            if color in COLOURS:
                resolved_color = COLOURS[color]
            elif HEX_COLOUR.match(color):
                resolved_color = color if color.startswith("#") else f"#{color}"

        style_parts = []
        if resolved_color:
            style_parts.append(f"color:{resolved_color}")
        if italic:
            style_parts.append("font-style:italic")
        if bold:
            style_parts.append("font-weight:bold")
        decorations = []
        if underlined:
            decorations.append("underline")
        if strikethrough:
            decorations.append("line-through")
        if decorations:
            style_parts.append("text-decoration:" + " ".join(decorations))
        style_str = ";".join(style_parts)
        new_inherited = dict(inherited)
        new_inherited.update({
            "color": resolved_color or color,
            "italic": italic,
            "bold": bold,
            "underlined": underlined,
            "strikethrough": strikethrough,
            "_style_str": style_str
        })

        if text:
            segments.append((text, style_str))

        for e in c.get("extra", []):
            collect(e, new_inherited)
    collect(component)
    if not segments:
        return Markup("")
    merged = []
    cur_text, cur_style = segments[0]
    for t, s in segments[1:]:
        if s == cur_style:
            cur_text += t
        else:
            merged.append((cur_text, cur_style))
            cur_text, cur_style = t, s
    merged.append((cur_text, cur_style))
    out = []
    for text, style in merged:
        if style:
            escaped = Markup.escape(text)
            out.append(f"<span style='{style}'>{escaped}</span>")
        else:
            out.append(Markup.escape(text))

    return Markup("".join(out))
