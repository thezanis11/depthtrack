"""Explicit camera-to-world conventions and rigid, metric geometry."""

import cv2
import numpy as np

# TUM recommends ROS-default intrinsics for pre-registered RGB/depth images.
K = np.array([[525., 0., 319.5], [0., 525., 239.5], [0., 0., 1.]])


def inverse(transform):
    result = np.eye(4)
    result[:3, :3] = transform[:3, :3].T
    result[:3, 3] = -result[:3, :3] @ transform[:3, 3]
    return result


def transform(rotation, translation):
    result = np.eye(4)
    result[:3, :3] = rotation
    result[:3, 3] = np.asarray(translation).reshape(3)
    return result


def angle_degrees(rotation):
    return float(np.degrees(np.arccos(np.clip((np.trace(rotation)-1)/2, -1, 1))))


def quaternion_rotation(q):
    q = np.asarray(q, dtype=float)
    norm = np.linalg.norm(q)
    if norm < 1e-10 or not np.isfinite(norm):
        raise ValueError("Invalid quaternion")
    x, y, z, w = q / norm
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def interpolate_pose(t0, p0, t1, p1, t):
    alpha = (t-t0)/(t1-t0)
    q0, q1 = np.array(p0[3:]), np.array(p1[3:])
    q0 /= np.linalg.norm(q0)
    q1 /= np.linalg.norm(q1)
    dot = np.dot(q0, q1)
    if dot < 0:
        q1, dot = -q1, -dot
    if dot > .9995:
        q = q0 + alpha*(q1-q0)
    else:
        theta = np.arccos(np.clip(dot, -1, 1))
        q = (np.sin((1-alpha)*theta)*q0 + np.sin(alpha*theta)*q1)/np.sin(theta)
    position = (1-alpha)*np.array(p0[:3]) + alpha*np.array(p1[:3])
    return transform(quaternion_rotation(q), position)


def backproject(uv, depth, camera=K):
    uv = np.asarray(uv, dtype=float)
    z = np.asarray(depth, dtype=float)
    return np.column_stack(((uv[:, 0]-camera[0, 2])*z/camera[0, 0],
                            (uv[:, 1]-camera[1, 2])*z/camera[1, 1], z))


def rigid_align(source, target):
    """SE(3) least squares, no scale fit and no reflection."""
    source, target = np.asarray(source), np.asarray(target)
    sm, tm = source.mean(axis=0), target.mean(axis=0)
    u, _, vt = np.linalg.svd((source-sm).T @ (target-tm))
    correction = np.eye(3)
    correction[-1, -1] = np.linalg.det(vt.T @ u.T)
    r = vt.T @ correction @ u.T
    return transform(r, tm-r@sm)


def estimate_pose(points, pixels, *, refine=True, threshold=3., seed=42):
    if len(points) < 8:
        return None
    points, pixels = np.ascontiguousarray(points, dtype=np.float64), np.ascontiguousarray(pixels, dtype=np.float64)
    cv2.setRNGSeed(int(seed))
    ok, rv, tv, inliers = cv2.solvePnPRansac(points, pixels, K, None,
        iterationsCount=150, reprojectionError=threshold, confidence=.999, flags=cv2.SOLVEPNP_EPNP)
    if not ok or inliers is None or len(inliers) < 8:
        return None
    selected = inliers.ravel()
    if refine:
        rv, tv = cv2.solvePnPRefineLM(points[selected], pixels[selected], K, None, rv, tv)
    rotation = cv2.Rodrigues(rv)[0]
    pose = transform(rotation, tv)
    projected = cv2.projectPoints(points, rv, tv, K, None)[0].reshape(-1, 2)
    errors = np.linalg.norm(projected-pixels, axis=1)
    positive = ((rotation @ points.T).T + tv.ravel())[:, 2] > 0
    selected = np.flatnonzero((errors <= threshold) & positive)
    if len(selected) < 8 or not np.isfinite(pose).all():
        return None
    return pose, selected, errors

