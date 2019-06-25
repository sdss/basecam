/*
 * !/usr/bin/env python
 *  -*- coding: utf-8 -*-
 *
 *  @Author: José Sánchez-Gallego (gallegoj@uw.edu)
 *  @Date: 2019-06-24
 *  @Filename: cmanta.cpp
 *  @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
 *
 *  @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
 *  @Last modified time: 2019-06-24 14:16:18
 */

#include <memory>
#include <pybind11/pybind11.h>
#include <VimbaCPP/Include/VimbaCPP.h>

namespace py = pybind11;

using namespace AVT::VmbAPI;


PYBIND11_MODULE(cmanta, module) {
    py::class_<VimbaSystem, std::unique_ptr<VimbaSystem, py::nodelete>>(module, "VimbaSystem")
        .def("GetInstance", &VimbaSystem::GetInstance)
        .def("GetCameras", &VimbaSystem::GetCameras);
}
