import os
import sys
from gi.repository import GObject, Gst, GstVideo
from scicall.stream_settings import MediaType
from scicall.device_adapter import (
    DeviceAdapterFabric,
    DefaultVideoDeviceAdapter,
    DefaultAudioDeviceAdapter
)

PORT_BASE = 10100
MONITOR = None


def start_device_monitor():
    global MONITOR
    MONITOR = Gst.DeviceMonitor()
    MONITOR.start()


def stop_device_monitor():
    global MONITOR
    MONITOR.stop()
    MONITOR = None


def get_video_captures_list(default=True):
    devs = MONITOR.get_devices()
    filtered_devs = [
        dev for dev in devs if dev.get_device_class() == "Video/Source"]
    defaults = [DefaultVideoDeviceAdapter()]
    adapters = [DeviceAdapterFabric().make_adapter(dev)
                for dev in filtered_devs]
    if default:
        adapters.insert(0, DefaultVideoDeviceAdapter())
    return adapters


def get_audio_captures_list(default=True):
    devs = MONITOR.get_devices()
    filtered_devs = [
        dev for dev in devs if dev.get_device_class() == "Audio/Source"]
    defaults = []
    adapters = [DeviceAdapterFabric().make_adapter(dev)
                for dev in filtered_devs]
    if default:
        adapters.insert(0, DefaultAudioDeviceAdapter())
    return adapters


def get_devices_list(mediatype):
    """ К счастью, gststreamer умеет добывать списки устройств,
        и довольно много о них знает. """
    if mediatype == MediaType.VIDEO:
        return get_video_captures_list()
    elif mediatype == MediaType.AUDIO:
        return get_audio_captures_list()

def channel_video_port(ch):
    return PORT_BASE + ch * 3 + 1

def channel_audio_port(ch):
    return PORT_BASE + ch * 3 + 2

def channel_control_port(ch):
    return PORT_BASE + ch * 3 + 0

def pipeline_chain(pipeline, *args):
    for el in args:
        pipeline.add(el)

    for i in range(len(args) - 1):
        args[i].link(args[i+1])

    return args[0], args[-1]
