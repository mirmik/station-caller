from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtNetwork import *
from gi.repository import GObject, Gst, GstVideo
import json
import time

from scicall.display_widget import GstreamerDisplay
from scicall.util import get_video_captures_list, get_audio_captures_list

from scicall.ports import *
from scicall.stream_settings import (
    MediaType,
)

import traceback
import scicall.pipeline_utils as pipeline_utils
import threading

class GuestCaller(QWidget):
    """ Пользовательский виджет реализует удалённой станции. """

    def __init__(self):
        self.mtx = threading.RLock()
        self.IMMITATION_FLAG=False
        self.SRTLATENCY=60
        self.VIDEO_DISABLE_TEXT = "Камера(отключить)"
        self.VIDEO_ENABLE_TEXT = "Камера(включить)"
        self.AUDIO_DISABLE_TEXT = "Микрофон(отключить)"
        self.AUDIO_ENABLE_TEXT = "Микрофон(включить)"
        self.OAUDIO_DISABLE_TEXT = "Динамик(отключить)"
        self.OAUDIO_ENABLE_TEXT = "Динамик(включить)"

        super().__init__()
        self.videos = get_video_captures_list(default=True,test=True)
        self.audios = [ a for a in get_audio_captures_list(default=True,test=True) if a.is_supported() ]

        for v in self.videos:
            print(v.filtered_video_caps())

        for v in self.audios:
            print(v.audio_caps())

        self.runned = False
        self.display_widget = GstreamerDisplay()
        self.display_widget.setFixedSize(320,240)
        self.spectroscope_widget = GstreamerDisplay()
        self.spectroscope_widget.setFixedSize(320,240)
        self.feedback_display_widget = GstreamerDisplay()
        self.feedback_display_widget.setFixedSize(320,240)
        self.feedback_spectroscope_widget = GstreamerDisplay()
        self.feedback_spectroscope_widget.setFixedSize(320,240)
        self.channel_list = QComboBox()
        self.channel_list.addItems(["1", "2", "3"])
        self.station_ip = QLineEdit("127.0.0.1")
        self.video_source = QComboBox()
        self.video_source.addItems([ r.user_readable_name() for r in self.videos ])
        self.audio_source = QComboBox()
        self.audio_source.addItems([ r.user_readable_name() for r in self.audios ])
        self.video_enable_button = QPushButton(self.VIDEO_DISABLE_TEXT)
        self.audio_enable_button = QPushButton(self.AUDIO_DISABLE_TEXT)
        self.feed_video_enable_button = QPushButton("")
        self.feed_audio_enable_button = QPushButton(self.OAUDIO_DISABLE_TEXT)
        self.feed_video_enable_button.setEnabled(False)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.fb_volume_slider = QSlider(Qt.Horizontal)

        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(2000)
        self.volume_slider.setValue(1000)
        self.volume_slider.sliderMoved.connect(self.volume_action)

        self.fb_volume_slider.setMinimum(0)
        self.fb_volume_slider.setMaximum(2000)
        self.fb_volume_slider.setValue(1000)
        self.fb_volume_slider.sliderMoved.connect(self.fb_volume_action)

        self.gpuchecker = pipeline_utils.GPUChecker()
        #self.imitation_label_text = "Запуск без установки соединения (тест оборудования)"
        self.stop_immitation_label_text = "Остановить"
        self.connect_label_text = "Установить соединение"
        self.disconnect_label_text = "Разорвать соединение"
        self.connect_button = QPushButton(self.connect_label_text)

        #self.immitation_button = QPushButton(self.imitation_label_text)

        self.main_layout = QHBoxLayout()
        self.left_layout = QVBoxLayout()
        self.left_feed_layout = QVBoxLayout()
        self.control_layout = QGridLayout()
        self.avpanel_layout = QHBoxLayout()
        self.avpanel_feed_layout = QHBoxLayout()
        self.volume_layout = QHBoxLayout()
        self.fb_volume_layout = QHBoxLayout()

        #self.volume_layout.addWidget(QLabel("Громкость:"))
        self.volume_layout.addWidget(self.volume_slider)
        #self.fb_volume_layout.addWidget(QLabel("Громкость:"))
        self.fb_volume_layout.addWidget(self.fb_volume_slider)

        #self.info_layout.addWidget(self.status_label)

        self.control_layout.addWidget(QLabel("IP адрес сервера:"), 0, 0)
        self.control_layout.addWidget(QLabel("Номер канала:"), 1, 0)
        self.control_layout.addWidget(QLabel("Источник видео:"), 2, 0)
        self.control_layout.addWidget(QLabel("Источник звука:"), 3, 0)
        self.control_layout.addWidget(QLabel("Аппаратное ускорение:\n(поддерживаются карты\nnvidia)"), 6, 0)
        self.control_layout.addWidget(self.station_ip, 0, 1)
        self.control_layout.addWidget(self.channel_list, 1, 1)
        self.control_layout.addWidget(self.video_source, 2, 1)
        self.control_layout.addWidget(self.audio_source, 3, 1)
        self.control_layout.addWidget(self.gpuchecker, 6, 1)
        self.control_layout.addWidget(self.connect_button, 8, 0, 1, 2)
        #self.control_layout.addWidget(self.immitation_button, 7, 0, 1, 2)

        label = QLabel()
        label.setMinimumSize( QSize(0,0) )
        label.setMaximumSize( QSize(16777215, 16777215) )
        label.setSizePolicy( QSizePolicy.Expanding, QSizePolicy.Preferred );
        self.control_layout.addWidget(label, 9,0)

        self.avpanel_layout.addWidget(self.video_enable_button)
        self.avpanel_layout.addWidget(self.audio_enable_button)
        self.avpanel_feed_layout.addWidget(self.feed_video_enable_button)
        self.avpanel_feed_layout.addWidget(self.feed_audio_enable_button)

        self.left_layout.addWidget(self.display_widget)     
        self.left_layout.addWidget(self.spectroscope_widget)
        self.left_layout.addLayout(self.volume_layout)
        self.left_layout.addLayout(self.avpanel_layout)
        
        self.left_feed_layout.addWidget(self.feedback_display_widget)       
        self.left_feed_layout.addWidget(self.feedback_spectroscope_widget)       
        self.left_feed_layout.addLayout(self.fb_volume_layout)
        self.left_feed_layout.addLayout(self.avpanel_feed_layout)

        self.main_layout.addLayout(self.left_layout)
        self.main_layout.addLayout(self.left_feed_layout)
        self.main_layout.addLayout(self.control_layout)

        self.setLayout(self.main_layout)
        self.client = QTcpSocket()

        self.audio_enable_button.clicked.connect(self.audio_clicked)
        self.video_enable_button.clicked.connect(self.video_clicked)
        self.feed_audio_enable_button.clicked.connect(self.feed_audio_clicked)
        self.feed_video_enable_button.clicked.connect(self.feed_video_clicked)

        self.client = QTcpSocket()
        self.client.connected.connect(self.on_client_connect)
        self.client.disconnected.connect(self.on_client_disconnect)
        self.client.readyRead.connect(self.client_ready_read)
        self.connect_button.clicked.connect(self.connect_action)
        #self.immitation_button.clicked.connect(self.immitation_action)

        self.common_pipeline = None
        self.feedback_pipeline = None

    def volume_action(self):
        with self.mtx:
            if self.common_pipeline:
                val = self.volume_slider.value()
                if val < 50: val = 0
                if val > 1950: val = 2000 
                self.common_pipeline.get_by_name("volume").set_property("volume", val/1000)

    def fb_volume_action(self):
        with self.mtx:
            if self.feedback_pipeline:
                val = self.fb_volume_slider.value()
                if val < 50: val = 0
                if val > 1950: val = 2000
                self.fast_feedback_pipeline.get_by_name("fbvolume").set_property("volume", val/1000)

    def opposite_ip(self):
        return self.station_ip.text()

    def on_client_disconnect(self):
        with self.mtx:
            self.stop_streams()
            print("GUEST : disconnect")
            self.connect_button.setText(self.connect_label_text)

    def on_client_connect(self):
        with self.mtx:
            self.connect_button.setText(self.disconnect_label_text)


    def client_ready_read(self):
        with self.mtx:
            while self.client.bytesAvailable():
                rawdata = self.client.readLineData(1024).decode("utf-8")
                data = json.loads(rawdata)
                self.new_opposite_command(data)

    def new_opposite_command(self, data):
        print("STATION >>", data)
        cmd = data["cmd"]
        
        if cmd == "hello_from_server":
            self.send_to_opposite({"cmd": "hello_from_guest"})
        elif cmd == "start_common_stream":
            print("START_COMMON_STREAM")
            time.sleep(0.2)
            self.start_common_stream()
        elif cmd == "start_feedback_stream":
            self.guest_channels_count = data["count_of_guests"]
            self.external_channels_count = data["count_of_externals"]
            time.sleep(0.2)
            self.start_feedback_stream()
            self.start_fast_feedback_audiostream()
        elif cmd == "set_srtlatency":
            self.SRTLATENCY = data["data"] 
        elif cmd == "client_collision":
            msgBox = QMessageBox()
            msgBox.setText("Кажется, этот канал кем-то занят. Попробуйте другой канал.")
            msgBox.exec()         
        elif cmd == "remote_restart":
            self.remote_restart()
        elif cmd == "set_volumes":
            self.set_mixer_volumes(guests=data["guest_channels"], externals=data["external_channels"])
        elif cmd == "keepalive":
            pass
        else:
            print("unresolved command")        

    def remote_restart(self):
        with self.mtx:
            self.connect_action()
            QTimer.singleShot(1000, self.connect_action)

    def send_to_opposite(self, dct):
        with self.mtx:
            self.client.writeData(json.dumps(dct).encode("utf-8"))

    def connect_action(self):
        with self.mtx:
            if self.client.state() == QTcpSocket.ConnectedState or self.common_pipeline:
                self.client.disconnectFromHost()
                self.stop_streams()
                return 

            print("tryConnectTo server")
            self.client.connectToHost(QHostAddress(self.opposite_ip()), channel_control_port(self.channelno()))
            success = self.client.waitForConnected(400)
            if success:
                print("success")
                self.client.disconnected.connect(self.on_disconnect)
                self.create_keepaliver()
            else:            
                msgBox = QMessageBox()
                msgBox.setText("Не удалось установить соединение с сервером. \nСервер недоступен, или запрошенный канал неактивен.")
                msgBox.exec()

    def create_keepaliver(self):
        self.keepaliver = QTimer()
        self.keepaliver.timeout.connect(self.keepalive_handler)
        self.keepaliver.setInterval(1500)
        self.keepaliver.start()

    def keepalive_handler(self):
        self.send_to_opposite({"cmd": "keepalive", "ch": self.channelno()+1})

    def on_disconnect(self):
        with self.mtx:
            self.stop_streams()
            self.client.disconnectFromHost()
            
            if self.keepaliver:
                self.keepaliver.stop()
                self.keepaliver = None

    def immitation_action(self):
        with self.mtx:   
            if self.common_pipeline:
                if self.client:
                    self.client.disconnectFromHost()
                self.stop_streams()
                return
    
            self.IMMITATION_FLAG=True
            self.start_common_stream()
            self.start_feedback_stream()

    def video_device(self):
        return self.videos[self.video_source.currentIndex()]

    def audio_device(self):
        return self.audios[self.audio_source.currentIndex()]

    def on_connect_button_clicked(self):
        self.client.open(self.ip, channel_connect_port(self.channelno()))

    def video_clicked(self):
        self.enable_disable_video_input()

    def audio_clicked(self):
        self.enable_disable_audio_input()

    def feed_video_clicked(self):
        pass

    def feed_audio_clicked(self):
        self.enable_disable_feed_audio_input()

    def channelno(self):
        return int(self.channel_list.currentText()) - 1

    def input_device(self, mediatype):
        if mediatype is MediaType.VIDEO:
            return self.video_device()
        else:
            return self.audio_device()

    def get_gpu_type(self):
        return self.gpuchecker.get()

    def start_common_stream(self):
        with self.mtx:
            video_device = self.input_device(MediaType.VIDEO).to_pipeline_string()
            audio_device = self.input_device(MediaType.AUDIO).to_pipeline_string()
    
            videocaps = pipeline_utils.global_videocaps()
            videocoder = pipeline_utils.video_coder_type(self.get_gpu_type())
            srtport = channel_mpeg_stream_port(self.channelno())
            srthost = self.station_ip.text()
            srtlatency = self.SRTLATENCY

            audioencoder = pipeline_utils.default_audioencoder()
    
            videoout = f"srtsink uri=srt://{srthost}:{srtport} wait-for-connection=true latency={srtlatency} sync=false"
            audioout = f"srtsink uri=srt://{srthost}:{srtport+1} wait-for-connection=true latency={srtlatency} sync=false"
    
            spectrogramm = "audiotee. ! queue name=q3 ! audioconvert ! spectrascope ! videoconvert ! autovideosink name=audioend"
            
            if self.IMMITATION_FLAG:
                videoout = f"srtsink uri=srt://127.0.0.1:{srtport} wait-for-connection=true latency={srtlatency} sync=false"
                audioout = f"srtsink uri=srt://127.0.0.1:{srtport+1} wait-for-connection=true latency={srtlatency} sync=false"
    
            audiocaps = pipeline_utils.global_audiocaps()
            h264caps = "video/x-h264,profile=baseline,stream-format=byte-stream,alignment=au,framerate=30/1"
            pipeline_string = f"""
                {video_device} name=cam ! video/x-raw,width=640,framerate=30/1 ! videoscale ! videoconvert ! 
                    {videocaps} ! videocompositor. 
                videotestsrc pattern=snow name=fakevideosrc ! video/x-raw,width=640,framerate=30/1 ! textoverlay text="Нет изображения" 
                    valignment=center halignment=center font-desc="Sans, 72" ! videoconvert ! videoscale ! 
                        {videocaps} ! videocompositor.
                compositor name=videocompositor ! tee name=videotee
    
                {audio_device} name=mic ! volume name=volume ! volume name=onoffvol 
                    ! tee name=audiotee 
    
                videotee. ! queue name=q0 ! videoconvert ! {videocoder} ! 
                    {h264caps} ! 
                         queue name=q4 ! 
                {videoout}
                
                videotee. ! queue name=q1 !videoconvert ! autovideosink name=videoend
                            
                {spectrogramm}
                audiotee. ! queue name=q2 ! audioconvert ! audioresample ! {audioencoder} ! 
                {audioout}
                """
            self.common_pipeline = Gst.parse_launch(pipeline_string)

            qs = [ self.common_pipeline.get_by_name(qname) for qname in [
                "q0", "q1", "q2", "q3", "q4"
            ]]
            for q in qs:
                pipeline_utils.setup_queuee(q)
    
            self.bus = self.common_pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.enable_sync_message_emission()
            self.bus.connect('sync-message::element', self.on_sync_message)
            self.common_pipeline.set_state(Gst.State.PLAYING)
    
            #self.fakevideosrc = pipeline_utils.imagesource("c:/users/asus/test.png")
            self.fakevideosrc = self.common_pipeline.get_by_name("fakevideosrc")
            self.videosrc = pipeline_utils.GstSubchain(self.common_pipeline.get_by_name("cam")) 
            self.audiosrc = self.common_pipeline.get_by_name("mic")
            self.vconv = pipeline_utils.GstSubchain(self.common_pipeline.get_by_name("vconv")) 
            self.aconv = pipeline_utils.GstSubchain(self.common_pipeline.get_by_name("aconv")) 
            self.srtout = pipeline_utils.GstSubchain(self.common_pipeline.get_by_name("srtout"))
            self.vstub = pipeline_utils.GstSubchain(self.common_pipeline.get_by_name("lalala"))
            self.vcompose = self.common_pipeline.get_by_name("videocompositor")
            self.videosrc.enabled=True
            self.audiosrc.enabled=True
    
            self.vcompose_sink_0 = self.vcompose.get_static_pad("sink_0")
            self.vcompose_sink_1 = self.vcompose.get_static_pad("sink_1")       
            self.vcompose_sink_1.set_property("alpha", 0)
    
            self.viden = True
            self.auden = True
            self.feed_auden = True
            self.volume_action()

    def start_feedback_stream(self):
        with self.mtx:
        
            videodecoder = pipeline_utils.video_decoder_type(self.get_gpu_type())
    
            srthost = self.station_ip.text()
            srtport = channel_feedback_mpeg_stream_port(self.channelno())
            srtin0uri = f"uri=srt://{srthost}:{srtport}"
            srtin1uri = f"uri=srt://{srthost}:{srtport+1}"
            if self.IMMITATION_FLAG:
                srtport = channel_mpeg_stream_port(self.channelno())
                srtin0uri = f"uri=srt://:{srtport}"
                srtin1uri = f"uri=srt://:{srtport+1}"
            
    
            audioparser = pipeline_utils.default_audioparser()
            audiodecoder = pipeline_utils.default_audiodecoder()
            srtlatency = self.SRTLATENCY
            audiocaps = pipeline_utils.global_audiocaps()
            
            videopart = f"""
                srtsrc {srtin0uri} latency={srtlatency} wait-for-connection=true
                     ! h264parse ! {videodecoder} ! videoconvert ! tee name=videotee 
                videotee. ! queue name=q0 ! autovideosink name=fbvideoend sync=false
            """
            self.feedback_pipeline = Gst.parse_launch(videopart)

            qs = [ self.feedback_pipeline.get_by_name(qname) for qname in [
                "q2", "q3", "q0"
            ]]
            for q in qs:
                pipeline_utils.setup_queuee(q)
                    
            self.fbbus = self.feedback_pipeline.get_bus()
            self.fbbus.add_signal_watch()
            self.fbbus.enable_sync_message_emission()
            self.fbbus.connect('sync-message::element', self.on_sync_message)
            self.feedback_pipeline.set_state(Gst.State.PLAYING)        
            
    def start_fast_feedback_audiostream(self):
        with self.mtx:
            audioparser = pipeline_utils.default_audioparser()
            audiodecoder = pipeline_utils.default_audiodecoder()
            srtlatency = self.SRTLATENCY
            audiocaps = pipeline_utils.global_audiocaps()
            srthost = self.station_ip.text()


            audio_mirror_ports = [ channel_audio_mirror_port(i) for i in range(self.guest_channels_count) ]   
            guests_srturi = [ f"uri=srt://{srthost}:{port}" for port in audio_mirror_ports ]

            external_audio_ports = [ external_mirror_audio_port(i) for i in range(self.external_channels_count) ]   
            externals_srturi = [ f"uri=srt://{srthost}:{port}" for port in external_audio_ports ]

            spectrogramm = """audiotee. ! queue name=q3 ! audioconvert ! audioresample ! 
                spectrascope ! videoconvert ! autovideosink name=fbaudioend sync=false"""
            audiosinkout = """
                audiotee. ! queue name=q2 ! audioconvert ! audioresample !
                    volume volume=1 name=onoffvol ! volume volume=1 name=fbvolume ! 
                        autoaudiosink sync=false ts-offset=-2000000000 name=asink                
            """
            template = f"""
                liveadder latency=0 name=mix ! audioconvert ! queue name=q4 ! tee name=audiotee 
                {spectrogramm}
                {audiosinkout}
            """
            for i in range(self.guest_channels_count):
                template += f"""
                    srtsrc {guests_srturi[i]} do-timestamp=true latency={srtlatency} wait-for-connection=true ! 
                        {audioparser} ! {audiodecoder} ! volume volume=1 name=guest_volume{i} ! queue name=qi{i} ! mix.
                """
            for i in range(self.external_channels_count):
                template += f"""
                    srtsrc {externals_srturi[i]} do-timestamp=true latency={srtlatency} wait-for-connection=true ! 
                        {audioparser} ! {audiodecoder} ! volume volume=1 name=external_volume{i} ! queue name=qe{i} ! mix.
                """
            

            self.fast_feedback_pipeline = Gst.parse_launch(template)
            qs = [ self.fast_feedback_pipeline.get_by_name(qname) for qname in [
                "q2", "q3", "q0", "q4"
            ] +
            [ f"qi{i}" for i in range(10) ] +
            [ f"qe{i}" for i in range(10) ]
            ]
            for q in qs:
                pipeline_utils.setup_queuee(q)

            self.guest_volumes = [ self.fast_feedback_pipeline.get_by_name(f"guest_volume{i}") for i in range(self.guest_channels_count) ]
            self.external_volumes = [ self.fast_feedback_pipeline.get_by_name(f"external_volume{i}") for i in range(self.external_channels_count) ]
                    
            bus = self.fast_feedback_pipeline.get_bus()
            bus.add_signal_watch()
            bus.enable_sync_message_emission()
            bus.connect('sync-message::element', self.on_sync_message)
            self.fast_feedback_pipeline.set_state(Gst.State.PLAYING)      

    def on_sync_message(self, bus, msg):
        """Биндим контрольное изображение к переданному снаружи виджету."""
        #pass
        with self.mtx:
            if msg.get_structure().get_name() == 'prepare-window-handle':
                name = msg.src.get_parent().get_parent().name
                if name=="videoend":
                    self.display_widget.connect_to_sink(msg.src)
                if name=="audioend":
                    self.spectroscope_widget.connect_to_sink(msg.src)
                if name=="fbvideoend":
                    self.feedback_display_widget.connect_to_sink(msg.src)
                if name=="fbaudioend":
                    self.feedback_spectroscope_widget.connect_to_sink(msg.src)
        
    def stop_common_stream(self):
        with self.mtx:
            if self.common_pipeline:
                self.common_pipeline.set_state(Gst.State.NULL)
            self.common_pipeline = None

    def stop_feedback_stream(self):
        with self.mtx:
            if self.feedback_pipeline:
                self.feedback_pipeline.set_state(Gst.State.NULL)
            self.feedback_pipeline = None        

    def stop_fast_feedback_stream(self):
        with self.mtx:
            if self.fast_feedback_pipeline:
                self.fast_feedback_pipeline.set_state(Gst.State.NULL)
            self.fast_feedback_pipeline = None        

    def enable_disable_video_input(self):
        with self.mtx:
            if self.viden is True:
                self.videosrc.set_state(Gst.State.NULL)           
                #self.fakevideosrc.set_state(Gst.State.PLAYING)
                self.viden = False  
                self.vcompose_sink_0.set_property("alpha", 0)       
                self.vcompose_sink_1.set_property("alpha", 1)
                self.video_enable_button.setText(self.VIDEO_ENABLE_TEXT)            
            else:
                self.videosrc.set_state(Gst.State.PLAYING)            
                #self.fakevideosrc.set_state(Gst.State.NULL)            
                self.vcompose_sink_0.set_property("alpha", 1)       
                self.vcompose_sink_1.set_property("alpha", 0)  
                self.video_enable_button.setText(self.VIDEO_DISABLE_TEXT)
                self.viden = True

    def enable_disable_audio_input(self):
        with self.mtx:
            if self.auden is True:
                self.common_pipeline.get_by_name("onoffvol").set_property("volume", 0) 
                self.audio_enable_button.setText(self.AUDIO_ENABLE_TEXT)              
                self.auden = False  
            else:
                self.common_pipeline.get_by_name("onoffvol").set_property("volume", 1)   
                self.audio_enable_button.setText(self.AUDIO_DISABLE_TEXT)  
                self.auden = True

    def enable_disable_feed_audio_input(self):
        with self.mtx:
            if self.feed_auden is True:
                self.fast_feedback_pipeline.get_by_name("onoffvol").set_property("volume", 0) 
                self.feed_audio_enable_button.setText(self.OAUDIO_ENABLE_TEXT)   
                #self.feedback_pipeline.get_by_name("asink").set_state(Gst.State.NULL)           
                self.feed_auden = False  
            else:
                self.fast_feedback_pipeline.get_by_name("onoffvol").set_property("volume", 1)   
                self.feed_audio_enable_button.setText(self.OAUDIO_DISABLE_TEXT)  
                #self.feedback_pipeline.get_by_name("asink").set_state(Gst.State.PLAYING)         
                self.feed_auden = True
        
    def start_streams(self):
        with self.mtx:
            self.start_common_stream()
            self.start_feedback_stream()
            self.start_fast_feedback_audiostream()
        
    def stop_streams(self):
        with self.mtx:
            self.stop_common_stream()
            self.stop_feedback_stream()
            self.stop_fast_feedback_stream()
            self.IMMITATION_FLAG = False

    def set_mixer_volumes(self, guests, externals):
        for i in range(len(guests)):
            self.guest_volumes[i].set_property("volume", guests[i])

        for i in range(len(externals)):
            self.external_volumes[i].set_property("volume", externals[i])