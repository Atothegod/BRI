# BRI Interface Colors

Source: `color_theme.jpg`. Use the printed hex codes, not sampled JPEG pixels.

| Color | Hex | Interface use |
| --- | --- | --- |
| Forest | `#12271D` | Navigation, LINE message headers, strong text |
| Sage | `#425B46` | Actions, selected controls, confirmed payment text |
| Gold | `#C2A256` | Small brand accents, active step, section borders |
| Ivory | `#F3F0E8` | Accent surfaces and LINE message footers |
| Terracotta | `#C25D37` | Pending-state borders and accents |

Keep the main reading surfaces white. Use `#A44928` for small pending-state
text: it has 5.90:1 contrast on white and 5.27:1 on the `#FBF0EB` status
surface. Sage on white is 7.46:1; gold on forest is 6.45:1.
Do not use gold as small text on white. Error states remain distinct red.
Interpret the chrome reference as restrained neutral borders, not reflective
backgrounds behind forms.

Web tokens live in `backend/school/static/school/css/brand.css`, loaded by
`base.html`. LINE Flex payloads in `backend/school/line.py` use literal hex
values because LINE cannot consume CSS variables.

The guide also names Cinzel, Tannakone, Noto Sans Thai and Quetine fonts.
This color update retains existing typography; it does not add unavailable
font files. LINE uses its own client fonts.

Pending payment is orange; approved payment is green. Student IDs remain
hidden until `is_paid=True`. Palette changes do not change these conditions.
