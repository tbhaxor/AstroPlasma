# -*- coding: utf-8 -*-
"""
Created on Tue Apr  4 21:30:23 2023

@author: alankar
"""

from __future__ import annotations

import logging
import sys
from itertools import product
from pathlib import Path
from typing import Callable

import h5py
import numpy as np

from .download_database import download_ionization_data, download_emission_data

log = logging.getLogger(__name__)


class DataSift:
    def __init__(self, data: h5py.File, **kwargs):
        """
        Prepares the location to read data for interpolation.
        """
        self.nH_data = np.array(data["params/nH"])
        self.T_data = np.array(data["params/temperature"])
        self.Z_data = np.array(data["params/metallicity"])
        self.red_data = np.array(data["params/redshift"])

        self.batch_size = np.prod(np.array(data["header/batch_dim"]))
        self.total_size = np.prod(np.array(data["header/total_size"]))

        child_class_name = self.__class__.mro()[0].__name__
        if child_class_name == "Ionization":
            self._downloader_function = download_ionization_data
        elif child_class_name == "EmissionSpectrum":
            self._downloader_function = download_emission_data
        else:
            raise ValueError(f"Class {child_class_name} inheritance is not supported.")

    def _identify_batch(self, i: int, j: int, k: int, m: int) -> int:
        batch_id = self._get_counter(i, j, k, m) // self.batch_size
        return batch_id

    def _get_counter(self, i: int, j: int, k: int, m: int) -> int:
        counter = (
            m * self.Z_data.shape[0] * self.T_data.shape[0] * self.nH_data.shape[0]
            + k * self.T_data.shape[0] * self.nH_data.shape[0]
            + j * self.nH_data.shape[0]
            + i
        )
        return counter

    def _get_file_path(self, batch_id: int) -> Path:
        ...

    def _determine_multiple_input(
        self,
        nH: int | float | list | np.ndarray,
        temperature: int | float | list | np.ndarray,
        metallicity: int | float | list | np.ndarray,
        redshift: int | float | list | np.ndarray,
    ) -> bool:
        """
        Determine if multiple datapoints are requested.

        Parameters
        ----------
        nH : float
            Hydrogen number density (all hydrogen both neutral and ionized.)
        temperature : float, array, list
            Plasma temperature.
        metallicity : float, array, list
            Plasma metallicity with respect to solar.
        redshift : float, array, list
            Cosmological redshift of the universe.

        Returns
        -------
        condition : bool
            True if multiple data is requested

        """
        condition = isinstance(nH, list) or isinstance(nH, np.ndarray)
        condition = condition and (isinstance(temperature, list) or isinstance(temperature, np.ndarray))
        condition = condition and (isinstance(metallicity, list) or isinstance(metallicity, np.ndarray))
        condition = condition and (isinstance(redshift, list) or isinstance(redshift, np.ndarray))

        return condition

    def _process_arguments_flags(
        self,
        nH: int | float | list | np.ndarray,
        temperature: int | float | list | np.ndarray,
        metallicity: int | float | list | np.ndarray,
        redshift: int | float | list | np.ndarray,
    ) -> tuple[list[bool], list[bool]]:
        """
        Determine if multiple datapoints are requested. Flags if
        some of the arguments are arrays. Also flags if any array
        is of size 1 which is a dummy array.

        Parameters
        ----------
        nH : float
            Hydrogen number density (all hydrogen both neutral and ionized.)
        temperature : float, array, list
            Plasma temperature.
        metallicity : float, array, list
            Plasma metallicity with respect to solar.
        redshift : float, array, list
            Cosmological redshift of the universe.

        Returns
        -------
        tuple
            All the process argument flags
        """
        # _argument_type = ["nH", "temperature", "metallicity", "redshift"]
        _array_argument = [True, True, True, True]  # array to flag which arguments are arrays
        _array_argument[0] = isinstance(nH, list) or (isinstance(nH, np.ndarray) and np.array(nH).ndim > 0)
        _array_argument[1] = isinstance(temperature, list) or (isinstance(temperature, np.ndarray) and np.array(temperature).ndim > 0)
        _array_argument[2] = isinstance(metallicity, list) or (isinstance(metallicity, np.ndarray) and np.array(metallicity).ndim > 0)
        _array_argument[3] = isinstance(redshift, list) or (isinstance(redshift, np.ndarray) and np.array(redshift).ndim > 0)

        _dummy_array = [False, False, False, False]  # array to flag which arguments are length 1 array
        if _array_argument[0]:
            _dummy_array[0] = np.array(nH).shape[0] == 1
        if _array_argument[1]:
            _dummy_array[1] = np.array(temperature).shape[0] == 1
        if _array_argument[2]:
            _dummy_array[2] = np.array(metallicity).shape[0] == 1
        if _array_argument[3]:
            _dummy_array[3] = np.array(redshift).shape[0] == 1

        return _array_argument, _dummy_array

    def _prepare_arguments(
        self,
        nH: int | float | list | np.ndarray,
        temperature: int | float | list | np.ndarray,
        metallicity: int | float | list | np.ndarray,
        redshift: int | float | list | np.ndarray,
        _array_argument: list[bool],
        _dummy_array: list[bool],
    ) -> tuple[tuple[int] | None, list[np.ndarray]]:
        """
        Determine if multiple datapoints are requested.

        Parameters
        ----------
        nH : float
            Hydrogen number density (all hydrogen both neutral and ionized.)
        temperature : float, array, list
            Plasma temperature.
        metallicity : float, array, list
            Plasma metallicity with respect to solar.
        redshift : float, array, list
            Cosmological redshift of the universe.

        Returns
        -------
        input data tuple : tuple
            prepared input data.

        """
        _input_shape: tuple[int] = None
        argument_collection = [np.array(nH), np.array(temperature), np.array(metallicity), np.array(redshift)]
        for indx, _if_this_is_arr in enumerate(_array_argument):
            if not _if_this_is_arr:
                argument_collection[indx] = np.array(
                    [
                        argument_collection[indx],
                    ]
                )
            else:
                if _input_shape is None:
                    _input_shape = argument_collection[indx].shape
                else:
                    if _input_shape != argument_collection[indx].shape:
                        print("Error: ", argument_collection[indx].shape, _input_shape)
                        print("Argument: ", argument_collection[indx])
                        raise ValueError("Check needed from user: Invalid input arguments which are not in compliance with each other! Code Aborted!")
            argument_collection[indx] = argument_collection[indx].flatten()
        if np.sum(_dummy_array) == 4 or np.sum(_array_argument) == 0:
            _input_shape = (1,)  # default only one datapoint is requested
        if _input_shape is None:
            raise ValueError("Check needed from user: Invalid input arguments which are not in compliance with each other! Code Aborted!")
        return _input_shape, argument_collection

    def _find_all_batches(self) -> set[int]:
        """
        Determine if multiple datapoints are requested.

        Returns
        -------
        set
            Set of all the unique batch ids from the entire requested data.
        """

        _array_argument, _dummy_array = self._array_argument, self._dummy_array
        _input_shape, argument_collection = self._input_shape, self.argument_collection

        if np.sum(_dummy_array) == 4 or np.sum(_array_argument) == 0:
            _argument = [argument[0] for argument in argument_collection]
            return self._find_all_batches_single(*_argument)

        _all_batches_all_data: set[int] = set()
        for indx in range(np.prod(_input_shape)):
            _argument = []
            for arg_pos, _dummy in enumerate(_dummy_array):
                if _dummy or not (_array_argument[arg_pos]):
                    _argument.append(argument_collection[arg_pos][0])
                else:
                    _argument.append(argument_collection[arg_pos][indx])
            hydrogen_num_density_val, temp_val, met_val, red_val = _argument
            _all_batches_all_data = _all_batches_all_data.union(self._find_all_batches_single(hydrogen_num_density_val, temp_val, met_val, red_val))
        if _all_batches_all_data == set():
            raise ValueError("Problem identifying batches! Code Aborted!")
        return _all_batches_all_data

    def _transform_edges(self, i: int, j: int, k: int, m: int) -> tuple[int, int, int, int]:
        if i == self.nH_data.shape[0]:
            log.warning("Invalid value for hydrogen number density.")
            i = i - 1
        if i == -1:
            log.warning("Invalid value for hydrogen number density.")
            i = i + 1
        if j == self.T_data.shape[0]:
            log.warning("Invalid temperature value.")
            j = j - 1
        if j == -1:
            log.warning("Invalid temperature value.")
            j = j + 1
        if k == self.Z_data.shape[0]:
            log.warning("Invalid value for mettalicity.")
            k = k - 1
        if k == -1:
            log.warning("Invalid value for mettalicity.")
            k = k + 1
        if m == self.red_data.shape[0]:
            log.warning("Invalid value for redshift.")
            m = m - 1
        if m == -1:
            log.warning("Invalid value for redshift.")
            m = m + 1
        return i, j, k, m

    def _identify_pos_in_each_dim(
        self,
        nH: int | float,
        temperature: int | float,
        metallicity: int | float,
        redshift: int | float,
    ) -> tuple[list[int], list[int], list[int], list[int]]:
        # positions in each data just around the requested value for any variable
        if np.sum(nH == self.nH_data) == 1:
            eq = int(np.where(nH == self.nH_data)[0][0])
            i_vals = [eq - 1, eq, eq + 1]
        else:
            i_vals = [
                np.sum(nH > self.nH_data) - 1,
                np.sum(nH > self.nH_data),
            ]

        if np.sum(temperature == self.T_data) == 1:
            eq = int(np.where(temperature == self.T_data)[0][0])
            j_vals = [eq - 1, eq, eq + 1]
        else:
            j_vals = [
                np.sum(temperature > self.T_data) - 1,
                np.sum(temperature > self.T_data),
            ]

        if np.sum(metallicity == self.Z_data) == 1:
            eq = int(np.where(metallicity == self.Z_data)[0][0])
            k_vals = [eq - 1, eq, eq + 1]
        else:
            k_vals = [
                np.sum(metallicity > self.Z_data) - 1,
                np.sum(metallicity > self.Z_data),
            ]

        if np.sum(redshift == self.red_data) == 1:
            eq = int(np.where(redshift == self.red_data)[0][0])
            m_vals = [eq - 1, eq, eq + 1]
        else:
            m_vals = [
                np.sum(redshift > self.red_data) - 1,
                np.sum(redshift > self.red_data),
            ]

        return i_vals, j_vals, k_vals, m_vals

    def _find_all_batches_single(
        self,
        nH: int | float,
        temperature: int | float,
        metallicity: int | float,
        redshift: int | float,
    ) -> set[int]:
        """
        Find the batches needed from the data files.

        Parameters
        ----------
        nH : float
            Hydrogen number density (all hydrogen both neutral and ionized.)
        temperature : float
            Plasma temperature.
        metallicity : float
            Plasma metallicity with respect to solar.
        redshift : float
            Cosmological redshift of the universe.

        Returns
        -------
        set
            Set of all the unique batch ids.
        """
        i_vals, j_vals, k_vals, m_vals = self._identify_pos_in_each_dim(nH, temperature, metallicity, redshift)

        batch_ids = set()
        # identify unique batches
        for i, j, k, m in product(i_vals, j_vals, k_vals, m_vals):
            i, j, k, m = self._transform_edges(i, j, k, m)
            batch_id = self._identify_batch(i, j, k, m)
            batch_ids.add(batch_id)

        # print("Batches involved: ", batch_ids)

        # self._fetch_data(batch_ids)

        return batch_ids

    def _interpolate(
        self,
        nH: int | float | list | np.ndarray,
        temperature: int | float | list | np.ndarray,
        metallicity: int | float | list | np.ndarray,
        redshift: int | float | list | np.ndarray,
        mode: str,
        interp_data: str,
        scaling_func: Callable = lambda x: x,
        cut: tuple[float | int | None, float | int | None] = (None, None),
    ) -> tuple[np.ndarray, bool]:
        """
        Interpolate from pre-computed Cloudy table.

        Parameters
        ----------
        nH : float, optional
            Hydrogen number density
            (all hydrogen both neutral and ionized.)
            The default is 1.2e-4.
        temperature : float, optional
            Plasma temperature.
            The default is 2.7e6.
        metallicity : float, optional
            Plasma metallicity with respect to solar.
            The default is 0.5.
        redshift : float, optional
            Cosmological redshift of the universe.
            The default is 0.2.
        mode : str, optional
            ionization condition
            either CIE (collisional) or PIE (photo).
            The default is 'PIE'.
        interp_data : str
            data location within HDF5 file
        scaling_func : callable function, optional
            function space in which intrepolation is
            carried out.
            The default is linear. log10 is another popular choice.
        cut : upper and lower bound on  data
            The default is (None, None)

        Returns
        -------
        (np.ndarray, bool)
            The interpolated result.
        """

        self._array_argument, self._dummy_array = self._process_arguments_flags(nH, temperature, metallicity, redshift)
        self._input_shape, self.argument_collection = self._prepare_arguments(nH, temperature, metallicity, redshift, self._array_argument, self._dummy_array)

        _array_argument, _dummy_array = self._array_argument, self._dummy_array
        _input_shape, argument_collection = self._input_shape, self.argument_collection

        if not (mode == "PIE" or mode == "CIE"):
            raise ValueError("Problem! Invalid mode: %s." % mode)

        batch_ids = self._find_all_batches()
        # Download files on demand if absent locally
        self._downloader_function(file_ids=list(batch_ids))

        # Load the data to memory from disk
        data = []
        for batch_id in batch_ids:
            filename = self._get_file_path(batch_id)
            hdf = h5py.File(filename, "r")
            data.append({"batch_id": batch_id, "file": hdf})
        """
        if np.sum(_dummy_array) == 4 or np.sum(_array_argument) == 0:
            _argument = [argument[0] for argument in argument_collection]
            i_vals, j_vals, k_vals, m_vals = self._identify_pos_in_each_dim(*_argument)
        """
        interp_value = []
        for indx in range(np.prod(_input_shape)):
            _argument = []
            for arg_pos, _dummy in enumerate(_dummy_array):
                if _dummy or not (_array_argument[arg_pos]):
                    _argument.append(argument_collection[arg_pos][0])
                else:
                    _argument.append(argument_collection[arg_pos][indx])
            hydrogen_num_density_this, temperature_this, metallicity_this, redshift_this = _argument
            i_vals, j_vals, k_vals, m_vals = self._identify_pos_in_each_dim(hydrogen_num_density_this, temperature_this, metallicity_this, redshift_this)

            """
            The trick is to take the floor value for interpolation only if it is the
            most frequent value in all the nearest neighbor. If not, then simply ignore
            the contribution of the floor value in interpolation.
            """
            epsilon = 1e-15
            _all_values = []
            _all_weights = []
            for i, j, k, m in product(i_vals, j_vals, k_vals, m_vals):
                i, j, k, m = self._transform_edges(i, j, k, m)
                # nearest neighbour interpolation
                d_i = np.abs(scaling_func(self.nH_data[i]) - scaling_func(float(_argument[0])))
                d_j = np.abs(scaling_func(self.T_data[j]) - scaling_func(float(_argument[1])))
                d_k = np.abs(scaling_func(self.Z_data[k]) - scaling_func(float(_argument[2])))
                d_m = np.abs(scaling_func(self.red_data[m]) - scaling_func(float(_argument[3])))
                dist_l2 = np.sqrt(d_i**2 + d_j**2 + d_k**2 + d_m**2)
                if dist_l2 <= 0.0:
                    dist_l2 = epsilon
                _all_weights.append(1 / dist_l2)

                batch_id = self._identify_batch(i, j, k, m)

                for id_data in data:
                    if id_data["batch_id"] == batch_id:
                        hdf = id_data["file"]
                        local_pos = self._get_counter(i, j, k, m) % self.batch_size - 1
                        break
                else:
                    raise ValueError("Target batch id is not found.")

                try:
                    value = np.array(hdf[interp_data])[local_pos, :]
                except UnboundLocalError:
                    print("Error: HDF5 files not properly loaded/initialized! Code Aborted!")
                    sys.exit(1)

                if cut[0] is not None:
                    value = np.piecewise(value, [value <= cut[0]], [cut[0], lambda x: x])
                if cut[1] is not None:
                    value = np.piecewise(value, [value >= cut[1]], [cut[1], lambda x: x])
                _all_values.append(value)

            all_values = np.array(_all_values)
            all_weights = np.array(_all_weights)
            # Filter the outliers (deviation from mean across column is large)
            all_values[(np.abs(all_values - np.mean(all_values, axis=0)) > 2.0 * np.std(all_values, axis=0))] = 0.0

            # _median_value = np.median(_all_values, axis=0)
            interp_value.append(all_weights.T @ all_values / np.sum(all_weights))
            # if (len(interp_value.shape)==2):
            #     interp_value = interp_value[0]

        for id_data in data:
            id_data["file"].close()
        if np.sum(_dummy_array) == 4 or np.sum(_array_argument) == 0:
            return interp_value[0], False
        else:
            _tmp = np.array(interp_value).reshape((*_input_shape, *np.array(interp_value[0]).shape))
            return _tmp, True

    def _determine_multiple(
        self,
        nH: int | float | list | np.ndarray,
        temperature: int | float | list | np.ndarray,
        metallicity: int | float | list | np.ndarray,
        redshift: int | float | list | np.ndarray,
    ) -> bool:
        """
        Interpolate from pre-computed Cloudy table.

        Parameters
        ----------
        nH : float, optional
            Hydrogen number density
            (all hydrogen both neutral and ionized.)
            The default is 1.2e-4.
        temperature : float, optional
            Plasma temperature.
            The default is 2.7e6.
        metallicity : float, optional
            Plasma metallicity with respect to solar.
            The default is 0.5.
        redshift : float, optional
            Cosmological redshift of the universe.
            The default is 0.2.

        Returns
        -------
        bool
            ``True`` If multiple input is passed, otherwise ``False``.
        """
        _is_multiple = (isinstance(nH, list) or isinstance(nH, np.ndarray)) and np.array(nH).flatten().shape[0] > 1
        _is_multiple = _is_multiple or (isinstance(temperature, list) or isinstance(temperature, np.ndarray)) and np.array(temperature).flatten().shape[0] > 1
        _is_multiple = _is_multiple or (isinstance(metallicity, list) or isinstance(metallicity, np.ndarray)) and np.array(metallicity).flatten().shape[0] > 1
        _is_multiple = _is_multiple or (isinstance(redshift, list) or isinstance(redshift, np.ndarray)) and np.array(redshift).flatten().shape[0] > 1

        return _is_multiple
