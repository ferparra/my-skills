# Element Templates

Copy-paste JSON snippets for common element types. All use semantic colors, `fontFamily: 3`, `roughness: 0`.

## Rectangle (with bound text)

```json
{
  "id": "rect_unique_id",
  "type": "rectangle",
  "x": 100,
  "y": 100,
  "width": 180,
  "height": 90,
  "strokeColor": "#1E1E1E",
  "backgroundColor": "#E8E8E8",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "roughness": 0,
  "opacity": 100,
  "seed": 123,
  "version": 1,
  "versionNonce": 1,
  "boundElements": [{"id": "text_unique_id", "type": "text"}]
}
```

## Text (bound to container)

```json
{
  "id": "text_unique_id",
  "type": "text",
  "x": 110,
  "y": 120,
  "width": 160,
  "height": 50,
  "text": "Label Text",
  "originalText": "Label Text",
  "fontSize": 20,
  "fontFamily": 3,
  "textAlign": "center",
  "verticalAlign": "middle",
  "lineHeight": 1.25,
  "strokeColor": "#1E1E1E",
  "backgroundColor": "transparent",
  "opacity": 100,
  "containerId": "rect_unique_id",
  "seed": 124,
  "version": 1,
  "versionNonce": 1
}
```

## Arrow (with bindings)

```json
{
  "id": "arrow_unique_id",
  "type": "arrow",
  "x": 300,
  "y": 145,
  "width": 100,
  "height": 0,
  "points": [[0, 0], [100, 0]],
  "strokeColor": "#1E1E1E",
  "backgroundColor": "transparent",
  "strokeWidth": 2,
  "roughness": 0,
  "opacity": 100,
  "startBinding": {"elementId": "source_id", "focus": 0, "gap": 10},
  "endBinding": {"elementId": "target_id", "focus": 0, "gap": 10},
  "startArrowhead": null,
  "endArrowhead": "arrow",
  "seed": 125,
  "version": 1,
  "versionNonce": 1
}
```

## Diamond (decision node)

```json
{
  "id": "diamond_unique_id",
  "type": "diamond",
  "x": 100,
  "y": 100,
  "width": 120,
  "height": 120,
  "strokeColor": "#1E1E1E",
  "backgroundColor": "#FFCC00",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "roughness": 0,
  "opacity": 100,
  "seed": 126,
  "version": 1,
  "versionNonce": 1
}
```

## Ellipse (entity)

```json
{
  "id": "ellipse_unique_id",
  "type": "ellipse",
  "x": 100,
  "y": 100,
  "width": 120,
  "height": 80,
  "strokeColor": "#1E1E1E",
  "backgroundColor": "#FFB366",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "roughness": 0,
  "opacity": 100,
  "seed": 127,
  "version": 1,
  "versionNonce": 1
}
```

## Line (non-directional connection)

```json
{
  "id": "line_unique_id",
  "type": "line",
  "x": 100,
  "y": 100,
  "width": 200,
  "height": 100,
  "points": [[0, 0], [100, 50], [200, 100]],
  "strokeColor": "#1E1E1E",
  "backgroundColor": "transparent",
  "strokeWidth": 2,
  "roughness": 0,
  "opacity": 100,
  "seed": 128,
  "version": 1,
  "versionNonce": 1
}
```

## Free-floating Text

```json
{
  "id": "text_free_unique_id",
  "type": "text",
  "x": 100,
  "y": 100,
  "width": 200,
  "height": 25,
  "text": "Free-floating label",
  "originalText": "Free-floating label",
  "fontSize": 20,
  "fontFamily": 3,
  "textAlign": "left",
  "verticalAlign": "top",
  "lineHeight": 1.25,
  "strokeColor": "#1E1E1E",
  "backgroundColor": "transparent",
  "opacity": 100,
  "containerId": null,
  "seed": 129,
  "version": 1,
  "versionNonce": 1
}
```
