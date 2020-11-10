import cherrypy as cherrypy
from paste.translogger import TransLogger
from app import app as flask_app
import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="The port of the WSGI server (default 8888)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="The hosts allowed by the WSGI server (default 0.0.0.0)",
    )
    args = parser.parse_args()

    app_logged = TransLogger(flask_app)

    # Mount the WSGI callable object (app) on the root directory
    cherrypy.tree.graft(app_logged, "/")

    # Set the configuration of the web server
    cherrypy.config.update(
        {
            "server.socket_port": args.port,
            "server.socket_host": args.host,
            "engine.autoreload.on": False,
            "log.screen": True,
            "log.access_file": "access.log",
            "log.error_file": "error.log",
            "server.shutdown_timeout": 1,
        }
    )

    try:
        # Start the CherryPy WSGI web server
        cherrypy.engine.start()
        cherrypy.engine.block()
    except KeyboardInterrupt:
        cherrypy.engine.exit()