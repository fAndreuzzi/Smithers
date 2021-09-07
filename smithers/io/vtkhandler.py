from .basevtkhandler import BaseVTKHandler

from vtk import vtkPolyDataReader, vtkPolyDataWriter
from vtk import vtkUnstructuredGridReader, vtkUnstructuredGridWriter
from vtk import vtkPolyData, vtkUnstructuredGrid

from vtk import vtkPolyData, vtkPoints, vtkCellArray
from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy

class VTKHandler(BaseVTKHandler):
    """
    Handler for .VTK files.
    """

    def __init__(self, reader, writer):
        self._reader = reader
        self._writer = writer

    def read(self, filename):
        reader = self._reader()
        reader.SetFileName(filename)
        reader.Update()
        return reader.GetOutput()

    def parse(self, data):
        result = {'cells': [], 'points': None}

        for id_cell in range(data.GetNumberOfCells()):
            cell = data.GetCell(id_cell)
            result['cells'].append([
                cell.GetPointId(id_point)
                for id_point in range(cell.GetNumberOfPoints())
            ])

        result['points'] = vtk_to_numpy(data.GetPoints().GetData())

        result['point_data'] = self._read_point_data(data)
        result['cell_data'] = self._read_cell_data(data)

        return result

    def write(self, filename, data):
        polydata = vtkPolyData()

        vtk_points = vtkPoints()
        vtk_points.SetData(numpy_to_vtk(data['points']))

        vtk_cells = vtkCellArray()
        for cell in data['cells']:
            vtk_cells.InsertNextCell(len(cell), cell)

        self._write_point_data(polydata, data)
        self._write_cell_data(polydata, data)

        polydata.SetPoints(vtk_points)
        polydata.SetPolys(vtk_cells)

        writer = self._writer()
        writer.SetFileName(filename)
        writer.SetInputData(polydata)
        writer.Write()
