// Run: node scripts/check_chart_fit.js  (from the repository root)
// Pulls the two shipped helpers out of filter_modal.js and checks them numerically.
const fs = require("fs");
const src = fs.readFileSync("cfb_system_maker/static/filter_modal.js", "utf8");
const grab = (name) => {
  const start = src.indexOf("  function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  let depth = 0, i = src.indexOf("{", start);
  for (let j = i; j < src.length; j++) {
    if (src[j] === "{") depth++;
    else if (src[j] === "}" && --depth === 0) return src.slice(start, j + 1);
  }
  throw new Error("unbalanced: " + name);
};
eval(grab("leastSquaresFit").replace(/^\s*function/, "var leastSquaresFit = function"));
eval(grab("clipToRange").replace(/^\s*function/, "var clipToRange = function"));
eval(grab("withinBounds").replace(/^\s*function/, "var withinBounds = function"));

const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;
let fails = 0;
const check = (label, ok) => { if (!ok) { fails++; console.log("FAIL " + label); } else console.log("ok   " + label); };

// Perfect positive line: slope 2, intercept 1, R2 exactly 1.
let f = leastSquaresFit([1, 2, 3, 4], [3, 5, 7, 9]);
check("perfect line slope/intercept/r2", near(f.slope, 2) && near(f.intercept, 1) && near(f.r2, 1));

// Perfect negative line still gives R2 = 1 (R2, not r).
f = leastSquaresFit([1, 2, 3], [10, 8, 6]);
check("negative slope, r2 = 1", near(f.slope, -2) && near(f.r2, 1));

// Known-noisy set, checked against the closed form by hand.
f = leastSquaresFit([0, 1, 2], [0, 0, 10]);
check("noisy slope 5 / intercept -1.667", near(f.slope, 5) && near(f.intercept, -5 / 3, 1e-9));
check("noisy r2 = 0.75", near(f.r2, 0.75, 1e-12));

// No spread on x, and no spread on y: nothing to fit either way.
check("flat x -> null", leastSquaresFit([2, 2, 2], [1, 5, 9]) === null);
check("flat y -> null", leastSquaresFit([1, 2, 3], [4, 4, 4]) === null);
check("single point -> null", leastSquaresFit([1], [1]) === null);

// R2 is scale-free: shifting/scaling either axis must not move it.
const xs = [1, 3, 4, 7, 9], ys = [2, 1, 6, 5, 9];
check("r2 scale-invariant",
  near(leastSquaresFit(xs, ys).r2,
       leastSquaresFit(xs.map((v) => v * 100 + 7), ys.map((v) => v * 0.01 - 3)).r2, 1e-12));

// Clipping: the fitted value at an x extreme sits below the ROI floor, so that end
// must be pulled back onto the floor along the line, not squashed vertically.
let c = clipToRange(0, -5 / 3, 2, 25 / 3, 0, 10);
check("low end pulled to floor", near(c.y0, 0) && near(c.x0, 1 / 3, 1e-6));
check("high end untouched", near(c.x1, 2) && near(c.y1, 25 / 3));

// Fully inside the range: both ends survive unchanged.
c = clipToRange(0, 1, 2, 9, 0, 10);
check("inside range unchanged", near(c.x0, 0) && near(c.y0, 1) && near(c.x1, 2) && near(c.y1, 9));

// Both ends outside, opposite directions.
c = clipToRange(0, -5, 10, 15, 0, 10);
check("both ends clipped", near(c.y0, 0) && near(c.y1, 10) && near(c.x0, 2.5) && near(c.x1, 7.5));


// An empty bound input parses to NaN and must mean "unbounded", not "match nothing".
check("NaN bounds admit everything",
  withinBounds(5, NaN, NaN) && withinBounds(-999, NaN, NaN) && withinBounds(0, NaN, 3));
check("one-sided bounds", withinBounds(5, 4, NaN) && !withinBounds(3, 4, NaN));
check("bounds are inclusive", withinBounds(4, 4, 8) && withinBounds(8, 4, 8));
check("outside the window", !withinBounds(3.99, 4, 8) && !withinBounds(8.01, 4, 8));

// Narrowing to a single bucket leaves nothing to fit: no line, no R2.
const w1 = [[1, 5], [2, 9], [3, 4]].filter(([x]) => withinBounds(x, 2, 2));
check("single-bucket window -> no fit",
  w1.length === 1 &&
  leastSquaresFit(w1.map((r) => r[0]), w1.map((r) => r[1])) === null);

// Refitting on a sub-window gives that window's slope, not the whole domain's.
const dom = [[1, 0], [2, 0], [3, 0], [4, 6], [5, 12]];
const sub = dom.filter(([x]) => withinBounds(x, 3, 5));
check("window refit uses only its own points",
  near(leastSquaresFit(sub.map((r) => r[0]), sub.map((r) => r[1])).slope, 6) &&
  !near(leastSquaresFit(dom.map((r) => r[0]), dom.map((r) => r[1])).slope, 6));
console.log(fails ? "\n" + fails + " FAILED" : "\nall passed");
process.exit(fails ? 1 : 0);
