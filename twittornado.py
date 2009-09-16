#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import os.path
import uuid

from tornado.options import define, options

twitter_consumer_key = ''
twitter_consumer_secret = ''


define("port", default=80, help="run on the given port", type=int)

define("twitter_consumer_key", help="The consumer key for Twitter", default="oaBDbZtsmcJ6nno45AA5w")
define("twitter_consumer_secret", help="The consumer secret", default="L5KH4UuMTwwh6CIb9rRI7TNsEtlPdAJAfgBokmXVYc")


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/a/message/updates", TweetUpdatesHandler),
            (r"/about", AboutHandler),
        ]
        settings = dict(
            twitter_consumer_key = options.twitter_consumer_key,
            twitter_consumer_secret = options.twitter_consumer_secret,
            ui_modules = {"Tweet": TweetModule},
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)

    def save_current_user(self, user):
        self.set_secure_cookie("user", tornado.escape.json_encode(user))

i = 0
POLL_INTERVAL = 20

class TweetMixin(object):
    waiters = {}
    polls = {}
    since_ids = {}
    def wait_for_tweets(self, callback, client_id):
        cls = TweetMixin
        user = self.get_current_user()
        id = user.get('id', None)
        if not cls.waiters.has_key(id):
            cls.waiters[id] = {}
        cls.waiters[id][client_id] = callback
        

    
    def on_new_text(self, text):
        
        " Push the newly rendered text "
        if self.request.connection.stream.closed():
            return
        self.finish(text)

    @tornado.web.asynchronous    
    def send_text_to_user(self, id, text):
    
        cls = TweetMixin
        clients = cls.waiters.get(id, {})
        for client_id, callback in clients.items():
            if callback:
                try:
                    callback(text)
                except:
                    clients.pop(client_id)
                    
    def receive_new_text(self, text):
        """ Send text to self """
        id = self.get_current_user()['id']
        self.send_text_to_user(id, text)

    def broadcast_new_text(self, text):
        """
        Send the new tweet to all of the user's followers.
        """
        cls = TweetMixin
        user = self.get_current_user()
        follower_ids = user.get('follower_ids', [])
        
        waiter_keys = cls.waiters.keys()
        active_ids = [id for id in follower_ids if waiter_keys.count(id)]
        for id in active_ids:
            self.send_text_to_user(id, text)


    @tornado.web.asynchronous  # Make it asynchronous    
    def poll_twitter(self): 
        user = self.get_current_user()
        import time
        global i
        i+=1
        cls = TweetMixin
        #since_id = self.current_user.get('since_id', 1)
        since_id = cls.since_ids.get(self.current_user['id'], 1)
        
#self.broadcast_new_text("<tr><td>count</td><td>%d</td></tr>" % i)
        
        timeout = self.polls.get(user['id'])
        # Start polling if they havent already!
        if not timeout or timeout.deadline < time.time():
            timeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + POLL_INTERVAL, self.poll_twitter)
        self.polls[user['id']] = timeout
        
        cls = TweetMixin
        if cls.waiters.get(user['id']):
            # There are clients so its worth polling twitter
            
            self.twitter_request(path = "/statuses/friends_timeline",
                                 #access_token=user["access_token"],
                                 access_token=self.current_user["access_token"],
                                 since_id = since_id,
                                 callback = self.async_callback(self.write_tweets),
                                 )

    @tornado.web.asynchronous
    def write_tweets(self, tweets):
        text = ""
        if not tweets:
            return text
        user = self.get_current_user()
        #since_id = user.get('since_id', 1)
        cls = TweetMixin
        since_id = cls.since_ids.get(user['id'], 1)
        for tweet in tweets:
            since_id = max(since_id, int(tweet['id']))
            text += self.render_string("modules/tweet.html", tweet=tweet, twittornado = False)
        
        cls.since_ids[user['id']] = since_id + 1
        self.save_current_user(user)

        self.send_text_to_user(user['id'], text)
        #self.receive_new_text("<tr><td>count</td><td>%d</td></tr>" % i)
        

class AboutHandler(BaseHandler):
    
    def get(self):
        self.render("about.html")

class MainHandler(BaseHandler, tornado.auth.TwitterMixin, TweetMixin):
    #@tornado.web.authenticated
    @tornado.web.asynchronous  # Make it asynchronous
    def get(self):
        
        user = self.get_current_user()
        if not user:
            return self.render("front.html")

        #Poll to update all other clients to the same spot
        self.async_callback(self.poll_twitter)()

        self.twitter_request(path = "/statuses/friends_timeline",
                             access_token=self.current_user["access_token"],
                             callback = self.async_callback(self._on_fetch),
                             )
        
        return 

    def _on_fetch(self, tweets):
        
        #self.finish('Fetched')
        if not tweets:
            tweets = []
        else:
            since_id = tweets[0]['id']
            cls = TweetMixin
            cls.since_ids[self.current_user['id']] = since_id
        
        self.render('index.html', tweets=tweets)

    @tornado.web.asynchronous 
    def post(self):
        
                
        self.twitter_request(
            "/statuses/update",
            post_args={"status": self.get_argument('status', None)},
            access_token=self.current_user["access_token"],
            callback=self.async_callback(self._on_post))

    def _on_post(self, tweet):

        result = self.render_string("modules/tweet.html", tweet=tweet, twittornado = True)
        self.broadcast_new_text(result)  # Send the Tweet out to everyone
        
        self.finish("Finished posting to Twitter")
        


class TweetModule(tornado.web.UIModule):
    def render(self, tweet):
        return self.render_string("modules/tweet.html", tweet=tweet, twittornado = False)


class TweetUpdatesHandler(BaseHandler, TweetMixin, tornado.auth.TwitterMixin):
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self):
        client_id = self.get_argument("client_id", None)
        self.wait_for_tweets(self.async_callback(self.on_new_text),
                               client_id=client_id)


class AuthLoginHandler(BaseHandler, tornado.auth.TwitterMixin):

     @tornado.web.asynchronous
     def get(self):
         if self.get_argument("oauth_token", None):
             self.get_authenticated_user(self.async_callback(self._on_auth))
             return
         self.authorize_redirect()

     @tornado.web.asynchronous
     def _on_auth(self, user):
         if not user:
             raise tornado.web.HTTPError(500, "Twitter auth failed")
             # Save the user using, e.g., set_secure_cookie()

         self.twitter_request(path = "/followers/ids",
                             #access_token=user["access_token"],
                             access_token=user["access_token"],
                             callback = self.async_callback(self._on_fetch_follower_ids),
                             )
         self.user = user

     def _on_fetch_follower_ids(self, ids):
         """ Get the follower ids of the given user """
         if not ids.count(self.user['id']):
             ids.append(self.user['id'])
         
         self.user['follower_ids'] = ids;
         self.save_current_user(self.user)
         self.redirect("/")
         
class AuthLogoutHandler(BaseHandler, tornado.auth.FacebookMixin):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
