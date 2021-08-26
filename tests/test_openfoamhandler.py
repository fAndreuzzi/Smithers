from unittest import TestCase
import unittest
import numpy as np
import Ofpp
from smithers.io.openfoam import OpenFoamHandler

openfoam_mesh_path = "tests/test_datasets/openfoam_mesh"
notime_openfoam_mesh_path = "tests/test_datasets/notime_openfoam_mesh"

handler = OpenFoamHandler()
mesh = handler.read(openfoam_mesh_path)
truth_mesh = Ofpp.FoamMesh(openfoam_mesh_path)


class TestOpenFoamHandler(TestCase):
    def test_read(self):
        assert type(mesh) == dict

        assert "points" in mesh["0"]
        assert "faces" in mesh["0"]
        assert "boundary" in mesh["0"]
        assert "cells" in mesh["0"]

    def test_read_boundary_names(self):
        assert set(mesh["0"]["boundary"].keys()) == set(
            [
                b"inlet",
                b"outlet",
                b"bottom",
                b"top",
                b"obstacle",
                b"frontAndBack",
            ]
        )

    def test_read_points(self):
        np.testing.assert_almost_equal(mesh["0"]["points"], truth_mesh.points)

    def test_read_faces(self):
        np.testing.assert_almost_equal(mesh["0"]["faces"], truth_mesh.faces)

    def test_read_cells(self):
        assert len(mesh["0"]["cells"]) == len(truth_mesh.cell_faces)

    def test_read_cell_faces(self):
        a_key = list(mesh["0"]["cells"].keys())[0]
        smithers_cell = mesh["0"]["cells"][a_key]

        np.testing.assert_almost_equal(
            smithers_cell["faces"], truth_mesh.cell_faces[a_key]
        )

    def test_read_cell_neighbors(self):
        a_key = list(mesh["0"]["cells"].keys())[-1]
        smithers_cell = mesh["0"]["cells"][a_key]
        np.testing.assert_almost_equal(
            smithers_cell["neighbours"], truth_mesh.cell_neighbour[a_key]
        )

    def test_read_cell_points(self):
        a_key = list(mesh["0"]["cells"].keys())[-1]
        smithers_cell = mesh["0"]["cells"][a_key]

        faces_idxes = truth_mesh.cell_faces[a_key]
        faces_points = np.concatenate(
            [truth_mesh.faces[face_idx] for face_idx in faces_idxes]
        )
        faces_points = np.unique(faces_points)

        np.testing.assert_almost_equal(smithers_cell["points"], faces_points)

    def test_boundary(self):
        ofpp_obstacle = truth_mesh.boundary[b"obstacle"]
        smithers_obstacle = mesh["0"]["boundary"][b"obstacle"]

        ofpp_obstacle_faces = truth_mesh.faces[
            ofpp_obstacle.start : ofpp_obstacle.start + ofpp_obstacle.num
        ]

        np.testing.assert_almost_equal(
            mesh["0"]["faces"][smithers_obstacle["faces"]["faces_indexes"]],
            ofpp_obstacle_faces,
        )

        points_indexes = np.concatenate(
            [face_points_idx for face_points_idx in ofpp_obstacle_faces]
        )
        points_indexes = np.unique(points_indexes)
        all_points = truth_mesh.points[points_indexes]

        np.testing.assert_almost_equal(
            mesh["0"]["points"][smithers_obstacle["points"]], all_points
        )

        assert smithers_obstacle["points"].ndim == 1
        assert (
            isinstance(smithers_obstacle["faces"]["faces_indexes"], list)
            or smithers_obstacle["faces"]["faces_indexes"].ndim == 1
        )

    def test_read_fields_time_instants_all(self):
        all_numeric_mesh = handler.read(
            openfoam_mesh_path, time_instants="all_numeric"
        )
        assert set(all_numeric_mesh.keys()) == set(["0", "1088", "4196"])

    def test_read_fields_time_instants_first(self):
        assert set(mesh.keys()) == set(["0"])

    def test_read_fields_time_instants_list(self):
        handler = OpenFoamHandler()
        time_list_mesh = handler.read(
            openfoam_mesh_path, time_instants=["1088"]
        )
        assert set(time_list_mesh.keys()) == set(["1088"])

    def test_read_fields_all(self):
        for tdc in mesh.values():
            assert set(tdc["fields"].keys()) == set(["U", "p"])

    def test_read_fields_list(self):
        fields_list_mesh = handler.read(openfoam_mesh_path, field_names=["p"])
        for tdc in fields_list_mesh.values():
            assert set(tdc["fields"].keys()) == set(["p"])

    def test_no_time_instants(self):
        # assert that this doesn't raise anything
        handler.read(notime_openfoam_mesh_path)

    def test_area(self):
        np.testing.assert_almost_equal(
            mesh["0"]["boundary"][b"obstacle"]["faces"]["area"][100],
            0.039269502373542965,
            decimal=7,
        )

    def test_normal(self):
        pts = np.array([
            [-0.0253502 ,  0.0316261 ,  0.00580305],
            [-0.0253914 ,  0.031353  ,  0.00544693],
            [-0.0256058 ,  0.0328658 ,  0.00509551],
            [-0.0254315 ,  0.0330261 ,  0.00597875]
        ])

        nrm = OpenFoamHandler._normal(pts)
