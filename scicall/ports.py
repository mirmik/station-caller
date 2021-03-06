PORT_BASE = 20100
EXTERNAL_PORT_BASE = 20190
PORTS_BY_CHANNEL = 20
PORTS_BY_EXTSOURCE = 20

def channel_video_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 1

def channel_audio_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 2

def channel_feedback_video_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 3

def channel_mpeg_stream_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 6

def channel_feedback_mpeg_stream_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 8

def channel_control_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 0

def internal_channel_audio_udpspam_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 5

def channel_feedback_audio_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 9

def channel_audio_mirror_port(ch):
    return PORT_BASE + ch * PORTS_BY_CHANNEL + 10

def external_mirror_audio_port(ch):
    return PORT_BASE + ch * PORTS_BY_EXTSOURCE + 0
