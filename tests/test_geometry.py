import tempfile
from pathlib import Path
import unittest

import cv2
import numpy as np

from depthtrack.dataset import associate,ground_truth,index_file
from depthtrack.evaluation import diagnostic_metrics,evaluate
from depthtrack.features import sample_depth
from depthtrack.geometry import K,angle_degrees,backproject,estimate_pose,inverse,rigid_align,transform
from depthtrack.tracker import Config,run


class SyntheticFeatures:
    """Known 3D landmarks and independent pinhole projections, not real data."""
    def __init__(self,missing=()):
        rng=np.random.default_rng(83)
        self.world=np.column_stack((rng.uniform(-.6,.6,120),rng.uniform(-.4,.4,120),rng.uniform(2.,4.,120)))
        self.descriptors=rng.integers(0,256,(120,32),dtype=np.uint8)
        self.times=np.arange(20)*.1
        self.missing=missing

    def frame(self,index,**kwargs):
        points=self.world-np.array([.01*index,0.,0.])
        pixels=np.column_stack((525*points[:,0]/points[:,2]+319.5,525*points[:,1]/points[:,2]+239.5)).astype(np.float32)
        if index in self.missing:
            return dict(uv=np.empty((0,2),np.float32),xyz=np.empty((0,3)),
                        desc=np.empty((0,32),np.uint8),valid=np.empty(0,bool),strict=np.empty(0,bool))
        return dict(uv=pixels,xyz=points,desc=self.descriptors,valid=np.ones(120,bool),strict=np.ones(120,bool))


class GeometryTests(unittest.TestCase):
    def test_transform_inverse(self):
        rotation=cv2.Rodrigues(np.array([.2,-.1,.4]))[0]
        pose=transform(rotation,[1.,2.,3.])
        np.testing.assert_allclose(pose@inverse(pose),np.eye(4),atol=1e-12)

    def test_depth_units_and_invalid_edge(self):
        depth=np.full((480,640),10000,dtype=np.uint16)
        uv=np.array([[319.5,239.5],[100.,100.]])
        xyz,valid,strict=sample_depth(uv,depth)
        np.testing.assert_allclose(xyz[0],[0,0,2])
        self.assertTrue(strict.all())
        depth[100,100]=0
        _,valid,strict=sample_depth(uv,depth)
        self.assertFalse(valid[1])
        depth[100,100]=10000;depth[100,101]=11000
        _,valid,strict=sample_depth(uv,depth)
        self.assertTrue(valid[1]);self.assertFalse(strict[1])

    def test_pnp_with_outliers_against_known_transform(self):
        rng=np.random.default_rng(4)
        points=rng.uniform([-1,-.7,2],[1,.7,5],(100,3))
        rotation=cv2.Rodrigues(np.array([.02,.04,-.03]))[0]
        translation=np.array([.1,-.03,.02])
        moved=points@rotation.T+translation
        uv=np.column_stack((525*moved[:,0]/moved[:,2]+319.5,525*moved[:,1]/moved[:,2]+239.5))
        uv[:25]=rng.uniform([0,0],[640,480],(25,2))
        pose,indices,_=estimate_pose(points,uv)
        np.testing.assert_allclose(pose[:3,3],translation,atol=1e-5)
        self.assertLess(angle_degrees(pose[:3,:3]@rotation.T),1e-3)
        self.assertGreaterEqual(len(indices),75)

    def test_missing_points_fail(self):
        self.assertIsNone(estimate_pose(np.zeros((3,3)),np.zeros((3,2))))

    def test_metric_alignment_does_not_fix_scale(self):
        points=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],dtype=float)
        fit=rigid_align(points,points*2)
        aligned=points@fit[:3,:3].T+fit[:3,3]
        self.assertGreater(np.linalg.norm(aligned-points*2),.5)
        self.assertAlmostEqual(np.linalg.det(fit[:3,:3]),1.)

    def test_alignment_never_reflects(self):
        points=np.random.default_rng(4).normal(size=(20,3))
        reflected=points.copy();reflected[:,0]*=-1
        fit=rigid_align(points,reflected)
        self.assertAlmostEqual(np.linalg.det(fit[:3,:3]),1.)

    def test_temporal_association_is_one_to_one(self):
        rgb=[(0.,['a']),(0.01,['b']),(.04,['c'])]
        depth=[(.009,['d']),(.042,['e'])]
        self.assertEqual(associate(rgb,depth),[(1,0),(2,1)])

    def test_duplicate_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'rgb.txt';path.write_text('1 a.png\n1 b.png\n')
            with self.assertRaises(ValueError):index_file(path)

    def test_ground_truth_gap_not_interpolated(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'groundtruth.txt';path.write_text('0 0 0 0 0 0 0 1\n1 1 0 0 0 0 0 1\n')
            truth=ground_truth(p,[.5])
            self.assertTrue(np.isnan(truth).all())

    def test_known_synthetic_camera_motion(self):
        result=run(SyntheticFeatures(),Config())
        np.testing.assert_allclose(result['poses'][:,0,3],np.arange(20)*.01,atol=1e-5)
        np.testing.assert_allclose(result['poses'][:,1:3,3],0,atol=1e-5)

    def test_failure_is_missing_pose_not_fabricated_identity(self):
        result=run(SyntheticFeatures(missing=(5,6)),Config())
        self.assertTrue(np.isnan(result['poses'][5:7]).all())
        self.assertTrue(np.isfinite(result['poses'][7]).all())
        self.assertEqual(result['diagnostics'][5]['status'],'lost')

    def test_evaluation_counts_missing_frames(self):
        data=SyntheticFeatures(missing=(5,6))
        result=run(data)
        truth=np.repeat(np.eye(4)[None],20,axis=0);truth[:,0,3]=np.arange(20)*.01
        metrics,_=evaluate(result,truth)
        self.assertAlmostEqual(metrics['tracked_fraction'],.9)
        self.assertEqual(metrics['loss_events'],1)
        self.assertLess(metrics['initial_alignment_ate_rmse_m'],1e-5)
        self.assertGreater(metrics['held_last_ate_rmse_m'],0.)

    def test_stationary_baseline_is_penalized(self):
        result=run(SyntheticFeatures(),stationary=True)
        truth=np.repeat(np.eye(4)[None],20,axis=0);truth[:,0,3]=np.arange(20)*.01
        metrics,_=evaluate(result,truth)
        self.assertGreater(metrics['initial_alignment_ate_rmse_m'],.1)
        self.assertAlmostEqual(metrics['tracked_fraction'],1.)

    def test_diagnostic_undefined_metrics_not_zero(self):
        result=diagnostic_metrics(np.array([False,False]),np.array([False,False]))
        self.assertIsNone(result['diagnostic_precision'])
        self.assertIsNone(result['diagnostic_recall'])
        self.assertEqual(result['diagnostic_false_warning_rate'],0.)


if __name__=='__main__':unittest.main()
