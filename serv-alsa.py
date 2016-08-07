#!/usr/bin/python2
import socket
import pyaudio
import zmq
import time

N_SAMP_BUFF = 4*2048 # samples in callback buffer
N_CHAN = 2
pa = pyaudio.PyAudio()

# setup zmq
ctx = zmq.Context()
pub = ctx.socket(zmq.PUB)
tcp = "tcp://%s:5555" % socket.gethostbyname('thebes')
pub.bind(tcp)

def alsa_callback(data, frames, time, status):
    pub.send('%s %s' % ('pcm_raw', data))
    return (data, pyaudio.paContinue)

class Alsa():
    def __init__(self):
        self.stream = pa.open(format=pyaudio.paInt32,
                rate=FS, input=True, channels=N_CHAN,
                frames_per_buffer=N_SAMP_BUFF,
                stream_callback=alsa_callback)

    def loop():
        while stream.is_active():
            time.sleep(0.1)

        # stop stream
        stream.stop_stream()
        stream.close()
        pa.terminate()

a = Alsa()
a.loop()