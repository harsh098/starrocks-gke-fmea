# Part 2 test diagrams

Each test has an editable draw.io source and a 1800 × 1120 PNG export.
The SVG files and build script preserve the common layout for later edits.

| Test | PNG | Editable source |
| --- | --- | --- |
| FE-1 | [Follower recovery](fe-1.png) | [draw.io](fe-1.drawio) |
| FE-2 | [Leader recovery](fe-2.png) | [draw.io](fe-2.drawio) |
| FE-3 | [Leader isolation](fe-3.png) | [draw.io](fe-3.drawio) |
| BE-1 | [Backend availability](be-1.png) | [draw.io](be-1.drawio) |
| CRED-1 | [Password rotation](cred-1.png) | [draw.io](cred-1.drawio) |

These are schematic placements for explaining the test mechanism. The runners
discover the actual leader, selected member, and zone for each run.

To rebuild matching source and PNG files, use Python with CairoSVG installed:

```bash
python docs/diagrams/build.py
```

After editing a draw.io source directly, use draw.io's PNG export to update the
image. Running the generator replaces the sources with its common layout.
