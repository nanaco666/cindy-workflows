# Model comparison poster workflow

This package is portable. Install it from nanaco666/cindy-workflows, fill the local configuration, then let Cindy or a local agent run the research-to-poster steps. It does not ship a private catalog, a local background library, credentials, or finished customer data.

The installer creates a local directory containing config.local.json, content/, out/, and a schedule template. Set source_urls to official pages for the model family. If you use a hero image, set hero_image or asset_dir to a path on the current machine and use only assets you are licensed to use. Leave them empty to render the typography/table poster without an image.

Manual run:

    python3 scripts/validate_facts.py content/<slug>.json --config config.local.json
    python3 scripts/render.py content/<slug>.json --config config.local.json --out-dir out/<slug>
    python3 scripts/capture_poster.py out/<slug>/index.html out/<slug>/poster-cn.png
    python3 scripts/capture_poster.py out/<slug>/index-en.html out/<slug>/poster-en.png

capture_poster.py needs a local Chrome/Chromium executable and Playwright. Set chrome in the config or CINDY_POSTER_CHROME; no executable path is hardcoded in the package.
