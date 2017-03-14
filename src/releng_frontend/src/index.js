'use strict';

require('expose-loader?jQuery!jquery');
require('expose-loader?Tether!tether');
require('bootstrap');
require('./scss/index.scss');

var redirect = require('./redirect');
var localstorage = require('./localstorage');
var hawk = require('./hawk');
var title = require('./title');

var url;
var getData = function(name, _default) {
  url = document.body.getAttribute('data-' + name);
  if (url === null) {
    url = _default || 'You need to set WEBPACK_' + name.replace('-', '_').toUpperCase() + ' variable or data-' + name;
  }
  return url;
};


// Start the ELM application
var KEY = 'taskclusterlogin';  // do not change this key
var app = require('./Main.elm').Main.fullscreen({
  user: localstorage.load_item(KEY),
  treestatusUrl: getData('treestatus-url', process.env.WEBPACK_TREESTATUS_URL),
  docsUrl: getData('docs-url', process.env.WEBPACK_DOCS_URL),
  version: getData('version', process.env.WEBPACK_VERSION)
});

// Setup ports
localstorage.init(app, KEY);
hawk(app);
redirect(app);
title(app);
