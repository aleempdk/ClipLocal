# Contributing

Report reproducible bugs and discuss larger changes before implementing them. Keep the core workflow local and usable without paid APIs. Avoid adding personal media, downloads, model caches, credentials or machine-specific settings to commits.

## Local checks

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

For changes to rendering, also export a short clip and review frames and audio. Explain what changed, how it was verified, and any limitations in your pull request. Contributions are distributed under the repository's MIT license; third-party components retain their own licenses.
