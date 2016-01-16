#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import codecs 
import base64
import webapp2
import urllib2
import urllib
import json
import re
import os
import datetime
from webapp2_extras import sessions

from google.appengine.api import urlfetch
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.api import taskqueue
from google.appengine.api import app_identity

urlfetch.set_default_fetch_deadline(30)
class Config(ndb.Model):
    name = ndb.StringProperty()
    value = ndb.StringProperty()
    
class BaseHandler(webapp2.RequestHandler):
    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)
        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)
 
    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

class Clear(BaseHandler):
    def get(self):	        
        c = Config.get_or_insert('bandwith')
        c.name = 'bandwith'
        c.value = '0'
        c.put()
        self.response.write("OK")
        
class PhotoSync(BaseHandler):
    def post(self): 
        slave_url = 'http://' + app_identity.get_default_version_hostname() + '/sync/'
        id = self.request.get('id')
        url = self.request.get('url')
        album_id = self.request.get('album_id')
        title = self.request.get('title')
        yaf_token = self.request.get('yaf_token')

        urlfetch.set_default_fetch_deadline(60)
        logging.info(url)
        data = ''
        result = urlfetch.fetch(url)
        data = result.content
        size = len(data)
        if result.status_code == 200:
            c = Config.get_or_insert('bandwith')
            c.name = 'bandwith'
            if c.value is None: c.value = "0"
            bandwith = int(c.value)
            if bandwith < 900000000:
                c.value = str(bandwith + size)
                c.put()
            else:
                form_fields = {
                  "slave_url": slave_url,
                  "id": id,
                  "status": 'busy',
                }
                form_data = urllib.urlencode(form_fields)
                result = urlfetch.fetch(url='http://photoo-1006.appspot.com/result/',
                    payload=form_data,
                    method=urlfetch.POST,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'})
                return
        url = 'http://api-fotki.yandex.ru/api/users/protasov-s/album/'+ album_id +'/photos/?format=json'
        logging.info(url)
        result = urlfetch.fetch(url=url,
            payload=data,
            method=urlfetch.POST,
            headers={'Content-Length': size,'Content-Type': 'image/jpeg', 'Authorization':'OAuth ' + yaf_token})

        url = result.headers.get('Location')
        photo = json.loads(result.content)
        
        yandex_id = photo['id']
        photo['title'] =  id
        photo['summary'] = title
        photo_data = json.dumps(photo)
        
        result = urlfetch.fetch(url=url,
            payload=photo_data,
            method=urlfetch.PUT,
            headers={'Accept': 'application/json','Content-Type': 'application/json; charset=utf-8; type=entry;', 'Authorization':'OAuth ' + yaf_token})
        
        
        if result.status_code == 200:
            form_fields = {
              "slave_url": slave_url,
              "id": id,
              "yandex_id": yandex_id,
              "status": "ok",
            }
            form_data = urllib.urlencode(form_fields)
            result = urlfetch.fetch(url='http://fytunnel.appspot.com/result/',
                payload=form_data,
                method=urlfetch.POST,
                headers={'Content-Type': 'application/x-www-form-urlencoded'})
                
        
        

class Sync(BaseHandler):
    def post(self):
        id = self.request.get('id')
        url = self.request.get('url')
        title = self.request.get('title')
        album_id = self.request.get('album_id')
        taskqueue.add(url='/psync/',queue_name='psync', params = {'id': id, 'url': url, 'title':title, 'album_id':album_id})
        

	
class MainHandler(BaseHandler):
    def get(self):
        self.response.write('Ok')

config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'some-secret-key',
}        
app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/clear/',Clear),
    ('/sync/',Sync),
    ('/psync/',PhotoSync),
    
], debug=True,config=config)
