// Copyright 2009 FriendFeed
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.

$(document).ready(function() {
    if (!window.console) window.console = {};
    if (!window.console.log) window.console.log = function() {};

    $("#messageform").live("submit", function() {
	newMessage($(this));
	return false;
    });
    $("#messageform").live("keypress", function(e) {
	if (e.keyCode == 13) {
	    newMessage($(this));
	    return false;
	}
    });
    $("#message").select();
    updater.poll();
});


// Unique ID for this window
var CLIENT_ID = Math.floor(Math.random()*99999999999);

// Add a rendered tweet to the list 
var last_message = "";

function newMessage(form) {
    var message = form.formToDict();
	console.log('message is', message);
    //var disabled = form.find("input[type=submit]");
    //disabled.disable();
    $.postJSON("/", message, function(response) {
	console.log('got this response', response);
	
    });
    $("textarea").val("").select();
 
}

function getCookie(name) {
    var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
    return r ? r[1] : undefined;
}

jQuery.postJSON = function(url, args, callback) {
    args._xsrf = getCookie("_xsrf");
  args.client_id = CLIENT_ID;
    $.ajax({url: url, data: $.param(args), dataType: "text", type: "POST",
	    success: function(response) {
	//if (callback) callback(eval("(" + response + ")"));
    }, error: function(response) {
	console.log("ERROR:", response)
    }});
};

jQuery.fn.formToDict = function() {
    var fields = this.serializeArray();
    var json = {}
    for (var i = 0; i < fields.length; i++) {
	json[fields[i].name] = fields[i].value;
    }
    if (json.next) delete json.next;
    return json;
};

jQuery.fn.disable = function() {
    this.enable(false);
    return this;
};

jQuery.fn.enable = function(opt_enable) {
    if (arguments.length && !opt_enable) {
        this.attr("disabled", "disabled");
    } else {
        this.removeAttr("disabled");
    }
    return this;
};

var updater = {
    errorSleepTime: 500,
    cursor: null,

    poll: function() {
	var args = {"_xsrf": getCookie("_xsrf")};
	if (updater.cursor) args.cursor = updater.cursor;
	args.client_id = CLIENT_ID;
	$.ajax({url: "/a/message/updates", type: "POST", dataType: "text",
		data: $.param(args), success: updater.onSuccess,
		error: updater.onError});
    },


    appendTweet: function(tweet) {   
	console.log('going to write tweets to the page');
	
	console.log('first delete the old dups')
	$(tweet).each(function() { console.log("dups", $("#" + this.id).remove()) });
	$($("#tweets").children()[0]).prepend($(tweet)) //.hide().fadeIn(1000));	
	console.log('going to make all links clickable')
	//$("div.text").linkify();	
    },

    onSuccess: function(response) {
	console.log('on success', response)
	last_message = response
	updater.appendTweet(response);

	updater.errorSleepTime = 500;
	window.setTimeout(updater.poll, 0);
    },

    onError: function(response) {
	updater.errorSleepTime *= 2;
	console.log("Poll error; sleeping for", updater.errorSleepTime, "ms");
	window.setTimeout(updater.poll, updater.errorSleepTime);
    },

    newMessages: function(response) {
	console.log("Inside newMessages.  Got this response.", response);

	last_message = response;
	appendTweet(response);

	/*
	if (!response.messages) return;
	updater.cursor = response.cursor;
	
	
	var messages = response.messages;
	

	updater.cursor = messages[messages.length - 1].id;
	console.log(messages.length, "new messages, cursor:", updater.cursor);
	
	for (var i = 0; i < messages.length; i++) {
	    updater.showMessage(messages[i]);
	}*/
    },

    showMessage: function(message) {
	var existing = $("#m" + message.id);
	if (existing.length > 0) return;
	var node = $(message.html);
	node.hide();
	$("#inbox").append(node);
	node.slideDown();
    }
};



// Define: Linkify plugin
(function($){

  var url1 = /(^|&lt;|\s)(www\..+?\..+?)(\s|&gt;|$)/g,
      url2 = /(^|&lt;|\s)(((https?|ftp):\/\/|mailto:).+?)(\s|&gt;|$)/g,

      linkifyThis = function () {
        var childNodes = this.childNodes,
            i = childNodes.length;
        while(i--)
        {
          var n = childNodes[i];
          if (n.nodeType == 3) {
            var html = $.trim(n.nodeValue);
            if (html)
            {
              html = html.replace(/&/g, '&amp;')
                         .replace(/</g, '&lt;')
                         .replace(/>/g, '&gt;')
                         .replace(url1, '$1<a href="http://$2">$2</a>$3')
                         .replace(url2, '$1<a href="$2">$2</a>$5');
              $(n).after(html).remove();
            }
          }
          else if (n.nodeType == 1  &&  !/^(a|button|textarea)$/i.test(n.tagName)) {
            linkifyThis.call(n);
          }
        }
      };

  $.fn.linkify = function () {
    return this.each(linkifyThis);
  };

})(jQuery);

// Usage example:
$('div.text').linkify();
 