"""
`appengine_config.py` is automatically loaded when Google App Engine
starts a new instance of your application. This runs before any
WSGI applications specified in app.yaml are loaded.
"""

from google.appengine.ext import vendor
from gaesessions import SessionMiddleware

# Third-party libraries are stored in "lib", vendoring will make
# sure that they are importable by the application.
vendor.add('lib')

def webapp_add_wsgi_middleware(app):
   app = SessionMiddleware(app, cookie_key = "CHANGE ME!kB56T7Rk2c..W=l3G3i=kK")
   return app