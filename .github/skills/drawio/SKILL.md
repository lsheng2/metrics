---
name: drawio
description: "Create and edit draw.io diagrams in XML format. Use for architecture diagrams, module flows, dependency maps, sequence-like diagrams, and PNG export."
---

# Draw.io Diagram Skill

Use draw.io for layout-heavy architecture diagrams, deployment diagrams, or module-boundary diagrams with explicit interface labels. Use Mermaid for simple Markdown-hosted diagrams.

## Repository Routing

- Default source path: `docs/<topic>/assets/<diagram>.drawio` or `docs/assets/<diagram>.drawio` when the doc has no local asset convention.
- Add PNG exports beside the `.drawio` file only when docs or review packets need image artifacts.
- On Windows, a common export command is:

```powershell
& "C:\Program Files\draw.io\draw.io.exe" --export --format png --scale 2 --output docs\assets\diagram.png docs\assets\diagram.drawio
```

If draw.io is not installed, create the `.drawio` XML and leave export as a documented manual step.

## XML Safety Rules

1. Do not include XML comments in generated `.drawio` files.
2. Escape special characters in `value` attributes: `&amp;`, `&lt;`, `&gt;`, `&quot;`.
3. Every edge must include an explicit `<mxGeometry relative="1" as="geometry" />` child.
4. All `mxCell` elements must be siblings under `<root>`.
5. Use `&#xa;` for line breaks in XML attribute values, not literal `\n`.
6. Set `defaultFontFamily="Helvetica"` on `mxGraphModel` and `fontFamily=Helvetica;` on text-bearing cells.
7. Avoid corner connection points; use side midpoints such as `exitX=1;exitY=0.5`.

## Minimal Template

```xml
<mxfile host="app.diagrams.net" modified="2026-08-19T00:00:00.000Z" agent="GitHub Copilot" version="21.0.0">
  <diagram name="Page-1" id="page-1">
    <mxGraphModel dx="1000" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0" defaultFontFamily="Helvetica">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

## Common Cells

Rectangle:

```xml
<mxCell id="rect-1" value="Label" style="rounded=1;whiteSpace=wrap;html=1;fontFamily=Helvetica;fontSize=14;" vertex="1" parent="1">
  <mxGeometry x="100" y="100" width="160" height="60" as="geometry" />
</mxCell>
```

Connector:

```xml
<mxCell id="edge-1" value="API" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;fontFamily=Helvetica;fontSize=12;" edge="1" parent="1" source="rect-1" target="rect-2">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

External system:

```xml
<mxCell id="jira" value="Jira" style="rounded=1;dashed=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontColor=#333333;fontFamily=Helvetica;fontSize=14;" vertex="1" parent="1">
  <mxGeometry x="100" y="100" width="140" height="50" as="geometry" />
</mxCell>
```
