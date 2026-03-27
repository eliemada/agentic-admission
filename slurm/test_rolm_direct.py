"""Quick standalone test: send a PDF page to RolmOCR via vLLM and print the result.

Usage (on the cluster, while vLLM is running):
    uv run python slurm/test_rolm_direct.py data/processed/dossiers/2020-21-fall/abi_antoun/.../some.pdf
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from openai import OpenAI


def ocr_page(client: OpenAI, model: str, image_b64: str) -> str:
    """Send a base64 image to RolmOCR and return the text."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Return the plain text representation of this document "
                            "as if you were reading it naturally.\n"
                        ),
                    },
                ],
            }
        ],
        temperature=0.2,
        max_tokens=2000,
    )
    return response.choices[0].message.content or ""


def pdf_page_to_png_b64(pdf_path: Path, page: int = 0) -> str:
    """Render a PDF page to PNG and return base64."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        pix = doc[page].get_pixmap(dpi=200)
        return base64.b64encode(pix.tobytes("png")).decode()
    except ImportError:
        from pdf2image import convert_from_path

        images = convert_from_path(str(pdf_path), first_page=page + 1, last_page=page + 1, dpi=200)
        import io

        buf = io.BytesIO()
        images[0].save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python slurm/test_rolm_direct.py <path-to-pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    import os

    base_url = os.environ.get("VLM_BASE_URL", "http://localhost:8001/v1")
    model = os.environ.get("VLM_MODEL_NAME", "reducto/RolmOCR")

    client = OpenAI(api_key="dummy", base_url=base_url)

    print(f"Rendering {pdf_path} page 1 to PNG ...")
    img_b64 = pdf_page_to_png_b64(pdf_path, page=0)
    print(f"Image size: {len(img_b64)} bytes (base64)")

    print(f"Sending to {base_url} model={model} ...")
    text = ocr_page(client, model, img_b64)

    print("\n=== OCR OUTPUT ===")
    print(text)
    print("=== END ===")
    print(f"\nCharacters: {len(text)}")


if __name__ == "__main__":
    main()
