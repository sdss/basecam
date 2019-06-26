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

#include <vector>
#include <pybind11/pybind11.h>
#include <VimbaCPP/Include/VimbaCPP.h>

namespace py = pybind11;

using namespace AVT::VmbAPI;


// PYBIND11_DECLARE_HOLDER_TYPE(CameraPtr, shared_ptr<CameraPtr>, true);


PYBIND11_MODULE(cmanta, module) {

    py::enum_<VmbErrorType>(module, "VmbErrorType")
        .value("VmbErrorSuccess", VmbErrorType::VmbErrorSuccess)
        .value("VmbErrorInternalFault", VmbErrorType::VmbErrorInternalFault)
        .value("VmbErrorApiNotStarted", VmbErrorType::VmbErrorApiNotStarted)
        .value("VmbErrorNotFound", VmbErrorType::VmbErrorNotFound)
        .value("VmbErrorBadHandle", VmbErrorType::VmbErrorBadHandle)
        .value("VmbErrorDeviceNotOpen", VmbErrorType::VmbErrorDeviceNotOpen)
        .value("VmbErrorInvalidAccess", VmbErrorType::VmbErrorInvalidAccess)
        .value("VmbErrorBadParameter", VmbErrorType::VmbErrorBadParameter)
        .value("VmbErrorStructSize", VmbErrorType::VmbErrorStructSize)
        .value("VmbErrorMoreData", VmbErrorType::VmbErrorMoreData)
        .value("VmbErrorWrongType", VmbErrorType::VmbErrorWrongType)
        .value("VmbErrorInvalidValue", VmbErrorType::VmbErrorInvalidValue)
        .value("VmbErrorTimeout", VmbErrorType::VmbErrorTimeout)
        .value("VmbErrorOther", VmbErrorType::VmbErrorOther)
        .value("VmbErrorResources", VmbErrorType::VmbErrorResources)
        .value("VmbErrorInvalidCall", VmbErrorType::VmbErrorInvalidCall)
        .value("VmbErrorNoTL", VmbErrorType::VmbErrorNoTL)
        .value("VmbErrorNotImplemented", VmbErrorType::VmbErrorNotImplemented)
        .value("VmbErrorNotSupported", VmbErrorType::VmbErrorNotSupported)
        .value("VmbErrorIncomplete", VmbErrorType::VmbErrorIncomplete);

    py::class_<Camera>(module, "Camera")
        .def(py::init<const char *, const char *, const char *, const char *, const char *, VmbInterfaceType>());

    py::class_<Interface>(module, "Interface")
        .def(py::init<const VmbInterfaceInfo_t *>());

    // py::bind_vector<std::vector<CameraPtr>>(module, "CameraPtrVector");

    // py::class_<CameraPtr, shared_ptr<Camera>>(module, "CameraPtr");

    py::class_<VimbaSystem, std::unique_ptr<VimbaSystem, py::nodelete>>(module, "VimbaSystem")
        .def_static("GetInstance", &VimbaSystem::GetInstance)
        .def("Startup", &VimbaSystem::Startup)
        .def("GetInterfaces", [](VimbaSystem &vs) {
            InterfacePtrVector interfaces;
            VmbErrorType err = vs.GetInterfaces(interfaces);
            return py::make_tuple(err, interfaces);
        })
        .def("GetCameras", [](VimbaSystem &vs) {
            CameraPtrVector cameras;
            VmbErrorType err = vs.GetCameras(cameras);
            return py::make_tuple(err, cameras);
        });

}
