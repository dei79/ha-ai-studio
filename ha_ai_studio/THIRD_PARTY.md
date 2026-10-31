# Origin and dependencies

The action core and Echo plugin are local project code evolved from the existing HA AI Studio development copy. Action-specific inference code and pretrained models are supplied by separate Action repositories. The runtime includes Tesseract OCR and English trained data from Ubuntu packages for local number-block recognition. Tesseract and its trained data retain their Apache-2.0 licenses; package copyright notices are retained under /usr/share/doc.

Runtime dependencies come from PyPI and are pinned in `requirements.lock.txt`. Installed distribution metadata and license files remain in the container. Metadata inspected in the built amd64 image reports:

| Package | License |
| --- | --- |
| aiohttp | Apache-2.0 AND MIT |
| packaging | Apache-2.0 OR BSD-2-Clause |
| paho-mqtt | EPL-2.0 OR BSD-3-Clause |
| aiohappyeyeballs, typing_extensions | PSF-2.0 |
| aiosignal, frozenlist, multidict, propcache, yarl | Apache-2.0 |
| attrs, jsonschema, jsonschema-specifications, referencing, rpds-py | MIT |
| idna | BSD-3-Clause |

The Ubuntu 24.04 LTS container base image is pinned by digest in the Dockerfile; its own runtime and system packages retain their upstream notices. The frontend bundles React, React DOM and Scheduler from npm, pinned in `frontend/package-lock.json`. Build-only tools and Node are excluded from the runtime image. No external fonts, images or CDN resources are loaded. HA AI Studio original code, documentation and artwork are licensed under MIT; see LICENSE. Third-party components retain their respective licenses.

## React, React DOM and Scheduler

MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
