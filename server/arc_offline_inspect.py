"""Bounded, local-only JPEG diagnostics. No model, action planning or persistence.

This module is intentionally not an AI substitute: it reports capture quality and
basic image metadata without inferring UI semantics, cards or account balances.
"""
from io import BytesIO
from PIL import Image, ImageStat, UnidentifiedImageError

MAX_DIMENSION = 4096
MAX_PIXELS = 12_000_000


class InvalidOfflineFrame(ValueError):
    pass


def inspect_jpeg(data: bytes) -> dict:
    if not isinstance(data, bytes) or not data.startswith(b'\xff\xd8'):
        raise InvalidOfflineFrame('expected_jpeg')
    try:
        with Image.open(BytesIO(data)) as original:
            if original.format != 'JPEG':
                raise InvalidOfflineFrame('expected_jpeg')
            width, height = original.size
            if (width < 64 or height < 64 or width > MAX_DIMENSION or
                    height > MAX_DIMENSION or width * height > MAX_PIXELS):
                raise InvalidOfflineFrame('unsupported_dimensions')
            # Decode the entire image before reporting success; JPEG SOI/EOI alone
            # is not sufficient to establish a valid capture.
            original.load()
            gray = original.convert('L')
            gray.thumbnail((128, 128))
            stat = ImageStat.Stat(gray)
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise InvalidOfflineFrame('invalid_or_truncated_jpeg') from exc

    brightness = round(float(stat.mean[0]), 1)
    contrast = round(float(stat.stddev[0]), 1)
    issues = []
    if min(width, height) < 480:
        issues.append('low_resolution')
    if brightness < 35:
        issues.append('very_dark')
    elif brightness > 225:
        issues.append('very_bright')
    if contrast < 15:
        issues.append('low_contrast')
    return {
        'mode': 'offline_capture_diagnostics',
        'provider': 'local_pillow',
        'uses_openai_api': False,
        'uses_chatgpt_subscription': False,
        'action': None,
        'money_actions_enabled': False,
        'authoritative': False,
        'width': width,
        'height': height,
        'jpeg_bytes': len(data),
        'mean_luminance_0_255': brightness,
        'luminance_stddev': contrast,
        'quality_flags': issues,
        'note': 'Capture quality only. No OCR, card recognition, or UI interpretation.',
    }
