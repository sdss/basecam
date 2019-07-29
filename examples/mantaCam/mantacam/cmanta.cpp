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
#include <pybind11/stl_bind.h>
#include <VimbaCPP/Include/VimbaCPP.h>

namespace py = pybind11;
using namespace AVT::VmbAPI;

// Adding #include <pybind11/stl.h> causes a SIGSEGV error although everything seems to work.


// This is necessary because VmbAPI defines it's own smart pointer.
PYBIND11_DECLARE_HOLDER_TYPE(T, AVT::VmbAPI::shared_ptr<T>, true);


// The Vimba API tends to use output parameters which don't work too well with
// pybind11. Instead we modify the method to return a tuple of error message and
// value. This macro simplifies that.
#define TUPLIFY(name, InstanceClass, ReturnType, method)  \
    .def(name, [](InstanceClass &instance) {              \
        ReturnType value;                                 \
        VmbErrorType err = instance.method(value);        \
        return py::make_tuple(err, value);                \
    })

#define GET_VALUE(name, type)                         \
    .def(name, [](Feature &feature) {                 \
        type value;                                   \
        VmbErrorType err = feature.GetValue(value);   \
        return py::make_tuple(err, value);            \
    })


// We need to declare a trampoline class for ICameraListObserver so that we
// can override the virtual function CameraListChanged in Python.
// See http://bit.ly/2Y8LtJg.
class TrampolineCameraListObserver : public ICameraListObserver {

    public:

        // Use UCameraListObserver constructors
        using ICameraListObserver::ICameraListObserver;

        // This defines a method that can be overriden in Python class.
        void CameraListChanged(CameraPtr pCam, UpdateTriggerType reason) override {
            PYBIND11_OVERLOAD_PURE(
                void,                 /* Return type */
                ICameraListObserver,  /* Parent class */
                CameraListChanged,    /* Name of function in C++ (must match Python name) */
                pCam,                 /* Argument(s) */
                reason
            );
        }
};


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

    py::enum_<VmbAccessModeType>(module, "VmbAccessModeType")
        .value("VmbAccessModeNone", VmbAccessModeType::VmbAccessModeNone)
        .value("VmbAccessModeFull", VmbAccessModeType::VmbAccessModeFull)
        .value("VmbAccessModeRead", VmbAccessModeType::VmbAccessModeRead)
        .value("VmbAccessModeConfig", VmbAccessModeType::VmbAccessModeConfig)
        .value("VmbAccessModeLite", VmbAccessModeType::VmbAccessModeLite);

    py::enum_<UpdateTriggerType>(module, "UpdateTriggerType")
        // A new camera was discovered by Vimba
        .value("UpdateTriggerPluggedIn", UpdateTriggerType::UpdateTriggerPluggedIn)
        // A camera has disappeared from the bus
        .value("UpdateTriggerPluggedOut", UpdateTriggerType::UpdateTriggerPluggedOut)
        // The possible opening mode of a camera has changed.
        .value("UpdateTriggerOpenStateChanged", UpdateTriggerType::UpdateTriggerOpenStateChanged);

    py::class_<Feature, AVT::VmbAPI::shared_ptr<Feature>>(module, "Feature")
        GET_VALUE("GetValueDouble", double)
        GET_VALUE("GetValueInt", VmbInt64_t)
        GET_VALUE("GetValueString", std::string)
        GET_VALUE("GetValueBool", bool)
        GET_VALUE("GetValueCharVector", UcharVector);

    py::class_<Camera, AVT::VmbAPI::shared_ptr<Camera>>(module, "Camera")
        .def(py::init<const char *, const char *, const char *,
                      const char *, const char *, VmbInterfaceType>())
        TUPLIFY("GetID", Camera, std::string, GetID)
        TUPLIFY("GetName", Camera, std::string, GetName)
        TUPLIFY("GetModel", Camera, std::string, GetModel)
        TUPLIFY("GetInterfaceID", Camera, std::string, GetInterfaceID)
        TUPLIFY("GetSerialNumber", Camera, std::string, GetSerialNumber)
        .def("GetFeatureByName", [](Camera &camera, const char *pName) {
            FeaturePtr featurePtr;
            VmbErrorType err = camera.GetFeatureByName(pName, featurePtr);
            // Derreferencing here seems to avoid problems.
            return py::make_tuple(err, featurePtr.get());
        })
        .def("Open", &Camera::Open)
        .def("Close", &Camera::Close);

    py::class_<Interface>(module, "Interface")
        .def(py::init<const VmbInterfaceInfo_t *>());

    py::bind_vector<std::vector<CameraPtr>>(module, "CameraPtrVector");
    py::bind_vector<std::vector<ICameraListObserverPtr>>(module, "ICameraListObserverPtrVector");

    py::class_<VimbaSystem, std::unique_ptr<VimbaSystem, py::nodelete>>(module, "VimbaSystem")
        .def_static("GetInstance", &VimbaSystem::GetInstance, py::return_value_policy::reference)
        .def("Startup", &VimbaSystem::Startup)
        .def("Shutdown", &VimbaSystem::Shutdown)
        TUPLIFY("GetInterfaces", VimbaSystem, InterfacePtrVector, GetInterfaces)
        TUPLIFY("GetCameras", VimbaSystem, CameraPtrVector, GetCameras)
        .def("GetCameraByID", [](VimbaSystem &vs, const char* cameraID) {
            CameraPtr cameraPtr;
            VmbErrorType err = vs.GetCameraByID(cameraID, cameraPtr);
            // Derreferencing here seems to avoid problems.
            return py::make_tuple(err, cameraPtr.get());
        })
        .def("RegisterCameraListObserver", &VimbaSystem::RegisterCameraListObserver);

    // Declare ICameraListObserver with its trampoline class.
    py::class_<ICameraListObserver, TrampolineCameraListObserver,
               AVT::VmbAPI::shared_ptr<ICameraListObserver>>
               icameralistobserver (module, "ICameraListObserver");
    icameralistobserver.def(py::init<>());
    icameralistobserver.def("CameraListChanged", &ICameraListObserver::CameraListChanged);

}
