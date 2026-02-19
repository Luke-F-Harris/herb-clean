"""OpenCV template matching with multi-scale support."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ..utils import BANK_BG_COLOR_BGR


@dataclass
class MatchResult:
    """Result of template matching."""

    found: bool
    confidence: float
    x: int  # Top-left x
    y: int  # Top-left y
    width: int
    height: int
    center_x: int
    center_y: int
    scale: float = 1.0


class TemplateMatcher:
    """Multi-scale template matching using OpenCV."""

    # Use shared constant for bank background color
    BANK_BG_COLOR = BANK_BG_COLOR_BGR

    def __init__(
        self,
        templates_dir: Path,
        confidence_threshold: float = 0.80,
        multi_scale: bool = True,
        scale_range: tuple[float, float] = (0.8, 1.2),
        scale_steps: int = 5,
    ):
        """Initialize template matcher.

        Args:
            templates_dir: Directory containing template images
            confidence_threshold: Minimum confidence for a match
            multi_scale: Enable multi-scale matching
            scale_range: (min_scale, max_scale) for multi-scale
            scale_steps: Number of scale steps to try
        """
        self.templates_dir = Path(templates_dir)
        self.confidence_threshold = confidence_threshold
        self.multi_scale = multi_scale
        self.scale_range = scale_range
        self.scale_steps = scale_steps
        self._template_cache: dict[str, np.ndarray] = {}
        self._template_mask_cache: dict[str, Optional[np.ndarray]] = {}
        self._histogram_cache: dict[str, np.ndarray] = {}

    def load_template(self, template_name: str) -> Optional[np.ndarray]:
        """Load a template image.

        Uses PIL for loading to properly handle palette-based PNGs with
        indexed transparency, which OpenCV's imread doesn't handle correctly.

        Args:
            template_name: Template filename

        Returns:
            BGR numpy array or None if not found
        """
        if template_name in self._template_cache:
            return self._template_cache[template_name]

        template_path = self.templates_dir / template_name
        if not template_path.exists():
            return None

        try:
            # Use PIL to load - handles palette PNGs with transparency correctly
            pil_image = Image.open(template_path)

            # Convert to RGBA to get proper alpha channel regardless of source format
            pil_rgba = pil_image.convert("RGBA")
            # Convert to numpy array (RGBA format)
            template_rgba = np.array(pil_rgba)
            # Convert from RGBA to BGRA (OpenCV format)
            template_bgra = cv2.cvtColor(template_rgba, cv2.COLOR_RGBA2BGRA)
        except Exception:
            return None

        # Extract alpha channel for mask
        alpha = template_bgra[:, :, 3]
        # Create mask where alpha > 0 (non-transparent pixels)
        mask = (alpha > 127).astype(np.uint8) * 255
        self._template_mask_cache[template_name] = mask

        # Composite onto bank background color for better matching
        template_bgr = template_bgra[:, :, :3].copy()
        # Where alpha is low (transparent), replace with bank background
        alpha_normalized = alpha.astype(np.float32) / 255.0
        for c in range(3):
            template_bgr[:, :, c] = (
                template_bgr[:, :, c] * alpha_normalized +
                self.BANK_BG_COLOR[c] * (1 - alpha_normalized)
            ).astype(np.uint8)

        self._template_cache[template_name] = template_bgr
        return template_bgr

    def get_template_mask(self, template_name: str) -> Optional[np.ndarray]:
        """Get the alpha mask for a template.

        Args:
            template_name: Template filename

        Returns:
            Grayscale mask or None if no mask exists
        """
        # Ensure template is loaded (which also loads mask)
        if template_name not in self._template_mask_cache:
            self.load_template(template_name)
        return self._template_mask_cache.get(template_name)

    def match(
        self,
        image: np.ndarray,
        template_name: str,
        method: int = cv2.TM_CCOEFF_NORMED,
        use_mask: bool = False,
    ) -> MatchResult:
        """Find template in image.

        Args:
            image: BGR image to search in
            template_name: Template filename to search for
            method: OpenCV template matching method
            use_mask: Whether to use alpha mask for matching (for transparent templates)

        Returns:
            MatchResult with match details
        """
        template = self.load_template(template_name)
        if template is None:
            return MatchResult(
                found=False,
                confidence=0.0,
                x=0,
                y=0,
                width=0,
                height=0,
                center_x=0,
                center_y=0,
            )

        mask = self.get_template_mask(template_name) if use_mask else None

        if self.multi_scale:
            return self._match_multi_scale(image, template, method, mask)
        else:
            return self._match_single_scale(image, template, method, mask)

    def _match_single_scale(
        self,
        image: np.ndarray,
        template: np.ndarray,
        method: int,
        mask: Optional[np.ndarray] = None,
    ) -> MatchResult:
        """Single-scale template matching."""
        h, w = template.shape[:2]

        # Skip if template larger than image
        if h > image.shape[0] or w > image.shape[1]:
            return MatchResult(
                found=False,
                confidence=0.0,
                x=0,
                y=0,
                width=0,
                height=0,
                center_x=0,
                center_y=0,
            )

        # Use mask-based matching if mask provided
        # Note: mask only works with TM_SQDIFF and TM_CCORR_NORMED
        if mask is not None and method in [cv2.TM_SQDIFF, cv2.TM_CCORR_NORMED]:
            result = cv2.matchTemplate(image, template, method, mask=mask)
        else:
            result = cv2.matchTemplate(image, template, method)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # For TM_SQDIFF methods, minimum is best match
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            confidence = 1.0 - min_val
            loc = min_loc
        else:
            confidence = max_val
            loc = max_loc

        found = confidence >= self.confidence_threshold

        return MatchResult(
            found=found,
            confidence=confidence,
            x=loc[0],
            y=loc[1],
            width=w,
            height=h,
            center_x=loc[0] + w // 2,
            center_y=loc[1] + h // 2,
        )

    def _run_match_template(
        self,
        image: np.ndarray,
        scaled_template: np.ndarray,
        method: int,
        scaled_mask: Optional[np.ndarray] = None,
    ) -> Tuple[float, Tuple[int, int]]:
        """Run template matching and extract confidence and location.

        Common helper for multi-scale matching methods.

        Args:
            image: BGR image to search in
            scaled_template: Pre-scaled template
            method: OpenCV template matching method
            scaled_mask: Pre-scaled mask (optional)

        Returns:
            (confidence, (x, y)) tuple with match confidence and location
        """
        # Use mask-based matching if available and method supports it
        if scaled_mask is not None and method in [cv2.TM_SQDIFF, cv2.TM_CCORR_NORMED]:
            result = cv2.matchTemplate(image, scaled_template, method, mask=scaled_mask)
        else:
            result = cv2.matchTemplate(image, scaled_template, method)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # For TM_SQDIFF methods, minimum is best match
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            confidence = 1.0 - min_val
            loc = min_loc
        else:
            confidence = max_val
            loc = max_loc

        return confidence, loc

    def _match_multi_scale(
        self,
        image: np.ndarray,
        template: np.ndarray,
        method: int,
        mask: Optional[np.ndarray] = None,
    ) -> MatchResult:
        """Multi-scale template matching for different resolutions."""
        best_result = MatchResult(
            found=False,
            confidence=0.0,
            x=0,
            y=0,
            width=0,
            height=0,
            center_x=0,
            center_y=0,
        )

        scales = np.linspace(
            self.scale_range[0], self.scale_range[1], self.scale_steps
        )

        for scale in scales:
            # Resize template
            h, w = template.shape[:2]
            new_w = int(w * scale)
            new_h = int(h * scale)

            if new_w <= 0 or new_h <= 0:
                continue
            if new_h > image.shape[0] or new_w > image.shape[1]:
                continue

            scaled_template = cv2.resize(template, (new_w, new_h))

            # Scale mask if provided
            scaled_mask = None
            if mask is not None:
                scaled_mask = cv2.resize(mask, (new_w, new_h))

            # Run template matching
            confidence, loc = self._run_match_template(
                image, scaled_template, method, scaled_mask
            )

            if confidence > best_result.confidence:
                best_result = MatchResult(
                    found=confidence >= self.confidence_threshold,
                    confidence=confidence,
                    x=loc[0],
                    y=loc[1],
                    width=new_w,
                    height=new_h,
                    center_x=loc[0] + new_w // 2,
                    center_y=loc[1] + new_h // 2,
                    scale=scale,
                )

        return best_result

    def _crop_to_bottom_region(
        self, image: np.ndarray, percentage: float = 0.65
    ) -> tuple[np.ndarray, int]:
        """Crop image to bottom N% of height.

        Args:
            image: Input image to crop
            percentage: Percentage of height to keep (0.0-1.0)

        Returns:
            Tuple of (cropped_image, crop_offset_y)
        """
        h = image.shape[0]
        crop_y = int(h * (1.0 - percentage))
        cropped = image[crop_y:, :]
        return cropped, crop_y

    def match_bottom_region(
        self,
        image: np.ndarray,
        template_name: str,
        region_percentage: float = 0.70,  # Balance: avoid stack text but keep enough template
        method: int = cv2.TM_CCORR_NORMED,  # Use CCORR_NORMED - supports masks
    ) -> MatchResult:
        """Match template using only bottom portion of image/template.

        This is useful for bank items where stack numbers overlay
        the top portion of the item icon.

        Uses TM_CCORR_NORMED by default since it supports mask-based matching,
        which ignores transparent pixels in the template.

        Args:
            image: BGR image to search in
            template_name: Template filename to search for
            region_percentage: Percentage of height to use (0.0-1.0), default 0.70
            method: OpenCV template matching method (must support masks for transparency)

        Returns:
            MatchResult with adjusted coordinates
        """
        template = self.load_template(template_name)
        if template is None:
            return MatchResult(
                found=False,
                confidence=0.0,
                x=0,
                y=0,
                width=0,
                height=0,
                center_x=0,
                center_y=0,
            )

        # Get original dimensions before cropping
        orig_template_h, orig_template_w = template.shape[:2]

        # Crop template to bottom region
        cropped_template, template_offset_y = self._crop_to_bottom_region(
            template, region_percentage
        )

        # Also crop mask if it exists
        mask = self.get_template_mask(template_name)
        cropped_mask = None
        if mask is not None:
            cropped_mask, _ = self._crop_to_bottom_region(mask, region_percentage)

        # Perform matching based on mode
        if self.multi_scale:
            result = self._match_multi_scale_cropped(
                image, cropped_template, template_offset_y,
                orig_template_w, orig_template_h, method, cropped_mask
            )
        else:
            result = self._match_single_scale_cropped(
                image, cropped_template, template_offset_y,
                orig_template_w, orig_template_h, method, cropped_mask
            )

        return result

    def _match_single_scale_cropped(
        self,
        image: np.ndarray,
        cropped_template: np.ndarray,
        template_offset_y: int,
        orig_width: int,
        orig_height: int,
        method: int,
        mask: Optional[np.ndarray] = None,
    ) -> MatchResult:
        """Single-scale matching with cropped template."""
        h, w = cropped_template.shape[:2]

        # Skip if template larger than image
        if h > image.shape[0] or w > image.shape[1]:
            return MatchResult(
                found=False,
                confidence=0.0,
                x=0,
                y=0,
                width=0,
                height=0,
                center_x=0,
                center_y=0,
            )

        # Use mask-based matching if mask provided
        if mask is not None and method in [cv2.TM_SQDIFF, cv2.TM_CCORR_NORMED]:
            result = cv2.matchTemplate(image, cropped_template, method, mask=mask)
        else:
            result = cv2.matchTemplate(image, cropped_template, method)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # For TM_SQDIFF methods, minimum is best match
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            confidence = 1.0 - min_val
            loc = min_loc
        else:
            confidence = max_val
            loc = max_loc

        found = confidence >= self.confidence_threshold

        # Adjust y-coordinate to account for crop offset
        # Use original template dimensions for width/height
        adjusted_y = loc[1] - template_offset_y

        return MatchResult(
            found=found,
            confidence=confidence,
            x=loc[0],
            y=adjusted_y,
            width=orig_width,
            height=orig_height,
            center_x=loc[0] + orig_width // 2,
            center_y=adjusted_y + orig_height // 2,
        )

    def _match_multi_scale_cropped(
        self,
        image: np.ndarray,
        cropped_template: np.ndarray,
        template_offset_y: int,
        orig_width: int,
        orig_height: int,
        method: int,
        mask: Optional[np.ndarray] = None,
    ) -> MatchResult:
        """Multi-scale matching with cropped template."""
        best_result = MatchResult(
            found=False,
            confidence=0.0,
            x=0,
            y=0,
            width=0,
            height=0,
            center_x=0,
            center_y=0,
        )

        scales = np.linspace(
            self.scale_range[0], self.scale_range[1], self.scale_steps
        )

        for scale in scales:
            # Resize cropped template
            h, w = cropped_template.shape[:2]
            new_w = int(w * scale)
            new_h = int(h * scale)

            if new_w <= 0 or new_h <= 0:
                continue
            if new_h > image.shape[0] or new_w > image.shape[1]:
                continue

            scaled_template = cv2.resize(cropped_template, (new_w, new_h))

            # Scale mask if provided
            scaled_mask = None
            if mask is not None:
                scaled_mask = cv2.resize(mask, (new_w, new_h))

            # Run template matching
            confidence, loc = self._run_match_template(
                image, scaled_template, method, scaled_mask
            )

            if confidence > best_result.confidence:
                # Scale original dimensions
                scaled_orig_w = int(orig_width * scale)
                scaled_orig_h = int(orig_height * scale)

                # Adjust y-coordinate for crop offset (also scaled)
                scaled_offset_y = int(template_offset_y * scale)
                adjusted_y = loc[1] - scaled_offset_y

                best_result = MatchResult(
                    found=confidence >= self.confidence_threshold,
                    confidence=confidence,
                    x=loc[0],
                    y=adjusted_y,
                    width=scaled_orig_w,
                    height=scaled_orig_h,
                    center_x=loc[0] + scaled_orig_w // 2,
                    center_y=adjusted_y + scaled_orig_h // 2,
                    scale=scale,
                )

        return best_result

    def match_all(
        self,
        image: np.ndarray,
        template_name: str,
        max_matches: int = 28,
        min_distance: int = 10,
    ) -> list[MatchResult]:
        """Find all instances of template in image.

        Args:
            image: BGR image to search in
            template_name: Template filename
            max_matches: Maximum number of matches to return
            min_distance: Minimum distance between matches

        Returns:
            List of MatchResults sorted by confidence
        """
        template = self.load_template(template_name)
        if template is None:
            return []

        h, w = template.shape[:2]
        if h > image.shape[0] or w > image.shape[1]:
            return []

        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        matches: list[MatchResult] = []

        while len(matches) < max_matches:
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val < self.confidence_threshold:
                break

            match = MatchResult(
                found=True,
                confidence=max_val,
                x=max_loc[0],
                y=max_loc[1],
                width=w,
                height=h,
                center_x=max_loc[0] + w // 2,
                center_y=max_loc[1] + h // 2,
            )
            matches.append(match)

            # Zero out the matched region to find next match
            x1 = max(0, max_loc[0] - min_distance)
            y1 = max(0, max_loc[1] - min_distance)
            x2 = min(result.shape[1], max_loc[0] + w + min_distance)
            y2 = min(result.shape[0], max_loc[1] + h + min_distance)
            result[y1:y2, x1:x2] = 0

        return matches

    def _compute_color_histogram(self, image: np.ndarray) -> np.ndarray:
        """Compute color histogram for an image.

        Uses HSV color space to capture color characteristics independent
        of brightness. Focuses on Hue and Saturation channels.

        Args:
            image: BGR image

        Returns:
            Normalized 2D histogram (Hue x Saturation)
        """
        # Convert to HSV color space
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Compute 2D histogram for Hue and Saturation
        # Hue: 0-180 (OpenCV), Saturation: 0-255
        # Using 32 bins for each dimension provides good discrimination
        hist = cv2.calcHist(
            [hsv],
            [0, 1],  # Hue and Saturation channels
            None,
            [32, 32],  # Histogram dimensions
            [0, 180, 0, 256]  # Value ranges
        )

        # Normalize histogram
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    def _get_template_histogram(self, template_name: str) -> Optional[np.ndarray]:
        """Get cached color histogram for a template.

        Args:
            template_name: Template filename

        Returns:
            Normalized histogram or None if template not found
        """
        if template_name in self._histogram_cache:
            return self._histogram_cache[template_name]

        template = self.load_template(template_name)
        if template is None:
            return None

        histogram = self._compute_color_histogram(template)
        self._histogram_cache[template_name] = histogram
        return histogram

    def _compare_histograms(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """Compare two histograms using correlation method.

        Args:
            hist1: First histogram
            hist2: Second histogram

        Returns:
            Similarity score (higher is more similar, range -1 to 1)
        """
        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

    def filter_templates_by_color(
        self,
        image: np.ndarray,
        template_names: list[str],
        top_k: int = 3,
    ) -> list[tuple[str, float]]:
        """Filter template candidates by color similarity.

        Pre-filters templates before expensive spatial matching by comparing
        color histograms. Returns the top-k most similar templates.

        Args:
            image: BGR image region to match against
            template_names: List of template filenames to filter
            top_k: Number of top candidates to return

        Returns:
            List of (template_name, color_similarity) tuples, sorted by similarity
        """
        # Compute histogram for search image
        image_hist = self._compute_color_histogram(image)

        # Compare with each template's histogram
        similarities = []
        for template_name in template_names:
            template_hist = self._get_template_histogram(template_name)
            if template_hist is not None:
                similarity = self._compare_histograms(image_hist, template_hist)
                similarities.append((template_name, similarity))

        # Sort by similarity (descending) and return top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def clear_cache(self) -> None:
        """Clear the template, mask, and histogram caches."""
        self._template_cache.clear()
        self._template_mask_cache.clear()
        self._histogram_cache.clear()
