#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, Blueprint
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os
from flask import render_template

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

profile = Blueprint('profile', __name__,
                    template_folder='static',
                    static_folder='static')
app.register_blueprint(profile, url_prefix='')


class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append(listener)

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners(entity)

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners(entity)

    def update_listeners(self, entity):
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity, dict())
    
    def world(self):
        return self.space


class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put(v, False)

    def get(self):
        return self.queue.get()

myWorld = World()
clients = list()


def send_all(msg):
    for client in clients:
        client.put(msg)


def send_all_json(obj):
    send_all(json.dumps(obj))


def set_listener(entity, data):
    an_entity = dict()
    an_entity[entity] = data
    send_all_json(an_entity)

myWorld.add_set_listener(set_listener)

@app.route('/')
def hello():
    return render_template('index.html')


def read_ws(ws, client):
    try:
        while True:
            msg = ws.receive()

            if msg is not None:
                packet = json.loads(msg)
                # just send a dictionary of k-v
                send_all_json(packet)
            else:
                break
    except:
        '''Done'''

@sockets.route('/subscribe')
def subscribe_socket(ws):

    client = Client()
    clients.append(client)
    g_event = gevent.spawn(read_ws, ws, client)

    try:
        while True:
            msg=client.get()
            ws.send(msg)
    except:
        print "error"

    finally:
        clients.remove(client)
        gevent.kill(g_event)

    return None


def flask_post_json():
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    myWorld.set(entity, flask_post_json())
    return json.dumps(myWorld.set(entity))

@app.route("/world", methods=['POST','GET'])    
def world():
    return json.dumps(myWorld.world())

@app.route("/entity/<entity>")    
def get_entity(entity):
    return json.dumps(myWorld.get(entity))

@app.route("/clear", methods=['POST','GET'])
def clear():
    myWorld.clear()
    return None


if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
