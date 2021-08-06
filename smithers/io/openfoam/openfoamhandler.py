import Ofpp
import os
import numpy as np
import matplotlib.pyplot as plt
from operator import itemgetter
from .openfoamutils import polyarea, project, Parser, read_mesh_file


class OpenFoamHandler:
    """
    Handler for OpenFOAM output files, based on the project Ofpp.
    """

    @classmethod
    def _build_boundary(
        cls, points, faces, boundary_data, incremental_point_count
    ):
        """Extract information about a boundary.

        :param points: An array of the points which compose the mesh.
        :type mesh: np.ndarray
        :param points: Faces which compose the whole mesh, represented by a list
            of lists of point indexes.
        :type mesh: np.ndarray
        :param boundary_data: A dict of data which represents the boundary.
        :type boundary_dict: dict
        :returns: A dictionary which contains the keys `'faces'`, `'points'`,
            `'type'`. The value corresponding to the key `'faces'` is a
            dictionary which contains the following keys:

            * `'faces_indexes'`: The indexes of the faces which compose this boundary;
            * `'normals'`: The normalized vector normal to each face. The direction is taken according to the right-hand rule.
        :rtype: dict
        """
        # extract the indexes of the faces which compose the boundary
        bd_faces_indexes = list(
            range(boundary_data.start, boundary_data.start + boundary_data.num)
        )

        # extract the faces which compose the boundary. each face is a
        # list of indexes of points
        bd_faces = np.concatenate([faces[idx] for idx in bd_faces_indexes])

        # extract a list of unique points which compose the boundary
        bd_points = np.unique(bd_faces)

        # adjust
        bd_faces -= incremental_point_count

        # we now compute the normal vector to each face. we want to use NumPy.
        # we just need the first three points for each face, therefore we can
        # fix the problem that there may not be a unique number of points for
        # each face.
        first_three_points_indexes = np.concatenate(
            [faces[idx][:3] for idx in bd_faces_indexes]
        )
        # the second index is the index of the point, the third is the cartesian
        # index
        first_three_points = np.reshape(
            (points[first_three_points_indexes]), (-1, 3, 3)
        )
        vectors1 = first_three_points[:, 1] - first_three_points[:, 0]
        vectors2 = first_three_points[:, 2] - first_three_points[:, 0]
        cross = np.cross(vectors1, vectors2, axis=1)
        normals_versors = np.divide(
            cross, np.linalg.norm(cross, axis=1)[:, None]
        )

        # we also compute two versors which lie on the face, which we will
        # use to get the projection of each point in order to obtain the
        # area of the face
        lying_versors1 = np.divide(
            vectors1, np.linalg.norm(vectors1, axis=1)[:, None]
        )
        notnormalized_lying_versors2 = np.cross(
            lying_versors1, normals_versors, axis=1
        )
        lying_versors2 = np.divide(
            notnormalized_lying_versors2,
            np.linalg.norm(notnormalized_lying_versors2, axis=1)[:, None],
        )

        lying_versors = np.concatenate(
            [lying_versors1[:, None], lying_versors2[:, None]], axis=1
        )

        # now we compute the area. we have to use a loop since the number of
        # points per face may not be unique
        area = [
            _polyarea(*project(points[point_idxes], versors).T)
            # for each face we have a matrix of two rows, which contain a couple
            # of orthogonal normalized vectors which lie on the corresponding
            # face
            for point_idxes, versors in zip(
                map(faces.__getitem__, bd_faces_indexes), lying_versors
            )
        ]

        return {
            "faces": {
                "faces_indexes": bd_faces_indexes,
                "normal": normals_versors,
                "area": area,
            },
            "points": bd_points,
            "type": data.type,
        }

    @classmethod
    def _build_cells(cls, mesh, cell_idx):
        """Extract information about a cell.

        :param mesh: An Ofpp OpenFOAM mesh.
        :type mesh: Ofpp.mesh_parser.FoamMesh
        :param cell_idx: The index of the cell in the list `mesh.cell_faces`.
        :type cell_idx: int
        :returns: A dictionary which contains the keys 'faces', 'points',
            'neighbours'.
        :rtype: dict
        """
        cell_faces_idxes = mesh.cell_faces[cell_idx]

        cell_faces = np.array([mesh.faces[idx] for idx in cell_faces_idxes])
        cell_points = np.unique(np.concatenate(cell_faces))

        return {
            "faces": cell_faces_idxes,
            "points": cell_points,
            "neighbours": mesh.cell_neighbour[cell_idx],
        }

    @classmethod
    def _find_time_instants_subfolders(cls, path, fields_time_instants):
        """Finds all the time instants in the subfolders of `path` (at the moment
        this is only used to find the time evolution of fields).

        :param path: The base folder for the mesh.
        :type path: str
        :param fields_time_instants: One of:

        * `'all_numeric'`: select all the subfolders of `path` whose name can be converted to float);
        * `'first'`: same of `'all_numeric'`, but return only the folder whose name is the smallest number of the set;
        * `'not_first'`: same of `'all_numeric'`, but exclude the first folder;
        * a list of folder names.
        :type fields_time_instants: str or list
        :returns: A list of tuples (first item: subfolder name, second item:
            subfolder full path).
        :rtype: list
        """
        full_path_with_label = lambda name: (name, os.path.join(path, name))

        def is_numeric(x):
            try:
                float(x)
                return True
            except ValueError:
                return False

        # if `fields_time_instants` is 'all_numeric', we load all the subfolders
        # of `path` whose name we can cast to a float. if 'first', we take only
        # the first one of those subfolders.
        if (
            fields_time_instants == "all_numeric"
            or fields_time_instants == "first"
            or fields_time_instants == "not_first"
        ):
            subfolders = next(os.walk(path))[1]
            subfolders = list(filter(is_numeric, subfolders))

            if len(subfolders) == 0:
                return None

            if fields_time_instants == "all_numeric":
                time_instant_subfolders = subfolders
            elif fields_time_instants == "not_first":
                time_instant_subfolders = sorted(subfolders)[1:]
            else:
                # we want a list in order to return an iterable object
                time_instant_subfolders = [sorted(subfolders)[0]]
            return map(full_path_with_label, time_instant_subfolders)

        # if `fields_time_instants` is a list of strings, we take only the
        # subfolders whose name exactly matches with the strings in the list.
        elif isinstance(fields_time_instants, list):
            return list(map(full_path_with_label, fields_time_instants))
        else:
            raise ValueError(
                """Invalid value for the argument
                `fields_time_instants`"""
            )

    @classmethod
    def _find_fields_files(cls, fields_root_path, field_names):
        """Finds all the fields in the subfolders of `fields_root_path`.

        :param fields_root_path: The base folder for the time instants at which
            we are looking for the fields.
        :type fields_root_path: str
        :param field_names: Refer to the documentation of the parameter
            `field_names` for the function :func:`_load_fields`.
        :type field_names: str or list
        :returns: A list of tuples (first item: subfolder name, second item:
            subfolder full path).
        :rtype: list
        """
        full_path_with_name = lambda name: (
            name,
            os.path.join(fields_root_path, name),
        )

        if field_names == "all":
            return map(full_path_with_name, next(os.walk(fields_root_path))[2])
        elif isinstance(field_names, list):
            return map(full_path_with_name, field_names)
        else:
            raise ValueError("Invalid value for the argument `field_names`")

    @classmethod
    def _no_fail_boundary_field(cls, path):
        """Parse the boundary field at the given `path`.

        :param path: The path which contains the boundary field.
        :type path: str
        :returns: The boundary field, or `None` if the parse fails.
        :rtype: list
        """
        try:
            return Ofpp.parse_boundary_field(path)
        except IndexError:
            return None

    @classmethod
    def _no_fail_internal_field(cls, path):
        """Parse the internal field at the given `path`.

        :param path: The path which contains the internal field.
        :type path: str
        :returns: The internal field, or `None` if the parse fails.
        :rtype: list
        """
        try:
            return Ofpp.parse_internal_field(path)
        except IndexError:
            return None

    @classmethod
    def _load_fields(cls, time_instant_path, field_names):
        """Read all the fields at the given path.

        :param time_instant_path: The base folder of the time instant at which
            we consider the fields.
        :type time_instant_path: str
        :param field_names: The string `'all'` (select all the subfolders of
            `fields_root_path`) or a `list` of exact names of the selected
            subfolders.
        :type field_names: str or list
        :returns: A dictionary of fields, whose keys are the names of the
            fields, and the values are 2-tuple whose indexes are organized as
            follows:

            0. Boundary value of the field (or `None` if not available);
            1. Internal value of the field (or `None` if not available).
        :rtype: dict
        """
        field_files = cls._find_fields_files(time_instant_path, field_names)

        return dict(
            (
                name,
                (
                    cls._no_fail_boundary_field(field_path),
                    cls._no_fail_internal_field(field_path),
                ),
            )
            for name, field_path in field_files
        )

    @classmethod
    def _build_time_instant_snapshot(
        cls,
        mesh,
        time_instant_path,
        field_names,
        traveling_mesh,
        incremental_point_count,
    ):
        """Read all the content available for the time instant at the given
            path.

        :param mesh: An Ofpp OpenFOAM mesh.
        :type mesh: Ofpp.mesh_parser.FoamMesh
        :param time_instant_path: The base folder of the time instant.
        :type time_instant_path: str
        :param field_names: Refer to the documentation of the parameter
            `field_names` for the function :func:`_load_fields`.
        :type field_names: str or list
        :returns: A dictionary with keys:

            * `'points'`: points of the mesh at the given time instants;
            * `'faces'`: faces of the mesh at the given time instants;
            * `'boundary'`: output of :func:`_build_boundary`;
            * `'cells'`: cells of the mesh at the given time instants;
            * `'fields'`: output of :func:`_load_fields`;
            * `'incremental_point_count'`: number of points defined in this mesh after parsing this time instant.
        :rtype: dict
        """

        if not traveling_mesh:
            points = mesh.points
            new_incremental_point_count = incremental_point_count
        else:
            points = read_mesh_file(
                os.path.join(time_instant_path, "polyMesh/points"),
                Parser.POINTS,
            )

            if points is None:
                print(
                    "'points' not found at t={}, using the initial value.".format(
                        time_instant_path
                    )
                )
                points = mesh.points
                new_incremental_point_count = incremental_point_count
            else:
                new_incremental_point_count = incremental_point_count + len(
                    points
                )

        if not traveling_mesh:
            faces = np.asarray(mesh.faces)
        else:
            faces = read_mesh_file(
                os.path.join(time_instant_path, "polyMesh/faces"),
                Parser.FACES,
            )

            if faces is None:
                print(
                    "'faces' not found at t={}, using the initial value.".format(
                        time_instant_path
                    )
                )
                faces = mesh.faces

        if not traveling_mesh:
            boundary_data = mesh.boundary
        else:
            boundary_data = read_mesh_file(
                os.path.join(time_instant_path, "polyMesh/boundary"),
                Parser.BOUNDARY,
            )

            if boundary_data is None:
                print(
                    "'boundary' not found at t={}, using the initial value.".format(
                        time_instant_path
                    )
                )
                # TODO: what if only certain boundaries are moving?
                boundary_data = mesh.boundary

        return {
            "points": points,
            "faces": faces,
            "boundary": {
                key: cls._build_boundary(
                    points, faces, boundary_data[key], incremental_point_count
                )
                for key in mesh.boundary
            },
            "cells": {
                cell_id: cls._build_cells(mesh, cell_id)
                for cell_id in range(len(mesh.cell_faces))
            },
            "fields": cls._load_fields(time_instant_path, field_names),
            "new_incremental_point_count": new_incremental_point_count,
        }

    @classmethod
    def read(
        cls,
        filename,
        time_instants="first",
        field_names="all",
        traveling_mesh=False,
    ):
        """Read the OpenFOAM mesh at the given path. Parsing of multiple time
        instants and of fields is supported.

        .. warning::
            At the moment the mesh is not allowed to change. We chose this
            interface to facilitate the conversion when this feature becomes
            available.

        :param filename: The root folder of the mesh.
        :type filename: str
        :param time_instants: Refer to the documentation of the parameter
            `field_names` for the function
            :func:`_find_time_instants_subfolders`.
        :type time_instants: str or list
        :param field_names: Refer to the documentation of the parameter
            `field_names` for the function :func:`_load_fields`.
        :type field_names: str or list
        :returns: A dictionary whose keys are the time instants found for this
            mesh, and the values are the corresponding outputs of
            :func:`_build_time_instant_snapshot`.

            .. note::
                If only one time instant is found the upper dictionary is
                skipped.
        :rtype: dict
        """

        ofpp_mesh = Ofpp.FoamMesh(filename)

        time_instants = cls._find_time_instants_subfolders(
            filename, time_instants
        )
        time_instants = map(str, sorted(map(float, time_instants)))
        if time_instants is not None:
            time_dict = {}

            incremental_points_count = 0
            for name, path in time_instants:
                dict[name] = cls._build_time_instant_snapshot(
                    ofpp_mesh,
                    path,
                    field_names,
                    traveling_mesh,
                    incremental_point_count=incremental_point_count,
                )
                incremental_points_count = dict[name][
                    "new_incremental_point_count"
                ]
        else:
            return cls._build_time_instant_snapshot(
                ofpp_mesh, filename, field_names
            )