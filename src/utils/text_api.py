import json
import html

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
