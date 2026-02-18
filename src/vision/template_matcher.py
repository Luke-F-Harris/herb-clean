"""OpenCV template matching with multi-scale support."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


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

    def load_template(self, template_name: str) -> Optional[np.ndarray]:
        """Load a template image.

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

        template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        if template is not None:
            self._template_cache[template_name] = template

        return template

    def match(
        self,
        image: np.ndarray,
        template_name: str,
        method: int = cv2.TM_CCOEFF_NORMED,
    ) -> MatchResult:
        """Find template in image.

        Args:
            image: BGR image to search in
            template_name: Template filename to search for
            method: OpenCV template matching method

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

        if self.multi_scale:
            return self._match_multi_scale(image, template, method)
        else:
            return self._match_single_scale(image, template, method)

    def _match_single_scale(
        self, image: np.ndarray, template: np.ndarray, method: int
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

    def _match_multi_scale(
        self, image: np.ndarray, template: np.ndarray, method: int
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

            result = cv2.matchTemplate(image, scaled_template, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                confidence = 1.0 - min_val
                loc = min_loc
            else:
                confidence = max_val
                loc = max_loc

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

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._template_cache.clear()
