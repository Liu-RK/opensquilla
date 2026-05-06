---
name: website-builder
description: "Generate a static website (HTML/CSS) from Jinja templates and a JSON content file. Trigger when the user wants to build a landing page, portfolio, marketing site, documentation home, or any small static site that does not need a CMS or backend. Two scripts: `generate.py` renders templates + content into a site directory; `preview.py` serves it locally for inspection. Output is plain static files — deploy with any host (GitHub Pages, Netlify, Vercel, S3+CloudFront, plain nginx)."
homepage: ""
provenance:
  origin: clawhub-mit0
  license: MIT-0
  upstream_url: https://clawhub.ai/website
  maintained_by: OpenSquilla
metadata:
  {
    "platform":
      {
        "emoji": "🌐",
        "requires": { "anyBins": ["python", "python3"] },
      },
  }
---

# website-builder

Build small static sites from Jinja templates and a JSON content file.
This is intentionally less than a full SSG (Hugo, Eleventy, Astro) — it
is the right tool when an LLM agent is generating the site one-shot from
a brief, not when a human team will iterate on it for months.

## When to use

- Single-page landing site for a project
- 3-10 page portfolio / marketing site
- Documentation home page
- Event invite, RSVP page
- Internal team page

## When NOT to use

- The site needs to scale to dozens of pages with editorial workflow —
  use Astro, Eleventy, or Hugo instead
- The site needs server-side logic, auth, or a database — that is a web
  app, not a static site
- The site needs a CMS for non-technical users — use Webflow, Framer,
  or a headless CMS

## Quick start

```bash
# Generate
python {baseDir}/scripts/generate.py \
    --template tpl/ \
    --content content.json \
    --out site/

# Preview locally
python {baseDir}/scripts/preview.py --root site/ --port 8000
# Open http://localhost:8000
```

## Project layout

```
my-site/
├── tpl/                        # Jinja templates and assets
│   ├── base.html.j2
│   ├── index.html.j2
│   ├── about.html.j2
│   └── static/                 # CSS / images / fonts (copied verbatim)
│       ├── styles.css
│       └── logo.svg
├── content.json                # the data driving template rendering
└── site/                       # output (generated; .gitignored)
```

`content.json`:

```json
{
  "site": {
    "title": "Acme",
    "base_url": "https://acme.com",
    "description": "We build...",
    "nav": [
      {"text": "Home", "href": "/"},
      {"text": "About", "href": "/about/"}
    ]
  },
  "pages": [
    {
      "template": "index.html.j2",
      "out": "index.html",
      "data": {
        "hero_title": "Build less, ship more",
        "hero_subtitle": "...",
        "features": [
          {"icon": "🚀", "title": "Fast", "body": "..."},
          {"icon": "🛠", "title": "Customizable", "body": "..."}
        ]
      }
    },
    {
      "template": "about.html.j2",
      "out": "about/index.html",
      "data": {"team_size": 12}
    }
  ]
}
```

The `data` block for each page is merged with the global `site` block and
passed to the Jinja template. Templates can reference both via
`{{ site.title }}` and page-local fields.

## Templates

Templates use standard Jinja 2 syntax. Inheritance via `extends`/`block`
is the standard pattern:

```jinja
{# base.html.j2 #}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ site.title }}{% block title_suffix %}{% endblock %}</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <nav>
    {% for item in site.nav %}<a href="{{ item.href }}">{{ item.text }}</a>{% endfor %}
  </nav>
  <main>{% block main %}{% endblock %}</main>
</body>
</html>
```

```jinja
{# index.html.j2 #}
{% extends "base.html.j2" %}
{% block main %}
<h1>{{ hero_title }}</h1>
<p>{{ hero_subtitle }}</p>
<section class="features">
  {% for feature in features %}
  <article><span>{{ feature.icon }}</span><h2>{{ feature.title }}</h2><p>{{ feature.body }}</p></article>
  {% endfor %}
</section>
{% endblock %}
```

## Static assets

Anything under `tpl/static/` is copied verbatim to `site/static/`. Do not
put `*.j2` files there; only fonts, images, CSS, JS that should ship as-is.

## SEO checklist

See [references/seo_checklist.md](references/seo_checklist.md) for the
short list of things to include in `base.html.j2`: meta description, og
tags, sitemap.xml, robots.txt, semantic heading hierarchy, alt text.

## Deploy

The skill stops at file generation. Deployment depends on host:

- GitHub Pages: push `site/` contents to `gh-pages` branch
- Netlify / Vercel: connect repo, set build command to invoke
  `generate.py`, output dir to `site/`
- S3 + CloudFront: `aws s3 sync site/ s3://bucket/`
- nginx: `rsync site/ user@host:/var/www/`

## Boundaries

- No JavaScript framework integration (React, Vue) — output is plain
  HTML/CSS. Use a JS framework's own SSG for those.
- No authentication, no forms backend, no databases.
- No incremental builds — every run rebuilds everything. For sites large
  enough to care, switch to a real SSG.
- No live reload — `preview.py` serves static files; refresh the browser
  manually after `generate.py` reruns.
