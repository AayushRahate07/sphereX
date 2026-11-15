/**
 * SPHEREx Sky Viewer — Dynamic Viewport Canvas Fit Utility
 *
 * Calculates the exact contain-fit scale factor to make an astronomical cutout
 * fill the available viewport area as much as possible while strictly preserving
 * the aspect ratio (w/h) and preventing distortion, overflow, or cropping.
 */

export function computeFitScale(
  width: number,
  height: number,
  containerWidth: number,
  containerHeight: number,
  padding: number = 24
): number {
  if (width <= 0 || height <= 0 || containerWidth <= 0 || containerHeight <= 0) {
    return 1.0;
  }
  const usableWidth = Math.max(10, containerWidth - padding * 2);
  const usableHeight = Math.max(10, containerHeight - padding * 2);

  const scaleX = usableWidth / width;
  const scaleY = usableHeight / height;

  // object-fit: contain (preserve aspect ratio)
  return Math.min(scaleX, scaleY);
}

export function computeDefaultZoom(
  w: number,
  h: number,
  containerWidth: number = 720,
  containerHeight: number = 540,
  padding: number = 24
): number {
  return computeFitScale(w, h, containerWidth, containerHeight, padding);
}
