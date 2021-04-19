#
# Daniel Bolanos (dbolano@us.ibm.com), April 2020
#

import asyncio
import json
import argparse
import uuid
import ssl
import time
import math
import yaml
import datetime
import itertools
import random
import pathlib
import socket
import certifi
from base64 import b64encode

import numpy  # Make sure NumPy is loaded before it is used in the callback

assert numpy  # avoid "imported but unused" message (W0611)
import queue

# Autobahn + asyncio websocket client
from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory

# Constants
WS_SUCCESSFUL_CLOSE = 1000
TRANSACTION_ID_HEADER = 'x-global-transaction-id'


class MyClientProtocol(WebSocketClientProtocol):
    """Takes care of the WebSocket interaction
    https://github.com/crossbario/autobahn-python/blob/master/autobahn/websocket/protocol.py
    """

    def onConnecting(self, transport_details):
        """Callback fired after the connection is established, but before the handshake has started.
        """

        print("onConnecting")
        self.uuid = str(uuid.uuid4())
        self.transfer_time = 0
        self.close_sent_time = 0
        self.time_before_handshake = time.time()
        self.results[self.uuid] = {"audio_file": None, "timestamp": None, "reco_results": None, "code": None,
                                   "reason": None, "transaction_id": None, "elapsed_time": None, "handshake_time": None,
                                   "close_time": None, "transfer_time": None, "transcripts": None}
        self.time_before_handshake = time.perf_counter()

    def onConnect(self, response):
        """Callback fired directly after WebSocket opening handshake when new WebSocket server connection was established.
        """

        print("Server connected: {0}".format(response.peer))
        if TRANSACTION_ID_HEADER in response.headers:
            self.results[self.uuid]["transaction_id"] = response.headers[TRANSACTION_ID_HEADER]
        else:
            self.results[self.uuid]["transaction_id"] = "no-transaction-id-available"
        self.results[self.uuid]["handshake_time"] = time.perf_counter() - self.time_before_handshake
        print("end of onConnect")

    def get_chunk_from_file(self, audio_file):
        with open(audio_file, "rb") as file:
            while True:
                chunk = file.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk
            yield None

    async def send_audio_data(self):

        audio_file = next(self.audio_file_generator)
        print("the audio file", audio_file)
        self.results[self.uuid]["audio_file"] = audio_file
        bytes_sent = 0

        g = self.get_chunk_from_file(audio_file)
        while True:
            while True:
                time_elapsed = time.perf_counter() - self.time_onopen
                if bytes_sent < self.byte_rate * time_elapsed:
                    break
                await asyncio.sleep(0.001)
            chunk = next(g)
            if chunk == None:
                break
            start = time.perf_counter()
            try:
                self.sendMessage(chunk, isBinary=True)
                # print("chunk goes",len(chunk))
            except Exception as e:  # closed connection, etc
                print(e)
                return
            self.transfer_time += time.perf_counter() - start  # total (i/o) time sending chunks
            bytes_sent += self.chunk_size

        # signal end of audio
        msg = '{ "action":"stop" }'.encode('utf8')
        self.sendMessage(msg)
        print(f"done sending audio!")

    async def onOpen(self):
        """Called when the WebSocket connection opens.
        """

        self.time_onopen = time.perf_counter()
        self.listening_counter = 0
        # msg = '{ "action":"start","inactivity_timeout":-1,"debugStats":true }'.encode('utf8')
        msg = '{ "action":"start","inactivity_timeout":-1 }'.encode('utf8')
        self.sendMessage(msg, isBinary=False)
        # send binary stream
        asyncio.get_running_loop().create_task(self.send_audio_data())
        print("onOpen ends")

    def onMessage(self, payload, isBinary):
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            msg = payload.decode('utf8')
            # print("Text message received: {0}".format(msg))
            json_msg = json.loads(msg)
            if json_msg.get('state', None) == 'listening':
                if self.listening_counter == 0:
                    self.listening_counter += 1
                else:
                    self.results[self.uuid]['time_stt'] = time.perf_counter() - self.time_onopen
                    print("onMessage: successful!")
                    self.results[self.uuid]["reco_results"] = True
                    self.sendClose(WS_SUCCESSFUL_CLOSE)
                    self.close_sent_time = time.perf_counter()
            elif "results" in json_msg:
                # print(json_msg)
                self.results[self.uuid]["transcripts"] = json_msg["results"]
            else:  # unexpected message
                print(json_msg)

    def update_session_stats(self, code):
        # global stats for printing intermediate summaries
        self.factory.finished_sessions += 1
        if code != WS_SUCCESSFUL_CLOSE:
            self.factory.finished_sessions_close_error += 1

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))
        self.update_session_stats(code)
        if self.uuid == None:  # in case not connected yet (opening handshake fails)
            self.uuid = str(uuid.uuid4())
            self.results[self.uuid] = {"timestamp": None, "reco_results": False, "code": None, "reason": None,
                                       "transaction_id": None, "elapsed_time": None, "time_stt": None,
                                       "handshake_time": None, "close_time": None, "transfer_time": None}
        self.results[self.uuid]["timestamp"] = datetime.datetime.utcnow().timestamp()
        self.results[self.uuid]["code"] = code
        self.results[self.uuid]["reason"] = reason
        self.results[self.uuid]["transfer_time"] = self.transfer_time
        self.results[self.uuid]["elapsed_time"] = time.perf_counter() - self.time_before_handshake
        if self.close_sent_time:
            self.results[self.uuid]["close_time"] = time.perf_counter() - self.close_sent_time
        self.sem.release()


class MyClientFactory(WebSocketClientFactory):
    protocol = MyClientProtocol
    protocol.uuid = None  # initialization for when "onClose" gets called before "onConnecting"

    def __init__(self, url, sem, audio_file_generator, results, **kwargs):
        self.protocol.sem = sem
        self.protocol.audio_file_generator = audio_file_generator
        self.protocol.results = results
        self.protocol.byte_rate = kwargs.pop('byte_rate', 8000)
        self.protocol.chunk_size = kwargs.pop('chunk_size', CHUNK_SIZE)
        self.protocol.verbose = kwargs.pop('verbose', 0)
        super(MyClientFactory, self).__init__(url, **kwargs)
        self.finished_sessions = 0  # total completed ws requests
        self.finished_sessions_close_error = 0  # total close errors


def print_results(results, out_file):
    if out_file:
        print(f"Saving results to {out_file}")
        try:
            with open(out_file, "w") as f:
                for entry in results:  # json line format
                    json.dump(entry, f, ensure_ascii=False)
                    f.write("\n")

        except Exception as e:
            print(e)
            print("results are:", results)
    else:
        print("results are:", results)

    print("-- summary -----------")
    successful_recognition = 0
    successful_close = 0
    failed = {}
    handshake_time_histo = [0] * 100  # initialize to zero
    total_time_stt = 0.0
    for entry in results:
        if entry["reco_results"] == True:
            successful_recognition += 1
            total_time_stt += entry["time_stt"]
        if entry["code"] == WS_SUCCESSFUL_CLOSE:
            successful_close += 1
            floor = math.floor(entry["handshake_time"])
            handshake_time_histo[floor] += 1
        else:
            code = entry["code"]
            reason = entry["reason"]
            str_error = str(code) + " " + reason
            if str_error not in failed:
                failed[str_error] = 1
            else:
                failed[str_error] += 1
    print("total:", total)
    print("successful recognitions:", successful_recognition)
    print("successful close:", successful_close)
    print("errors:", total - successful_close, "(", str(100.0 * ((total - successful_close) / total)), "%)")
    if total - successful_close > 0:
        print(failed)
    print("total time stt:", total_time_stt)
    print("---------------------")
    print("opening handshake timing distribution")
    for s in range(100):
        if handshake_time_histo[s] > 0:
            print("[" + str(s) + "," + str(s + 1) + ") seconds:", handshake_time_histo[s])


def get_timestamp():
    ts = time.time()
    timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    return timestamp


async def progress_updates(interval_seconds, results, total):
    while len(results) < total:
        await asyncio.sleep(interval_seconds)
        percent = 100.0 * factory.finished_sessions / total
        print(
            f"=== progress: sessions completed = {factory.finished_sessions} ({percent}%), errors = {factory.finished_sessions_close_error} ===")


def get_next_audio_file(audio_file, database_file=None, randomize=False):
    """Generator that returns the next audio file to process
    """

    if audio_file:
        while True:
            yield audio_file
    else:
        with open(database_file, "rt") as f:
            entries = f.read().splitlines()
            if randomize:
                while True:
                    yield random.choice(entries)
            else:
                cycle_entries = itertools.cycle(entries)
                while True:
                    yield next(cycle_entries)


def sort_results(results, database_file):
    """Sort entries in the results dictionary according to the order of entries in the database
    """

    database_entries = None
    if database_file:
        with open(database_file, "rt") as f:
            database_entries = f.read().splitlines()

    # create a map id <> audio
    audio2id = {}
    for key, value in results.items():
        audio2id[value["audio_file"]] = key

    print(audio2id)
    sorted_results = []
    for entry in database_entries:
        # maybe not all the database was processed which means # items in db > # items in results
        if entry not in audio2id:
            continue
        sorted_results.append(results[audio2id[entry]])
    return sorted_results


# Constants
CHUNK_SIZE = 1000

if __name__ == '__main__':

    # load profiles
    with open("./client_config/profiles.yaml", 'r') as stream:
        try:
            profiles = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-p', '--profile', type=str, default='local', help='profile to use (local, production, etc)')
    parser.add_argument(
        '-m', '--model', type=str, default="en-US_NarrowbandModel", help='model to use')
    parser.add_argument(
        '-q', '--query-params', type=str, help='additional query params such as custom models, etc (\'&\' separated)')
    parser.add_argument(
        '-he', '--headers', type=str,
        help='additional headers to be passed in the request (\'|\' separated, for example \'content-type:audio/wav|...\')')
    # parser.add_argument(
    #    '-i', '--init-fields', type=str, help='session initialization fields, passed on the start json object')
    parser.add_argument(
        '-s', '--chunk-size', type=int, default=CHUNK_SIZE, help='size of audio chunks, in bytes')
    parser.add_argument(
        '-a', '--audio', type=str, help='audio file')
    parser.add_argument(
        '-d', '--database', type=str,
        help='database file, plain text file containing the paths to the files to process')
    parser.add_argument(
        '-t', '--total', type=int, default=1, help='total number of requests')
    parser.add_argument(
        '-b', '--byterate', type=int, help='total number of bytes to feed per second within a single session',
        default='512000')
    parser.add_argument(
        '-c', '--concurrent', type=int, default=1, help='total number of concurrent requests')
    parser.add_argument(
        '-g', '--progress-updates', type=int, default=0, help='print a progress update every n seconds')
    parser.add_argument(
        '-o', '--out-file', type=str, default=None,
        help='save json results to file instead of printing to standard out')
    parser.add_argument(
        '-r', '--random', action='store_true', help='randomize audio file selection when using database')
    parser.add_argument(
        '-oht', '--open-handshake-timeout', type=int, default=10, help='open websocket handshake timeout')
    parser.add_argument(
        '-cht', '--close-handshake-timeout', type=int, default=10, help='close websocket handshake timeout')
    parser.add_argument(
        '-ct', '--connection-timeout', type=int, default=10, help='tcp connection timeout')
    # the goal of the ramp up time is to reduce the number of connections starting at the same time, if we are running C concurrent requests (see '-c')
    # then adding a waiting time after each of the first C requests is enough (this is good enough even if all requests take the same time to complete,
    # which is typically the case if the same file duration is used)
    parser.add_argument(
        '-u', '--ramp-up', type=float, default=None,
        help='ramp-up time, seconds in between two consecutive connection creations (for the first \'-c\' ones)')
    parser.add_argument(
        '-v', '--verbose', action='count', default=0)
    args = parser.parse_args()

    profile = profiles[args.profile]
    host = profile["STT_HOST"]
    port = profile["STT_PORT"]
    path = profile["path"]
    query = "?model=" + args.model
    if args.query_params != None:
        query += "&" + args.query_params
    url = "wss://" + host + path + query
    print("url:", url)
    total = args.total
    total_concurrent = args.concurrent
    sem = asyncio.Semaphore(total_concurrent)
    results = {}
    # use a custom factory to pass gobals
    audio_file_generator = get_next_audio_file(args.audio, args.database, args.random)
    factory = MyClientFactory(url,
                              sem,
                              audio_file_generator,
                              results,
                              chunk_size=args.chunk_size,
                              byte_rate=args.byterate,
                              verbose=args.verbose
                              )
    headers = {}
    if "apikey" in profile:
        user_pass = b64encode(b"apikey:" + profile["apikey"].encode('ascii')).decode("ascii")
        headers = {'Authorization': 'Basic %s' % user_pass}
    if "bearer_apikey" in profile:
        headers = {'Authorization': 'Bearer %s' % profile["bearer_apikey"]}
    if args.headers:
        pairs = args.headers.split('|')
        for pair in pairs:
            items = pair.split(':')
            headers[items[0]] = items[1]
    factory.headers = headers
    factory.setProtocolOptions(serverConnectionDropTimeout=10,
                               openHandshakeTimeout=args.open_handshake_timeout,
                               closeHandshakeTimeout=args.close_handshake_timeout)

    # Do SSL certificate validation if a server certificate was provided, otherwise trust any certificate
    if "certificate" in profile:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        localhost_pem = pathlib.Path(__file__).with_name(profile["certificate"])
        context.load_verify_locations(localhost_pem)
    else:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    loop = asyncio.get_event_loop()
    total = args.total
    if args.progress_updates > 0:
        loop.create_task(progress_updates(args.progress_updates, results, total))


    async def worker():
        i = 0
        while True:
            await sem.acquire()
            # await loop.create_connection(factory, STT_HOST=STT_HOST, STT_PORT=STT_PORT, ssl=context)
            try:
                await asyncio.wait_for(loop.create_connection(factory, host=host, port=port, ssl=context),
                                       timeout=args.connection_timeout)
            except asyncio.TimeoutError as e:
                print(e)
                print("connection timeout!")
                sem.release()
                i += 1
                if i == total:
                    break
                else:
                    continue
            if args.ramp_up != None and i < total_concurrent:
                await asyncio.sleep(args.ramp_up)
            print("connection", i, "started")
            i += 1
            if i == total:
                break
        # wait for all of them to finish
        for i in range(total_concurrent):
            await sem.acquire()


    print("test starting at:", get_timestamp())
    loop.run_until_complete(worker())
    print("test ended at:", get_timestamp())

    # sort results in database order, if necessary
    print("results:", results)
    sorted_results = [v for k, v in results.items()] if args.database == None else sort_results(results, args.database)
    print("sorted results:", sorted_results)
    print_results(sorted_results, args.out_file)
    loop.close()
    print("asyncio loop closed!")


