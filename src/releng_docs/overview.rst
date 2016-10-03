Services
========

Quick overview of all releng services with short description.

.. todo:: add diagram how everything fits together

.. todo:: add a note how to manage mozilla-releng.net domain

.. todo:: who to bug for heroku admin rights

.. todo:: write about AWS policies (production/staging)


releng_frontend
---------------

Staging:

- Url: https://staging.mozilla-releng.net
- S3: https://console.aws.amazon.com/s3/home?region=us-west-2&bucket=releng-staging-frontend
- CloudFront: https://console.aws.amazon.com/cloudfront/home?region=us-west-2#distribution-settings:E21OUD0VFT2UQ6

Production:

- Url: https://mozilla-releng.net
- S3: https://console.aws.amazon.com/s3/home?region=us-west-2&bucket=releng-production-frontend
- CloudFront: https://console.aws.amazon.com/cloudfront/home?region=us-west-2#distribution-settings:E7SMSK9P6UW3N


releng_clobberer
----------------

.. todo:: mention that newrelic and papertrail addons are used


Staging:

- Url: https://clobberer.staging.mozilla-releng.net
- Heroku: https://dashboard.heroku.com/apps/releng-staging-clobberer

Production:

- Url: https://clobberer.mozilla-releng.net
- Heroku: https://dashboard.heroku.com/apps/releng-production-clobberer


database
--------

Postgresql on Heroku

.. todo:: write something about migration script and how to sync production
          databases locally

Staging:

- Heroku: https://dashboard.heroku.com/apps/releng-staging-database

Production:

- Heroku: https://dashboard.heroku.com/apps/releng-production-database



documentation
-------------

Documentation you are currently reading.
Written in Sphinx_.


Staging:

- Url: https://docs.staging.mozilla-releng.net
- S3: https://console.aws.amazon.com/s3/home?region=us-west-2&bucket=releng-staging-docs
- CloudFront: https://console.aws.amazon.com/cloudfront/home?region=us-west-2#distribution-settings:E1LW0QJF456NUG

Production:

- Url: https://docs.mozilla-releng.net
- S3: https://console.aws.amazon.com/s3/home?region=us-west-2&bucket=releng-production-docs
- CloudFront: https://console.aws.amazon.com/cloudfront/home?region=us-west-2#distribution-settings:EPUEJ5MNC6OE
