# DepthTrack protocol v1

## Question

Measure the accuracy, availability and computational cost of CPU RGB-D visual odometry, and assess whether a causal geometric quality score identifies currently unreliable estimates. No learned model is fitted. No future failure prediction or calibrated risk probability is claimed.

## Data and split

Real data: four complete TUM RGB-D Freiburg 1 sequences, public CC BY 4.0 data by Sturm et al. (IROS 2012).

| Sequence | Role | Use |
|---|---|---|
| xyz | Development | Geometry and basic pipeline development |
| rpy | Validation | Choose keyframe age and warning threshold |
| desk | Evaluation | Office trajectory after parameter freeze |
| floor | Evaluation | Predominantly planar floor trajectory after parameter freeze |

The downloader pins archive sizes and records SHA-256 after initial HTTPS acquisition. These are locally measured hashes, not publisher-signed checksums. Subsequent downloads must match them. Archives and original data stay outside Git. Extraction rejects traversal, links, unexpected top-level folders and excessive sizes, and preserves a free-disk reserve. `DATASET_MANIFEST.json` records provenance, attribution and index hashes.

RGB and depth indices must be strictly chronological. A greedy closest-first association pairs RGB and depth frames one-to-one within 20 ms, then restores chronological order. Counts and synchronization errors are reported. Ground truth is not loaded by feature extraction or tracking. Evaluation interpolates translation and quaternion orientation between ground-truth neighbors separated by at most 100 ms; it does not extrapolate outside ground-truth coverage.

## Camera model and geometry

TUM color and depth images are pre-registered. Following the authors' recommendation for pre-registered depth, this implementation uses ROS-default intrinsics: fx=fy=525, cx=319.5, cy=239.5, no additional undistortion. This is a documented approximation, not a recalibration. PNG depth values are divided by 5000 to obtain metres. The dataset's existing depth correction is not applied a second time.

Coordinates are optical-camera coordinates. PnP estimates `T_current_reference`, transforming 3D points in the reference camera to the current camera. Camera-to-world odometry composes `T_world_current = T_world_reference @ inverse(T_current_reference)`. Ground truth never supplies an odometry state or reset.

## Feature and pose pipeline

ORB extracts at most 1600 features per image. Hamming-distance two-neighbor matching applies a 0.75 ratio test and unique current-image matches. Reference points use registered depth; the normal filter retains 0.3–6 m depths and rejects 3×3 neighborhoods with missing depth or more than 8 cm variation. The no-depth-filter ablation retains the basic valid range but disables the neighborhood test.

PnP uses EPNP RANSAC, 150 iterations, 3-pixel reprojection threshold and 0.999 confidence. The normal method refines the inlier solution using Levenberg–Marquardt. After refinement it recomputes reprojection and positive-depth support. A pose needs at least 12 inliers and 30% inlier ratio. Translation above 3 m/s or rotation above 360 deg/s relative to the last successful estimate is rejected. These are fixed modeling limits, not safety guarantees.

The frame reference uses the last successfully localized image. The keyframe method retains its reference until the selected age, low inlier ratio or a successful fallback to the last tracked image. A failed estimate emits a missing pose. References are not reset using ground truth. Recovery is possible when a later frame matches a retained reference, but there is no place-recognition relocalizer or global map.

## Parameter selection before evaluation

Only keyframe ages 5, 10 and 20 source-frame indices are compared on clean rpy. The fixed selection objective is:

`held-last initial-aligned ATE [m] + 0.01 × orientation RMSE [deg] + missing-frame fraction`.

The best validation candidate is frozen in `reports/calibration.json` with hashes of the core files. Benchmarking refuses a changed core until explicit recalibration. The warning threshold is the fifth percentile of the quality score among successful clean rpy tracking frames; it is not chosen to maximize a test score. The development/validation results are visible during development. Evaluation results are then analyzed without retuning to desk/floor. This is a small engineering study, not a blind external audit.

## Comparison and ablations

- Stationary: output identity at every observation, making a trivial reference explicit.
- Frame: last-successful-frame PnP with refinement and depth-neighborhood filtering.
- Keyframe: selected main method, same core pose solver.
- No refinement: keyframe method without LM refinement.
- No depth filter: keyframe method without depth-neighborhood filtering.

All five run on all four clean sequences. The main method also runs with every third/fifth associated frame, 70% missing reference feature depths, and a 100 ms old depth map. The mask affects depth support, not color descriptors; it is not a simulation of every real sensor dropout process. Depth lag samples actual earlier depth images at current color-feature pixels. The first observations can lack suitable lagged depth.

The depth mask uses seeds 42, 43 and 44. These are three corruptions of the same recording, not independent physical trials. Other conditions use seed 42. Total: 44 runs (11 per sequence). The extraction cache is keyed by recipe, OpenCV version and data indices, and checksummed. Run caches use feature hash, core source hashes, method, perturbation and seed. Cached timings retain their original measurement; reuse is counted in the manifest.

## Accuracy and missing tracking

Primary positional error uses alignment at the first jointly available estimated/reference pose, with **no scale fit**. A second metric reports least-squares rigid SE(3) position alignment, also without scale. The distinction matters: global alignment can hide initial orientation drift and is degenerate for some nearly stationary trajectories.

ATE is accompanied by frame coverage, duration-weighted coverage, loss events and longest loss. An evaluation-only held-last estimate penalizes missing output over the observed timeline; it is never written back to the tracker as a successful pose. If there is no valid pose, errors are undefined and coverage is zero. Initialization can occur after initial invalid depth; missing initial frames remain counted.

RPE compares pose changes over approximately 0.5 s, accepting an endpoint difference within 40 ms of the target horizon. Both endpoints must have estimated and reference poses. Translation and rotation errors are reported separately, along with the number of usable pairs. RPE does not imply uninterrupted tracking between endpoints.

## Reliability diagnostic

Quality is a bounded heuristic combining inlier count, inlier ratio, occupied 80×80 image cells and median reprojection residual. It is causal and requires no reference trajectory. A warning occurs below the validation-selected threshold or when tracking fails.

Retrospective diagnostic labels mark an available 0.5 s RPE above 5 cm or 5 degrees, or a missing pose. Frames without a usable RPE and without a tracking failure are excluded from this diagnostic comparison. Precision, recall, false-warning rate, confusion counts and always/never-warning references are exported. These labels measure current/local error, not impending future loss or total accumulated drift. A geometrically consistent wrong estimate can remain confidently wrong.

No frame-level confidence interval is used: adjacent images, local errors and perturbation seeds are correlated. The four sequences share camera and acquisition domain. Results do not establish outdoor, automotive or cross-sensor generalization.

## Timing and resources

Feature extraction streams images and measures image I/O, ORB and both normal/lagged depth sampling together. Tracking times are measured separately after loading features and include matching, PnP, diagnostics and pose composition. The lag cache makes extraction timing heavier than a clean-only implementation. A low tracking time alone is not end-to-end real-time performance.

Only one benchmark process runs; OpenCV uses one thread. NumPy caches retain at most one sequence's features during processing (plus temporary allocation during loading). Source/output hashes, dependency versions, data provenance and calibration are exported. Wall time depends on cache reuse and machine. No GPU or robot is used.

## Primary references

- [TUM RGB-D benchmark and license](https://cvg.cit.tum.de/data/datasets/rgbd-dataset)
- [TUM file formats and calibration recommendation](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats)
- [TUM download page](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download)
- [OpenCV pose-estimation documentation](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html)
- [OpenCV license](https://opencv.org/license/)

Synthetic geometry tests validate conventions and mathematical behavior against known transforms; they do not independently validate a physical camera model.
