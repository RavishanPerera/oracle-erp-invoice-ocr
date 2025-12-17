from typing import Iterable

from pdf2image import convert_from_path
from PIL import Image, ImageOps
import pytesseract


# Absolute path to your Poppler installation (already installed on your machine)
POPPLER_PATH = r"C:\poppler-23.08.0\Library\bin"


def _preprocess_image(image: Image.Image) -> Image.Image:
    """
    Basic preprocessing to improve OCR quality:
    - convert to grayscale
    - apply automatic contrast enhancement
    """
    gray = ImageOps.grayscale(image)
    enhanced = ImageOps.autocontrast(gray)
    return enhanced


def _image_to_text(image: Image.Image, tesseract_config: str | None = None) -> str:
    """
    Run Tesseract on a PIL image with optional configuration.
    """
    processed = _preprocess_image(image)
    config = tesseract_config or "--oem 3 --psm 6"
    return pytesseract.image_to_string(processed, config=config)


def extract_text_from_image(image_path: str, tesseract_config: str | None = None) -> str:
    """
    Read an image from disk and extract text using Tesseract OCR.

    Parameters
    ----------
    image_path: str
        Path to the image file.
    tesseract_config: str | None
        Extra configuration flags passed directly to Tesseract.
    """
    image = Image.open(image_path)
    return _image_to_text(image, tesseract_config=tesseract_config)


def extract_text_from_pdf(
    pdf_path: str,
    dpi: int = 300,
    tesseract_config: str | None = None,
) -> str:
    """
    Convert each page of a PDF to an image and run Tesseract OCR using Poppler.

    Parameters
    ----------
    pdf_path: str
        Path to the PDF file.
    dpi: int
        Resolution used when rasterizing PDF pages. Higher values improve OCR
        quality at the cost of performance and memory.
    tesseract_config: str | None
        Extra configuration flags passed directly to Tesseract.
    """
    pages: Iterable[Image.Image] = convert_from_path(
        pdf_path,
        dpi=dpi,
        poppler_path=POPPLER_PATH,
    )

    full_text_parts: list[str] = []
    for page in pages:
        text = _image_to_text(page, tesseract_config=tesseract_config)
        if text:
            full_text_parts.append(text.strip())

    return "\n\n".join(full_text_parts)
