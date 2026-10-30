# Origin and dependencies

The action core and Echo plugin are local project code evolved from the existing HA AI Studio development copy. No inference code, pretrained models, image processing or OCR runtime is shipped.

Runtime dependencies come from PyPI and are pinned in `requirements.lock.txt`. Installed distribution metadata and license files remain in the container. Metadata inspected in the built amd64 image reports:

| Package | License |
| --- | --- |
| aiohttp | Apache-2.0 AND MIT |
| packaging | Apache-2.0 OR BSD-2-Clause |
| paho-mqtt | EPL-2.0 OR BSD-3-Clause |
| aiohappyeyeballs, typing_extensions | PSF-2.0 |
| aiosignal, frozenlist, multidict, propcache, yarl | Apache-2.0 |
| attrs | MIT |
| idna | BSD-3-Clause |

The Ubuntu 24.04 LTS container base image is pinned by digest in the Dockerfile; its own runtime and system packages retain their upstream notices. No third-party frontend framework, fonts, images or CDN resources are included. HA AI Studio original code, documentation and artwork are licensed under MIT; see LICENSE. Third-party components retain their respective licenses.
