# SEO checklist

Short, opinionated list of what every page rendered by this skill should
include. Add these to `base.html.j2` once and they cover every page that
extends it.

## Meta head

```html
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page_title }} — {{ site.title }}</title>
  <meta name="description" content="{{ page_description | default(site.description) }}">
  <link rel="canonical" href="{{ site.base_url }}{{ page_path }}">

  <!-- Open Graph -->
  <meta property="og:title" content="{{ page_title }}">
  <meta property="og:description" content="{{ page_description | default(site.description) }}">
  <meta property="og:url" content="{{ site.base_url }}{{ page_path }}">
  <meta property="og:type" content="website">
  <meta property="og:image" content="{{ site.base_url }}{{ og_image | default('/static/og-default.png') }}">

  <!-- Twitter -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{{ page_title }}">
  <meta name="twitter:description" content="{{ page_description | default(site.description) }}">
  <meta name="twitter:image" content="{{ site.base_url }}{{ og_image | default('/static/og-default.png') }}">

  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <link rel="alternate icon" href="/static/favicon.ico">
</head>
```

`page_title`, `page_description`, `page_path`, and `og_image` are
per-page variables in `content.json`'s `pages[].data` block.

## Heading hierarchy

One `<h1>` per page. Subsections in `<h2>`, nested in `<h3>`. Do not
skip levels.

```html
<main>
  <h1>{{ hero_title }}</h1>
  <section>
    <h2>{{ section_title }}</h2>
    <h3>...</h3>
  </section>
</main>
```

## Image alt text

Every `<img>` must have an `alt` attribute. Decorative images use
`alt=""` (empty but present); content images use a description.

```html
<img src="/static/team.jpg" alt="Team photo from offsite, 2026">
<img src="/static/decoration.svg" alt="">
```

## Sitemap

Generate `sitemap.xml` at the site root. The generator does not produce
this automatically; add a `sitemap.xml.j2` template to the project and
include it in `content.json`'s pages list with `out: "sitemap.xml"`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  {% for page in site.sitemap_pages %}
  <url>
    <loc>{{ site.base_url }}{{ page.path }}</loc>
    <lastmod>{{ page.lastmod }}</lastmod>
    <priority>{{ page.priority }}</priority>
  </url>
  {% endfor %}
</urlset>
```

## robots.txt

```
User-agent: *
Allow: /
Sitemap: {{ site.base_url }}/sitemap.xml
```

Render this as another page entry: `template: "robots.txt.j2"`,
`out: "robots.txt"`.

## Performance

Two cheap wins:

- Inline above-the-fold CSS in `<style>` so first paint does not wait
  for `styles.css`. Keep below-the-fold CSS in the external file.
- `loading="lazy"` on every `<img>` below the fold.

Real performance work belongs in a follow-up step (image optimization,
CSS purging, font subsetting). The skill does not do these.

## Lighthouse minimums

After preview, run Lighthouse against the local URL. Targets:

| Metric | Minimum |
|---|---|
| Performance | 90+ |
| Accessibility | 95+ |
| Best practices | 95+ |
| SEO | 95+ |

Most failures are missing meta tags, alt text, or contrast. The
checklist above prevents the common ones.

## Anti-patterns

- **Skipping heading levels**: jumping from `<h1>` to `<h3>`. Screen
  readers and search bots both penalize.
- **Empty `<title>` tag**: Lighthouse fails Best Practices and SEO.
- **Same `og:image` for every page**: technically valid but a missed
  opportunity. Generate per-page OG images when stakes are high.
- **Mixing relative and absolute URLs**: pick one (recommended:
  absolute, since `og:url` and canonical require them anyway).
