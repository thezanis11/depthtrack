# Validation record

Initial local execution: Windows, Python 3.14.0, OpenCV 5.0.0, CPU only.

- 14 synthetic and boundary tests passed: transform direction, metric scale, outlier-resistant PnP, invalid depth, one-to-one temporal association, missing poses, recovery through retained references and coverage-aware evaluation.
- Four complete real TUM sequences were downloaded, checksummed and processed. The calibrated tracker and all comparison/perturbation runs were executed; 44 trial traces are exported.
- Hyperparameter selection used only xyz/rpy. The selected keyframe age is five source-frame indices. Test observations were subsequently inspected for analysis, without retuning the frozen core.
- Data/archive provenance, calibration/core hashes, source files used by the experiment, compressed trajectory hashes and result identities are checked by `scripts/check_report.py`.
- Scientific figures and a representative RGB/feature/trajectory preview were visually inspected. The standalone HTML has structural checks; browser interaction was not visually validated in the initial local environment.
- During the campaign a process-memory observation showed approximately 185 MB resident and a 371 MB process peak at that sampling time. This is not a claim about the final full-run peak. The dataset/cache footprint and remaining disk space were checked during execution; the downloader also enforces a free-space reserve.
- The locked dependency audit reported no known vulnerability for the 12 runtime distributions on 2026-11-10. This is a time-specific database result, not a guarantee of vulnerability absence.

GitHub Actions checks Windows and Ubuntu with Python 3.12 and 3.14. The optional real-data job downloads only the public xyz sequence, runs all five clean comparisons and applies broad coverage/position/rotation regression bounds selected on that development sequence. Check the corresponding workflow run for the result of a particular commit.

The tests and benchmark are not a formal proof, independent physical validation or demonstration of autonomous-navigation safety.
