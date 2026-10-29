# Third-party components

The [MIT license](LICENSE) covers Frankesso's original source code and documentation. It does not relicense separately installed models, runtimes, libraries, private skills, or user data.

Frankesso does not bundle or download the following components. Obtain them separately and retain the licenses and notices supplied with the exact distributions you use.

| Component | Use | Upstream license |
| --- | --- | --- |
| [Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) | Local language model | [Apache-2.0](https://huggingface.co/Qwen/Qwen3-4B/blob/main/LICENSE) |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | Local inference server | [MIT](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) |
| [Python](https://www.python.org/) | Interpreter and standard library | [PSF license agreement and included notices](https://docs.python.org/3/license.html) |
| [pypdf](https://github.com/py-pdf/pypdf) | Optional PDF text extraction | [BSD-3-Clause](https://github.com/py-pdf/pypdf/blob/main/LICENSE) |
| [Pillow](https://github.com/python-pillow/Pillow) | Optional image metadata | [MIT-CMU](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |

The configured GGUF filename does not identify its distributor. Check the source and license of the specific quantized model you install, not only the upstream model card. Packaged runtimes and libraries may include additional components and notices. Any redistribution of those components must comply with their own terms.
