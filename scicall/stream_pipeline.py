import sys
import time
from gi.repository import GObject, Gst, GstVideo

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from scicall.stream_settings import (
    SourceMode,
    TranslateMode,
    VideoCodecType,
    AudioCodecType,
    TransportType,
    MediaType,
    StreamSettings
)

from scicall.stream_transport import SourceTransportBuilder, TranslationTransportBuilder
from scicall.stream_codec import SourceCodecBuilder, TranslationCodecBuilder
from scicall.util import pipeline_chain
from scicall.interaptor import Interaptor


class SourceBuilder:
    """ Строитель входного каскада. 

            В зависимости от типа @settings.mode, строит разные типы входных каскадов. 
    """

    def __init__(self):
        self.nocaps = False
        self.video_width = 640
        self.video_height = 480
        self.framerate = 30

    def make(self, pipeline, settings):
        if isinstance(settings, list):
            return self.make_muxer(pipeline, settings)
        builders = {
            SourceMode.TEST: self.test_source,
            SourceMode.CAPTURE: self.capture,
            SourceMode.STREAM: self.stream,
        }
        return builders[settings.mode](pipeline, settings)

    def make_muxer(self, pipeline, settings):
        mixer = Gst.ElementFactory.make("audiomixer", None)
        pipeline.add(mixer)
        for s in settings:
            _, oend = SourceBuilder().make(pipeline, s) 
            oend.link(mixer)
        return None, mixer    

    def test_source(self, pipeline, settings):
        source = Gst.ElementFactory.make({
            MediaType.VIDEO: "videotestsrc",
            MediaType.AUDIO: "audiotestsrc"
        }[settings.mediatype], None)
        pipeline.add(source)
        return source, source

    def stream(self, pipeline, settings):
        trans_src, trans_sink = SourceTransportBuilder().make(pipeline, settings)
        codec_src, codec_sink = SourceCodecBuilder().make(pipeline, settings)
        trans_sink.link(codec_src)
        return trans_src, codec_sink

    def capture_video_linux(self, pipeline, settings):
        source = settings.device.make_gst_element()
        if self.nocaps:
            pipeline.add(source)
            return source, source
        capsfilter = self.make_source_capsfilter()
        return pipeline_chain(pipeline, source, capsfilter)

    def capture_video_windows(self, pipeline, settings):
        source = settings.device.make_gst_element()
        pipeline.add(source)
        return source, source

    def capture_audio(self, pipeline, settings):
        source = settings.device.make_gst_element()
        aconvert = Gst.ElementFactory.make("audioconvert", None)
        return pipeline_chain(pipeline, source, aconvert)

    def capture(self, pipeline, settings):
        if sys.platform == "linux":
            return{
                MediaType.VIDEO: self.capture_video_linux,
                MediaType.AUDIO: self.capture_audio
            }[settings.mediatype](pipeline, settings)
        elif sys.platform == "win32":
            return{
                MediaType.VIDEO: self.capture_video_windows,
                MediaType.AUDIO: self.capture_audio
            }[settings.mediatype](pipeline, settings)
        else:
            raise Extension("platform is not supported")

    def make_source_capsfilter(self):
        caps = Gst.Caps.from_string(
            f'video/x-raw,width={self.video_width},height={self.video_height},framerate={self.framerate}/1')
        #caps = Gst.Caps.from_string(
        #    f'image/jpeg,width={self.video_width},height={self.video_height},framerate={self.framerate}/1')
        capsfilter = Gst.ElementFactory.make('capsfilter', None)
        capsfilter.set_property("caps", caps)
        return capsfilter


class TranslationBuilder:
    """ Строитель выходного каскада. 

            В зависимости от типа @settings.mode, строит разные типы выходных каскадов. 
    """

    def make(self, pipeline, settings):
        builders = {
            TranslateMode.NOTRANS: self.fake,
            TranslateMode.STREAM: self.stream,
        }
        return builders[settings.mode](pipeline, settings)

    def fake(self, pipeline, settings):
        fakesink = Gst.ElementFactory.make("fakesink", None)
        pipeline.add(fakesink)
        return fakesink, fakesink

    def stream(self, pipeline, settings):
        codec_src, codec_sink = TranslationCodecBuilder().make(pipeline, settings)
        trans_src, trans_sink = TranslationTransportBuilder().make(pipeline, settings)
        codec_sink.link(trans_src)
        return codec_src, trans_sink

class StreamPipeline(QObject):
    """Класс отвечает за строительство работы каскада gstreamer и инкапсулирует
            логику работы с ним.

            NB: Помимо объектов данного класса и подчинённых им объектов, 
            работа с конвеером и элементами ковеера не должна нигда происходить. 

            Схема конвеера:
            source_end --> tee --> queue --> translation_end
                            |
                             ----> queue --> videoscale --> videoconvert --> display_widget 
                            |
                            --(not optimal?>)-> coder -> udpspam
    """

    def __init__(self, display_widget):
        super().__init__()
        self.display_widget = display_widget
        self.pipeline = None
        self.sink_width = 320
        if display_widget:
	        display_widget.setFixedWidth(self.sink_width)

    def make_video_feedback_capsfilter(self, settings):
        """Создаёт capsfilter, определяющий, форматирование ответвления конвеера, идущего
        к контрольному видео виджету."""
        caps = Gst.Caps.from_string(
            f"video/x-raw,width={settings.width},height={settings.height}")
        capsfilter = Gst.ElementFactory.make('capsfilter', None)
        capsfilter.set_property("caps", caps)
        return capsfilter

    def make_video_middle_end(self, settings):
        if settings.display_enabled:
            videoscale = Gst.ElementFactory.make("videoscale", None)
            videoconvert = Gst.ElementFactory.make("videoconvert", None)
            sink = Gst.ElementFactory.make("autovideosink", None)
            sink.set_property("sync", False)
            sink_capsfilter = self.make_video_feedback_capsfilter(settings)
            return pipeline_chain(self.pipeline, videoscale, videoconvert, sink_capsfilter, sink)
        else:
            sink = Gst.ElementFactory.make("fakesink", None)
            self.pipeline.add(sink)
            return (sink, sink)

    def make_audio_middle_end(self, settings):
        if settings.display_enabled:
            convert = Gst.ElementFactory.make("audioconvert", None)
            spectrascope = Gst.ElementFactory.make("spectrascope", None)
            vconvert = Gst.ElementFactory.make("videoconvert", None)
            sink = Gst.ElementFactory.make("autovideosink", None)
            sink_capsfilter = self.make_video_feedback_capsfilter(settings)
            return pipeline_chain(self.pipeline, convert, spectrascope, vconvert, sink_capsfilter, sink)
        else:
            sink = Gst.ElementFactory.make("fakesink", None)
            self.pipeline.add(sink)
            return (sink, sink)

    def new_sample(self, a, b):
        self.last_sample = time.time()
        return Gst.FlowReturn.OK

    def sample_flow_control(self):
        if self.flow_runned is False and time.time() - self.last_sample < 0.3:
            print("Connect?")
            self.flow_runned = True
            self.last_sample = time.time()
            return

        if self.flow_runned is True and time.time() - self.last_sample > 0.3:
            self.flow_runned = False
            print("Disconnect?")
            if self.last_input_settings.transport == TransportType.SRT:
                self.srt_disconnect()
            return

    def link_pipeline(self, input_settings, translation_settings, middle_settings):
        self.last_sample = time.time()
        self.flow_runned = False
        self.sample_controller = QTimer()
        self.sample_controller.timeout.connect(self.sample_flow_control)
        self.sample_controller.setInterval(100)
        self.sample_controller.start()
        tee = Gst.ElementFactory.make("tee", None)

        appsink = Gst.ElementFactory.make("appsink", None)
        queue1 = Gst.ElementFactory.make("queue", None)
        queue2 = Gst.ElementFactory.make("queue", None)
        queue3 = Gst.ElementFactory.make("queue", None)

        for q in [queue1, queue2, queue3]:
            q.set_property("max-size-bytes", 100000) 
            q.set_property("max-size-buffers", 0) 

        self.pipeline.add(appsink)
        self.pipeline.add(tee)
        self.pipeline.add(queue1)
        self.pipeline.add(queue2)
        self.pipeline.add(queue3)

        tee.link(queue3)
        queue3.link(appsink)
        appsink.set_property("sync", True)
        appsink.set_property("emit-signals", True)
        appsink.set_property("max-buffers", 1)
        appsink.set_property("drop", True)
        appsink.set_property("emit-signals", True)
        appsink.connect("new-sample", self.new_sample, None)

        self.source_sink.link(tee)
        tee.link(queue1)
        queue1.link(self.middle_src)

        if self.output_src is not None:
            tee.link(queue2)
            queue2.link(self.output_src)

        if translation_settings.udpspam:
            queue4 = Gst.ElementFactory.make("queue", None)
            queue4.set_property("max-size-bytes", 100000) 
            queue4.set_property("max-size-buffers", 0) 
            print("UDPSPAM ENABLED", translation_settings.udpspam, input_settings.codec)
            if translation_settings.mediatype is not MediaType.AUDIO:
                raise Exception("UDPSPAM is not supported for videosignal") 
            udpspam_settings = StreamSettings(
                mediatype= translation_settings.mediatype,
                mode = TranslateMode.STREAM,
                codec=input_settings.codec,
                transport=TransportType.UDP,
                port=translation_settings.udpspam,
                ip="127.0.0.1"
            )
            spamsrc, spamsink = TranslationBuilder().make(self.pipeline, udpspam_settings)
            self.pipeline.add(queue4)
            tee.link(queue4)
            queue4.link(spamsrc)

    def make_pipeline(self, input_settings, translation_settings, middle_settings):
        print("make_pipeline")
        self.last_input_settings = input_settings
        self.last_translation_settings = translation_settings
        self.last_middle_settings = middle_settings

        self.pipeline = Gst.Pipeline()
        print("do pipeline elements")
        srcsrc, srcsink = SourceBuilder().make(self.pipeline, input_settings)
        outsrc, outsink = TranslationBuilder().make(self.pipeline, translation_settings)
        
        mediatype = middle_settings.mediatype if middle_settings.mediatype is not None else translation_settings.mediatype
        middle_src, middle_sink = {
            MediaType.VIDEO: self.make_video_middle_end,
            MediaType.AUDIO: self.make_audio_middle_end
        }[mediatype](middle_settings)

        self.source_sink = srcsink
        self.output_src = outsrc
        self.middle_src = middle_src

        self.link_pipeline(input_settings, translation_settings, middle_settings)
        return self.pipeline

    def runned(self):
        return self.pipeline is not None

    def bus_callback(self, bus, msg):
        print("bus_callback", msg.parse_error())

    def setup(self):
        """Подготовка сконструированного конвеера к работе."""
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()
        self.bus.connect('sync-message::element', self.on_sync_message)
        self.bus.connect('message::error', self.on_error_message)
        self.bus.connect("message::eos", self.eos_handle)

        Interaptor.instance().srt_disconnect.connect(self.srt_disconnect)

    def srt_disconnect(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.pipeline.set_state(Gst.State.READY)
            self.pipeline.set_state(Gst.State.PAUSED)
            self.pipeline.set_state(Gst.State.PLAYING)        

    def on_error_message(self, bus, msg):
        print("on_error_message", msg.parse_error())

    def start(self):
        self.pipeline.set_state(Gst.State.READY)
        self.pipeline.set_state(Gst.State.PAUSED)
        self.pipeline.set_state(Gst.State.PLAYING)

    def on_sync_message(self, bus, msg):
        """Биндим контрольное изображение к переданному снаружи виджету."""
        if msg.get_structure().get_name() == 'prepare-window-handle':
            self.display_widget.connect_to_sink(msg.src)

    def stop(self):
        if self.sample_controller:
            self.sample_controller.stop()
            self.sample_controller = None
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.pipeline.set_state(Gst.State.READY)
            self.pipeline.set_state(Gst.State.NULL)
        self.pipeline = None

    def eos_handle(self, bus, msg):
        """Конец потока вызывает пересборку конвеера.
           Это решает некоторые проблемы srt стрима.
        """
        print("eos handle")
        self.pipeline.set_state(Gst.State.PAUSED)
        self.pipeline.set_state(Gst.State.READY)
        self.pipeline.set_state(Gst.State.PAUSED)
        self.pipeline.set_state(Gst.State.PLAYING)
        #self.stop()
        #self.make_pipeline(self.last_input_settings,
        #                   self.last_translation_settings,
        #                   self.last_middle_settings)
        #self.setup()
        #self.start()
