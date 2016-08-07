#!/usr/bin/python2
import numpy as np
import socket
import pyaudio
import zmq
import time

SYNC_CHAN = 0
SGNL_CHAN = 1
N_SAMP_BUFF = 2048 # samples in callback buffer
FS = 48000
T_BUFFER_MS = 200

n_fft = 2048
pa = pyaudio.PyAudio()

# setup zmq
ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.setsockopt(zmq.SUBSCRIBE, 'pcm_raw')
tcp = "tcp://%s:5555" % socket.gethostbyname('thebes')
sock.connect(tcp)
print 'Listening on %s' % tcp
t0 = time.time()


class Sync():
    def __init__(self):
        self.have_period = False
        self.period = []
        self.edges = {}
        self.T = []
        self.pulses = []
        self.tail = np.array([0])
        self.head = []

    def get_edges(self, q):
        dref = np.diff((q.ref > 0).astype(np.float))
        # find indices of rising edges
        self.edges['rise'] = np.where(dref == 1)[0]

        # find indices of falling edges
        self.edges['fall'] = np.where(dref == -1)[0]

    def align_edges(self, q):
        # make sure fall follows rise, save head
        head_idx = np.argmax(self.edges['fall'] > self.edges['rise'][0])
        self.edges['fall'] = self.edges['fall'][head_idx:-1]
        head_idx = self.edges['rise'][0] - 1

        # make sure each vector is equi-length
        if len(self.edges['rise']) > len(self.edges['fall']):
            self.edges['rise'] = self.edges['rise'][0:len(self.edges['fall'])]
        else:
            self.edges['fall'] = self.edges['fall'][0:len(self.edges['rise'])]

        # try stitch previous tail to current head
        self.head = q.ref[0:head_idx]
        self.stitch(q)
        self.tail = q.ref[self.edges['fall'][-1] + 1:-1]

    def check_period(self):
        if self.period:
            prev_period = self.period
        else:
            prev_period = 0

        self.period = np.floor(np.mean(self.edges['fall'] - self.edges['rise']))
        rez = np.abs(self.period - prev_period)

        if rez < 5:
            print 'pulse period acquired --> %d samples' % (self.period)
            if not self.have_period:
                self.have_period = True
                self.T = self.period*FS

        elif self.have_period:
            self.have_period = False
            self.period = []
            print 'pulse period lost. residual --> %d samples' % (rez)

    def stitch(self, q):
        if self.tail.any():
            x = np.hstack((self.tail, self.head))

            # sync clock signal
            dx = np.diff((x > 0).astype(np.float))

            # find indices of rising edges
            rise = np.where(dx == 1)[0].tolist()

            while rise:

                r = rise.pop()
                if self.period is list:
                    import pdb; pdb.set_trace()
                self.pulses.append(q.sig[r:r+self.period])

    # given a buffer of audio frames, find the pulses within the clock signal and extract received chirp
    def extract_pulses(self, sig):
        rises = self.edges['rise'].tolist()
        while rises:
            idx = rises.pop()
            self.pulses.append(sig[idx:idx+self.period])


def fft_mag_dB(x):
    X = np.fft.fft(x, n=n_fft)
    return 20*np.log10(np.abs(X[:n_fft/2]))

def process_queue(s):
    global t0
    dt = time.time() - t0
    t0 = time.time()
    print 'Process queue... dt is %f --> pulse count is %d' % (dt, len(s.pulses))

class Queue():
    def __init__(self):
        self.buff_idx = 0
        self.ref = []
        self.sig = []
        self.raw = []
        self.n_buff =  1

    def re_init(self):
        self.buff_idx = 0
        self.ref = []
        self.sig = []

    def fetch_format(self):
        # fetch format data
        x = (np.fromstring(sock.recv(), np.int32)).astype(np.float)/2**31
        self.sig = np.hstack((self.sig, x[SGNL_CHAN::2]))
        self.ref = np.hstack((self.ref, x[SYNC_CHAN::2]))

    def update_buff(self):
        self.buff_idx += 1
        self.fetch_format()

    def is_full(self):
        return self.buff_idx == self.n_buff


# init
q = Queue()
s = Sync()

print 'Queue and Sync init''zd... Entering loop now... '
while True:
    q.update_buff()

    if q.is_full():
        s.get_edges(q)
        s.align_edges(q)
        s.check_period()
        if s.have_period:
            s.extract_pulses(q.sig)
            z = process_queue(s)
        else:
            pass

        q.re_init()



