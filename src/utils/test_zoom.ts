import { computeFitScale, computeDefaultZoom } from './zoom.ts';

function assert(condition: boolean, msg: string) {
  if (!condition) {
    throw new Error(`FAIL: ${msg}`);
  }
}

console.log('Running dynamic test_zoom...');

// Test 1: Small 29x29 cutout (0.05°) in desktop container (750x560, padding 24)
const scale005 = computeFitScale(29, 29, 750, 560, 24);
const rendered005 = 29 * scale005;
assert(Math.abs(rendered005 - 512) < 1e-6, `29x29 should fill usable height 512px, got ${rendered005}`);
assert(rendered005 <= 560, `29x29 must fit within container height`);

// Test 2: 146x146 cutout (0.25°) in desktop container
const scale025 = computeFitScale(146, 146, 750, 560, 24);
const rendered025 = 146 * scale025;
assert(Math.abs(rendered025 - 512) < 1e-6, `146x146 should fill usable height 512px, got ${rendered025}`);
assert(rendered025 <= 560, `146x146 must fit within container height`);

// Test 3: 292x292 cutout (0.50°) in desktop container
const scale050 = computeFitScale(292, 292, 750, 560, 24);
const rendered050 = 292 * scale050;
assert(Math.abs(rendered050 - 512) < 1e-6, `292x292 should fill usable height 512px, got ${rendered050}`);
assert(rendered050 <= 560, `292x292 must fit within container height`);

// Test 4: Rectangular detector-edge cutout (294x213) in desktop container
const scaleRect = computeFitScale(294, 213, 750, 560, 24);
const rWidth = 294 * scaleRect;
const rHeight = 213 * scaleRect;
assert(rWidth <= 750 && rHeight <= 560, `Rectangular cutout must fit inside container`);
assert(Math.abs(rWidth / rHeight - 294 / 213) < 1e-6, `Aspect ratio must be strictly preserved`);
// In 750x560 with 24px pad: usableW=702, usableH=512. 702/294=2.3877, 512/213=2.4037 -> fits width exactly (702px)
assert(Math.abs(rWidth - 702) < 1e-6, `Rectangular cutout should fill usable width 702px`);

// Test 5: Mobile viewport (360x480, padding 16) - width constrained
const scaleMobile = computeFitScale(146, 146, 360, 480, 16);
const rMobile = 146 * scaleMobile;
assert(Math.abs(rMobile - 328) < 1e-6, `Mobile 146x146 should fill usable width 328px, got ${rMobile}`);
assert(rMobile <= 360, `Mobile render must not exceed mobile screen width`);

// Test 6: Fallback for degenerate/extreme dimensions
assert(computeFitScale(0, 0, 750, 560) === 1.0, `Zero dimension should fallback safely`);
assert(computeDefaultZoom(100, 100, 500, 500, 0) === 5.0, `computeDefaultZoom compatibility check`);

console.log('All dynamic zoom and viewport fitting tests passed!');
