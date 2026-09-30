"""Semantic edit regions, independent of image libraries and model providers."""
import math

VERSION = 'image.journey.mask@1.0.0'


def dimensions_3mp(size):
    width, height = size
    scale = min(math.sqrt(3 * 1024 ** 2 / (width * height)), 4096 / max(size))
    return tuple(max(64, round(side * scale / 32) * 32) for side in size)


def validate_plan(value):
    if not isinstance(value, dict) or set(value) != {'observation', 'regions'}:
        raise ValueError('Le masque automatique doit décrire les zones à conserver du rendu.')
    observation, regions = value['observation'], value['regions']
    if not isinstance(observation, str) or not observation.strip() or len(observation) > 3000:
        raise ValueError('Description du masque automatique invalide.')
    if not isinstance(regions, list) or len(regions) > 24:
        raise ValueError('Le masque automatique accepte au maximum 24 zones.')

    def polygon(points):
        if not isinstance(points, list) or not 3 <= len(points) <= 64:
            raise ValueError('Un contour du masque doit avoir entre 3 et 64 points.')
        for point in points:
            if not isinstance(point, dict) or set(point) != {'x', 'y'}:
                raise ValueError('Coordonnées du masque invalides.')
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1000
                   for v in point.values()):
                raise ValueError('Les coordonnées du masque doivent être comprises entre 0 et 1000.')
        area = abs(sum(a['x'] * b['y'] - b['x'] * a['y'] for a, b in zip(points, points[1:] + points[:1])))
        if area < 1:
            raise ValueError('Un contour du masque a une surface nulle.')
        return points

    for region in regions:
        if not isinstance(region, dict) or set(region) != {'label', 'outline', 'holes'}:
            raise ValueError('Zone du masque automatique invalide.')
        if not isinstance(region['label'], str) or not region['label'].strip() or len(region['label']) > 300:
            raise ValueError('Libellé de zone invalide.')
        polygon(region['outline'])
        if not isinstance(region['holes'], list) or len(region['holes']) > 12:
            raise ValueError('Exclusions du masque invalides.')
        for hole in region['holes']:
            polygon(hole)
    return value
