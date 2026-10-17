# Dashboard design: what I did and why

[Русская версия](dashboard_design.ru.md)

The numbers and the logic of the dashboard come from the SQL in `sql/dashboard/` and
the definitions in [dashboard_spec.md](dashboard_spec.md). This note is only about
how the page looks and reads. Every principle below is applied in `src/pa/dashboard.py`.

| Principle | What the page does | Why |
|---|---|---|
| Headlines state the finding | The page title and every block title are sentences with numbers ("Weekly orders grew from about 270 to about 1,370, with one spike: the Black Friday week..."). They are written in code from the query results, so they cannot drift from the data. | A reader gets the point without decoding the chart; a label like "Orders per week" leaves that work to them. |
| One "so what" line | Under the headline: June 2018 had the lowest late share in the window, so July's rise looks bigger than it is. | The raw card says "+2.2 pp, bad"; the context says it is not alarming. A number without context misleads. |
| Annotate on the chart | The Black Friday week is marked on the trend; the shaded tail says the data thins out in August 2018 and is not drawn; the last value is printed at the line end instead of a legend. | Direct labels remove the look-up between legend and line. |
| Grey for context, one accent | Greys for everything that is context, one deep teal for what matters (the current period, the biggest funnel drop, the trend line). | When everything is coloured, nothing stands out. |
| Colour-blind-safe meaning | Good = teal, bad = orange (different hue and lightness), and every delta also has an arrow and a sign (▲ +2.2 pp). Tables tint only the late % and review cells, softly. | Red/green alone fails for a noticeable share of men (red-green colour blindness is common); meaning must not rest on colour only. |
| Declutter | No card borders, shadows or gradients; no Plotly toolbar or logo; no vertical grid, a very light horizontal grid, no axis lines, transparent plot background, small margins. | Every pixel that is not data or a label competes with the data. |
| Clean hover | Unified hover on the trend with formatted numbers, white label, no trace boxes. | Hover is for exact values, so it shows only those. |
| Sparklines in the cards | A 12-month line without axes under each card, the last point in the accent colour. | A card shows one number; the sparkline shows whether it is a trend or a blip, in 32 pixels. |
| Consistent deltas | The same shape everywhere: "▲ +1.9% vs Jun 2018" and "▲ +79.7% vs Jul 2017"; pp for the late share, pts for the review score. | Fewer formats to learn. |
| Typography | One font (Inter, with system fallback; IBM Plex Sans is the second choice), tabular numbers, numbers right-aligned, one format per kind (BRL 1.04M, thousands separators), same font inside the Plotly charts, near-black text. | Aligned digits can be compared by eye; one font looks designed. |
| Spacing and layout | An 8-pixel grid, wide margins, content width up to 1,200 px, the grid stacks on a phone. | White space groups things without lines. |
| Funnel as bars | Horizontal bars in grey, with the step conversion and the number of lost orders printed on each bar; the biggest drop is in the accent colour. | The step bars are almost the same length (the losses are a few percent), so the labels carry the information and the colour points to the one that matters. |
| Tables with inline bars | The GMV column has a light bar behind the number (relative to the largest row). | Ranking is visible without a separate chart. |
| Narrative order | Headline and "so what", KPI cards, funnel, trend, tables, footer with source, licence credit, window and the note that the requirements are simulated. | The order the Head of Sales reads in: what happened, where it leaks, since when, who. |

## Choices I made and what they cost

- The Inter font is loaded from Google Fonts. Offline, the page falls back to the
  system font; the numbers do not change.
- Plotly is loaded from a CDN, so the two charts need internet.
- The static preview PNG (matplotlib) uses the same palette and layout; it uses Inter
  or IBM Plex Sans if installed, otherwise DejaVu Sans, so letter shapes can differ
  from the HTML. It shows 8 table rows instead of 15.
- The thresholds for tinting (1 pp, 0.1 points) are simulated, as in the spec.
- I could not open the HTML in a browser in my environment, so the visual check was
  made on the PNG; check the HTML once in a browser.

## Sources

- Datawrapper, text in data visualizations:
  https://www.datawrapper.de/blog/text-in-data-visualizations
- Datawrapper, colours in data visualization: https://www.datawrapper.de/blog/colors
- Datawrapper, emphasize with colour:
  https://www.datawrapper.de/blog/emphasize-with-color-in-data-visualizations
- Financial Times, Visual Vocabulary (which chart for which question):
  https://github.com/Financial-Times/chart-doctor/tree/main/visual-vocabulary
- Plotly, configuration options (`displayModeBar`):
  https://plotly.com/python/configuration-options/
- Plotly, hover text and formatting (`hovertemplate`, unified hover):
  https://plotly.com/python/hover-text-and-formatting/
- Plotly, templates: https://plotly.com/python/templates/
- Cole Nussbaumer Knaflic, *Storytelling with Data* (declutter, focus attention); Edward
  Tufte, sparklines in *Beautiful Evidence* (the term is Tufte's; the card
  sparklines follow his idea of a word-sized chart).

The principles came to me as a research summary of these sources; I did not re-read
the pages or the books while writing this note, so treat the links as the place to
check the details. The Plotly links are the documentation for the options used.
