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

#include <sstream>
#include <vector>
#include <pybind11/pybind11.h>
#include <pybind11/stl_bind.h>
#include <VimbaCPP/Include/VimbaCPP.h>


namespace py = pybind11;
using namespace AVT::VmbAPI;

// Adding #include <pybind11/stl.h> causes a SIGSEGV error although everything seems to work.


// This is necessary because VmbAPI defines it's own smart pointer.
PYBIND11_DECLARE_HOLDER_TYPE(T, AVT::VmbAPI::shared_ptr<T>, true);


// Convenience function to throw error if not successful
void check_vmb_success(VmbErrorType err, char const *name) {
    if (VmbErrorSuccess != err) {
        std::ostringstream errstr;
        errstr << "Runtime error in " << name ;
        errstr << ": code " << err << std::endl;
        throw errstr;
    }
}


// The Vimba API tends to use output parameters which don't work too well with
// pybind11. Instead we modify the method to throw an error if the method fails
// and otherwise return the value.
#define GET_METHOD(name, InstanceClass, ReturnType, method)  \
    .def(name, [](InstanceClass &instance) {                 \
        ReturnType value;                                    \
        VmbErrorType err = instance.method(value);           \
        check_vmb_success(err, name);                        \
        return value;                                        \
    })


#define GET_VALUE(name, type)                         \
    .def(name, [](Feature &feature) {                 \
        type value;                                   \
        VmbErrorType err = feature.GetValue(value);   \
        check_vmb_success(err, name);                 \
        return value;                                 \
    })

#define SET_VALUE(name, type)                     \
    .def(name, [](Feature &feature, type value)   \
        { return feature.SetValue(value); })


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


class TrampolineFrameObserver : public IFrameObserver {

    public:

        TrampolineFrameObserver(CameraPtr pCamera) : IFrameObserver(pCamera) { }

        // using IFrameObserver::IFrameObserver;
        void FrameReceived(const FramePtr pFrame) override {
            PYBIND11_OVERLOAD_PURE(
                void,
                IFrameObserver,
                FrameReceived,
                pFrame
            );
        }
};


class PublicistIFrameObserver : public IFrameObserver {

    public:
        using IFrameObserver::m_pCamera;

};


// A thin wrapper around the image buffer so that it can be wrapped in a
// buffer protocol.
class Image {

    public:
        Image(VmbUchar_t *buffer, VmbUint32_t rows, VmbUint32_t cols) :
            m_rows(rows), m_cols(cols), m_data(buffer) { }
        VmbUchar_t *data() { return m_data; }
        VmbUint32_t rows() const { return m_rows; }
        VmbUint32_t cols() const { return m_cols; }

    private:
        VmbUint32_t m_rows, m_cols;
        VmbUchar_t *m_data;
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

    py::enum_<VmbPixelFormatType>(module, "VmbPixelFormatType")
        .value("VmbPixelFormatMono8", VmbPixelFormatType::VmbPixelFormatMono8)
        .value("VmbPixelFormatMono10p", VmbPixelFormatType::VmbPixelFormatMono10p)
        .value("VmbPixelFormatMono12", VmbPixelFormatType::VmbPixelFormatMono12)
        .value("VmbPixelFormatMono12Packed", VmbPixelFormatType::VmbPixelFormatMono12Packed)
        .value("VmbPixelFormatMono12p", VmbPixelFormatType::VmbPixelFormatMono12p)
        .value("VmbPixelFormatMono14", VmbPixelFormatType::VmbPixelFormatMono14)
        .value("VmbPixelFormatMono16", VmbPixelFormatType::VmbPixelFormatMono16);

    py::class_<Feature, AVT::VmbAPI::shared_ptr<Feature>>(module, "Feature")
        GET_VALUE("GetValueDouble", double)
        GET_VALUE("GetValueInt", VmbInt64_t)
        GET_VALUE("GetValueString", std::string)
        GET_VALUE("GetValueBool", bool)
        GET_VALUE("GetValueCharVector", UcharVector)
        SET_VALUE("SetValueDouble", const double &)
        SET_VALUE("SetValueInt", const VmbInt64_t &)
        SET_VALUE("SetValueString", const char *)
        SET_VALUE("SetValueBool", bool)
        SET_VALUE("SetValueCharVector", const UcharVector &)
        .def("RunCommand", &Feature::RunCommand);

    py::class_<Camera, AVT::VmbAPI::shared_ptr<Camera>>(module, "Camera")
        .def(py::init<const char *, const char *, const char *,
                      const char *, const char *, VmbInterfaceType>())
        GET_METHOD("GetID", Camera, std::string, GetID)
        GET_METHOD("GetName", Camera, std::string, GetName)
        GET_METHOD("GetModel", Camera, std::string, GetModel)
        GET_METHOD("GetInterfaceID", Camera, std::string, GetInterfaceID)
        GET_METHOD("GetSerialNumber", Camera, std::string, GetSerialNumber)
        .def("GetFeatureByName", [](Camera &camera, const char *pName) {
            FeaturePtr featurePtr;
            VmbErrorType err = camera.GetFeatureByName(pName, featurePtr);
            check_vmb_success(err, "GetFeatureByName");
            // Derreferencing here seems to avoid problems.
            return featurePtr.get();
        })
        .def("Open", &Camera::Open)
        .def("Close", &Camera::Close)
        .def("QueueFrame", &Camera::QueueFrame)
        .def("StartCapture", &Camera::StartCapture)
        .def("EndCapture", &Camera::EndCapture)
        .def("AnnounceFrame", &Camera::AnnounceFrame)
        .def("RevokeAllFrames", &Camera::RevokeAllFrames);

    py::class_<Interface>(module, "Interface")
        .def(py::init<const VmbInterfaceInfo_t *>());

    py::bind_vector<std::vector<CameraPtr>>(module, "CameraPtrVector");
    py::bind_vector<std::vector<ICameraListObserverPtr>>(module, "ICameraListObserverPtrVector");

    py::class_<VimbaSystem, std::unique_ptr<VimbaSystem, py::nodelete>>(module, "VimbaSystem")
        .def_static("GetInstance", &VimbaSystem::GetInstance, py::return_value_policy::reference)
        .def("Startup", &VimbaSystem::Startup)
        .def("Shutdown", &VimbaSystem::Shutdown)
        GET_METHOD("GetInterfaces", VimbaSystem, InterfacePtrVector, GetInterfaces)
        GET_METHOD("GetCameras", VimbaSystem, CameraPtrVector, GetCameras)
        .def("GetCameraByID", [](VimbaSystem &vs, const char* cameraID) {
            CameraPtr cameraPtr;
            VmbErrorType err = vs.GetCameraByID(cameraID, cameraPtr);
            // Derreferencing here seems to avoid problems.
            return py::make_tuple(err, cameraPtr.get());
        })
        .def("RegisterCameraListObserver", &VimbaSystem::RegisterCameraListObserver);

    // Declare ICameraListObserver with its trampoline class.
    py::class_<ICameraListObserver, TrampolineCameraListObserver,
               AVT::VmbAPI::shared_ptr<ICameraListObserver>> icameralistobserver
                    (module, "ICameraListObserver");
    icameralistobserver
        .def(py::init<>())
        .def("CameraListChanged", &ICameraListObserver::CameraListChanged);

    // Wrap Image class to return a python buffer that can be directly read
    // by numpy.
    py::class_<Image>(module, "Image", py::buffer_protocol())
        .def_buffer([](Image &m) -> py::buffer_info {
            return py::buffer_info(
                m.data(),                                     /* Pointer to buffer */
                sizeof(VmbUchar_t),                           /* Size of one scalar */
                py::format_descriptor<VmbUchar_t>::format() , /* Python struct-style format descriptor */
                2,                                            /* Number of dimensions */
                {m.rows(), m.cols()},                         /* Buffer dimensions */
                {sizeof(VmbUchar_t) * m.rows() ,              /* Strides (in bytes) for each index */
                sizeof(VmbUchar_t)}
            );
    });

    py::class_<Frame, AVT::VmbAPI::shared_ptr<Frame>>(module, "Frame")
        .def(py::init<VmbInt64_t>())
        .def("RegisterObserver", &Frame::RegisterObserver)
        .def("GetImageInstance", [](Frame &frame) {
            VmbUchar_t *buffer;
            VmbUint32_t InputWidth, InputHeight;
            frame.GetWidth(InputWidth);
            frame.GetHeight(InputHeight);
            frame.GetBuffer(buffer);
            Image image {buffer, InputWidth, InputHeight};
            return image;
        });

    py::class_<IFrameObserver, TrampolineFrameObserver,
               AVT::VmbAPI::shared_ptr<IFrameObserver>> iframeobserver
                    (module, "IFrameObserver");
    iframeobserver
        .def(py::init<CameraPtr>())
        .def_readonly("camera", &PublicistIFrameObserver::m_pCamera)
        .def("FrameReceived", &IFrameObserver::FrameReceived);

}
