'use strict';

require('expose?$!expose?jQuery!jquery');
require('expose?Tether!tether');
require('bootstrap');
require("./index.scss");

var url = require('url');

var user = null;
try {
  user = JSON.parse(window.localStorage.getItem('credentials'));
} catch (e) {
  // pass
}

var clobbererUrl = document.body.getAttribute('data-clobberer-url');
if (clobbererUrl === null) {
  clobbererUrl = process.env.NEO_CLOBBERER_URL || "You need to set NEO_CLOBBERER_URL variable or data-clobberer-url";
}

var tooltoolUrl = document.body.getAttribute('data-tooltool-url');
if (tooltoolUrl=== null) {
  tooltoolUrl = process.env.NEO_TOOLTOOL_URL || "You need to set NEO_TOOLTOOL_URL variable or data-tooltool-url";
}

var treestatusUrl = document.body.getAttribute('data-treestatus-url');
if (treestatusUrl === null) {
  treestatusUrl = process.env.NEO_TREESTATUS_URL || "You need to set NEO_TREESTATUS_URL variable or data-treestatus-url";
}

var app = require('./Main.elm').Main.fullscreen({
  user: user,
  clobbererUrl: clobbererUrl,
  tooltoolUrl: tooltoolUrl,
  treestatusUrl: treestatusUrl 
});
    

app.ports.localstorage_remove.subscribe(function() {
  window.localStorage.removeItem('credentials');
  app.ports.localstorage_get.send(null);
});

app.ports.localstorage_set.subscribe(function(user) {
  window.localStorage.setItem('credentials', JSON.stringify(user));
  app.ports.localstorage_get.send(user);
});

app.ports.redirect.subscribe(function(redirect) {
   var redirect_url = url.parse(redirect.url);
   if (redirect.target !== null) {
     redirect_url = url.format(window.$.extend({}, redirect_url, {
       query: {
         target: url.format({
             protocol: window.location.protocol,
             host: window.location.host,
             port: window.location.port,
             pathname: redirect.target[0]
         }),
         description: redirect.target[1]
       }
     }));
   } else {
     redirect_url = url.format(redirect_url)
   }
   window.location = redirect_url;
});
