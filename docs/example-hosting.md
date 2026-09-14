# Hosting the static example

[View the live designed example](https://loubuilds.github.io/uk-labour-market-navigator/). The [Markdown brief](../examples/brief.md) remains readable on GitHub, and the [HTML file](../examples/brief.html) can be downloaded for local reading. The live response was checked byte-for-byte against the generated HTML.

The manual GitHub Pages workflow is [example-pages.yml](../.github/workflows/example-pages.yml). It does not run on push or pull request. It regenerates and verifies the fictional example, then deploys **only its self-contained HTML as index.html**. It uploads no engine, research folders, account configuration or private drafts. This is a static demonstration, not a hosted research application.

## Updating the example

1. Regenerate and check the fictional example through the supported workflow, then push the reviewed changes. Wait for validation to pass.
2. Open **Actions → Publish static example → Run workflow**, selecting **main**. This is the separate action that publishes the HTML.
3. Wait for deployment to succeed and check the URL reported by its `github-pages` environment on desktop and mobile. A push alone does not update the hosted report.

GitHub Pages is configured to use **GitHub Actions** in this repository. A fork's owner must first select that source under **Settings → Pages → Build and deployment**; account permissions or environment protection may require the owner's action. The workflow does not enable Pages or change account settings itself.

To prepare the identical upload locally without deployment, from the repository folder use:

```sh
python -m scripts.prepare_example_site --output dist/example-site
```

Choose a new output directory on a later run. The command refuses an existing directory so unrelated files cannot be included. The resulting directory contains just `index.html`.

The chart preview is extracted from the generated report by `scripts.make_example`; it is a chart excerpt, not a browser screenshot. No browser, image service or extra runtime dependency is needed. The example check compares the SVG as well as HTML, Markdown and evidence, so it cannot silently lag behind the report.

See [GitHub's custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) for the hosting mechanism.
