"""Lightweight local SVG icons; no external fonts or scripts."""

from base64 import b64encode
from html import escape

PATHS = {
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    "database": (
        '<ellipse cx="12" cy="5" rx="8" ry="3"/>'
        '<path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7"/>'
    ),
    "file": (
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/>'
        '<path d="M14 2v6h6M8 13h8M8 17h6"/>'
    ),
    "shield": '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6Z"/><path d="m8 12 3 3 5-6"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m7.5 12 3 3 6-6"/>',
    "sparkles": (
        '<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4Z"/>'
        '<path d="m20 2 .5 1.5L22 4l-1.5.5L20 6l-.5-1.5L18 4l1.5-.5Z"/>'
    ),
    "globe": (
        '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/>'
        '<path d="M3 12h18M5 7h14M5 17h14"/>'
    ),
    "calendar": (
        '<rect x="3" y="5" width="18" height="16" rx="2"/>'
        '<path d="M3 10h18M7 2v6M17 2v6M8 14h2M14 14h2"/>'
    ),
    "arrow": '<path d="M4 12h15m-6-6 6 6-6 6"/>',
    "diamond": '<path d="m3 8 4-5h10l4 5-9 13Z"/><path d="M3 8h18M7 3l5 18 5-18"/>',
    "chart": '<path d="M4 21V13h4v8M10 21V8h4v13M16 21V3h4v18"/>',
    "workspace": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 10h18M9 10v10"/>',
}


def svg_image(svg, class_name="", alt=""):
    # st.html sanitizes inline SVG; an encoded local image keeps the artwork intact.
    svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    encoded = b64encode(svg.encode()).decode("ascii")
    return (
        f'<img class="{class_name}" src="data:image/svg+xml;base64,{encoded}" '
        f'alt="{escape(alt, quote=True)}"/>'
    )


def icon(name, size=20, color="#3b82f6"):
    svg = (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.65" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{PATHS.get(name, PATHS["chart"])}</svg>'
    )
    return svg_image(svg, "dj-icon")


LOGO = (
    '<svg viewBox="0 0 34 38" aria-hidden="true"><defs><linearGradient id="brand" '
    'x2="1" y2="0"><stop stop-color="#16b4fc"/><stop offset="1" stop-color="#1c48ed"/>'
    '</linearGradient></defs><rect x="2" y="23" width="7" height="13" rx="2" fill="#14b3f6"/>'
    '<rect x="13" y="12" width="7" height="24" rx="2" fill="#2487f6"/>'
    '<rect x="24" y="3" width="7" height="33" rx="2" fill="url(#brand)"/></svg>'
)

MOUNTAIN = """
<svg viewBox="0 0 530 230" fill="none" aria-hidden="true">
<defs><linearGradient id="mountain" x1="330" y1="40" x2="230" y2="230"
gradientUnits="userSpaceOnUse"><stop stop-color="#7db5ed"/>
<stop offset="1" stop-color="#e8f5ff"/></linearGradient></defs>
<ellipse cx="340" cy="150" rx="190" ry="69" fill="#e4f3ff" opacity=".65"/>
<path d="m40 226 108-114 42 39 48-43 61-91 42 60 31-25 122 174Z"
fill="url(#mountain)" opacity=".66"/>
<path d="m169 225 69-117 61-91-6 83 24 32-27 12-10 81Z" fill="#99c5ee" opacity=".55"/>
<path d="m299 17 42 60 31-25 28 45-37-19-22 15-17-14-17 8-14 13Z"
fill="#f6fbff" opacity=".93"/>
<path d="m40 226 108-114 42 39-22-5-13 18-10-9-24 44Z" fill="#fff" opacity=".85"/>
<path d="m290 145 34-66 17 14-28 45 37 58-19-10-14 39h-37Z" fill="#79afe6" opacity=".24"/>
<path d="m109 226 73-51 42 23 45-27 42 30 77-51 77 76Z" fill="#daeefd"/>
<path d="M0 200c107-41 175 30 263 4s193-47 267 4v22H0Z" fill="#f6faff" opacity=".8"/>
</svg>
"""

LOGO = svg_image(LOGO, "dj-logo")
MOUNTAIN = svg_image(MOUNTAIN, "dj-mountain")
