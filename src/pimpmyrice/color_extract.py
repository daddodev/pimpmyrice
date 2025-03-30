import logging
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from pimpmyrice.colors import Color

log = logging.getLogger(__name__)


def kmeans(
    pixels: NDArray[np.uint8],
    num_clusters: int = 6,
    max_iter: int = 100,
    tol: float = 1e-4,
) -> list[tuple[tuple[int, int, int], int]]:
    np.random.seed(42)
    indices = np.random.choice(len(pixels), num_clusters, replace=False)
    cluster_centers = pixels[indices]

    for iteration in range(max_iter):
        distances = np.linalg.norm(pixels[:, np.newaxis] - cluster_centers, axis=2)
        labels = np.argmin(distances, axis=1)

        new_cluster_centers: Any = []
        cluster_sizes = []

        for k in range(num_clusters):
            cluster_pixels = pixels[labels == k]
            if len(cluster_pixels) == 0:
                new_center = pixels[np.random.choice(len(pixels))]
            else:
                new_center = cluster_pixels.mean(axis=0)
            new_cluster_centers.append(new_center)
            cluster_sizes.append(len(cluster_pixels))

        new_cluster_centers = np.array(new_cluster_centers)

        if np.linalg.norm(new_cluster_centers - cluster_centers) < tol:
            break
        cluster_centers = new_cluster_centers

    sorted_clusters = sorted(
        zip(cluster_centers, cluster_sizes), key=lambda x: x[1], reverse=True
    )

    sorted_cluster_centers = [
        (tuple(center.astype(int)), size) for center, size in sorted_clusters
    ]

    return sorted_cluster_centers


@cache
def extract_colors(
    image_path: Path, num_colors: int = 6, resize_to_size: int = 300
) -> list[tuple[Color, int]]:
    img = Image.open(image_path).convert("RGB")

    width, height = img.size
    resize_factor = resize_to_size / max(width, height)
    new_width, new_height = (int(width * resize_factor), int(height * resize_factor))
    img = img.resize((new_width, new_height))

    img_array: NDArray[np.uint8] = np.array(img)
    pixels: NDArray[np.uint8] = img_array.reshape(-1, 3)

    rgb_with_count = kmeans(pixels, num_clusters=num_colors)
    colors_with_count = [(Color(rgb), count) for rgb, count in rgb_with_count]

    return colors_with_count


# def are_hues_close(hue1: float, hue2: float, tolerance: int = 30) -> bool:
#     if abs(hue1 - hue2) < tolerance:
#         return True
#     elif hue1 - tolerance < 0 and hue1 + 360 - hue2 < tolerance:
#         return True
#     elif hue2 - tolerance < 0 and hue2 + 360 - hue1 < tolerance:
#         return True
#     return False
