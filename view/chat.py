# coding:utf-8

import json
import uuid
from view import route, url_for, View
from sockjs.tornado import SockJSRouter, SockJSConnection

key_to_user_info = {}

@route('/room_info', name='room_info')
class RoomInfo(View):
    def get(self):
        ret = {}
        for k, v in ChatConnection.rooms.items():
            if len(v.users):
                ret[k] = {'title': 'Room %s' % k, 'num':len(v.users)}
        self.finish(ret)

@route('/my_info', name='my_info')
class MyInfo(View):
    def post(self):
        uid = self.get_argument('uid')
        username = self.get_argument('username')
        self.set_secure_cookie('alice', json.dumps({'uid': uid, 'username': username, 'key': uuid.uuid4().hex}))
        self.finish({'code': 0})

@route('/i_am_here', name='i_am_here')
class Hello(View):
    def get(self):
        info = json.loads((self.get_secure_cookie('alice') or '{}').decode('utf-8'))
        if 'key' in info:
            key_to_user_info[info['key']] = info
            self.finish({'key': info['key']})
        else:
            self.finish({})


class Room(object):
    def __init__(self):
        self.users = set()


class ChatConnection(SockJSConnection):
    rooms = {}
    visitors = set()
    uid_start = 1000

    def on_open(self, request):
        self.room_id = None
        self.username = None
        self.visitors.add(self)

        self.uid = self.uid_start
        self.session.uid = self.uid
        ChatConnection.uid_start += 1

    def on_close(self):
        self.leave_room()
        self.visitors.remove(self)

    def say(self, txt):
        if self.room_id:
            r = self.rooms[self.room_id]
            self.broadcast(r.users, json.dumps([
               ['say', [self.uid, self.username], txt],
            ]))

    def enter_room(self, room_id):
        self.leave_room()
        if not room_id in self.rooms:
            self.rooms[room_id] = Room()
        if not self.room_id in self.rooms:
            self.room_id = room_id
            r = self.rooms[room_id]
            r.users.add(self)
            #self.broadcast([self], json.dumps([['enter_room', self.uid]]))
            self.broadcast(r.users, json.dumps([['enter_room', room_id, [self.uid, self.username]]]))

    def leave_room(self):
        if self.room_id in self.rooms:
            r = self.rooms[self.room_id]

            self.broadcast(r.users, json.dumps([['leave_room', self.room_id, [self.uid, self.username]]]))

            r.users.remove(self)
            if len(r.users) == 0:
                del self.rooms[self.room_id]

            self.room_id = None

    def on_message(self, message):
        info = json.loads(message)

        for i in info:
            key = i[0]
            if key == 'set_username':
                self.username = i[1]
                self.broadcast([self], json.dumps([['user_info', [self.uid, self.username]]]))
            elif key == 'enter_room':
                if self.username:
                    self.enter_room(int(i[1]))
            elif key == 'leave_room':
                if self.username:
                    self.leave_room()
            elif key == 'say':
                if self.username:
                    self.say(i[1])
            elif key == 'rebirth':
                if i[1] in key_to_user_info:
                    k = i[1]
                    self.uid = key_to_user_info[k]['uid']
                    self.username = key_to_user_info[k]['username']
                    del key_to_user_info[k]
                    self.broadcast([self], json.dumps([['user_info', [self.uid, self.username]]]))


chat_route = SockJSRouter(ChatConnection, '/ws/api')
